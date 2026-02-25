#!/usr/bin/env bash
set -euo pipefail

# 1) Must run as root
if [ "$(id -u)" -ne 0 ]; then
  echo "Error: run as root: sudo ./install.sh"
  exit 1
fi

# 2) Update & core deps
apt update
apt install -y python3 python3-venv python3-pip \
               gocryptfs fuse rclone

# 3) Optional SSH server
read -p "Enable SSH server for /ssh command? [y/N] " USE_SSH
if [[ "$USE_SSH" =~ ^[Yy] ]]; then
  apt install -y openssh-server
  echo "→ Setting root password (you’ll be prompted)"
  passwd root
  sed -i \
    -e 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' \
    -e 's/^#\?PermitRootLogin .*/PermitRootLogin yes/' \
    /etc/ssh/sshd_config
  systemctl restart ssh
  echo "✔ SSH server configured"
else
  echo "→ Skipping SSH server install"
fi

# 4) Optional rsync
read -p "Install rsync for local backups? [y/N] " USE_RSYNC
if [[ "$USE_RSYNC" =~ ^[Yy] ]]; then
  apt install -y rsync
  echo "✔ rsync installed, set it up and COPY YOUR BUCKET REMOTE (e.g. bucket:bucket)"
  rclone config
else
  echo "→ Skipping rsync"
fi

# 5) Python libs
python3 -m pip install --upgrade pip --break-system-packages
python3 -m pip install python-telegram-bot requests --break-system-packages

# 6) Prompt for bot & folder config
read -p "Telegram BOT_TOKEN: "      BOT_TOKEN
read -p "Bot command PASSWORD: "    BOT_PASSWORD
read -p "gocryptfs encryption password: "  GFS_PASSWORD
read -p "Target folder [~/Videos]: " TARGET
TARGET=${TARGET:-~/Videos}
TARGET=$(eval echo "$TARGET")

read -p "Rclone remote (e.g. myremote:bucket) [leave blank to skip upload]: " RCLONE_REMOTE

# 7) Deploy code
BOT_HOME=/opt/remote-bot
rm -rf "$BOT_HOME"
mkdir -p "$BOT_HOME"
cp -R . "$BOT_HOME"

# 8) Save defaults
ENVFILE=/etc/default/remote-bot
cat >"$ENVFILE" <<EOF
# Telegram bot settings
BOT_TOKEN='$BOT_TOKEN'
PASSWORD='$BOT_PASSWORD'

# gocryptfs encryption password
GOCYPTFS_PASSWORD='$GFS_PASSWORD'

# Folder to encrypt/shred/etc.
TARGET='$TARGET'

# rclone remote (empty = disable /upload)
RCLONE_REMOTE='$RCLONE_REMOTE'
EOF
chmod 600 "$ENVFILE"

# 9) Install systemd service
SERVICE=/etc/systemd/system/remote-bot.service
cat >"$SERVICE" <<EOF
[Unit]
Description=Telegram Remote-Control Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=$ENVFILE
WorkingDirectory=$BOT_HOME
ExecStart=/usr/bin/env python3 $BOT_HOME/remote.py \\
  --bot-token "\${BOT_TOKEN}" \\
  --password   "\${PASSWORD}" \\
  --target     "\${TARGET}" \\
  --rclone-remote "\${RCLONE_REMOTE}"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 10) Enable & start
systemctl daemon-reload
systemctl enable --now remote-bot

cat <<EOF

✅ Installation complete!

• Bot home: $BOT_HOME
• Config:   $ENVFILE
• Logs:     journalctl -u remote-bot -f

To update settings, edit $ENVFILE and then:
  sudo systemctl restart remote-bot

EOF
