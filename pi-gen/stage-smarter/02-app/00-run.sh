#!/bin/bash -e
# Copy the app into the target filesystem. The tree is synced from
# ../smart-screen-app by pi-gen/prepare.sh so there is no duplication.

install -d "${ROOTFS_DIR}/opt/smart-screen/backend"
install -d "${ROOTFS_DIR}/opt/smart-screen/frontend"
install -d "${ROOTFS_DIR}/opt/smart-screen/sounds"

cp -r files/smart-screen-app/backend/. "${ROOTFS_DIR}/opt/smart-screen/backend/"
cp -r files/smart-screen-app/frontend/. "${ROOTFS_DIR}/opt/smart-screen/frontend/"

find "${ROOTFS_DIR}/opt/smart-screen" -type d -exec chmod 755 {} \;
find "${ROOTFS_DIR}/opt/smart-screen" -type f -exec chmod 644 {} \;