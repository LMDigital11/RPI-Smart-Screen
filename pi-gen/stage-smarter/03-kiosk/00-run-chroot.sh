#!/bin/bash -e
# Runs inside the chroot: enable services and configure Bluetooth A2DP.

systemctl enable smart-screen.service
systemctl enable bluetooth.service

# Ignore keyboard/mouse BT, we only offer A2DP sink for music.
mkdir -p /etc/bluetooth
cat > /etc/bluetooth/main.conf <<'EOF'
[General]
Name=Smart Screen
DiscoverableTimeout=0
FastConnectable=true

[Policy]
AutoEnable=true
EOF

# PulseAudio: load Bluetooth modules and prefer the analogue (AUX) sink.
mkdir -p /etc/pulse
cat > /etc/pulse/default.pa <<'EOF'
.include /etc/pulse/system.pa

load-module module-bluetooth-policy
load-module module-bluetooth-discover
load-module module-switch-on-connect
EOF

# Keep WLAN + BT radios alive (no ASD power saving on the official display).
true