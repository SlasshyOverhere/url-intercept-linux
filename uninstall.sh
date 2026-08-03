#!/usr/bin/env bash
# Remove Linux URL Interceptor and restore the previous default handler.
set -euo pipefail

PKG_NAME="linux_url_interceptor"
BIN_NAME="linux-url-interceptor"
DATA_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$DATA_ROOT/linux-url-interceptor"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/linux-url-interceptor"
BIN_DIR="$HOME/.local/bin"
APPLICATIONS_DIR="$DATA_ROOT/applications"
ICONS_DIR="$DATA_ROOT/icons/hicolor/scalable/apps"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

# Stop a running instance so it does not re-register.
if [ -S "${XDG_RUNTIME_DIR:-$HOME/.config}/linux-url-interceptor/instance.sock" ] || [ -e "$APP_DIR" ]; then
  pkill -f "$BIN_NAME" 2>/dev/null || true
  pkill -f "python3 -m $PKG_NAME" 2>/dev/null || true
fi
sleep 1

# Restore the original handler from the saved config, then clean up files.
if [ -d "$APP_DIR" ]; then
  LINUX_URL_INTERCEPTOR_LAUNCHER="$BIN_DIR/$BIN_NAME" \
    PYTHONPATH="$APP_DIR" python3 -m $PKG_NAME --uninstall 2>/dev/null || true
fi

rm -f "$BIN_DIR/$BIN_NAME"
rm -f "$APPLICATIONS_DIR/linux-url-interceptor.desktop"
rm -f "$ICONS_DIR/linux-url-interceptor.svg"
rm -f "$AUTOSTART_DIR/linux-url-interceptor.desktop"
rm -rf "$APP_DIR"
rm -rf "$CONFIG_DIR"

echo "Removed. The original http/https handler has been restored."
