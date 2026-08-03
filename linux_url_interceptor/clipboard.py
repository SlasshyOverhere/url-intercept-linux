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
    candidates = []
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        candidates.append(["wl-copy", []])
    for tool, args in (("xclip", ["-selection", "clipboard"]),
                       ("xsel", ["-b", "-i"])):
        if shutil.which(tool):
            candidates.append([tool, args])
    for tool, args in candidates:
        try:
            p = subprocess.Popen(
                [tool, *args],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                p.stdin.write(text.encode("utf-8"))
            finally:
                try:
                    p.stdin.close()
                except Exception:
                    pass
            # These tools fork a daemon that owns the selection; the parent
            # usually exits once registered. A wedged compositor can make the
            # parent block, so never wait more than 1s: interception must not
            # stall on the clipboard.
            try:
                p.wait(timeout=1.0)
                if p.returncode == 0:
                    return True
            except subprocess.TimeoutExpired:
                return True
        except Exception:
            continue
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
