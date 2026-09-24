import copy
import json
import os
import sys
import uuid

DEVICE_ID = uuid.uuid5(
    uuid.NAMESPACE_DNS,
    "smart-screen-{}".format(uuid.getnode()),
).hex[:12].upper()

if sys.platform == "win32":
    CONFIG_PATH = os.environ.get("SMART_SCREEN_CONFIG", "config.json")
else:
    CONFIG_PATH = os.environ.get(
        "SMART_SCREEN_CONFIG", "/etc/smart-screen/config.json"
    )

DEFAULT_CONFIG = {
    "device_name": "Smart Screen",
    "setup_complete": False,
    "wifi": {"ssid": "", "connected": False},
    "immich": {
        "server_url": "",
        "api_key": "",
        "album_ids": [],
        "refresh_minutes": 60,
        "include_shared": False,
    },
    "weather": {
        "latitude": None,
        "longitude": None,
        "unit": "celsius",
    },
    "slideshow": {
        "source": "auto",
        "photo_duration_sec": 12,
        "weather_every_n_photos": 5,
        "shuffle": True,
        "usb_drive": "",
    },
    "home_assistant": {
        "server_url": "",
        "token": "",
        "dashboard_path": "",
    },
    "mqtt": {
        "enabled": False,
        "host": "",
        "port": 1883,
        "username": "",
        "password": "",
    },
    "sleep": {
        "enabled": True,
        "idle_seconds": 30,
        "wake_seconds": 20,
    },
    "display": {"brightness": 100},
    "schedule": {
        "enabled": False,
        "days": {},
    },
    "alarm": {
        "enabled": False,
        "time": "07:00",
        "days": [1, 2, 3, 4, 5],
        "sound": "default",
        "light_ramp": True,
        "light_entity": "light.bedroom_lamp",
        "ramp_minutes": 10,
    },
    "bluetooth": {"speaker_name": "Smart Screen", "discoverable": True},
    "jellyfin": {
        "server_url": "",
        "username": "",
        "password": "",
        "api_key": "",
        "volume": 80,
    },
    "update": {"repo_url": "", "branch": "main"},
}


class Config:
    def __init__(self, path=CONFIG_PATH):
        self.path = path
        self._config = self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        merged = copy.deepcopy(DEFAULT_CONFIG)
        self._deep_merge(merged, data)
        return merged

    def _deep_merge(self, base, override):
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def save(self):
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2)

    def get(self):
        return self._config

    def update(self, patch):
        self._deep_merge(self._config, patch)
        self.save()

    def mark_setup_complete(self):
        self._config["setup_complete"] = True
        self.save()


config = Config()