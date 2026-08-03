#!/usr/bin/env bash
# Install Linux URL Interceptor into the user's ~/.local prefix.
# Usage: ./install.sh [--no-register] [--no-autostart]
set -euo pipefail

PKG_NAME="linux_url_interceptor"
BIN_NAME="linux-url-interceptor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DATA_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$DATA_ROOT/linux-url-interceptor"
APPLICATIONS_DIR="$DATA_ROOT/applications"
ICONS_DIR="$DATA_ROOT/icons/hicolor/scalable/apps"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

REGISTER=1
AUTOSTART=1
for arg in "$@"; do
  case "$arg" in
    --no-register) REGISTER=0 ;;
    --no-autostart) AUTOSTART=0 ;;
    -h|--help)
      echo "Usage: ./install.sh [--no-register] [--no-autostart]"
      echo "  --no-register   install but do NOT take over the default http/https handler"
      echo "  --no-autostart  install but do NOT add a login autostart entry"
      exit 0 ;;
  esac
done

command -v python3 >/dev/null || { echo "error: python3 is required"; exit 1; }
python3 -c "from PyQt6.QtWidgets import QApplication" >/dev/null 2>&1 || \
  { echo "error: PyQt6 is required (pip install PyQt6, or install python3-pyqt6)"; exit 1; }

mkdir -p "$APP_DIR" "$BIN_DIR" "$APPLICATIONS_DIR" "$ICONS_DIR" "$AUTOSTART_DIR"

rm -rf "$APP_DIR/$PKG_NAME"
cp -r "$SCRIPT_DIR/$PKG_NAME" "$APP_DIR/"

cat > "$BIN_DIR/$BIN_NAME" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="$APP_DIR:\${PYTHONPATH:-}"
exec python3 -m $PKG_NAME "\$@"
EOF
chmod +x "$BIN_DIR/$BIN_NAME"

cp "$SCRIPT_DIR/$PKG_NAME/resources/linux-url-interceptor.svg" "$ICONS_DIR/"

cat > "$APPLICATIONS_DIR/linux-url-interceptor.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Linux URL Interceptor
Comment=Intercept http/https URLs launched by apps, copy to clipboard and forward
GenericName=URL Interceptor
Exec=$BIN_DIR/$BIN_NAME %u
Icon=linux-url-interceptor
Terminal=false
NoDisplay=true
Categories=Utility;
Keywords=url;link;intercept;redirect;oauth;
MimeType=x-scheme-handler/http;x-scheme-handler/https;
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" 2>/dev/null || true
fi

if [ "$AUTOSTART" = "1" ]; then
cat > "$AUTOSTART_DIR/linux-url-interceptor.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Linux URL Interceptor
Comment=Start URL interceptor tray at login
Exec=$BIN_DIR/$BIN_NAME
Icon=linux-url-interceptor
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
else
  rm -f "$AUTOSTART_DIR/linux-url-interceptor.desktop"
fi

if [ "$REGISTER" = "1" ]; then
  echo "Taking over the default http/https handler (original saved and restored on uninstall)..."
  LINUX_URL_INTERCEPTOR_LAUNCHER="$BIN_DIR/$BIN_NAME" \
    PYTHONPATH="$APP_DIR" python3 -m $PKG_NAME --install
fi

echo
echo "Installed."
echo "  Start it now:   $BIN_DIR/$BIN_NAME"
if [ "$AUTOSTART" = "1" ]; then
  echo "  Or next login (autostart entry was created)."
else
  echo "  Autostart: off (add it later from the tray menu)."
fi
echo "  Uninstall:      ./uninstall.sh"
