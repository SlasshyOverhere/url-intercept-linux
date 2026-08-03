"""Browser discovery and URL forwarding.

We never hand a URL back to xdg-open (that would loop straight into us). We
launch a browser executable directly by parsing its .desktop file Exec line.
"""

import os
import subprocess
from pathlib import Path

from . import config

_DESKTOP_DIRS = [
    Path.home() / ".local/share/applications",
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
    Path("/var/lib/flatpak/exports/share/applications"),
    Path.home() / ".local/share/flatpak/exports/share/applications",
]


def _desktop_dirs():
    dirs = []
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        dirs.append(Path(xdg) / "applications")
    dirs.extend(_DESKTOP_DIRS)
    return dirs


def find_desktop_file(desktop_id: str):
    if not desktop_id.endswith(".desktop"):
        desktop_id += ".desktop"
    for d in _desktop_dirs():
        p = d / desktop_id
        if p.exists():
            return p
    return None


def _read_desktop(path: Path) -> dict:
    entry = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            in_entry = False
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("["):
                    in_entry = line == "[Desktop Entry]"
                    continue
                if in_entry and "=" in line:
                    k, _, v = line.partition("=")
                    entry[k.strip()] = v.strip()
    except OSError:
        pass
    return entry


def _parse_exec(exec_line: str):
    tokens = []
    buf = ""
    quote = None
    i = 0
    n = len(exec_line)
    while i < n:
        c = exec_line[i]
        if quote:
            if c == quote:
                quote = None
                i += 1
            elif c == "\\" and quote == '"':
                if i + 1 < n:
                    buf += exec_line[i + 1]
                    i += 2
                else:
                    i += 1
            else:
                buf += c
                i += 1
        elif c in "\"'":
            quote = c
            i += 1
        elif c == "\\":
            if i + 1 < n:
                buf += exec_line[i + 1]
                i += 2
            else:
                i += 1
        elif c == " ":
            if buf:
                tokens.append(buf)
                buf = ""
            i += 1
        else:
            buf += c
            i += 1
    if buf:
        tokens.append(buf)
    return tokens


def _build_command(exec_tokens, url: str):
    cmd = []
    for tok in exec_tokens:
        if tok in ("%u", "%U", "%f", "%F"):
            cmd.append(url)
        elif tok == "%%":
            cmd.append("%")
        elif tok in ("%i", "%c", "%k", "%v", "%m"):
            pass
        else:
            cmd.append(tok)
    # strip flatpak --file-forwarding markers (e.g. `@@u ... @@`)
    out = []
    for tok in cmd:
        if tok.startswith("@@"):
            continue
        out.append(tok)
    return out


def launch_url(desktop_id: str, url: str) -> bool:
    if not desktop_id or desktop_id == config.DESKTOP_ID:
        return False
    path = find_desktop_file(desktop_id)
    if not path:
        return False
    entry = _read_desktop(path)
    exec_line = entry.get("Exec")
    if not exec_line:
        return False
    cmd = _build_command(_parse_exec(exec_line), url)
    if not cmd:
        return False
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except OSError:
        return False


def original_handler(cfg) -> str:
    for key in ("original_https", "original_http"):
        val = cfg.get(key)
        if val and val != config.DESKTOP_ID:
            return val
    return ""


def list_browsers():
    found = {}
    for d in _desktop_dirs():
        if not d.is_dir():
            continue
        for p in d.glob("*.desktop"):
            if p.name in found:
                continue
            entry = _read_desktop(p)
            mime = entry.get("MimeType", "")
            if "x-scheme-handler/https" in mime or "x-scheme-handler/http" in mime:
                found[p.name] = {
                    "id": p.name,
                    "name": entry.get("Name") or p.stem,
                }
    return sorted(found.values(), key=lambda b: b["name"].lower())


def forward(url: str, cfg) -> str:
    """Launch the URL in the chosen browser. Returns where it was sent."""
    chosen = cfg.get("forward_browser", "auto")
    if chosen and chosen != "auto" and chosen != config.DESKTOP_ID:
        if launch_url(chosen, url):
            return f"forward:{chosen}"
    orig = original_handler(cfg)
    if orig and launch_url(orig, url):
        return f"original:{orig}"
    for b in list_browsers():
        if b["id"] == config.DESKTOP_ID:
            continue
        if launch_url(b["id"], url):
            return f"fallback:{b['id']}"
    # last resort: only safe if something else owns the scheme
    if not _we_are_default():
        try:
            subprocess.Popen(
                ["xdg-open", url],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return "xdg-open"
        except OSError:
            pass
    return "failed"


def _we_are_default() -> bool:
    from . import schemes

    return schemes.is_default("https") and schemes.is_default("http")
