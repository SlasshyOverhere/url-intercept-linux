"""Register/unregister this app as the default http/https handler.

Linux dispatches URLs through the xdg MIME machinery: the app that owns
x-scheme-handler/http|https in mimeapps.list is launched with the URL as an
argument whenever a desktop program calls xdg-open / gio open.
"""

import os
import shutil
import subprocess
from pathlib import Path

from . import config, logger

_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect x="8" y="8" width="240" height="240" rx="56" fill="#1f6f5c"/>
  <circle cx="128" cy="128" r="76" fill="none" stroke="#eaf6ef" stroke-width="14"/>
  <line x1="52" y1="128" x2="204" y2="128" stroke="#eaf6ef" stroke-width="14"/>
  <line x1="128" y1="52" x2="128" y2="204" stroke="#eaf6ef" stroke-width="14"/>
  <ellipse cx="128" cy="128" rx="38" ry="76" fill="none" stroke="#eaf6ef" stroke-width="14"/>
  <path d="M128 52 a76 76 0 0 1 53 22" fill="none" stroke="#f6d98a" stroke-width="16" stroke-linecap="round"/>
  <polygon points="190,52 176,62 200,74" fill="#f6d98a"/>
</svg>"""


def launcher_command() -> str:
    """Command used to re-invoke ourselves for a URL or autostart."""
    env = os.environ.get("LINUX_URL_INTERCEPTOR_LAUNCHER")
    if env:
        return env
    p = Path.home() / ".local/bin/linux-url-interceptor"
    if p.exists():
        return str(p)
    here = Path(__file__).resolve().parent
    return f"python3 {here / '__main__.py'}"


def handler_desktop_path() -> Path:
    return Path.home() / ".local/share/applications" / config.DESKTOP_ID


def icon_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local/share"
    return root / "icons" / "hicolor" / "scalable" / "apps" / "linux-url-interceptor.svg"


def ensure_icon() -> None:
    p = icon_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_text(_ICON_SVG, encoding="utf-8")
    except OSError:
        pass


def write_handler_desktop() -> None:
    p = handler_desktop_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Linux URL Interceptor\n"
        "Comment=Intercept http/https URLs launched by apps, copy to clipboard and forward\n"
        "GenericName=URL Interceptor\n"
        f"Exec={launcher_command()} %u\n"
        "Icon=linux-url-interceptor\n"
        "Terminal=false\n"
        "NoDisplay=true\n"
        "Categories=Utility;\n"
        "Keywords=url;link;intercept;redirect;oauth;\n"
        "MimeType=x-scheme-handler/http;x-scheme-handler/https;\n"
    )
    p.write_text(content, encoding="utf-8")


def _update_desktop_db() -> None:
    if shutil.which("update-desktop-database"):
        try:
            subprocess.run(
                ["update-desktop-database", str(handler_desktop_path().parent)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
        except Exception:
            pass


def query(scheme: str) -> str:
    try:
        out = subprocess.run(
            ["xdg-mime", "query", "default", f"x-scheme-handler/{scheme}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def is_default(scheme: str = "https") -> bool:
    return query(scheme) == config.DESKTOP_ID


def is_installed() -> bool:
    return is_default("https") and is_default("http")


def install(cfg) -> bool:
    ensure_icon()
    if not cfg.get("original_http"):
        cfg["original_http"] = query("http") or ""
    if not cfg.get("original_https"):
        cfg["original_https"] = query("https") or ""
    write_handler_desktop()
    _update_desktop_db()
    ok = True
    for scheme in ("http", "https"):
        try:
            subprocess.run(
                ["xdg-mime", "default", config.DESKTOP_ID, f"x-scheme-handler/{scheme}"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
        except Exception:
            ok = False
    cfg["installed"] = ok
    config.save(cfg)
    logger.runtime_log(f"installed (original http={cfg.get('original_http')} https={cfg.get('original_https')}) ok={ok}")
    return ok


def uninstall(cfg) -> bool:
    ok = True
    for scheme, backup in (("http", cfg.get("original_http")), ("https", cfg.get("original_https"))):
        target = backup or ""
        try:
            subprocess.run(
                ["xdg-mime", "default", target, f"x-scheme-handler/{scheme}"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
        except Exception:
            ok = False
    cfg["installed"] = False
    config.save(cfg)
    logger.runtime_log(f"restored original handlers ok={ok}")
    return ok


def autostart_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "autostart" / "linux-url-interceptor.desktop"


def set_autostart(enabled: bool) -> None:
    p = autostart_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if enabled:
        p.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Linux URL Interceptor\n"
            "Comment=Start URL interceptor tray at login\n"
            f"Exec={launcher_command()}\n"
            "Icon=linux-url-interceptor\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
    else:
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
    logger.runtime_log(f"autostart set to {enabled}")
