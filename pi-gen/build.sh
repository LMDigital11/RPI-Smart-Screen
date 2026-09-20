#!/usr/bin/env bash
# Builds the Smart Screen OS image with pi-gen on a Linux machine (or WSL2).
#
#   sudo bash pi-gen/build.sh
#
# Produces: <pi-gen>/deploy/YYYY-MM-DD-smart-screen.zip  (note: .zip)
# The .zip contains the .img to flash with the Raspberry Pi Imager.
#
# Requirements:
#   - Debian/Ubuntu (bookworm or newer), 8GB+ free, ~2h build time
#   - sudo, git, and docker (for build-docker.sh) OR the native toolchain
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PI_GEN_DIR="${PI_GEN_DIR:-/tmp/pi-gen}"

if [ "$(id -u)" != "0" ]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi
if [ "$(basename "$(pwd)")" != "pi-gen" ] && [ ! -d "$PI_GEN_DIR" ]; then
  echo "pi-gen will be set up in $PI_GEN_DIR"
fi

# 1. Bring in pi-gen (official Raspberry Pi OS build tool).
if [ ! -d "$PI_GEN_DIR/.git" ]; then
  git clone --depth 1 https://github.com/RPi-Distro/pi-gen "$PI_GEN_DIR"
fi
cd "$PI_GEN_DIR"

# 2. Sync the app source into the stage.
bash "$REPO_DIR/pi-gen/prepare.sh"

# 3. Drop our stage into the pi-gen tree.
ln -sfn "$REPO_DIR/pi-gen/stage-smarter" "$PI_GEN_DIR/stage-smarter"

# 4. Use our config (sets STAGE_LIST, IMG_NAME, user, etc.).
cp "$REPO_DIR/pi-gen/config" "$PI_GEN_DIR/config"

# 5. Only OUR stage produces the image; stop stage2's default export.
touch "$PI_GEN_DIR/stage2/SKIP_IMAGES"

# 6. Build. build-docker.sh keeps your machine clean; use ./build.sh if you
#    prefer a native build (requires the tools from pi-gen/depends).
if command -v docker >/dev/null 2>&1; then
  echo "Using Docker build..."
  ./build-docker.sh
else
  echo "No Docker found. pi-gen will install/require the native toolchain..."
  ./build.sh
fi

echo
echo "Done. Image(s) and archives are in: $PI_GEN_DIR/deploy/"
echo "Flash the .img (extracted from the .zip) with the Raspberry Pi Imager."