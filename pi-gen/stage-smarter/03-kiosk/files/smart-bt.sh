#!/bin/bash
# Make the Pi discoverable as a Bluetooth speaker for ~10 minutes,
# like the "pair me" mode in a real smart speaker.
bluetoothctl power on >/dev/null 2>&1
bluetoothctl discoverable on >/dev/null 2>&1
sleep 600
bluetoothctl discoverable off >/dev/null 2>&1