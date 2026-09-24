import os
import random

import flask

from config import config
import wifi
import display
import weather as weather_service
import usb_photos
import schedule
from immich import immich
from homeassistant import home_assistant, embed_url, embed_add_device_url, device_registered
from mqtt import mqtt_service
from jellyfin import jellyfin
from player import player
from audio import (
    alarm_scheduler,
    bluetooth_status_service,
    play,
    stop,
    set_volume,
    force_aux_output,
)
import updater

app = flask.Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "..", "frontend"),
    static_url_path="",
)

alarm_scheduler.start()
mqtt_service.start()

try:
    display.set_brightness(config.get()["display"].get("brightness", 100))
except Exception:
    pass


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def index():
    return flask.send_from_directory(app.static_folder, "index.html")


@app.get("/api/status")
def api_status():
    cfg = config.get()
    return {
        "setup_complete": cfg["setup_complete"],
        "device_name": cfg["device_name"],
        "immich_configured": immich.enabled,
        "home_assistant_configured": home_assistant.configured,
        "weather_configured": cfg["weather"]["latitude"] is not None,
    }


@app.get("/api/config")
def api_get_config():
    return config.get()


@app.post("/api/config")
def api_update_config():
    patch = flask.request.get_json(silent=True) or {}
    config.update(patch)
    mqtt_service.reload()
    return config.get()


@app.post("/api/config/setup-complete")
def api_setup_complete():
    config.mark_setup_complete()
    return {"ok": True}


@app.get("/api/immich/photos")
def api_immich_photos():
    photos = immich.refresh()
    return {"photos": [immich.photo_url(pid) for pid in photos], "count": len(photos)}


@app.post("/api/immich/refresh")
def api_immich_refresh():
    photos = immich.refresh(force=True)
    return {"photos": [immich.photo_url(pid) for pid in photos], "count": len(photos)}


@app.get("/api/proxy/immich/<photo_id>")
def api_immich_photo(photo_id):
    try:
        content, content_type = immich.fetch(photo_id)
        return flask.Response(content, content_type=content_type)
    except Exception:
        return flask.Response("photo unavailable", status=503)


@app.get("/api/weather")
def api_weather():
    return weather_service.weather.get()


@app.get("/api/slideshow/photos")
def api_slideshow_photos():
    cfg = config.get()["slideshow"]
    source = cfg["source"]
    photos = []
    if source in ("auto", "immich"):
        photos = [immich.photo_url(pid) for pid in immich.refresh()]
    if (source in ("auto", "usb") and not photos) or source == "usb":
        files = usb_photos.list_photos(cfg.get("usb_drive"))
        photos = [
            "/api/photos/file?path={}".format(flask.quote(p, safe="")) for p in files
        ]
    if cfg.get("shuffle"):
        random.shuffle(photos)
    return {
        "photos": photos,
        "photo_duration_sec": cfg["photo_duration_sec"],
        "weather_every_n_photos": cfg["weather_every_n_photos"],
    }


@app.get("/api/drives")
def api_drives():
    return {"drives": usb_photos.list_drives()}


@app.post("/api/drives/mount")
def api_mount():
    name = (flask.request.get_json(silent=True) or {}).get("name")
    if not name:
        return {"ok": False}
    usb_photos.mount(name)
    return {"ok": True, "mountpoint": usb_photos.current_mountpoint(name)}


@app.get("/api/photos/file")
def api_photo_file():
    path = flask.request.args.get("path")
    if not path or ".." in path:
        return flask.abort(404)
    if os.path.isfile(path):
        return flask.send_file(path)
    return flask.abort(404)


@app.get("/api/ha/states")
def api_ha_states():
    return home_assistant.process_entities()


@app.post("/api/ha/service")
def api_ha_service():
    data = flask.request.get_json(silent=True) or {}
    ok = home_assistant.call_service(
        data.get("domain"),
        data.get("service"),
        entity_id=data.get("entity_id"),
        data=data.get("data"),
    )
    return {"ok": ok}


@app.get("/api/ha/embed")
def api_ha_embed():
    return {
        "url": embed_url(),
        "add_device_url": embed_add_device_url(),
        "registered": device_registered(),
        "configured": home_assistant.configured,
    }


@app.get("/api/wifi/scan")
def api_wifi_scan():
    return {"networks": wifi.scan()}


@app.get("/api/wifi/status")
def api_wifi_status():
    return wifi.status()


@app.post("/api/wifi/connect")
def api_wifi_connect():
    data = flask.request.get_json(silent=True) or {}
    ok = wifi.connect(data.get("ssid"), data.get("password"))
    return {"ok": ok}


@app.get("/api/display/status")
def api_display_status():
    return display.status()


@app.get("/api/schedule/now")
def api_schedule_now():
    return schedule.today()


@app.post("/api/display/power")
def api_display_power():
    data = flask.request.get_json(silent=True) or {}
    powered = bool(data.get("powered"))
    display.set_power(powered)
    mqtt_service.notify_display_change(powered)
    return {"ok": True}


@app.post("/api/display/brightness")
def api_display_brightness():
    data = flask.request.get_json(silent=True) or {}
    percent = display.set_brightness(int(data.get("percent", 100)))
    config.update({"display": {"brightness": percent}})
    return {"ok": True, "percent": percent}


@app.get("/api/mqtt/status")
def api_mqtt_status():
    return mqtt_service.status()


@app.post("/api/mqtt/reload")
def api_mqtt_reload():
    mqtt_service.reload()
    return mqtt_service.status()


@app.get("/api/notifications/latest")
def api_notifications_latest():
    notification = mqtt_service.pop_notification()
    if notification:
        return notification
    return {}


@app.post("/api/audio/volume")
def api_audio_volume():
    data = flask.request.get_json(silent=True) or {}
    set_volume(int(data.get("percent", 80)))
    return {"ok": True}


@app.post("/api/audio/test")
def api_audio_test():
    up = flask.request.get_json(silent=True) or {}
    if up.get("stop"):
        stop()
        return {"ok": True}
    play("default", 80)
    return {"ok": True}


@app.get("/api/bluetooth/status")
def api_bluetooth():
    return bluetooth_status_service.status()


@app.post("/api/bluetooth/discoverable")
def api_bluetooth_discoverable():
    data = flask.request.get_json(silent=True) or {}
    bluetooth_status_service.set_discoverable(bool(data.get("on", True)))
    return bluetooth_status_service.status()


@app.get("/api/jellyfin/status")
def api_jellyfin_status():
    return jellyfin.status()


@app.get("/api/jellyfin/browse")
def api_jellyfin_browse():
    return jellyfin.browse()


@app.get("/api/jellyfin/search")
def api_jellyfin_search():
    return {"items": jellyfin.search(flask.request.args.get("q", ""))}


@app.get("/api/jellyfin/image/<item_id>")
def api_jellyfin_image(item_id):
    try:
        content, content_type = jellyfin.image_bytes(item_id)
    except Exception:
        content, content_type = None, None
    if not content:
        return flask.Response("", status=404)
    return flask.Response(content, content_type=content_type or "image/jpeg")


@app.post("/api/jellyfin/play")
def api_jellyfin_play():
    data = flask.request.get_json(silent=True) or {}
    result = jellyfin.browse()
    if not result.get("enabled"):
        return {"ok": False, "error": result.get("error") or "Jellyfin not configured"}
    albums = result.get("albums") or []
    tracks = []
    start = 0
    album_id = data.get("album_id")
    track_id = data.get("track_id")
    index = int(data.get("index", 0) or 0)
    shuffle = bool(data.get("shuffle"))
    if album_id is not None:
        album = next(
            (
                a
                for a in albums
                if str(a.get("key")) == str(album_id) or str(a.get("id")) == str(album_id)
            ),
            None,
        )
        if album:
            tracks = album["tracks"]
            start = max(0, index)
            if shuffle:
                order = list(range(len(tracks)))
                if start < len(order):
                    first = order.pop(start)
                    random.shuffle(order)
                    order = [first] + order
                else:
                    random.shuffle(order)
                tracks = [tracks[i] for i in order]
                start = 0
    elif track_id:
        track = None
        for album in albums:
            t = next(
                (t for t in album["tracks"] if str(t.get("id")) == str(track_id)),
                None,
            )
            if t:
                track = t
                track["album"] = album["name"]
                break
        if track:
            tracks = [track]
    if not tracks:
        return {"ok": False, "error": "Nothing to play"}
    player.play(tracks, start)
    return {"ok": True, "state": player.state()}


@app.post("/api/jellyfin/stop")
def api_jellyfin_stop():
    player.stop()
    return {"ok": True, "state": player.state()}


@app.post("/api/jellyfin/pause")
def api_jellyfin_pause():
    state = player.state()
    if state["playing"]:
        player.pause()
    elif state["paused"]:
        player.resume()
    return {"ok": True, "state": player.state()}


@app.post("/api/jellyfin/volume")
def api_jellyfin_volume():
    data = flask.request.get_json(silent=True) or {}
    percent = int(data.get("percent", 80))
    player.set_volume(percent)
    config.update({"jellyfin": {"volume": player.volume}})
    return {"ok": True, "state": player.state()}


@app.get("/api/jellyfin/now")
def api_jellyfin_now():
    return player.state()


@app.post("/api/alarm/test")
def api_alarm_test():
    play("default", 80)
    return {"ok": True}


@app.get("/api/update/status")
def api_update_status():
    return updater.status()


@app.post("/api/update/check")
def api_update_check():
    return updater.check()


@app.post("/api/update/apply")
def api_update_apply():
    return updater.apply()


if __name__ == "__main__":
    force_aux_output()
    bluetooth_status_service.power_on()
    try:
        bluetooth_status_service.set_discoverable(
            config.get()["bluetooth"].get("discoverable", True)
        )
    except Exception:
        pass
    app.run(host="127.0.0.1", port=8080, debug=False, threaded=True)