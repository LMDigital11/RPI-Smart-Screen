#!/usr/bin/env bash
# In-place installer for testing the Smart Screen on a Pi that already runs
# Raspberry Pi OS (Desktop recommended). Copies the app, wires the kiosk,
# and enables services. Reverse of the pi-gen build — same end result.
#
# Usage (on the Pi, as root):
#   sudo bash deploy/install.sh [mountpoint]
#
# The app source is read from ../smart-screen-app relative to this repo.

set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_SRC="$REPO_DIR/smart-screen-app"
DEST=/opt/smart-screen
BOOT_USER="${SUDO_USER:-pi}"

if [ "$(id -u)" != "0" ]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi

echo "==> Installing packages"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  chromium \
  xserver-xorg \
  openbox \
  lightdm \
  unclutter \
  x11-xserver-utils \
  python3 \
  python3-flask \
  python3-requests \
  python3-paho-mqtt \
  udisks2 \
  alsa-utils \
  pulseaudio \
  pulseaudio-module-bluetooth \
  bluez \
  bluez-tools \
  network-manager \
  git \
  rsync

echo "==> Copying app to $DEST"
install -d "$DEST"
cp -r "$APP_SRC/." "$DEST/"
chmod 755 "$DEST/backend/main.py" 2>/dev/null || true

python3 "$DEST/backend/gen_sound.py"

echo "==> Config directory for $BOOT_USER"
install -d -o "$BOOT_USER" -g "$BOOT_USER" /etc/smart-screen

echo "==> OTA updater (pull from a git repo)"
cat > /usr/local/sbin/smart-screen-update <<'UPEOF'
#!/bin/bash
set -euo pipefail
REPO_DIR=/opt/smart-screen-src
APP_DIR=/opt/smart-screen
URL="$1"
BRANCH="${2:-main}"
APP_USER="${SUDO_USER:-pi}"
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone --depth 1 -b "$BRANCH" "$URL" "$REPO_DIR"
else
  git -C "$REPO_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$REPO_DIR" checkout -f "origin/$BRANCH"
fi
rsync -a --delete "$REPO_DIR/smart-screen-app/" "$APP_DIR/"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chown -R "$APP_USER:$APP_USER" /etc/smart-screen 2>/dev/null || true
python3 "$APP_DIR/backend/gen_sound.py"
python3 -m pip install --break-system-packages -r "$APP_DIR/backend/requirements.txt" >/dev/null 2>&1 || true
systemctl daemon-reload
( sleep 2 && systemctl restart smart-screen.service ) >/dev/null 2>&1 &
echo "updated"
UPEOF
chmod 755 /usr/local/sbin/smart-screen-update

printf '%s\n' \
  "# Smart Screen: let the app user run the pinned updater script as root." \
  "$BOOT_USER ALL=(root) NOPASSWD: /usr/local/sbin/smart-screen-update" \
  > /etc/sudoers.d/50-smart-screen
chmod 440 /etc/sudoers.d/50-smart-screen

echo "==> Backend service"
cat > /etc/systemd/system/smart-screen.service <<EOF
[Unit]
Description=Smart Screen backend
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $DEST/backend/main.py
WorkingDirectory=$DEST/backend
Restart=always
RestartSec=3
User=$BOOT_USER
Environment=SMART_SCREEN_CONFIG=/etc/smart-screen/config.json
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
systemctl enable smart-screen.service

echo "==> Kiosk: autologin + openbox autostart"
mkdir -p /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-smart-screen.conf <<EOF
[Seat:*]
autologin-user=$BOOT_USER
autologin-session=openbox
autologin-user-timeout=0
EOF

mkdir -p "/home/$BOOT_USER/.config/openbox"
cat > "/home/$BOOT_USER/.config/openbox/autostart" <<EOF
#!/bin/bash
xset s off -dpms
unclutter -idle 0.5 &
chromium --kiosk --noerrdialogs --disable-infobars --no-first-run \
  --disable-translate --check-for-update-interval=31536000 \
  --overscroll-history-navigation-disabled \
  http://127.0.0.1:8080 &
pulseaudio --start --exit-idle-time=-1 2>/dev/null || true
exit 0
EOF
chmod 755 "/home/$BOOT_USER/.config/openbox/autostart"
chown -R "$BOOT_USER":"$BOOT_USER" "/home/$BOOT_USER/.config"

echo "==> Analogue (AUX) audio + splash"
CONFIG_TXT=/boot/firmware/config.txt
[ -f "$CONFIG_TXT" ] || CONFIG_TXT=/boot/config.txt
grep -q '^dtparam=audio=on' "$CONFIG_TXT" || {
  printf '\n# Smart Screen\ndtparam=audio=on\ndtoverlay=disable-hdmi-audio\n' >> "$CONFIG_TXT"
}
raspi-config nonint do_boot_splash 1 2>/dev/null || true

echo "==> Bluetooth A2DP speaker"
systemctl enable bluetooth.service 2>/dev/null || true
mkdir -p /etc/pulse
if ! grep -q module-bluetooth-discover /etc/pulse/default.pa 2>/dev/null; then
  printf '\nload-module module-bluetooth-policy\nload-module module-bluetooth-discover\n' >> /etc/pulse/default.pa
fi

echo
echo "Installed. Reboot now: sudo reboot"
echo "On first boot the setup wizard will appear on the touchscreen."