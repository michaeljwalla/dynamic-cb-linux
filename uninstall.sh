#!/bin/bash
set -e

SERVICE="dynamic-clipboard"
APP_DIR="/usr/local/lib/$SERVICE"
BIN_DIR="/usr/local/bin"
SRC_DIR="$(cd "$(dirname "$0")/py-impl" && pwd)"
echo "Delete pinned history now? You can find your data at ~/.cb_history/"
read -p " [y/n] " -n 1 -r
echo -e "\n"
sudo rm -f ~/.cb_history/blobs/tutorial
if [[ $REPLY =~ ^[Yy]$ ]]; then
  sudo rm -rf ~/.cb_history
  echo "Deleted ~/.cb_history/"
else
  echo "Preserved data at ~/.cb_history"
fi

systemctl --user stop "$SERVICE" 2>/dev/null || true
systemctl --user disable "$SERVICE" 2>/dev/null || true

systemctl --user daemon-reload

sudo rm -rf $APP_DIR
#sudo rm -rf ~/.cb_history
sudo rm -f $BIN_DIR/$SERVICE
sudo rm -f $BIN_DIR/$SERVICE-restart
sudo rm -f ~/.config/systemd/user/$SERVICE.service
sudo rm -f /tmp/dynamic-cb.sock
echo ========================================================
echo "Uninstalled dynamic clipboard, thanks for using!"
echo "You may need to reboot to fully apply."
echo ========================================================