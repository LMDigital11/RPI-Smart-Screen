# RPI Smart Screen

An Echo-Show-style smart screen for the home, running as its own
"operating system" (Raspberry Pi OS / Debian + this app) on a
Raspberry Pi 4 with the official 7" touchscreen.

The SD card boots straight into the app — no desktop, no browser
chrome. Like RetroPie, but for a bedside / room smart display.

## What it does

- Big clock + full-screen photo slideshow
- Photos from your **Immich** server (refreshes on a configurable schedule)
- Photos from a **USB stick** (pick the drive in settings)
- Every few photos, a **weather** card slides in (Open-Meteo, no API key needed)
- **Swipe up** → full smart-home control via **Home Assistant**
  (embedded dashboards + native light/switch/thermostat controls)
- **Settings** screen configures everything about the device
- **First boot setup wizard**: connect to WiFi, wire up Immich,
  weather location, USB drives, sleep, and alarm in a few steps
- **Sleep mode**: screen off; tap to wake for 20 seconds, then back off
- **Alarm clock**: sounds through the AUX jack, with an optional
  "wake with light" — a smart bulb ramps up slowly in the morning
- **Bluetooth speaker**: another phone can pair and play music
  through the AUX port

## Project layout

```
smart-screen-app/   the app itself (Python backend + web frontend)
  backend/          Python API server (localhost) — Immich, weather, HA,
                    USB, audio/alarm, display sleep, WiFi, config
  frontend/         the touchscreen UI (single-page web app)
deploy/install.sh   INSTALL IT ONTO A STOCK Raspberry Pi OS — the fast path
pi-gen/             optional: turns the app into a bootable .img instead
docs/build-guide.md the .img path, if you ever want it
```

## Quick start (install on stock Raspberry Pi OS — recommended)

Skip image building entirely. Flash a normal **Raspberry Pi OS** SD card
(Desktop 64-bit is easiest), boot the Pi once, then:

```bash
git clone <your-repo-url> smart-screen     # e.g. https://github.com/you/smart-screen
cd smart-screen
sudo bash deploy/install.sh
sudo reboot
```

That's it — the installer copies the app to `/opt/smart-screen`, wires up
WiFi/Immich/weather/Home Assistant backend, the kiosk (autologin into a
fullscreen browser), the AUX alarm audio, Bluetooth speaker mode, sleep/display
handling, and the over-the-air updater. After reboot the Pi launches straight
into the app and the **first-boot setup wizard** appears on the touchscreen.

From then on, settings are changed on the screen (no shell needed). Pushing
new versions = commit + push to your git repo → the device pulls it via
**Settings → Software update**.

## Optional: build your own .img instead

Want a single flashable "appliance" image instead? See
`docs/build-guide.md` — it produces a `smart-screen-*.img` with pi-gen, but
is heavier: it requires a Linux build machine with Docker, ~10 GB free and
1–2 h to build. The install approach above gives the identical result in
~10 minutes.

## Developing on a PC while the Pi builds are done elsewhere

Run the app standalone to iterate on the UI and backend logic:

```
cd smart-screen-app/backend
pip install -r requirements.txt
python main.py            # serves the UI at http://localhost:8080
```

Backend + frontend then run anywhere (Windows/Linux/macOS); the
Pi-only bits (backlight, jack audio, WiFi) degrade gracefully.