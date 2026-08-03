"""Argument dispatch.

* no arguments        -> start the tray app
* http(s)://... arg   -> we were launched as the http/https handler
* --install/uninstall -> register / restore the default handler
* --status/...        -> small diagnostic commands
"""

import os
import sys

from . import __version__, browser, config, processes, service as service_mod


def run_handler(url: str) -> int:
    source = processes.source_process()
    if service_mod.send_to_running(url, source):
        return 0
    from . import interception

    interception.run(url, source=source)
    return 0


def _print_status() -> int:
    from . import schemes

    http = schemes.query("http")
    https = schemes.query("https")
    print(f"version:        {__version__}")
    print(f"our desktop id: {config.DESKTOP_ID}")
    print(f"http handler:   {http or 'none'}")
    print(f"https handler:  {https or 'none'}")
    print(f"installed:      {'yes' if http == config.DESKTOP_ID and https == config.DESKTOP_ID else 'no'}")
    cfg = config.load()
    print(f"forward browser:{cfg.get('forward_browser', 'auto')}")
    print(f"original http:  {cfg.get('original_http') or 'none'}")
    print(f"original https: {cfg.get('original_https') or 'none'}")
    return 0


def run_tray() -> int:
    cfg = config.load()
    if service_mod.is_running():
        print("linux-url-interceptor is already running in the tray.")
        return 0

    from . import logger, schemes

    schemes.ensure_icon()

    # On Wayland the Qt tray has no XEmbed owner to dock into, so it runs with
    # an invisible icon; the StatusNotifier (AppIndicator) backend is the one
    # that actually shows there.
    if os.environ.get("WAYLAND_DISPLAY"):
        try:
            from .indicator import IndicatorApp

            return IndicatorApp(cfg).run()
        except Exception:
            pass

    # Preferred: Qt tray icon (X11 desktops with an XEmbed tray).
    try:
        from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
    except Exception:
        QApplication = None

    if QApplication is not None:
        app = QApplication(sys.argv)
        app.setApplicationName("Linux URL Interceptor")
        app.setApplicationDisplayName("Linux URL Interceptor")
        app.setQuitOnLastWindowClosed(False)
        if QSystemTrayIcon.isSystemTrayAvailable():
            from .app import TrayApp

            tray = TrayApp(app, cfg)
            logger.runtime_log("tray started (Qt)")
            code = app.exec()
            tray.shutdown()
            return code

    # Fallback: AppIndicator (GNOME etc. without XEmbed).
    try:
        from .indicator import IndicatorApp

        return IndicatorApp(cfg).run()
    except Exception:
        pass

    print(
        "No system tray available. The http/https handler still works: "
        "each intercepted URL is handled in its own short-lived process. "
        "Install an AppIndicator extension for GNOME to get the tray."
    )
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return run_tray()

    first = argv[0]
    if first in ("--version", "-V"):
        print(__version__)
        return 0
    if first == "--status":
        return _print_status()
    if first == "--install":
        from . import schemes

        cfg = config.load()
        ok = schemes.install(cfg)
        print("installed as default http/https handler" if ok else "install failed")
        return 0 if ok else 1
    if first == "--uninstall":
        from . import schemes

        ok = schemes.uninstall(config.load())
        print("restored original http/https handler" if ok else "restore failed")
        return 0 if ok else 1
    if first == "--list-browsers":
        for b in browser.list_browsers():
            print(f"{b['id']}\t{b['name']}")
        return 0
    if first == "--intercept":
        if len(argv) < 2:
            print("usage: --intercept <url>")
            return 1
        return run_handler(argv[1])
    if first.startswith(("http://", "https://")):
        return run_handler(first)

    print(f"unknown argument: {first}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
