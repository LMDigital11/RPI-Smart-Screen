import requests

from config import config, DEVICE_ID

API_TIMEOUT = 10


class HomeAssistant:
    @property
    def configured(self):
        c = config.get()["home_assistant"]
        return bool(c["server_url"] and c["token"])

    def _base_headers(self):
        return {
            "Authorization": "Bearer " + config.get()["home_assistant"]["token"],
            "Content-Type": "application/json",
        }

    def states(self):
        if not self.configured:
            return []
        base = config.get()["home_assistant"]["server_url"].rstrip("/")
        try:
            resp = requests.get(
                base + "/api/states", headers=self._base_headers(), timeout=API_TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return []

    def call_service(self, domain, service, entity_id=None, data=None):
        if not self.configured:
            return False
        base = config.get()["home_assistant"]["server_url"].rstrip("/")
        payload = dict(data or {})
        if entity_id:
            payload["entity_id"] = entity_id
        try:
            resp = requests.post(
                base + "/api/services/{}/{}".format(domain, service),
                headers=self._base_headers(),
                json=payload,
                timeout=API_TIMEOUT,
            )
            resp.raise_for_status()
            return True
        except requests.RequestException:
            return False

    def process_entities(self):
        states = self.states()
        output = []
        for state in states:
            entity_id = state.get("entity_id", "")
            domain = entity_id.split(".")[0] if "." in entity_id else ""
            if domain not in {
                "light",
                "switch",
                "fan",
                "cover",
                "media_player",
                "climate",
                "scene",
            }:
                continue
            attrs = state.get("attributes", {})
            output.append(
                {
                    "entity_id": entity_id,
                    "name": attrs.get("friendly_name", entity_id),
                    "domain": domain,
                    "state": state.get("state"),
                    "brightness_pct": _brightness_pct(state.get("state"), attrs),
                    "temperature": attrs.get("temperature"),
                    "current_temperature": attrs.get("current_temperature"),
                    "fan_modes": attrs.get("fan_modes", []),
                    "status": attrs.get("status"),
                }
            )
        return _order(output)


def _brightness_pct(state, attrs):
    brightness = attrs.get("brightness")
    if state != "on" or brightness is None:
        return None
    return round(int(brightness) / 255 * 100)


def _order(entities):
    priority = {"scene": 1, "light": 2, "switch": 3, "media_player": 4, "fan": 5}
    return sorted(entities, key=lambda e: (priority.get(e["domain"], 9), e["name"]))


home_assistant = HomeAssistant()


def embed_dashboard_url():
    c = config.get()["home_assistant"]
    if not (c["server_url"] and c["token"]):
        return None
    base = c["server_url"].rstrip("/")
    path = (c.get("dashboard_path") or "/lovelace/").lstrip("/").rstrip("/")
    return "{}/{}/?auth_callback=1&token={}".format(base, path, c["token"])


def embed_add_device_url():
    c = config.get()["home_assistant"]
    if not (c["server_url"] and c["token"]):
        return None
    base = c["server_url"].rstrip("/")
    return "{}/config/integrations/add?auth_callback=1&token={}".format(base, c["token"])


def embed_url():
    return embed_dashboard_url()


def device_registered():
    try:
        states = home_assistant.states()
        return any(
            (s.get("entity_id") or "").split(".")[-1].startswith("smart_screen")
            for s in states
        )
    except Exception:
        return False