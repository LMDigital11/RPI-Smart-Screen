import threading
import time

import requests

from config import config

API_TIMEOUT = 20


class ImmichClient:
    def __init__(self):
        self._photos = []
        self._cache_time = 0.0
        self._lock = threading.Lock()

    @property
    def enabled(self):
        c = config.get()["immich"]
        return bool(c["server_url"] and c["api_key"])

    def _headers(self):
        return {"x-api-key": config.get()["immich"]["api_key"]}

    def refresh(self, force=False):
        if not self.enabled:
            return []
        c = config.get()["immich"]
        now = time.time()
        interval = max(1, int(c["refresh_minutes"])) * 60
        with self._lock:
            if not force and now - self._cache_time < interval and self._photos:
                return self._photos
            try:
                base = c["server_url"].rstrip("/")
                resp = requests.post(
                    base + "/api/search/metadata",
                    headers=self._headers(),
                    json={
                        "page": 1,
                        "size": 200,
                        "order": "desc",
                        "withExif": True,
                    },
                    timeout=API_TIMEOUT,
                )
                resp.raise_for_status()
                items = resp.json().get("assets", {}).get("items", [])
                self._photos = [
                    item["id"] for item in items if item.get("type") == "IMAGE"
                ]
            except requests.RequestException:
                pass
            self._cache_time = now
            return self._photos

    def photo_url(self, photo_id, kind="thumb"):
        base = config.get()["immich"]["server_url"].rstrip("/")
        if kind == "thumb":
            return "/api/proxy/immich/{}".format(photo_id)
        return "/api/proxy/immich/{}?kind=original".format(photo_id)

    def fetch(self, photo_id, kind="thumb"):
        base = config.get()["immich"]["server_url"].rstrip("/")
        if kind == "thumb":
            resp = requests.get(
                base + "/api/assets/" + photo_id + "/thumbnail",
                headers=self._headers(),
                params={"size": "preview"},
                timeout=API_TIMEOUT,
            )
        else:
            resp = requests.get(
                base + "/api/assets/" + photo_id + "/original",
                headers=self._headers(),
                timeout=API_TIMEOUT,
            )
        resp.raise_for_status()
        return resp.content, resp.headers.get("Content-Type", "image/jpeg")


immich = ImmichClient()