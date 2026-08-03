"""Application paths and persistent configuration.

Everything lives under the XDG base directories so the app is self-contained:
  ~/.config/linux-url-interceptor/config.json     settings
  ~/.config/linux-url-interceptor/app.log         runtime log
  ~/.config/linux-url-interceptor/logs/*.jsonl    captured URLs
"""

import json
import os
from pathlib import Path

APP_NAME = "linux-url-interceptor"
DESKTOP_ID = "linux-url-interceptor.desktop"

DEFAULTS = {
    "enabled": True,
    "copy_to_clipboard": True,
    "open_in_browser": True,
    "resolve_redirect_chain": False,
    "forward_browser": "auto",
    "excluded_apps": [],
    "launch_at_startup": True,
    "installed": False,
    "original_http": None,
    "original_https": None,
    "launcher": None,
    "version": 1,
}


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".config" / APP_NAME


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def logs_dir() -> Path:
    return config_dir() / "logs"


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base and Path(base).is_dir():
        d = Path(base) / APP_NAME
    else:
        d = config_dir()
    return d


class Config:
    def __init__(self, data=None):
        self.data = dict(DEFAULTS)
        if isinstance(data, dict):
            for k, v in data.items():
                if k in DEFAULTS:
                    self.data[k] = v

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value


def load() -> Config:
    path = config_dir() / "config.json"
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return Config(json.load(fh))
    except Exception:
        return Config()


def save(cfg: Config) -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    path = config_dir() / "config.json"
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg.data, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
