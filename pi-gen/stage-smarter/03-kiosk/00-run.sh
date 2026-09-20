#!/bin/bash -e
# Kiosk plumbing: place systemd units, autologin, autostart, polkit and
# audio/bluetooth helper files into the target filesystem.

install -d "${ROOTFS_DIR}/etc/systemd/system"
install -m 644 files/smart-screen.service "${ROOTFS_DIR}/etc/systemd/system/smart-screen.service"

install -d "${ROOTFS_DIR}/etc/lightdm/lightdm.conf.d"
install -m 644 files/50-autologin.conf "${ROOTFS_DIR}/etc/lightdm/lightdm.conf.d/50-autologin.conf"

install -d "${ROOTFS_DIR}/home/pi/.config/openbox"
install -m 755 files/openbox-autostart "${ROOTFS_DIR}/home/pi/.config/openbox/autostart"

install -d "${ROOTFS_DIR}/etc/polkit-1/rules.d"
install -m 644 files/50-smart-screen.rules "${ROOTFS_DIR}/etc/polkit-1/rules.d/50-smart-screen.rules"

install -m 755 files/smart-bt.sh "${ROOTFS_DIR}/usr/local/sbin/smart-bt.sh"

install -m 755 files/smart-screen-update "${ROOTFS_DIR}/usr/local/sbin/smart-screen-update"
install -m 440 files/50-smart-screen-sudoers "${ROOTFS_DIR}/etc/sudoers.d/50-smart-screen"

# Force analogue (AUX jack) audio and silence the boot splash.
CONFIG_TXT="${ROOTFS_DIR}/boot/firmware/config.txt"
if [ ! -f "${CONFIG_TXT}" ]; then
	CONFIG_TXT="${ROOTFS_DIR}/boot/config.txt"
fi
cat >> "${CONFIG_TXT}" <<'EOF'

# --- Smart Screen ---
disable_splash=1
boot_delay=0
dtparam=audio=on
dtoverlay=disable-hdmi-audio
EOF