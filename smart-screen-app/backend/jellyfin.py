import functools
from urllib.parse import quote

import requests

from config import config, DEVICE_ID

TIMEOUT = 12
CLIENT = (
    'MediaBrowser Client="Smart Screen", Device="Raspberry Pi 4", '
    'DeviceId="{}{}", Version="1.0.0"'
)


def _auth_header():
    return CLIENT.format("smart-screen-", DEVICE_ID)


def _join_names(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


class Jellyfin:
    def __init__(self):
        self._token = ""
        self._user_id = ""
        self._user_name = ""
        self._auth_error = ""

    @property
    def enabled(self):
        c = config.get().get("jellyfin") or {}
        return bool(
            c.get("server_url")
            and (c.get("api_key") or (c.get("username") and c.get("password")))
        )

    @property
    def authenticated(self):
        return bool(self._token and self._user_id)

    def base(self):
        return (config.get().get("jellyfin") or {}).get("server_url", "").rstrip("/")

    def _headers(self):
        headers = {"Accept": "application/json"}
        if self._token:
            headers["X-Emby-Token"] = self._token
        return headers

    def login(self):
        c = config.get().get("jellyfin") or {}
        base = (c.get("server_url") or "").rstrip("/")
        if not base:
            self._auth_error = "No server URL configured"
            return False
        try:
            if c.get("api_key"):
                self._token = c["api_key"]
                users = self._get_json(base + "/Users")
                match = None
                if c.get("username"):
                    wanted = c["username"].lower()
                    match = next(
                        (u for u in users if (u.get("Name") or "").lower() == wanted),
                        None,
                    )
                user = match or (users[0] if users else None)
                if user and user.get("Id"):
                    self._user_id = user["Id"]
                    self._user_name = user.get("Name", "")
                    self._auth_error = ""
                    return True
                self._auth_error = "API key worked but no users are visible"
                return False

            resp = requests.post(
                base + "/Users/AuthenticateByName",
                headers={"Accept": "application/json", "X-Emby-Authorization": _auth_header()},
                json={"Username": c.get("username", ""), "Pw": c.get("password", "")},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data.get("AccessToken") or data.get("Token") or ""
            user = data.get("User") or {}
            self._user_id = user.get("Id", "")
            self._user_name = user.get("Name", "") or c.get("username", "")
            if self._token and self._user_id:
                self._auth_error = ""
                return True
            self._auth_error = "Authentication succeeded but returned no token"
            return False
        except requests.RequestException as exc:
            self._auth_error = "{}".format(exc)
            return False
        except (ValueError, KeyError) as exc:
            self._auth_error = "{}".format(exc)
            return False

    def _get_json(self, url):
        resp = requests.get(url, headers=self._headers(), timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def browse(self):
        if not self.enabled:
            return {"enabled": False, "albums": []}
        if not self.login():
            return {
                "enabled": True,
                "error": self._auth_error,
                "albums": [],
                "user": "",
            }
        uid = self._user_id
        items = self._query_items(
            "/Users/{}/Items".format(uid),
            {
                "IncludeItemTypes": "Audio",
                "Recursive": "true",
                "SortBy": "SortName",
                "SortOrder": "Ascending",
                "Fields": "Album,Artists,RunTimeTicks",
            },
        )
        tracks = (items or {}).get("Items") or []
        albums = {}
        for t in tracks:
            artist = _join_names(t.get("Artists"))
            key = t.get("AlbumId") or ("~" + (t.get("Album") or "Unknown album"))
            album = albums.setdefault(
                key,
                {
                    "id": t.get("AlbumId") or "",
                    "key": key,
                    "name": t.get("Album") or "Unknown album",
                    "artist": artist,
                    "tracks": [],
                },
            )
            album["tracks"].append(
                {
                    "id": t.get("Id"),
                    "name": t.get("Name"),
                    "artist": artist,
                    "album": album["name"],
                    "album_id": key if t.get("AlbumId") else "",
                    "seconds": round((t.get("RunTimeTicks") or 0) / 10000000),
                }
            )
        return {
            "enabled": True,
            "albums": [albums[k] for k in albums],
            "user": self._user_name,
        }

    def _query_items(self, path, params):
        try:
            resp = requests.get(
                self.base() + path,
                headers=self._headers(),
                params=params,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return {"Items": []}

    def search(self, term):
        if not term or not self.enabled or not self.login():
            return []
        data = self._query_items(
            "/Users/{}/Items".format(self._user_id),
            {
                "IncludeItemTypes": "Audio,MusicAlbum",
                "Recursive": "true",
                "SearchTerm": term,
                "Fields": "Album,Artists",
            },
        )
        return (data or {}).get("Items") or []

    def stream_url(self, item_id):
        return "{}/Audio/{}/stream?static=true&api_key={}".format(
            self.base(), item_id, quote(self._token)
        )

    @functools.lru_cache(maxsize=256)
    def image_bytes(self, item_id, width=256, height=256):
        if not self.enabled or not self.login():
            return None, None
        try:
            resp = requests.get(
                "{}/Items/{}/Images/Primary".format(self.base(), item_id),
                headers=self._headers(),
                params={"fillWidth": width, "fillHeight": height, "quality": 92},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            return resp.content, resp.headers.get("Content-Type", "image/jpeg")
        except requests.RequestException:
            return None, None

    def status(self):
        base = self.base()
        public = {}
        if base:
            try:
                public = requests.get(
                    base + "/System/Info/Public", timeout=5
                ).json()
            except requests.RequestException:
                public = {}
        if self.enabled and not self.authenticated:
            self.login()
        return {
            "enabled": self.enabled,
            "server_url": base,
            "server_name": public.get("ServerName", ""),
            "version": public.get("Version", ""),
            "authenticated": self.authenticated,
            "user": self._user_name,
            "error": self._auth_error if not self.authenticated else "",
        }


jellyfin = Jellyfin()