import datetime
import subprocess
import threading
import time

import requests

from config import config
from homeassistant import home_assistant


def force_aux_output():
    try:
        subprocess.run(
            ["amixer", "cset", "numid=3", "1"], capture_output=True, text=True
        )
    except Exception:
        pass


def set_volume(percent):
    try:
        subprocess.run(
            ["amixer", "set", "PCM", "{}%".format(int(percent))],
            capture_output=True,
            text=True,
        )
    except Exception:
        pass


def play(sound="default", volume=80):
    set_volume(volume)
    paths = {
        "default": "/opt/smart-screen/sounds/alarm.wav",
    }
    path = paths.get(sound, sound)
    try:
        subprocess.Popen(
            ["aplay", "-q", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def stop():
    try:
        subprocess.run(["pkill", "-f", "aplay"], capture_output=True, text=True)
    except Exception:
        pass


class AlarmScheduler:
    def __init__(self):
        self._fired_for = {}
        self._watch = None

    def start(self):
        if self._watch:
            return
        self._watch = threading.Thread(target=self._loop, daemon=True)
        self._watch.start()

    def _loop(self):
        while True:
            time.sleep(15)
            self.check()

    def check(self):
        cfg = config.get()["alarm"]
        if not cfg["enabled"]:
            self._fired_for.clear()
            return
        now = datetime.datetime.now()
        today = now.date().isoformat()
        if now.weekday() not in cfg["days"]:
            return
        if self._fired_for.get(today, False):
            return
        try:
            hour, minute = (int(p) for p in cfg["time"].split(":"))
        except ValueError:
            return
        if (now.hour, now.minute) != (hour, minute):
            return
        self._fired_for[today] = True
        self._trigger()

    def _trigger(self):
        cfg = config.get()["alarm"]
        if cfg["light_ramp"] and cfg["light_entity"]:
            threading.Thread(target=self._ramp_light, daemon=True).start()
        play(cfg["sound"], 80)

    def _ramp_light(self):
        cfg = config.get()["alarm"]
        entity = cfg["light_entity"]
        minutes = max(1, cfg.get("ramp_minutes", 10))
        home_assistant.call_service(
            "light", "turn_on", entity_id=entity, data={"brightness_pct": 2}
        )
        steps = 20
        delay = (minutes * 60) / steps
        for i in range(1, steps + 1):
            time.sleep(delay)
            pct = round(i / steps * 100)
            home_assistant.call_service(
                "light", "turn_on", entity_id=entity, data={"brightness_pct": pct}
            )


class Bluetooth:
    def status(self):
        try:
            discoverable = subprocess.run(
                ["bluetoothctl", "show"], capture_output=True, text=True, timeout=10
            ).stdout
            paired = subprocess.run(
                ["bluetoothctl", "paired-devices"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
            devices = [line.split(" ", 2)[-1] for line in paired.splitlines() if line]
            speakers = []
            try:
                sinks = subprocess.run(
                    ["pactl", "-f", "json", "list", "sinks"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                ).stdout
                import json as _json

                for sink in _json.loads(sinks or "[]"):
                    props = sink.get("properties", {})
                    if "a2dp" in str(props).lower() or "bluetooth" in str(props).lower():
                        speakers.append(
                            {
                                "name": props.get("device.description", "Bluetooth"),
                                "device": props.get("device.name", ""),
                            }
                        )
            except Exception:
                pass
            return {
                "discoverable": "Discoverable: yes" in discoverable,
                "aliases": devices,
                "a2dp_sinks": speakers,
            }
        except Exception:
            return {"discoverable": None, "aliases": [], "a2dp_sinks": []}


bluetooth_status_service = Bluetooth()
alarm_scheduler = AlarmScheduler()