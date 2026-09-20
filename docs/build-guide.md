# Building the Smart Screen `.img`

The Smart Screen is built with **pi-gen**, the official tool the
Raspberry Pi foundation uses to build Raspberry Pi OS. It stitches
Raspberry Pi OS **Lite (64-bit)** together with this repo's
`stage-smarter` stage, producing an SD-card `.img` that boots straight
into the app.

## What you need

- A Linux machine (Debian/Ubuntu) or WSL2. ~8 GB free disk, ~1.5–2 h CPU time.
- `git`, `sudo`, and either **Docker** (recommended) or the native build tools.
  pi-gen installs the rest itself.

## Procedure

```bash
# from this repo, on the Linux box
sudo bash pi-gen/build.sh
```

That does the whole thing for you:

1. Clones `https://github.com/RPi-Distro/pi-gen` into `/tmp/pi-gen`
2. Syncs `smart-screen-app/` into the stage
3. Symlinks `stage-smarter/` into the pi-gen tree
4. Installs `pi-gen/config` (sets `STAGE_LIST`, `IMG_NAME=smart-screen`, user `pi`)
5. Disables stage2's image export so only our stage emits the final image
6. Runs `build-docker.sh` (or `./build.sh` if Docker is missing)

## Output

```
/tmp/pi-gen/deploy/2026-09-20-smart-screen.zip
```

The zip wraps the `.img`. To produce a plain `.img` instead, set
`DEPLOY_COMPRESSION="none"` in `pi-gen/config`.

## Flash it

1. Raspberry Pi Imager → "Choose OS" → "Use custom" → pick the `.img`
2. Choose your microSD → Write
3. Put the SD card in the Pi 4 (with the 7" touchscreen attached), boot
4. The **first-boot setup wizard appears**: connect WiFi, point it at your
   Immich server, give it a location for weather, and your Home Assistant
   URL + long-lived access token

## Rebuilding / iterating

- Change the app → rerun `sudo bash pi-gen/build.sh` (a full rebuild).
- To test app changes without rebuilding the whole image, run the in-place
  installer on a working Pi instead: `deploy/install.sh`.

## Making a long-lived token in Home Assistant

Settings → People → Users → your user → Security →
**Create Long-Lived Access Token**.

## Tuning

| pi-gen/config key            | Meaning                                      |
| ---------------------------- | -------------------------------------------- |
| `WPA_SSID` / `WPA_PASSPHRASE`| Pre-wire the Pi's WiFi during the build (skips that setup step) |
| `FIRST_USER_PASS`            | The `pi` user's login password                |
| `KEYBOARD_KEYMAP` / `LAYOUT` | Keyboard/locale (UK default)                  |
| `ARCH=arm64`                 | 64-bit OS (right for the Pi 4)                |

## Optional: pair Bluetooth for speaker use

In **Bluetooth speaker** settings, tap *Check status*. To make the Pi
discoverable for pairing, run `sudo smart-bt.sh` on the Pi (it stays
discoverable ~10 minutes). Pair from your phone — audio plays through the
AUX jack, and the `pulseaudio` auto-loads the A2DP sink.