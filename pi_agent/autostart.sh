#!/usr/bin/env bash
# ==============================================================================
# Auto-start RaspTank on Raspberry Pi Boot
# ==============================================================================
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Please run with sudo: sudo ./autostart.sh"
  exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SERVICE_FILE="/etc/systemd/system/tank-agent.service"

echo "=== Setting up RaspTank Boot Service ==="

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=RaspTank Cloud Tele-Operation Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/tank_agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tank-agent
systemctl restart tank-agent

echo ""
echo "=== SUCCESS! RaspTank will now auto-start whenever powered on! ==="
systemctl status tank-agent --no-pager
