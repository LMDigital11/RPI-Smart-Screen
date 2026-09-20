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
            "media": "smart_screen_media_{}".format(did),
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
            (PREFIX + "/media_player", ids["media"]): {
                "name": "Smart Screen",
                "unique_id": ids["media"],
                "command_topic": _topic("", "media", "command"),
                "support_play": ["play", "stop"],
                "icon": "mdi:speaker",
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
        alarm_cfg = config.get().get("alarm") or {}
        self.alarm_enabled = bool(alarm_cfg.get("enabled"))
        self._publish(_topic("", "alarm", "state"), on_off(self.alarm_enabled))
        self._publish(_topic("", "alarm", "time"), self.next_alarm_iso())
        self._publish(_topic("", "status", ""), "online")

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
                return candidate.isoformat()
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
        client.subscribe([(_topic("", "alarm", "set"), 0)])
        client.subscribe([(_topic("", "media", "command"), 0)])
        client.subscribe([(_topic("", "notify", "command"), 0)])
        client.subscribe([(_topic("", ids["notify"], "command"), 0)])

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False

    def _on_message(self, client, userdata, msg):
        topic = (msg.topic or "")
        payload = (msg.payload or b"").decode("utf-8", "replace").strip()
        from display import set_power
        from audio import alarm_scheduler, play, stop

        if topic.endswith("/display/set"):
            set_power(payload == "ON")
            self.display_power = payload == "ON"
            self._publish(_topic("", "display", "state"), "ON" if payload == "ON" else "OFF")
        elif topic.endswith("/alarm/set"):
            self.set_alarm(payload == "ON")
        elif topic.endswith("/media/command"):
            command = (payload or "").upper()
            if command in ("PLAY", "START"):
                play("default", 80)
            elif command in ("STOP", "PAUSE", "OFF"):
                stop()
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
        self._publish(_topic("", "alarm", "time"), self.next_alarm_iso())

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