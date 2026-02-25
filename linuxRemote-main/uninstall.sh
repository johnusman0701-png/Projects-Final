#!/usr/bin/env bash
set -euo pipefail

# Must run as root
if [ "$(id -u)" -ne 0 ]; then
  echo "Error: run as root: sudo ./uninstall.sh"
  exit 1
fi

# Stop & disable service
if systemctl is-active --quiet remote-bot; then
  systemctl stop remote-bot
fi
if systemctl is-enabled --quiet remote-bot; then
  systemctl disable remote-bot
fi

# Remove service & defaults
rm -f /etc/systemd/system/remote-bot.service
rm -f /etc/default/remote-bot

# Remove code
rm -rf /opt/remote-bot

# Reload systemd
systemctl daemon-reload

cat <<EOF
✅ Uninstalled remote-bot.
You may also remove dependencies if desired:
  sudo apt remove --purge -y python3-venv python3-pip python3 \\
      gocryptfs fuse rclone openssh-server rsync
EOF
