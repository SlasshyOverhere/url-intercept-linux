"""Resolve a URL's redirect chain (HTTP redirects plus meta-refresh)."""

import re
import urllib.request
from urllib.parse import urljoin

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) LinuxURLInterceptor/1.0"
MAX_HOPS = 10
TIMEOUT = 8.0

_META_REFRESH_RE = re.compile(
    r'<meta[^>]+http-equiv=["\']?\s*refresh\s*["\']?[^>]+content=["\']'
    r'\s*\d+\s*;\s*url\s*=\s*["\']?([^"\' >]+)',
    re.IGNORECASE,
)


class _RedirectCaptured(Exception):
    def __init__(self, location, newurl):
        self.location = location
        self.newurl = newurl


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise _RedirectCaptured(headers.get("Location"), newurl)


def resolve(url: str):
    """Follow redirects and return (final_url, trace_list)."""
    opener = urllib.request.build_opener(_NoRedirect)
    trace = [url]
    current = url
    for _ in range(MAX_HOPS):
        try:
            req = urllib.request.Request(
                current,
                headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            )
            with opener.open(req, timeout=TIMEOUT) as resp:
                final = resp.geturl()
                if final == current:
                    ctype = resp.headers.get("Content-Type", "")
                    if "html" in ctype:
                        body = resp.read(65536).decode("utf-8", "replace")
                        m = _META_REFRESH_RE.search(body)
                        if m:
                            nxt = urljoin(final, m.group(1).strip("'\""))
                            if nxt.startswith(("http://", "https://")):
                                trace.append(nxt)
                                current = nxt
                                continue
                return final, trace
        except _RedirectCaptured as e:
            if not e.location:
                return current, trace
            nxt = urljoin(current, e.location)
            if not nxt.startswith(("http://", "https://")):
                return current, trace
            trace.append(nxt)
            current = nxt
            continue
        except Exception:
            return current, trace
    return current, trace
