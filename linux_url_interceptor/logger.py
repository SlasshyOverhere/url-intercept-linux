"""Logging helpers: a runtime log and machine-readable JSONL intercept records."""

import json
import threading
import time
from datetime import datetime, timezone

from . import config

_lock = threading.Lock()


def utcnow_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        + "Z"
    )


def runtime_log(message: str) -> None:
    _lock.acquire()
    try:
        d = config.config_dir()
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "app.log", "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")
    except Exception:
        pass
    finally:
        _lock.release()


def intercept_log(record: dict) -> None:
    d = config.logs_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        name = f"intercepts-{datetime.now().strftime('%Y%m%d')}.jsonl"
        _lock.acquire()
        try:
            with open(d / name, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        finally:
            _lock.release()
    except Exception:
        pass
