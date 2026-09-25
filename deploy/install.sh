#!/usr/bin/env bash
# Smart Screen installer for Raspberry Pi OS.
#
# Designed to be the fast path (no .img building): flash stock Raspberry Pi OS
# (64-bit Desktop or Lite — Desktop is easiest) onto an SD card, boot the Pi
# once, then:
#
#     git clone <your repo URL> smart-screen
#     cd smart-screen
#     sudo bash deploy/install.sh
#     sudo reboot
#
# After reboot the Pi boots into a systemd-managed WebKitGTK kiosk app showing
# the app, and the first-boot setup wizard appears on the touchscreen. The
# kiosk is a small PyGObject app (smart-screen-app/kiosk/webkit_kiosk.py) that
# fullscreens itself via the GTK API, so it works on Wayland (labwc) and X11
# sessions alike. Chromium is deliberately avoided: its renderer fails to paint
# on many arm64 Raspberry Pi OS builds (blank/white tab), while WebKitGTK
# renders reliably.
# Fully idempotent — safe to re-run to refresh the app or re-wire services.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_SRC="$REPO_DIR/smart-screen-app"
DEST=/opt/smart-screen
BOOT_USER="${SUDO_USER:-pi}"

if [ "$(id -u)" != "0" ]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi

if [ ! -d "$APP_SRC/backend" ]; then
  echo "error: $APP_SRC/backend not found (run this from inside the cloned repo)" >&2
  exit 1
fi

if grep -qi "raspberry pi" /proc/device-tree/model 2>/dev/null; then
  echo "Detected a Raspberry Pi. Good."
else
  echo "warning: this machine does not look like a Raspberry Pi."
  echo "The kiosk/touchscreen parts are Pi-specific; continuing anyway."
fi

echo "==> Installing packages (this can take a few minutes)"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3-gi \
  gir1.2-gtk-3.0 \
  gir1.2-webkit2-4.1 \
  xserver-xorg \
  xinit \
  openbox \
  lightdm \
  unclutter \
  x11-xserver-utils \
  python3 \
  python3-flask \
  python3-requests \
  python3-urllib3 \
  python3-paho-mqtt \
  imagemagick \
  udisks2 \
  usbutils \
  alsa-utils \
  pulseaudio \
  pulseaudio-module-bluetooth \
  bluez \
  bluez-tools \
  network-manager \
  raspi-config \
  git \
  rsync

echo "==> Copying app to $DEST"
install -d "$DEST"
rsync -a --delete "$APP_SRC/" "$DEST/"
chmod 755 "$DEST/backend/main.py" 2>/dev/null || true
if git -C "$REPO_DIR" rev-parse --short=8 HEAD >/dev/null 2>&1; then
  printf '%s\n' "$(git -C "$REPO_DIR" rev-parse --short=8 HEAD)" > "$DEST/VERSION"
  chown "$BOOT_USER":"$BOOT_USER" "$DEST/VERSION"
fi

echo "==> Generating alarm sound"
python3 "$DEST/backend/gen_sound.py"

echo "==> Config directory + default config for $BOOT_USER"
install -d -o "$BOOT_USER" -g "$BOOT_USER" /etc/smart-screen
if [ ! -f /etc/smart-screen/config.json ]; then
  printf '{}\n' > /etc/smart-screen/config.json
fi
chown "$BOOT_USER":"$BOOT_USER" /etc/smart-screen/config.json

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
NEW_SHA=$(git -C "$REPO_DIR" rev-parse --short=8 HEAD 2>/dev/null || true)
printf '%s\n' "${NEW_SHA:-1.0.0}" > "$APP_DIR/VERSION"
chown "$APP_USER:$APP_USER" "$APP_DIR/VERSION" 2>/dev/null || true
echo "updated to ${NEW_SHA:-unknown}"
UPEOF
chmod 755 /usr/local/sbin/smart-screen-update

printf '%s\n' \
  "# Smart Screen: let the app user run the pinned updater script as root." \
  "$BOOT_USER ALL=(root) NOPASSWD: /usr/local/sbin/smart-screen-update" \
  "$BOOT_USER ALL=(root) NOPASSWD: /usr/local/sbin/smart-bt.sh" \
  > /etc/sudoers.d/50-smart-screen
chmod 440 /etc/sudoers.d/50-smart-screen
visudo -c -f /etc/sudoers.d/50-smart-screen >/dev/null 2>&1 || true

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
Environment=XDG_RUNTIME_DIR=/run/user/%U
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
systemctl enable smart-screen.service

echo "==> Kiosk app (WebKitGTK) + service"
chmod 755 "$DEST/kiosk/webkit_kiosk.py"
cat > /etc/systemd/system/smart-screen-kiosk.service <<EOF
[Unit]
Description=Smart Screen kiosk
After=graphical.target smart-screen.service
Requires=smart-screen.service

[Service]
Type=simple
User=$BOOT_USER
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/$BOOT_USER/.Xauthority
Environment=GDK_BACKEND=x11
Environment=WEBKIT_DISABLE_DMABUF_RENDERER=1
Environment=XDG_RUNTIME_DIR=/run/user/%U
ExecStart=/usr/bin/python3 $DEST/kiosk/webkit_kiosk.py
Restart=always
RestartSec=5

[Install]
WantedBy=graphical.target
EOF
systemctl enable smart-screen-kiosk.service

echo "==> Kiosk: autologin"
mkdir -p /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-smart-screen.conf <<EOF
[Seat:*]
autologin-user=$BOOT_USER
autologin-session=openbox
autologin-user-timeout=0
EOF
systemctl enable lightdm.service
systemctl set-default graphical.target

mkdir -p "/home/$BOOT_USER/.config/openbox"
cat > "/home/$BOOT_USER/.config/openbox/autostart" <<EOF
#!/bin/bash
xset s off -dpms
unclutter -idle 0.5 &
pulseaudio --start --exit-idle-time=-1 2>/dev/null || true
exit 0
EOF
chmod 755 "/home/$BOOT_USER/.config/openbox/autostart"
chown -R "$BOOT_USER":"$BOOT_USER" "/home/$BOOT_USER/.config"

echo "==> Polkit: allow USB mounting + display power for $BOOT_USER"
mkdir -p /etc/polkit-1/rules.d
cat > /etc/polkit-1/rules.d/50-smart-screen.rules <<EOF
polkit.addRule(function (action, subject) {
    if (
        subject.user === "$BOOT_USER" &&
        (action.id.indexOf("org.freedesktop.udisks2.") === 0 ||
         action.id.indexOf("org.freedesktop.display1.set-reset") === 0)
    ) {
        return polkit.Result.YES;
    }
});
EOF

echo "==> Bluetooth: A2DP speaker mode + pair helper"
systemctl enable bluetooth.service 2>/dev/null || true
mkdir -p /etc/pulse
if ! grep -q module-bluetooth-discover /etc/pulse/default.pa 2>/dev/null; then
  printf '\nload-module module-bluetooth-policy\nload-module module-bluetooth-discover\n' >> /etc/pulse/default.pa
fi
cat > /usr/local/sbin/smart-bt.sh <<'BTEOF'
#!/bin/bash
# Make the Pi discoverable as a Bluetooth speaker ~10 min (like "pair me").
bluetoothctl power on >/dev/null 2>&1
bluetoothctl discoverable on >/dev/null 2>&1
sleep 600
bluetoothctl discoverable off >/dev/null 2>&1
BTEOF
chmod 755 /usr/local/sbin/smart-bt.sh

# The Pi's radio is often soft-blocked by rfkill after boot; bluetoothctl power
# on then fails with "org.bluez.Error.Busy", so nothing ever sees the device.
# Unblock it as root before the backend comes up.
echo "==> Bluetooth: unblock radio at boot"
cat > /etc/systemd/system/smart-screen-bt.service <<'EOF'
[Unit]
Description=Unblock Raspberry Pi Bluetooth for Smart Screen
After=bluetooth.service
Before=smart-screen.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/rfkill unblock bluetooth
ExecStart=/usr/bin/bluetoothctl power on

[Install]
WantedBy=multi-user.target
EOF
systemctl enable smart-screen-bt.service

echo "==> Boot tweaks: AUX audio, splash off, quicker boot"
CONFIG_TXT=/boot/firmware/config.txt
[ -f "$CONFIG_TXT" ] || CONFIG_TXT=/boot/config.txt
append_cfg() {
  grep -qF "$1" "$CONFIG_TXT" || printf '%s\n' "$1" >> "$CONFIG_TXT"
}
if [ "$(stat -c %U "$CONFIG_TXT" 2>/dev/null)" = "root" ]; then
  append_cfg ""
  append_cfg "# --- Smart Screen ---"
  append_cfg "disable_splash=1"
  append_cfg "boot_delay=0"
  append_cfg "dtparam=audio=on"
  append_cfg "dtoverlay=disable-hdmi-audio"
else
  # Some images mount this FAT partition with a non-root owner; fall back to tee.
  printf '\n# --- Smart Screen ---\ndisable_splash=1\nboot_delay=0\ndtparam=audio=on\ndtoverlay=disable-hdmi-audio\n' | tee -a "$CONFIG_TXT" >/dev/null
fi

echo "==> raspi-config: nothing blocks first boot"
raspi-config nonint do_boot_splash 1 2>/dev/null || true
raspi-config nonint do_expand_rootfs 2>/dev/null || true

echo
echo "============================================="
echo " Smart Screen installed."
echo " Reboot now: sudo reboot"
echo
echo " On next boot the setup wizard appears on the touchscreen:"
echo "   - connect WiFi"
echo "   - Immich server + API key"
echo "   - weather location"
echo "   - Home Assistant URL + long-lived token"
echo " Settings > Software update lets you pull newer versions from git."
echo "============================================="