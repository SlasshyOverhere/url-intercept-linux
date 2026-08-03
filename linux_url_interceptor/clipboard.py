"""Set the clipboard.

The external clipboard tools (wl-copy/xclip/xsel) own the selection
themselves and fork a daemon, so they are the most reliable path on both
Wayland and X11. We only fall back to the Qt clipboard when none of them is
installed; Qt works in the long-lived tray process, which stays alive and
keeps the selection on Wayland.
"""

import os
import shutil
import subprocess


def _external_set(text: str) -> bool:
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        try:
            p = subprocess.run(
                ["wl-copy"],
                input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            return p.returncode == 0
        except Exception:
            pass
    for tool, args in (("xclip", ["-selection", "clipboard"]),
                       ("xsel", ["-b", "-i"])):
        if shutil.which(tool):
            try:
                p = subprocess.run(
                    [tool, *args],
                    input=text.encode("utf-8"),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
                return p.returncode == 0
            except Exception:
                pass
    return False


def set_clipboard(text: str) -> bool:
    if _external_set(text):
        return True
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            QApplication.clipboard().setText(text)
            return True
    except Exception:
        pass
    return False
