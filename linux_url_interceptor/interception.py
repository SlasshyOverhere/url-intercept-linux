"""The core interception action, shared by the tray and one-shot handlers."""

from . import browser, clipboard, config, logger, notify, processes, redirects


def is_excluded(cfg, source_name: str) -> bool:
    name = (source_name or "").lower()
    return bool(name) and name in {a.lower() for a in cfg.get("excluded_apps", [])}


def run(url: str, source=None):
    """Process one captured URL. Returns the JSONL record, or None on pass-through."""
    source = source or processes.source_process()
    src_name = (source or {}).get("name", "unknown")
    cfg = config.load()

    if not cfg.get("enabled", True):
        browser.forward(url, cfg)
        logger.runtime_log(f"disabled, pass-through url={url} app={src_name}")
        return None

    excluded = is_excluded(cfg, src_name)

    record = {
        "TimestampUtc": logger.utcnow_iso(),
        "SourceApp": src_name,
        "SourcePid": (source or {}).get("pid", 0),
        "SourceExe": (source or {}).get("exe", ""),
        "Url": url,
    }

    # Copy immediately so the user sees the URL without waiting on anything.
    if cfg.get("copy_to_clipboard", True):
        record["CopiedToClipboard"] = clipboard.set_clipboard(url)

    final_url = url
    if cfg.get("resolve_redirect_chain"):
        final_url, trace = redirects.resolve(url)
        record["FinalUrl"] = final_url
        record["RedirectTrace"] = trace
        if final_url != url and record.get("CopiedToClipboard"):
            clipboard.set_clipboard(final_url)

    if excluded:
        # Trusted app: open the link in the browser AND grab it.
        record["ExcludedApp"] = True
        record["ForwardedTo"] = browser.forward(final_url, cfg)
    elif cfg.get("open_in_browser", False):
        # Intercepted app: clipboard only, unless forwarding is explicitly enabled.
        record["ForwardedTo"] = browser.forward(final_url, cfg)

    logger.intercept_log(record)
    logger.runtime_log(f"{'excluded' if excluded else 'intercepted'} url={url} app={src_name}")
    if excluded:
        notify.send(f"Opened link from {src_name or 'unknown'}", final_url or url)
    else:
        notify.send(f"URL intercepted from {src_name or 'unknown'}", final_url or url)
    return record
