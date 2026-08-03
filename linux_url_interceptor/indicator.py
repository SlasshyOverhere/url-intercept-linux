"""AppIndicator fallback (GTK) for desktops where the Qt tray is unavailable."""

import subprocess

import gi

gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3, Gtk, GLib  # noqa: E402

from . import browser, config, logger, processes, schemes, service as service_mod  # noqa: E402


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
        self.svc.dispatch = lambda u, s: GLib.idle_add(self.svc.handle, u, s)
        self.svc.start()
        logger.runtime_log("tray started (AppIndicator)")
        # Build the first menu once the main loop is running: libayatana
        # appindicator can trip over a GTK widget that is not ready yet if we
        # set the menu before Gtk.main().
        GLib.idle_add(self._rebuild)

    def run(self) -> int:
        try:
            Gtk.main()
        finally:
            self.svc.stop()
        return 0

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
        self.cfg = config.load()
        dlg = Gtk.Dialog(title="Excluded apps", transient_for=None)
        dlg.set_default_size(640, 440)
        area = dlg.get_content_area()

        hint = Gtk.Label(
            label="Excluded apps are trusted: their links open in the browser AND are copied to "
            "the clipboard. Links from every other app are only copied. Pick running apps on the "
            "left or type a process name below."
        )
        hint.set_wrap(True)
        hint.set_xalign(0)
        area.pack_start(hint, False, False, 6)

        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(4)
        grid.set_margin_top(6)

        run_label = Gtk.Label(label="Running apps")
        run_label.set_halign(Gtk.Align.START)
        grid.attach(run_label, 0, 0, 1, 1)
        exc_label = Gtk.Label(label="Excluded apps")
        exc_label.set_halign(Gtk.Align.START)
        grid.attach(exc_label, 1, 0, 1, 1)

        run_scroll = Gtk.ScrolledWindow()
        run_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        run_scroll.set_min_content_height(280)
        run_list = Gtk.ListBox()
        run_list.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        for name in processes.list_running_processes():
            run_list.add(Gtk.Label(label=name, xalign=0))
        run_scroll.add(run_list)
        grid.attach(run_scroll, 0, 1, 1, 1)

        exc_scroll = Gtk.ScrolledWindow()
        exc_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        exc_scroll.set_min_content_height(280)
        exc_list = Gtk.ListBox()
        exc_list.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        for name in sorted(self.cfg.get("excluded_apps", [])):
            exc_list.add(Gtk.Label(label=name, xalign=0))
        exc_scroll.add(exc_list)
        grid.attach(exc_scroll, 1, 1, 1, 1)

        add_btn = Gtk.Button(label="Add selected ->")
        remove_btn = Gtk.Button(label="Remove selected")
        grid.attach(add_btn, 0, 2, 1, 1)
        grid.attach(remove_btn, 1, 2, 1, 1)

        area.pack_start(grid, True, True, 6)

        manual = Gtk.Entry()
        manual.set_placeholder_text("Type a process name to trust (e.g. telegram-desktop)")
        manual_add = Gtk.Button(label="Add")
        manual_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        manual_row.pack_start(manual, True, True, 0)
        manual_row.pack_start(manual_add, False, False, 0)
        area.pack_start(manual_row, False, False, 6)

        def existing(name):
            for child in exc_list.get_children():
                if child.get_label().lower() == name:
                    return True
            return False

        def add_selected(_btn):
            for child in run_list.get_selected_rows():
                name = child.get_label().strip().lower()
                if name and not existing(name):
                    exc_list.add(Gtk.Label(label=name, xalign=0))
                    exc_list.show_all()

        def remove_selected(_btn):
            for child in exc_list.get_selected_rows():
                exc_list.remove(child)

        def add_manual(_btn=None):
            name = manual.get_text().strip().lower()
            if name and not existing(name):
                exc_list.add(Gtk.Label(label=name, xalign=0))
                exc_list.show_all()
            manual.set_text("")

        add_btn.connect("clicked", add_selected)
        remove_btn.connect("clicked", remove_selected)
        manual_add.connect("clicked", add_manual)
        manual.connect("activate", add_manual)

        dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dlg.add_button("Save", Gtk.ResponseType.OK)
        dlg.show_all()
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            names = sorted(
                {child.get_label().strip().lower() for child in exc_list.get_children() if child.get_label().strip()}
            )
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
