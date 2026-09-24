import datetime
import json
import re
import subprocess
import threading
import time

import requests

from config import config
from homeassistant import home_assistant


def _jack_card():
    try:
        out = subprocess.run(
            ["aplay", "-l"], capture_output=True, text=True, timeout=10
        ).stdout
    except Exception:
        return None
    for line in out.splitlines():
        m = re.match(r"card\s+(\d+):\s+\S+\s+\[([^\]]+)\]", line)
        if m and ("Headphones" in m.group(2) or "bcm2835" in m.group(2).lower()):
            return int(m.group(1))
    return None


def force_aux_output():
    card = _jack_card()
    if card is None:
        return
    subprocess.run(
        ["amixer", "-c", str(card), "sset", "Master", "100%"],
        capture_output=True,
        text=True,
    )


def set_volume(percent):
    card = _jack_card()
    base = ["amixer", "-c", str(card)] if card is not None else ["amixer"]
    level = "{}%".format(max(0, min(100, int(percent))))
    for ctl in ("Master", "PCM", "Headphone", "Speaker"):
        r = subprocess.run(
            base + ["sset", ctl, level], capture_output=True, text=True
        )
        if r.returncode == 0:
            return


def play(sound="default", volume=80):
    bluetooth_status_service.set_volume(volume)
    paths = {
        "default": "/opt/smart-screen/sounds/alarm.wav",
    }
    path = paths.get(sound, sound)
    dev = bluetooth_status_service.output_alsa_device()
    cmd = ["aplay", "-q", "-D", dev, path]
    try:
        subprocess.Popen(
            cmd,
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
    def power_on(self):
        try:
            subprocess.run(
                ["bluetoothctl", "power", "on"], capture_output=True, text=True, timeout=10
            )
        except Exception:
            pass

    def set_discoverable(self, on):
        try:
            if on:
                self.power_on()
            subprocess.run(
                ["bluetoothctl", "discoverable", "on" if on else "off"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            subprocess.run(
                ["bluetoothctl", "pairable", "on"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            pass

    def _btctl(self, args, timeout=25):
        try:
            resp = subprocess.run(
                ["bluetoothctl"] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return (resp.stdout or "") + (resp.stderr or "")
        except Exception:
            return ""

    def _pulse_sinks(self):
        try:
            out = subprocess.run(
                ["pactl", "-f", "json", "list", "sinks"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
            return json.loads(out or "[]")
        except Exception:
            return []

    def _default_sink(self):
        try:
            out = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            return out or None
        except Exception:
            return None

    def _set_default_sink(self, name):
        try:
            subprocess.run(
                ["pactl", "set-default-sink", name],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            pass

    @staticmethod
    def _norm_mac(mac):
        return str(mac or "").upper().replace("-", ":")

    def _bt_sink(self, mac=None):
        mac = self._norm_mac(
            mac if mac is not None else (config.get().get("bluetooth") or {}).get("bt_speaker")
        )
        if not mac:
            return ""
        key = mac.replace(":", "_")
        for sink in self._pulse_sinks():
            name = (sink.get("name") or "").upper()
            props = " ".join(
                str(v) for v in (sink.get("properties") or {}).values()
            ).upper()
            if key in name or key in props:
                return sink.get("name")
        return ""

    def set_mode(self, mode):
        mode = "connect" if mode == "connect" else "speaker"
        cfg = dict(config.get().get("bluetooth") or {})
        cfg["mode"] = mode
        config.update({"bluetooth": cfg})
        try:
            if mode == "speaker":
                self.set_discoverable(cfg.get("discoverable", True))
                if self._bt_sink():
                    mac = self._norm_mac(cfg.get("bt_speaker"))
                    if mac:
                        self._btctl(["disconnect", mac], timeout=20)
                    self._restore_default_sink()
            else:
                self.power_on()
                self._btctl(["discoverable", "off"])
                self._btctl(["pairable", "on"])
        except Exception:
            pass
        return self.status()

    def scan(self, duration=12):
        self._btctl(["scan", "off"])
        self.power_on()
        try:
            proc = subprocess.Popen(
                ["bluetoothctl", "scan", "on"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(max(4, min(int(duration), 30)))
            proc.terminate()
        except Exception:
            pass
        self._btctl(["scan", "off"])
        out = self._btctl(["devices"])
        devices = []
        seen = set()
        for line in out.splitlines():
            m = re.match(
                r"Device\s+((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s+(.*)", line
            )
            if not m:
                continue
            mac = m.group(1).upper()
            if mac in seen:
                continue
            seen.add(mac)
            info = self._btctl(["info", mac])
            name = (m.group(2) or "").strip() or self._parse_field(info, "Alias")
            devices.append(
                {
                    "mac": mac,
                    "name": name or mac,
                    "speaker": self._looks_like_speaker(info),
                    "paired": "Paired: yes" in info,
                    "connected": "Connected: yes" in info,
                }
            )
        return devices

    @staticmethod
    def _parse_field(info, field):
        try:
            for line in info.splitlines():
                if line.strip().startswith(field + ":"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _looks_like_speaker(info):
        blob = (info or "").lower()
        return bool(
            "icon: audio-card" in blob
            or "audio/video" in blob
            or ("audio" in blob and "class:" in blob)
        )

    def connect(self, mac, name="", pair=True):
        mac = self._norm_mac(mac)
        self.power_on()
        self._btctl(["scan", "off"])
        info = self._btctl(["info", mac], timeout=30)
        if "Paired: yes" not in info and pair:
            self._btctl(["pairable", "on"])
            self._btctl(["pair", mac], timeout=40)
        self._btctl(["trust", mac])
        self._btctl(["connect", mac], timeout=40)
        sink = ""
        alias = ""
        for _ in range(25):
            time.sleep(1)
            info = self._btctl(["info", mac], timeout=15)
            if "Connected: yes" not in info:
                continue
            sink = self._bt_sink(mac)
            alias = self._parse_field(info, "Alias")
            if sink:
                break
        if not sink:
            return self.status()
        name = (name or alias or mac)
        prev = self._default_sink()
        if prev and prev != sink:
            self._last_default_sink = prev
        self._set_default_sink(sink)
        cfg = dict(config.get().get("bluetooth") or {})
        cfg["mode"] = "connect"
        cfg["bt_speaker"] = mac
        cfg["bt_speaker_name"] = name
        config.update({"bluetooth": cfg})
        return self.status()

    def disconnect(self):
        cfg = dict(config.get().get("bluetooth") or {})
        mac = self._norm_mac(cfg.get("bt_speaker"))
        if mac:
            self._btctl(["disconnect", mac], timeout=20)
        self._restore_default_sink()
        return self.status()

    def _restore_default_sink(self):
        prev = getattr(self, "_last_default_sink", None)
        target = prev
        if not target:
            for sink in self._pulse_sinks():
                name = sink.get("name") or ""
                if "bluez" not in name.lower():
                    target = name
                    break
        if target:
            cur = self._default_sink()
            if cur != target and any(
                s.get("name") == target for s in self._pulse_sinks()
            ):
                self._set_default_sink(target)

    def set_volume(self, percent):
        pct = max(0, min(100, int(percent or 80)))
        sink = self._bt_sink()
        if sink:
            try:
                subprocess.run(
                    ["pactl", "set-sink-volume", sink, "{}%".format(pct)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return
            except Exception:
                pass
        set_volume(pct)

    def output_alsa_device(self):
        if self._bt_sink():
            return "pulse"
        card = _jack_card()
        return "plughw:{},0".format(card) if card is not None else "default"

    def status(self):
        try:
            show = subprocess.run(
                ["bluetoothctl", "show"], capture_output=True, text=True, timeout=10
            ).stdout
            paired = subprocess.run(
                ["bluetoothctl", "paired-devices"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
            devices = [
                line.split(" ", 2)[-1]
                for line in paired.splitlines()
                if re.search(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", line)
            ]
            speakers = []
            try:
                for sink in self._pulse_sinks():
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
            cfg = config.get().get("bluetooth") or {}
            mac = self._norm_mac(cfg.get("bt_speaker"))
            sink = self._bt_sink()
            return {
                "powered": "Powered: yes" in show,
                "pairable": "Pairable: yes" in show,
                "discoverable": "Discoverable: yes" in show,
                "aliases": devices,
                "a2dp_sinks": speakers,
                "mode": (cfg or {}).get("mode", "speaker"),
                "bt_speaker": mac,
                "bt_speaker_name": cfg.get("bt_speaker_name", ""),
                "bt_connected": bool(sink),
                "bt_sink": sink,
                "default_sink": self._default_sink(),
            }
        except Exception:
            return {
                "powered": None,
                "pairable": None,
                "discoverable": None,
                "aliases": [],
                "a2dp_sinks": [],
                "mode": "speaker",
                "bt_speaker": "",
                "bt_speaker_name": "",
                "bt_connected": False,
                "bt_sink": "",
                "default_sink": None,
            }


bluetooth_status_service = Bluetooth()
alarm_scheduler = AlarmScheduler()