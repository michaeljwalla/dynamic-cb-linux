#!/bin/bash
set -e

SERVICE="dynamic-clipboard"
APP_DIR="/usr/local/lib/$SERVICE"
BIN_DIR="/usr/local/bin"
SRC_DIR="$(cd "$(dirname "$0")/py-impl" && pwd)"

systemctl --user stop "$SERVICE" 2>/dev/null || true
systemctl --user disable "$SERVICE" 2>/dev/null || true

systemctl --user daemon-reload

sudo rm -rf $APP_DIR
sudo rm -rf ~/.cb_history
sudo rm -f $BIN_DIR/$SERVICE
sudo rm -f $BIN_DIR/$SERVICE-toggle
sudo rm -f ~/.config/systemd/user/$SERVICE.service
sudo rm -f /tmp/dynamic-cb.sock
echo ========================================================
echo "Uninstalled dynamic clipboard, thanks for using!"
echo "Reboot your device to apply."
echo ========================================================