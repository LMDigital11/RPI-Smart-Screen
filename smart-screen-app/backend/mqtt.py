import datetime
import json
import threading
import time
from collections import deque

from config import config, DEVICE_ID

try:
    import paho.mqtt.client as paho
except ImportError:
    paho = None

PREFIX = "homeassistant"
TOPIC_BASE = "smart_screen"


def _topic(kind, entity, suffix):
    return "{}/{}".format(TOPIC_BASE, entity) + (("/" + suffix) if suffix else "")


class MqttService:
    def __init__(self):
        self._client = None
        self._lock = threading.Lock()
        self.connected = False
        self.last_error = ""
        self.display_power = True
        self.alarm_enabled = False
        self._notifications = deque(maxlen=10)
        self._t0 = 0.0

    @property
    def enabled(self):
        mqtt_cfg = config.get().get("mqtt") or {}
        return bool(paho and mqtt_cfg.get("enabled") and mqtt_cfg.get("host"))

    def device_id(self):
        return DEVICE_ID

    def entity_ids(self):
        did = self.device_id()
        return {
            "display": "smart_screen_display_{}".format(did),
            "alarm": "smart_screen_alarm_{}".format(did),
            "alarm_time": "smart_screen_alarm_time_{}".format(did),
            "music_play": "smart_screen_music_play_{}".format(did),
            "music_pause": "smart_screen_music_pause_{}".format(did),
            "music_stop": "smart_screen_music_stop_{}".format(did),
            "music_source": "smart_screen_music_source_{}".format(did),
            "music_volume": "smart_screen_music_volume_{}".format(did),
            "brightness": "smart_screen_brightness_{}".format(did),
            "sleep": "smart_screen_sleep_{}".format(did),
            "notify": "smart_screen_notify_{}".format(did),
        }

    def _device_payload(self):
        return {
            "identifiers": ["smart_screen_{}".format(self.device_id())],
            "name": config.get()["device_name"],
            "manufacturer": "Smart Screen",
            "model": "Raspberry Pi 4",
            "sw_version": "1.0.0",
        }

    def _availability(self):
        return {
            "availability_topic": _topic("", "status", ""),
            "payload_available": "online",
            "payload_not_available": "offline",
        }

    def _publish_discovery(self):
        did = self.device_id()
        dev = self._device_payload()
        avail = self._availability()
        ids = self.entity_ids()

        topics = {
            (PREFIX + "/switch", ids["display"]): {
                "name": "Screen",
                "unique_id": ids["display"],
                "state_topic": _topic("", "display", "state"),
                "command_topic": _topic("", "display", "set"),
                "payload_on": "ON",
                "payload_off": "OFF",
                "icon": "mdi:monitor",
            },
            (PREFIX + "/switch", ids["alarm"]): {
                "name": "Alarm",
                "unique_id": ids["alarm"],
                "state_topic": _topic("", "alarm", "state"),
                "command_topic": _topic("", "alarm", "set"),
                "payload_on": "ON",
                "payload_off": "OFF",
                "icon": "mdi:alarm",
            },
            (PREFIX + "/sensor", ids["alarm_time"]): {
                "name": "Alarm time",
                "unique_id": ids["alarm_time"],
                "state_topic": _topic("", "alarm", "time"),
                "icon": "mdi:alarm",
                "device_class": "timestamp",
            },
            (PREFIX + "/button", ids["music_play"]): {
                "name": "Music play",
                "unique_id": ids["music_play"],
                "command_topic": _topic("", "media", "command"),
                "payload_press": "PLAY",
                "icon": "mdi:play",
            },
            (PREFIX + "/button", ids["music_pause"]): {
                "name": "Music pause",
                "unique_id": ids["music_pause"],
                "command_topic": _topic("", "media", "command"),
                "payload_press": "PAUSE",
                "icon": "mdi:pause",
            },
            (PREFIX + "/button", ids["music_stop"]): {
                "name": "Music stop",
                "unique_id": ids["music_stop"],
                "command_topic": _topic("", "media", "command"),
                "payload_press": "STOP",
                "icon": "mdi:stop",
            },
            (PREFIX + "/select", ids["music_source"]): {
                "name": "Music source",
                "unique_id": ids["music_source"],
                "command_topic": _topic("", "media", "source/set"),
                "state_topic": _topic("", "media", "source"),
                "options": ["Jellyfin", "Silent", "Idle"],
                "icon": "mdi:music",
            },
            (PREFIX + "/number", ids["music_volume"]): {
                "name": "Music volume",
                "unique_id": ids["music_volume"],
                "command_topic": _topic("", "media", "volume/set"),
                "state_topic": _topic("", "media", "volume"),
                "min": 0,
                "max": 100,
                "step": 5,
                "mode": "slider",
                "unit_of_measurement": "%",
                "icon": "mdi:volume-high",
            },
            (PREFIX + "/select", ids["brightness"]): {
                "name": "Screen brightness",
                "unique_id": ids["brightness"],
                "command_topic": _topic("", "display", "brightness/set"),
                "state_topic": _topic("", "display", "brightness"),
                "options": ["0", "25", "50", "75", "100"],
                "icon": "mdi:brightness-6",
            },
            (PREFIX + "/button", ids["sleep"]): {
                "name": "Sleep now",
                "unique_id": ids["sleep"],
                "command_topic": _topic("", "button", "sleep/command"),
                "payload_press": "PRESS",
                "icon": "mdi:sleep",
            },
            (PREFIX + "/notify", ids["notify"]): {
                "name": "Smart Screen",
                "unique_id": ids["notify"],
                "state_topic": _topic("", "notify", "state"),
                "command_topic": _topic("", "notify", "command"),
                "payload_notify_enable": "ON",
                "payload_notify_disable": "OFF",
                "icon": "mdi:bell",
            },
        }
        for (discovery, ident), payload in topics.items():
            payload.update(avail)
            payload["device"] = dev
            self._publish(
                "{}/{}/config".format(discovery, ident),
                json.dumps(payload),
                retain=True,
            )

    def _publish(self, topic, payload, retain=False):
        client = self._client
        if not client or not self.connected:
            return
        client.publish(topic, payload, qos=1, retain=retain)

    def publish_all(self):
        if not self.enabled or not self.connected:
            return
        self._publish_discovery()
        on_off = lambda flag: "ON" if flag else "OFF"
        self._publish(_topic("", "display", "state"), on_off(self.display_power))
        try:
            from display import status as display_status

            self._publish(
                _topic("", "display", "brightness"),
                str(display_status().get("brightness", 100)),
            )
        except Exception:
            pass
        alarm_cfg = config.get().get("alarm") or {}
        self.alarm_enabled = bool(alarm_cfg.get("enabled"))
        self._publish(_topic("", "alarm", "state"), on_off(self.alarm_enabled))
        alarm_time = self.next_alarm_iso()
        if alarm_time:
            self._publish(_topic("", "alarm", "time"), alarm_time)
        self._publish(_topic("", "status", ""), "online")
        try:
            from player import player

            self.publish_media_state(player.state())
        except Exception:
            pass

    def publish_media_state(self, state):
        if not self.connected:
            return
        st = state or {}
        if st.get("playing"):
            mode = "playing"
        elif st.get("paused"):
            mode = "paused"
        else:
            mode = "idle"
        track = st.get("track") or {}
        volume = st.get("volume", 80)
        self._publish(_topic("", "media", "state"), mode)
        self._publish(
            _topic("", "media", "volume"),
            str(int(round(max(0.0, min(100.0, float(volume)))))),
        )
        self._publish(
            _topic("", "media", "source"),
            st.get("source") or ("Jellyfin" if mode != "idle" else "Idle"),
        )
        self._publish(_topic("", "media", "title"), track.get("name") or "")
        self._publish(_topic("", "media", "artist"), track.get("artist") or "")
        self._publish(_topic("", "media", "album"), track.get("album") or "")

    def next_alarm_iso(self):
        alarm_cfg = config.get().get("alarm") or {}
        if not alarm_cfg.get("enabled"):
            return ""
        now = datetime.datetime.now()
        for delta in range(8):
            candidate = now + datetime.timedelta(days=delta)
            if candidate.weekday() + 1 in alarm_cfg.get("days", []):
                try:
                    hour, minute = (int(p) for p in alarm_cfg["time"].split(":"))
                except (KeyError, ValueError):
                    return ""
                candidate = candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if candidate <= now:
                    continue
                tz = now.astimezone().tzinfo
                return candidate.replace(tzinfo=tz).isoformat()
        return ""

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            self.connected = False
            self.last_error = "MQTT connect failed (rc={})".format(rc)
            return
        self.connected = True
        self.last_error = ""
        with self._lock:
            self._t0 = time.time()
        self.publish_all()

        ids = self.entity_ids()
        client.subscribe([(_topic("", "display", "set"), 0)])
        client.subscribe([(_topic("", "display", "brightness/set"), 0)])
        client.subscribe([(_topic("", "alarm", "set"), 0)])
        client.subscribe([(_topic("", "media", "command"), 0)])
        client.subscribe([(_topic("", "media", "volume/set"), 0)])
        client.subscribe([(_topic("", "media", "source/set"), 0)])
        client.subscribe([(_topic("", "button", "sleep/command"), 0)])
        client.subscribe([(_topic("", "notify", "command"), 0)])
        client.subscribe([(_topic("", ids["notify"], "command"), 0)])

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False

    def _on_message(self, client, userdata, msg):
        topic = (msg.topic or "")
        payload = (msg.payload or b"").decode("utf-8", "replace").strip()
        from display import set_power, set_brightness
        from audio import alarm_scheduler, play, stop
        from player import player

        if topic.endswith("/display/set"):
            set_power(payload == "ON")
            self.display_power = payload == "ON"
            self._publish(_topic("", "display", "state"), "ON" if payload == "ON" else "OFF")
        elif topic.endswith("/display/brightness/set"):
            try:
                percent = max(0, min(100, int(float(payload))))
            except ValueError:
                percent = 100
            set_brightness(percent)
            self._publish(_topic("", "display", "brightness"), str(percent))
        elif topic.endswith("/alarm/set"):
            self.set_alarm(payload == "ON")
        elif topic.endswith("/media/command"):
            command = (payload or "").upper()
            if command in ("PLAY", "START"):
                if player.playlist:
                    player.resume()
                else:
                    play("default", 80)
            elif command in ("PAUSE", "OFF"):
                player.pause() if player.playlist else stop()
            elif command in ("STOP",):
                player.stop()
                stop()
        elif topic.endswith("/media/volume/set"):
            try:
                level = float(payload)
            except ValueError:
                level = 0.8
            if 0 < level <= 1:
                player.set_volume(round(level * 100))
            else:
                player.set_volume(round(level))
        elif topic.endswith("/media/source/set"):
            source = (payload or "").lower()
            if source == "jellyfin":
                if player.playlist:
                    player.resume()
            else:
                player.stop()
                stop()
        elif topic.endswith("/button/sleep/command"):
            set_power(False)
            self.display_power = False
            self._publish(_topic("", "display", "state"), "OFF")
        elif topic.endswith("/notify/command"):
            self._notifications.append(
                {"message": payload, "ts": time.time()}
            )

    def set_alarm(self, flag):
        cfg = config.get()
        cfg["alarm"]["enabled"] = bool(flag)
        config.save()
        self.alarm_enabled = bool(flag)
        self._publish(_topic("", "alarm", "state"), "ON" if flag else "OFF")
        alarm_time = self.next_alarm_iso()
        if alarm_time:
            self._publish(_topic("", "alarm", "time"), alarm_time)

    def start(self):
        if not self.enabled:
            self.connected = False
            return
        try:
            self._start_client()
        except Exception as exc:
            self.last_error = str(exc)

    def _start_client(self):
        if paho is None:
            self.last_error = "paho-mqtt is not installed"
            return
        self.stop()
        mqtt_cfg = config.get().get("mqtt") or {}
        client = paho.Client()
        try:
            client._sock_timeout = 5
        except AttributeError:
            pass
        if mqtt_cfg.get("username"):
            client.username_pw_set(mqtt_cfg["username"], mqtt_cfg.get("password") or "")
        client.will_set(_topic("", "status", ""), "offline", qos=1, retain=True)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        self._client = client
        client.connect(
            mqtt_cfg.get("host"),
            int(mqtt_cfg.get("port") or 1883),
            keepalive=30,
        )
        client.loop_start()

    def stop(self):
        client = self._client
        self._client = None
        self.connected = False
        if client:
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:
                pass

    def reload(self):
        with self._lock:
            self.stop()
            self.start()

    def notify_display_change(self, powered):
        self.display_power = bool(powered)
        if self.connected:
            self._publish(_topic("", "display", "state"), "ON" if powered else "OFF")

    def pop_notification(self):
        if self._notifications:
            return self._notifications.popleft()
        return None

    def status(self):
        return {
            "enabled": self.enabled,
            "connected": self.connected,
            "last_error": self.last_error,
            "host": config.get().get("mqtt", {}).get("host", ""),
            "uptime_s": round(time.time() - self._t0) if self._t0 else 0,
        }


mqtt_service = MqttService()