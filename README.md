# Linux URL Interceptor

A lightweight system-tray app for Linux that intercepts URLs desktop apps launch through the
system (`xdg-open` / `gio open`), copies them to your clipboard instantly, logs them with the
source app, and can forward them to your real browser.

It is a Linux port of [SlasshyOverhere/RedirectURLInterceptor](https://github.com/SlasshyOverhere/RedirectURLInterceptor)
(Windows). On Windows that app registers itself as the `HTTP`/`HTTPS` protocol handler; on Linux
the same idea is done with the `xdg-mime` / desktop-entry `x-scheme-handler` mechanism.

## Install with your AI agent

Paste this prompt into Claude Code, AmpCode, Cursor, or any agent:

```text
Install and configure Linux URL Interceptor by following the instructions here:
https://raw.githubusercontent.com/SlasshyOverhere/url-intercept-linux/main/docs/guide/installation.md
```

## Why this exists

Many apps trigger browser redirects for sign-in, OAuth flows, preset downloads and deep links.
Linux URL Interceptor gives you control over those links:

- captures the URL before it disappears into the browser,
- copies it to the clipboard immediately,
- optionally forwards it to your preferred browser,
- logs source app + process for debugging and automation.

## Common use cases

- Capture OAuth links (`Sign in with Google`, Microsoft login, etc.).
- Capture one-click resource links from tools like audio/util apps.
- Debug which app launched a link and with what URL.
- Build automations that depend on intercepted URL data.

## Features

- Always-on tray app, built for low overhead (Python + Qt6).
- `HTTP`/`HTTPS` scheme interception for full coverage.
- On/off switch from the tray menu.
- Trusted-app exclusion list you can fill from your running processes.
- Optional browser forwarding for excluded apps; auto-detects your previous handler.
- Optional redirect-chain resolution (HTTP redirects + meta-refresh).
- Desktop notification on every captured URL.
- Launch at login (autostart entry).
- JSONL logging for machine-readable history.
- Falls back to a GTK AppIndicator tray when no Qt tray is available (GNOME).

## How it works

1. The app installs a desktop entry (`~/.local/share/applications/linux-url-interceptor.desktop`)
   and claims the `x-scheme-handler/http` and `x-scheme-handler/https` defaults via `xdg-mime`.
2. When any desktop app calls `xdg-open` or `gio open` with a URL, Linux launches the interceptor
   with that URL as its argument.
3. The short-lived handler detects the source app from `/proc`, then hands the URL to the
   long-lived tray process over a Unix socket (if it is running), which owns the clipboard
   reliably on Wayland.
4. The URL is copied to the clipboard, written to the JSONL log, and forwarded to the browser
   registered before interception (or one you pick from the menu).

## Requirements

- Python 3.8+
- `PyQt6` (Qt6 bindings) — `pip install PyQt6`, or your distro's `python3-pyqt6` package.
- `wl-clipboard` (Wayland, recommended) or `xclip`/`xsel` (X11) for clipboard in one-shot mode.
- `xdg-mime`, `notify-send` (usually present).

## Install

```sh
./install.sh            # installs into ~/.local, registers as default handler, enables autostart
./install.sh --no-register   # install without taking over the handler
```

This writes:

- `~/.local/share/linux-url-interceptor/` — the Python package
- `~/.local/bin/linux-url-interceptor` — the launcher
- `~/.local/share/applications/linux-url-interceptor.desktop` — the URL handler
- `~/.config/autostart/linux-url-interceptor.desktop` — starts the tray at login

The previous `http`/`https` handler is saved and restored by `./uninstall.sh` or by the
*Restore original http/https handler* tray menu item.

## Uninstall

```sh
./uninstall.sh
```

## Usage

Start the tray (it appears in the notification area):

```sh
linux-url-interceptor
```

If the http/https handler is not yet registered, use *Install as default http/https handler* in
the tray menu (or `linux-url-interceptor --install`).

### Tray menu options

- `Interception enabled` — master switch. When off, URLs pass straight to the browser.
- `Copy URL to clipboard` — copy every intercepted URL.
- `Open intercepted links in browser` — also forward intercepted (non-excluded) links after
  capture. Off by default: intercepted links are only copied.
- `Resolve redirect chain` — follow HTTP/meta-refresh redirects and log the final URL.
- `Forward browser` — choose the browser excluded apps open with (`Auto` = the handler that was
  registered before interception).
- `Excluded apps...` — trusted apps, picked from your running processes or typed by name. Their
  links open in the browser **and** are copied to the clipboard. Everything else is only copied.
- `Install as default http/https handler` / `Restore original http/https handler`
- `Launch at login` — autostart entry.
- `Interception status...`, `Open logs folder`, `Open config folder`, `Exit`.

## Data storage

Path: `~/.config/linux-url-interceptor/`

- `config.json` — settings.
- `app.log` — runtime/status logs.
- `logs/intercepts-YYYYMMDD.jsonl` — captured URL records.

Example JSONL record:

```json
{"TimestampUtc": "2026-08-03T18:00:24.542Z", "SourceApp": "myapp", "SourcePid": 12345, "SourceExe": "myapp", "Url": "https://accounts.google.com/o/oauth2/v2/auth?...", "CopiedToClipboard": true, "ForwardedTo": "original:brave-browser.desktop"}
```

## CLI

```
linux-url-interceptor                  start the tray
linux-url-interceptor --status         show handler state and config
linux-url-interceptor --install        take over http/https defaults
linux-url-interceptor --uninstall      restore the original handler
linux-url-interceptor --list-browsers  list detected browsers
linux-url-interceptor --intercept URL  simulate an intercepted URL
linux-url-interceptor https://...      handle a URL (used by the desktop entry)
```

## Run from the source tree (dev)

```sh
python3 -m linux_url_interceptor
```

The desktop entry falls back to `python3 <repo>/linux_url_interceptor/__main__.py %u` when the
installed launcher is missing, so `xdg-open` interception works from the repo too.

## Limits and notes

- Full capture requires owning the `http` + `https` scheme defaults (done by `install.sh`).
- In-page JavaScript redirects inside an already-open browser tab are outside scheme interception
  (same as the Windows app).
- On GNOME under Wayland, the launching app is often spawned by systemd user-session activation,
  so the source app may be logged as `unknown`; the URL, timestamp and clipboard copy are still
  captured.
- Captured URLs may contain sensitive OAuth parameters. Protect `logs/` accordingly.
