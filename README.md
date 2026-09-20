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
pi-gen/             OS build recipe: turns the app into a bootable .img
deploy/             scripts to install the app onto a running Pi (dev/test)
docs/build-guide.md step-by-step guide to produce the .img on a Linux machine
```

## Building the .img (the short version)

You need a Linux machine (or WSL2). See `docs/build-guide.md` for details.

```
git clone https://github.com/RPi-Distro/pi-gen
cd pi-gen
cp ~/path/to/this/repo/pi-gen/config ./config
ln -s ~/path/to/this/repo/pi-gen/stage-smarter ./stage-smarter
./build-docker.sh
# → deploy/ smart-screen-*.img
```

Flash the resulting `.img` to a microSD card with the Raspberry Pi Imager,
boot the Pi, and the setup wizard walks you through the rest.

## Developing on a PC while the Pi builds are done elsewhere

Run the app standalone to iterate on the UI and backend logic:

```
cd smart-screen-app/backend
pip install -r requirements.txt
python main.py            # serves the UI at http://localhost:8080
```

Backend + frontend then run anywhere (Windows/Linux/macOS); the
Pi-only bits (backlight, jack audio, WiFi) degrade gracefully.