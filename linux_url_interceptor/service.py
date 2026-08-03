"""Single-instance handoff.

The tray app owns a Unix socket. When the system launches a fresh copy of us
with a URL (because we are the registered http/https handler), that copy pushes
the URL and the detected source app to the running tray, which is long-lived
and can own the clipboard reliably. If no tray is running, the copy handles the
interception itself.
"""

import json
import socket
import threading

from . import config, interception, logger


def socket_path():
    return config.runtime_dir() / "instance.sock"


class Service:
    def __init__(self, cfg):
        self.cfg = cfg
        self.notify_cb = None
        self.dispatch = None
        self._sock = None
        self._thread = None

    def start(self) -> bool:
        path = socket_path()
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.bind(str(path))
            self._sock.listen(8)
        except OSError as exc:
            logger.runtime_log(f"service bind failed: {exc}")
            return False
        self._thread = threading.Thread(target=self._loop, daemon=True, name="url-handoff")
        self._thread.start()
        logger.runtime_log("interception service started")
        return True

    def _loop(self) -> None:
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break
            try:
                conn.settimeout(5)
                data = conn.recv(65536).decode("utf-8", "replace").strip()
                conn.sendall(b"ok")
                if data:
                    try:
                        msg = json.loads(data)
                    except Exception:
                        continue
                    if msg.get("type") == "url" and msg.get("url"):
                        if self.dispatch:
                            self.dispatch(msg["url"], msg.get("source") or {})
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def handle(self, url: str, source: dict) -> None:
        interception.run(url, source=source, gui_notify=self.notify_cb)

    def stop(self) -> None:
        try:
            if self._sock is not None:
                self._sock.close()
        except OSError:
            pass
        try:
            socket_path().unlink(missing_ok=True)
        except OSError:
            pass


def send_to_running(url: str, source: dict) -> bool:
    path = socket_path()
    if not path.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(str(path))
            payload = json.dumps({"type": "url", "url": url, "source": source or {}})
            s.sendall((payload + "\n").encode("utf-8"))
            return s.recv(4) == b"ok"
    except OSError:
        return False


def is_running() -> bool:
    path = socket_path()
    if not path.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect(str(path))
            return True
    except OSError:
        return False
