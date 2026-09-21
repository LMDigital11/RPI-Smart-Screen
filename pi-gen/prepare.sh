#!/usr/bin/env bash
# Syncs the live app source into the pi-gen stage so no files are duplicated.
# Run this from anywhere (Linux / macOS / WSL). Windows users run
# `bash pi-gen/prepare.sh` from a bash-ish shell (Git Bash works).

set -euo pipefail
cd "$(dirname "$0")"

SRC="$(pwd)/../smart-screen-app"
DST="$(pwd)/stage-smarter/02-app/files/smart-screen-app"

if [ ! -d "$SRC" ]; then
  echo "error: $SRC not found" >&2
  exit 1
fi

rm -rf "$DST"
mkdir -p "$DST"
cp -r "$SRC/." "$DST/"

find "$DST" -name '.gitkeep' -delete 2>/dev/null || true

# Files created on Windows/network shares loose their exec bit. pi-gen requires
# prerun.sh and 00-run.sh to be executable or it silently skips them.
chmod +x "$(pwd)/stage-smarter/prerun.sh"
find "$(pwd)/stage-smarter" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true

# Stamp the build with the source commit so the updater can detect newer
# versions. Falls back to the checked-in VERSION file outside a git checkout.
GIT_SHA=$(git -C "$(pwd)/.." rev-parse --short HEAD 2>/dev/null || true)
if [ -n "$GIT_SHA" ]; then
  printf '1.0.0+%s\n' "$GIT_SHA" > "$DST/VERSION"
fi

echo "Synced $SRC -> $DST"
echo "Next: copy stage-smarter into your pi-gen checkout (see build.sh)."