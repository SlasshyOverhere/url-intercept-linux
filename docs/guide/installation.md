# Installation Guide

Install and configure **Linux URL Interceptor** on this machine by following every step below.
Work from the terminal. If a step needs `sudo`, ask the user before running it.

## What you are installing

A system-tray app that intercepts `http`/`https` URLs desktop apps launch via
`xdg-open` / `gio open`. When an app opens a link, the URL is copied to the clipboard, the
source app and URL are logged to a JSONL file, and the link is forwarded to the browser that was
registered before interception. It works by claiming the `x-scheme-handler/http` and
`x-scheme-handler/https` defaults through `xdg-mime`.

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

## Step 1 - Get the code

```sh
git clone https://github.com/SlasshyOverhere/url-intercept-linux.git ~/src/url-intercept-linux
cd ~/src/url-intercept-linux
```

## Step 2 - Install

Run the installer. It copies the app to `~/.local/share/linux-url-interceptor`, creates the
`~/.local/bin/linux-url-interceptor` launcher, writes the handler `.desktop` file, takes over the
default `http`/`https` handler (the previous one is saved), and adds a login autostart entry.

```sh
./install.sh
```

Use `./install.sh --no-register` if the default handler should be left alone for now; it can be
registered later from the tray menu.

The previous handler is saved in `~/.config/linux-url-interceptor/config.json` and is restored by
`./uninstall.sh`.

## Step 3 - Start it

```sh
setsid -f ~/.local/bin/linux-url-interceptor
```

## Step 4 - Verify

1. Confirm the handler is registered:

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

Summarize what was done: the distro, whether all dependencies installed cleanly, whether the
handler is registered (`installed: yes`), and the path of the verified intercept log line.

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
