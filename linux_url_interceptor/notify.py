"""Desktop notifications via notify-send (best-effort, never blocks)."""

import shutil
import subprocess


def send(title: str, body: str) -> bool:
    if not shutil.which("notify-send"):
        return False
    try:
        subprocess.Popen(
            ["notify-send", title, body,
             "-a", "Linux URL Interceptor", "-i", "linux-url-interceptor"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False
