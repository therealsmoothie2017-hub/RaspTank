#!/usr/bin/env bash
# ==============================================================================
# RaspTank Cloud Agent Installation Script (for Raspberry Pi OS)
# ==============================================================================
set -e

echo "=== Installing RaspTank Cloud Agent Dependencies ==="
sudo apt-get update
sudo apt-get install -y python3-pip python3-opencv python3-numpy libatlas-base-dev

# Install Python packages
pip3 install websockets requests --break-system-packages 2>/dev/null || pip3 install websockets requests

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

echo "=== Configuring Systemd Service ==="
SERVICE_FILE="/etc/systemd/system/tank-agent.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=RaspTank Cloud Tele-Operation Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/tank_agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable tank-agent.service

echo ""
echo "===================================================================="
echo "Setup Complete!"
echo "1. Edit '$SCRIPT_DIR/config.json' with your Render app URL."
echo "2. Start the agent now:   sudo systemctl start tank-agent"
echo "3. View real-time logs:   sudo journalctl -u tank-agent -f"
echo "===================================================================="

