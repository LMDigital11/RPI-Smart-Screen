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
    def __init__(self):
        self._last_default_sink = None
        self._last_bt_error = ""

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

    def _btctl_session(self, commands, timeout=70):
        try:
            proc = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception:
            return ""

        out = []
        answers = [
            "enter pin code",
            "enter passkey",
            "confirm passkey",
            "confirm pin",
            "authorize service",
        ]
        reply = {
            "enter pin code": "0000",
            "enter passkey": "0000",
            "confirm passkey": "yes",
            "confirm pin": "yes",
            "authorize service": "yes",
        }

        def reader():
            try:
                for line in proc.stdout:
                    out.append(line)
                    low = line.lower()
                    for key in answers:
                        if key in low:
                            try:
                                proc.stdin.write(reply[key] + "\n")
                                proc.stdin.flush()
                            except Exception:
                                pass
                            break
            except Exception:
                pass

        rt = threading.Thread(target=reader, daemon=True)
        rt.start()
        try:
            for cmd in commands:
                try:
                    proc.stdin.write(cmd + "\n")
                    proc.stdin.flush()
                except Exception:
                    break
                time.sleep(1.0)
            deadline = time.time() + timeout
            while time.time() < deadline:
                if not rt.is_alive():
                    break
                blob = "".join(out)
                if (
                    "failed to pair" in blob.lower()
                    or "failed to connect" in blob.lower()
                    or "not available" in blob.lower()
                ):
                    break
                if "connected: yes" in blob.lower():
                    time.sleep(1)
                    break
                time.sleep(0.5)
            try:
                proc.stdin.write("quit\n")
                proc.stdin.flush()
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        return "".join(out)

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
        self._last_bt_error = ""
        self._btctl(["scan", "off"])
        self.power_on()
        show = self._btctl(["show"])
        if re.search(r"(discover|scann)ing:\s*yes", show, re.I):
            self._btctl(["scan", "off"])
            time.sleep(2)
        dur = max(4, min(int(duration or 12), 30))
        found = {}
        fail_reason = ""
        ack = False
        new_seen = False
        try:
            proc = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception:
            return {"devices": [], "error": "Couldn't start Bluetooth discovery"}

        out = []
        dev_re = re.compile(
            r"^(?:\[NEW\]\s+)?Device\s+((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s+(.*)$"
        )

        def reader():
            nonlocal fail_reason, new_seen
            try:
                for line in proc.stdout:
                    out.append(line)
                    low = line.lower()
                    if "failed to start discovery" in low:
                        fail_reason = (
                            line.split(":", 1)[1] if ":" in line else ""
                        ).strip() or "failed to start"
                    if line.strip().startswith("[NEW]"):
                        new_seen = True
                    m = dev_re.match(line.strip())
                    if m:
                        found.setdefault(m.group(1).upper(), (m.group(2) or "").strip())
            except Exception:
                pass

        def scanning():
            s = self._btctl(["show"])
            return bool(re.search(r"(discover|scann)ing:\s*yes", s, re.I))

        rt = threading.Thread(target=reader, daemon=True)
        rt.start()
        try:
            proc.stdin.write("scan on\n")
            proc.stdin.flush()
            time.sleep(2.5)
            ack = scanning()
            if not ack and not fail_reason:
                try:
                    proc.stdin.write("scan off\n")
                    proc.stdin.flush()
                except Exception:
                    pass
                time.sleep(1.5)
                proc.stdin.write("scan on\n")
                proc.stdin.flush()
                time.sleep(2.5)
                ack = scanning()
            deadline = time.time() + dur
            while time.time() < deadline:
                time.sleep(1)
                try:
                    proc.stdin.write("devices\n")
                    proc.stdin.flush()
                except Exception:
                    break
            try:
                proc.stdin.write("devices\n")
                proc.stdin.flush()
            except Exception:
                pass
            time.sleep(0.5)
            try:
                proc.stdin.write("scan off\nquit\n")
                proc.stdin.flush()
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

        for line in out:
            m = dev_re.match(line.strip())
            if m:
                found.setdefault(m.group(1).upper(), (m.group(2) or "").strip())

        error = ""
        if fail_reason and any(
            k in fail_reason.lower() for k in ("inprogress", "rejected", "busy")
        ):
            error = (
                "Bluetooth discovery was blocked — a previous scan may be stuck. "
                "Tap 'Restart Bluetooth adapter' and scan again."
            )
        elif fail_reason:
            error = (
                "Bluetooth discovery failed to start (" + fail_reason + "). "
                "Tap 'Restart Bluetooth adapter' and scan again."
            )
        elif not ack and not new_seen and not found:
            error = (
                "Bluetooth discovery didn't start — tap 'Restart Bluetooth adapter' "
                "and scan again."
            )

        devices = []
        for mac, name in found.items():
            info = self._btctl(["info", mac], timeout=20)
            devices.append(
                {
                    "mac": mac,
                    "name": name or self._parse_field(info, "Alias") or mac,
                    "speaker": self._looks_like_speaker(info),
                    "paired": "Paired: yes" in info,
                    "connected": "Connected: yes" in info,
                }
            )
        devices.sort(key=lambda d: (not d["paired"], d["name"].lower()))
        if error:
            self._last_bt_error = error
        return {"devices": devices, "error": error, "ack": ack}

    def restart_adapter(self):
        try:
            subprocess.run(
                ["bluetoothctl", "power", "off"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            time.sleep(2)
            self.power_on()
            self._btctl(["pairable", "on"])
            cfg = config.get().get("bluetooth") or {}
            if cfg.get("mode") != "connect":
                self.set_discoverable(bool(cfg.get("discoverable", True)))
            self._btctl(["scan", "off"])
        except Exception:
            pass
        self._last_bt_error = ""
        return self.status()

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
        self._last_bt_error = ""
        self.power_on()
        self._btctl(["scan", "off"])
        info = self._btctl(["info", mac], timeout=30)
        if "not available" in info.lower():
            try:
                proc = subprocess.Popen(
                    ["bluetoothctl", "scan", "on"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(8)
                proc.terminate()
            except Exception:
                pass
            self._btctl(["scan", "off"])
            info = self._btctl(["info", mac], timeout=30)
            if "not available" in info.lower():
                self._last_bt_error = (
                    "Device not found — put the speaker in pairing mode and scan again"
                )
                return self.status()

        was_paired = "Paired: yes" in info
        cmds = ["agent on", "default-agent"]
        if not was_paired and pair:
            cmds.append("pairable on")
            cmds.append("pair " + mac)
        cmds.append("trust " + mac)
        cmds.append("connect " + mac)
        out = self._btctl_session(cmds, timeout=75)
        blob = (out or "").lower()
        if "failed to pair" in blob:
            self._last_bt_error = (
                "Pairing failed — put the speaker in pairing mode and try again"
            )
        elif "failed to connect" in blob:
            self._last_bt_error = "Couldn't connect to the speaker"

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
            if not self._last_bt_error:
                self._last_bt_error = "Connected but no audio output appeared yet"
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
        self._last_bt_error = ""
        return self.status()

    def disconnect(self):
        cfg = dict(config.get().get("bluetooth") or {})
        mac = self._norm_mac(cfg.get("bt_speaker"))
        if mac:
            self._btctl(["disconnect", mac], timeout=20)
        self._restore_default_sink()
        self._last_bt_error = ""
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
                "bt_error": self._last_bt_error or "",
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
                "bt_error": self._last_bt_error or "",
                "default_sink": None,
            }


bluetooth_status_service = Bluetooth()
alarm_scheduler = AlarmScheduler()