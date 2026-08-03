"""The core interception action, shared by the tray and one-shot handlers."""

from . import browser, clipboard, config, logger, processes, redirects


def should_intercept(cfg, source_name: str) -> bool:
    if not cfg.get("enabled", True):
        return False
    name = (source_name or "").lower()
    if name and name in {a.lower() for a in cfg.get("excluded_apps", [])}:
        return False
    return True


def run(url: str, source=None, gui_notify=None):
    """Process one captured URL. Returns the JSONL record, or None on pass-through."""
    source = source or processes.source_process()
    src_name = (source or {}).get("name", "unknown")
    cfg = config.load()

    if not should_intercept(cfg, src_name):
        browser.forward(url, cfg)
        logger.runtime_log(f"pass-through url={url} app={src_name}")
        return None

    record = {
        "TimestampUtc": logger.utcnow_iso(),
        "SourceApp": src_name,
        "SourcePid": (source or {}).get("pid", 0),
        "SourceExe": (source or {}).get("exe", ""),
        "Url": url,
    }

    final_url = url
    if cfg.get("resolve_redirect_chain"):
        final_url, trace = redirects.resolve(url)
        record["FinalUrl"] = final_url
        record["RedirectTrace"] = trace

    if cfg.get("copy_to_clipboard", True):
        record["CopiedToClipboard"] = clipboard.set_clipboard(final_url)

    if cfg.get("open_in_browser", True):
        record["ForwardedTo"] = browser.forward(final_url, cfg)

    logger.intercept_log(record)
    logger.runtime_log(f"intercepted url={url} app={src_name}")
    if gui_notify:
        try:
            gui_notify(src_name, url, final_url)
        except Exception:
            pass
    return record
