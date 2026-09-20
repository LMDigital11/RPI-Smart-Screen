#!/bin/bash -e
# Runs inside the chroot: generate the built-in alarm sound, fix ownership,
# and prepare the config directory for the pi user.

mkdir -p /etc/smart-screen
chown -R pi:pi /etc/smart-screen

python3 /opt/smart-screen/backend/gen_sound.py

chown -R pi:pi /opt/smart-screen