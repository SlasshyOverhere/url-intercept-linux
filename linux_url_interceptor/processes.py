"""Identify the desktop app that caused our handler to be launched.

Linux launches us through a chain of helpers (xdg-open, gio, gvfsd,
gtk-launch, the shell, ...). We walk /proc upward from our own parent and
report the first process that is not one of those intermediaries.
"""

import os
from pathlib import Path

_INTERMEDIARIES = {
    "xdg-open", "xdg-settings", "xdg-mime", "gio", "gvfs-open",
    "gvfsd-open", "gvfsd", "gvfsd-uri", "gvfsd-fuse", "gtk-launch",
    "dbus-daemon", "dbus-broker", "dbus-launch", "systemd", "init",
    "sh", "bash", "dash", "zsh", "fish", "ksh", "csh", "runuser",
    "sudo", "su", "pkexec", "setsid", "nohup", "systemd-run",
    "linux-url-interceptor", "python3", "python",
}


def _proc_info(pid: int):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    try:
        comm = stat[stat.index("(") + 1: stat.rindex(")")]
        rest = stat[stat.rindex(")") + 1:].split()
        ppid = int(rest[1])
    except Exception:
        return None
    argv0 = ""
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        parts = raw.split(b"\0")
        if parts and parts[0]:
            argv0 = parts[0].decode("utf-8", "replace")
    except OSError:
        pass
    return {"pid": pid, "name": comm, "argv0": argv0, "ppid": ppid}


def source_process() -> dict:
    pid = os.getppid()
    seen = set()
    while pid and pid not in seen and len(seen) < 64:
        seen.add(pid)
        info = _proc_info(pid)
        if info is None:
            break
        name = info["name"]
        if name not in _INTERMEDIARIES:
            return {"name": name, "pid": pid, "exe": info["argv0"] or name}
        pid = info["ppid"]
    return {"name": "unknown", "pid": 0, "exe": "unknown"}


def list_running_processes() -> list:
    """Unique process names owned by the current user, for the excluded-apps picker."""
    names = set()
    uid = os.getuid()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            if Path(f"/proc/{pid}/stat").stat().st_uid != uid:
                continue
        except OSError:
            continue
        info = _proc_info(int(pid))
        if info and info["name"]:
            names.add(info["name"])
    return sorted(names)
