"""AppIndicator fallback (GTK) for desktops where the Qt tray is unavailable."""

import subprocess

import gi

gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3, Gtk, GLib  # noqa: E402

from . import browser, config, logger, schemes, service as service_mod  # noqa: E402


class IndicatorApp:
    def __init__(self, cfg):
        self.cfg = cfg
        self._busy = False
        self._old_menu = None

        try:
            Gtk.IconTheme.get_default().add_search_path(str(schemes.icon_path().parent))
        except Exception:
            pass

        self.indicator = AyatanaAppIndicator3.Indicator.new(
            "linux-url-interceptor",
            "linux-url-interceptor",
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)

        self.svc = service_mod.Service(cfg)
        self.svc.notify_cb = self._notify
        self.svc.dispatch = lambda u, s: GLib.idle_add(self.svc.handle, u, s)
        self.svc.start()
        logger.runtime_log("tray started (AppIndicator)")
        self._rebuild()

    def run(self) -> int:
        try:
            Gtk.main()
        finally:
            self.svc.stop()
        return 0

    # ---- notifications -------------------------------------------------

    def _notify(self, app_name, url, final_url):
        try:
            body = url if len(url) <= 96 else url[:93] + "..."
            subprocess.Popen(
                ["notify-send", f"URL intercepted from {app_name}", body,
                 "-a", "linux-url-interceptor", "-i", "linux-url-interceptor"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    # ---- menu ----------------------------------------------------------

    def _rebuild(self, *args):
        self._busy = True
        try:
            menu = Gtk.Menu()
            self._build_menu(menu)
            menu.show_all()
            self.indicator.set_menu(menu)
            if self._old_menu is not None:
                self._old_menu.destroy()
            self._old_menu = menu
        finally:
            self._busy = False

    def _build_menu(self, menu):
        self.cfg = config.load()

        for label, key in (
            ("Interception enabled", "enabled"),
            ("Copy URL to clipboard", "copy_to_clipboard"),
            ("Open intercepted links in browser", "open_in_browser"),
            ("Resolve redirect chain", "resolve_redirect_chain"),
        ):
            item = Gtk.CheckMenuItem(label=label)
            item.set_active(bool(self.cfg.get(key, False)))
            item.connect("toggled", self._on_toggle, key)
            menu.append(item)

        menu.append(Gtk.SeparatorMenuItem())

        top = Gtk.MenuItem(label="Forward browser")
        sub = Gtk.Menu()
        chosen = self.cfg.get("forward_browser", "auto")
        group = None
        entries = [("auto", "Auto (original handler)")]
        entries += [(b["id"], b["name"]) for b in browser.list_browsers()]
        for bid, blabel in entries:
            item = Gtk.RadioMenuItem.new_with_label(group, blabel)
            if group is None:
                group = item.get_group()
            active = chosen == bid or (bid == "auto" and chosen in (None, "", "auto"))
            item.set_active(active)
            item.connect("toggled", self._on_forward, bid)
            sub.append(item)
        top.set_submenu(sub)
        menu.append(top)
        menu.append(Gtk.SeparatorMenuItem())

        ex = Gtk.MenuItem(label="Excluded apps...")
        ex.connect("activate", self._excluded_dialog)
        menu.append(ex)
        menu.append(Gtk.SeparatorMenuItem())

        if schemes.is_installed():
            it = Gtk.MenuItem(label="Restore original http/https handler")
            it.connect("activate", self._install_or_restore, False)
        else:
            it = Gtk.MenuItem(label="Install as default http/https handler")
            it.connect("activate", self._install_or_restore, True)
        menu.append(it)

        as_item = Gtk.CheckMenuItem(label="Launch at login")
        as_item.set_active(schemes.autostart_path().exists())
        as_item.connect("toggled", self._on_autostart)
        menu.append(as_item)
        menu.append(Gtk.SeparatorMenuItem())

        st = Gtk.MenuItem(label="Interception status...")
        st.connect("activate", self._status_dialog)
        menu.append(st)
        for label in ("Open logs folder", "Open config folder"):
            folder = config.logs_dir() if label == "Open logs folder" else config.config_dir()
            it = Gtk.MenuItem(label=label)
            it.connect("activate", self._open_folder, folder)
            menu.append(it)
        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Exit")
        quit_item.connect("activate", self._exit)
        menu.append(quit_item)

    # ---- callbacks -----------------------------------------------------

    def _on_toggle(self, item, key):
        if self._busy:
            return
        self.cfg[key] = item.get_active()
        config.save(self.cfg)
        logger.runtime_log(f"set {key}={item.get_active()}")
        GLib.idle_add(self._rebuild)

    def _on_forward(self, item, bid):
        if self._busy or not item.get_active():
            return
        self.cfg["forward_browser"] = bid
        config.save(self.cfg)
        logger.runtime_log(f"forward browser -> {bid}")
        GLib.idle_add(self._rebuild)

    def _on_autostart(self, item):
        if self._busy:
            return
        self.cfg["launch_at_startup"] = item.get_active()
        config.save(self.cfg)
        schemes.set_autostart(item.get_active())

    def _install_or_restore(self, item, install):
        if self._busy:
            return
        cfg = config.load()
        if install:
            schemes.install(cfg)
        else:
            schemes.uninstall(cfg)
        self.cfg = config.load()
        self._rebuild()

    def _excluded_dialog(self, *args):
        dlg = Gtk.Dialog(title="Excluded apps", transient_for=None)
        dlg.set_default_size(360, 260)
        area = dlg.get_content_area()
        lbl = Gtk.Label(
            label="Apps that should never be intercepted\n(process names, one per line).\n"
            "Their links pass straight to the browser."
        )
        lbl.set_halign(Gtk.Align.START)
        area.pack_start(lbl, False, False, 6)
        tv = Gtk.TextView()
        tv.get_buffer().set_text("\n".join(self.cfg.get("excluded_apps", [])))
        area.pack_start(tv, True, True, 6)
        dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dlg.add_button("Save", Gtk.ResponseType.OK)
        dlg.show_all()
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            buf = tv.get_buffer()
            text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
            names = sorted(set(ln.strip().lower() for ln in text.splitlines() if ln.strip()))
            self.cfg["excluded_apps"] = names
            config.save(self.cfg)
            logger.runtime_log(f"excluded apps -> {names}")
        dlg.destroy()

    def _status_dialog(self, *args):
        http = schemes.query("http")
        https = schemes.query("https")
        installed = schemes.is_installed()
        dlg = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Interception status",
        )
        dlg.format_secondary_text(
            f"Current http handler:  {http or 'none'}\n"
            f"Current https handler: {https or 'none'}\n\n"
            f"Interceptor is {'installed' if installed else 'NOT installed'} as the default handler."
        )
        dlg.run()
        dlg.destroy()

    def _open_folder(self, item, path):
        import os

        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            pass
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _exit(self, *args):
        self.svc.stop()
        Gtk.main_quit()
