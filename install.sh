#!/bin/bash


set -e
# SYSTEM packages check (not venv)
missing=()
for pkg in python3-tk socat python3-venv; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        missing+=("$pkg")
    fi
done
if [ "$1" != "skip" ]; then
    if [ ${#missing[@]} -ne 0 ]; then
        echo "Missing required system packages: ${missing[*]}"
        read -rp "Force-install clipboard anyways? (Not recommended) (y/n): " choice
    
        if [[ "$choice" =~ ^[Yy]$ ]]; then
            echo "Attempting to force install..."
        else
            echo "Installation cancelled. Please install:"
            echo ${missing[*]}
            exit 1
        fi
    fi
fi

###

APP_DIR="/usr/local/lib/dynamic-clipboard"
BIN_DIR="/usr/local/bin"
SRC_DIR="$(cd "$(dirname "$0")/py-impl" && pwd)"

echo "Installing to $APP_DIR..."

sudo mkdir -p $APP_DIR
sudo cp -r $SRC_DIR/* $APP_DIR/

echo "Creating environment..."
echo
sudo python3 -m venv $APP_DIR/.venv
sudo $APP_DIR/.venv/bin/pip install --upgrade pip
sudo $APP_DIR/.venv/bin/pip install -r $SRC_DIR/requirements.txt

echo
echo "Installing launcher to $BIN_DIR/dynamic-clipboard(-toggle)..."

#hardcoded path
sudo tee $BIN_DIR/dynamic-clipboard > /dev/null << 'EOF'
#!/bin/bash
exec /usr/local/lib/dynamic-clipboard/.venv/bin/python3 \
     /usr/local/lib/dynamic-clipboard/main_ui.py "$@"
EOF
sudo chmod +x $BIN_DIR/dynamic-clipboard 

#hardcoded path 
sudo tee /usr/local/bin/dynamic-clipboard-toggle > /dev/null << 'EOF'
#!/bin/bash
echo "you should set /usr/local/bin/dynamic-clipboard-toggle to a hotkey!"
echo "show" | /usr/bin/socat - UNIX-CONNECT:/tmp/dynamic-cb.sock
EOF
sudo chmod +x /usr/local/bin/dynamic-clipboard-toggle


echo "Installing systemd service to "
mkdir -p ~/.config/systemd/user/
tee ~/.config/systemd/user/dynamic-clipboard.service > /dev/null << 'EOF'
[Unit]
Description=Dynamic Clipboard
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/local/bin/dynamic-clipboard
WorkingDirectory=/usr/local/bin
Restart=on-failure
RestartSec=3

# Needed for GUI apps to connect to your display
Environment=DISPLAY=:0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/%U/bus

[Install]
WantedBy=default.target
EOF

echo modifying R/W access...
sudo chown -R $USER:$USER /usr/local/lib/dynamic-clipboard

systemctl --user daemon-reload
systemctl --user enable dynamic-clipboard.service

# systemctl --user restart dynamic-clipboard.service

echo -e "\ndone.\n\n"
echo ========================================================
echo -e "set your shortcuts app to some key (Ctrl+Alt+V ?) to\n\
run 'dynamic-clipboard-toggle'!"
echo -e "\nor, you can toggle directly from terminal\n\
'dynamic-clipboard-toggle'"
echo ========================================================
echo "reboot your system to start using Dynamic Clipboard!"
