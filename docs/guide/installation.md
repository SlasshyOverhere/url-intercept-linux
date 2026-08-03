# Installation Guide

Install, update or configure **Linux URL Interceptor** on this machine by following every step
below. Work from the terminal. If a step needs `sudo`, ask the user before running it. **Ask the
user the questions in Step 1 before running any install command.**

## What you are installing

A system-tray app that intercepts `http`/`https` URLs desktop apps launch via
`xdg-open` / `gio open`. When an app opens a link, the URL is copied to the clipboard, the source
app and URL are logged to a JSONL file, and links from trusted apps are opened in the browser.
It works by claiming the `x-scheme-handler/http` and `x-scheme-handler/https` defaults through
`xdg-mime`. The handler that was registered before interception is saved and restored on
uninstall.

## Prerequisites

Confirm these first, installing any that are missing with the distro's package manager.

| Dependency | Why | Package (example) |
| --- | --- | --- |
| `python3` (>= 3.8) | runtime | `python3` |
| `PyQt6` | system tray / GUI | `python3-pyqt6`, or `pip install PyQt6` |
| `wl-clipboard` (Wayland) **or** `xclip`/`xsel` (X11) | clipboard | `wl-clipboard`, `xclip`, `xsel` |
| `xdg-utils` | `xdg-open` / `xdg-mime` | `xdg-utils` |
| `notify-send` (libnotify) | desktop notifications | `libnotify-bin`, `libnotify` |
| `git` | cloning the repo | `git` |

Detect the distro from `/etc/os-release` and use the right package manager:

- Debian/Ubuntu: `sudo apt install -y python3-pip python3-pyqt6 wl-clipboard xdg-utils libnotify-bin git`
- Fedora: `sudo dnf install -y python3-pip python3-qt6 wl-clipboard xdg-utils libnotify git`
- Arch: `sudo pacman -S --noconfirm python-pyqt6 wl-clipboard xdg-utils libnotify git`
- openSUSE: `sudo zypper install -y python3-pip python3-PyQt6 wl-clipboard xdg-utils libnotify git`

## Step 0 - Check whether it is already installed

```sh
ls -la ~/.local/bin/linux-url-interceptor ~/.local/share/linux-url-interceptor 2>/dev/null
```

- **Already installed** (both the launcher and the app directory exist): do **not** do a fresh
  install. Read the installed version with `~/.local/bin/linux-url-interceptor --version`, and
  compare it with the latest release (Step 2 pulls the repo). If the installed version is older,
  update it: `git pull` in the repo, then re-run `./install.sh` with the flags from Step 1 - this
  overwrites the app files but **keeps** `~/.config/linux-url-interceptor/config.json`, so the
  saved original handler and the user's settings survive. If the tray is running
  (`pgrep -f "python3 -m linux_url_interceptor"`), restart it after the update so the new code
  loads. If versions already match, tell the user it is up to date and stop unless they ask for a
  reinstall.
- **Not installed**: continue with the steps below.

## Step 1 - Ask the user first

Ask these questions and record the answers before running any install command. For each one,
explain the trade-off in one sentence and note your recommended default.

1. **Start at login?** "Should it start automatically when you log in?"
   - Yes (recommended) -> use the autostart entry.
   - No -> pass `--no-autostart` to `./install.sh` (or toggle it later from the tray menu,
     *Launch at login*).
2. **Take over http/https now?** "May it become your default handler for http/https links? Your
   current handler is saved and restored on uninstall."
   - Yes (recommended) -> install with the default (registered).
   - No -> pass `--no-register`; it can be registered later from the tray menu (*Install as default
     http/https handler*).
3. **How should intercepted links behave?** "Links from non-trusted apps are copied to the
   clipboard. Should they also open in your browser?"
   - No, clipboard only (recommended) -> leave `open_in_browser` as `false`.
   - Yes -> set `"open_in_browser": true` in the config after install.
4. **Which browser should trusted / forwarded links open with?**
   - Auto, the previous handler (recommended) -> leave `forward_browser` as `"auto"`.
   - A specific browser -> set `forward_browser` to its desktop id (list them with
     `~/.local/bin/linux-url-interceptor --list-browsers`).
5. **Resolve redirect chains?** "Should it follow redirects so the final URL is logged and copied
   instead of the first hop?"
   - No (recommended) -> leave `resolve_redirect_chain` as `false`.
   - Yes -> set `"resolve_redirect_chain": true` in the config after install.
6. **Trusted apps?** "Any apps you always want to open links in the browser AND copy to the
   clipboard? (for example a password manager, Steam, Discord). Name their process names, or say
   none."
   - None (recommended) -> leave `excluded_apps` empty.

Only ask question 2 if this is a fresh install; on an update, keep whatever handler choice the
user already made and only re-register if it was registered before.

## Step 2 - Get the code

```sh
git clone https://github.com/SlasshyOverhere/url-intercept-linux.git ~/src/url-intercept-linux
cd ~/src/url-intercept-linux
```

If `~/src/url-intercept-linux` already exists (the update case), `git pull` it instead of
cloning, then `cd` into it.

## Step 3 - Install or update

Run the installer with the flags the user chose. It copies the app to
`~/.local/share/linux-url-interceptor`, creates the `~/.local/bin/linux-url-interceptor` launcher,
writes the handler `.desktop` file, takes over the default `http`/`https` handler (the previous
one is saved) unless `--no-register` was chosen, and adds a login autostart entry unless
`--no-autostart` was chosen.

```sh
./install.sh [--no-register] [--no-autostart]
```

On an update this overwrites the app files while keeping `~/.config/linux-url-interceptor/config.json`.

If the tray was running before an update, restart it to load the new code:

```sh
pkill -f "python3 -m linux_url_interceptor" || true
setsid -f ~/.local/bin/linux-url-interceptor
```

## Step 4 - Apply the user's behavior choices

Config lives at `~/.config/linux-url-interceptor/config.json` (created during install, when the
original handler is saved). Apply the answers from Step 1 by editing only the keys the user asked
to change, leaving everything else untouched:

```sh
python3 - <<'EOF'
import json, os
p = os.path.expanduser("~/.config/linux-url-interceptor/config.json")
cfg = json.load(open(p))
# cfg["open_in_browser"]        = True      # question 3 = Yes
# cfg["forward_browser"]        = "brave-browser.desktop"  # question 4 = specific browser
# cfg["resolve_redirect_chain"] = True      # question 5 = Yes
# cfg["excluded_apps"]          = ["steam", "discord"]     # question 6 = listed apps
json.dump(cfg, open(p, "w"), indent=2)
EOF
```

Uncomment only the lines that match the user's answers. If the tray is already running, restart it
after changing the config so the new values take effect.

## Step 5 - Start it

```sh
setsid -f ~/.local/bin/linux-url-interceptor
```

## Step 6 - Verify

1. Confirm the handler is registered (skip this check if the user chose `--no-register`):

   ```sh
   ~/.local/bin/linux-url-interceptor --status
   ```

   `installed: yes` must be printed.

2. Confirm the tray is reachable and the interception loop works, without opening a browser tab:

   ```sh
   ~/.local/bin/linux-url-interceptor --intercept "https://example.com/test"
   ```

3. Confirm the capture was logged:

   ```sh
   cat ~/.config/linux-url-interceptor/logs/intercepts-$(date +%Y%m%d).jsonl
   ```

   The file must contain a line with the `https://example.com/test` URL, the source app, and
   `"CopiedToClipboard": true`.

4. Confirm the clipboard holds the URL:

   - Wayland: `wl-paste`
   - X11: `xclip -o` (or `xsel -b`)

## Report

Summarize what was done: fresh install or update (with the old and new versions if updated), the
distro, whether all dependencies installed cleanly, each answer the user gave in Step 1 and how it
was applied, whether the handler is registered (`installed: yes`), whether autostart is on, and the
path of the verified intercept log line.

## Troubleshooting

- **`--status` shows `installed: no`**: run `~/.local/bin/linux-url-interceptor --install`, or
  use the *Install as default http/https handler* tray menu item.
- **No tray icon appears**: on GNOME the Qt tray needs the AppIndicator extension. The app falls
  back to AppIndicator automatically; if neither is available it still intercepts in one-shot
  mode (each URL is handled in its own short-lived process).
- **Source app logged as `unknown`**: on GNOME/Wayland the handler is spawned by systemd
  user-session activation, which loses the caller. The URL, timestamp and clipboard copy are
  still captured.

## Uninstall

```sh
cd ~/src/url-intercept-linux && ./uninstall.sh
```

This restores the previous `http`/`https` handler and removes all installed files.
