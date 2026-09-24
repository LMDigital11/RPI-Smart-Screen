import os
import signal
import subprocess
import tempfile
import threading
import time

from config import config
from audio import bluetooth_status_service


class Player:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._proc = None
        self._stop = threading.Event()
        self.playlist = []
        self.index = -1
        self.current = None
        self.playing = False
        self.paused = False
        self.volume = 80
        self.last_error = ""

    def set_volume(self, percent):
        with self._lock:
            self.volume = max(0, min(100, int(percent)))
        bluetooth_status_service.set_volume(self.volume)
        self._publish()

    def play(self, tracks, start_index=0):
        if not tracks:
            return
        self._stop_current()
        with self._lock:
            self.playlist = [dict(t) for t in tracks]
            self.index = max(0, start_index)
            self.current = None
            self.playing = True
            self.paused = False
            self.volume = int(config.get().get("jellyfin", {}).get("volume", 80))
        bluetooth_status_service.set_volume(self.volume)
        self._publish()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self):
        with self._lock:
            if not self.playing and not self.paused:
                return
            self.paused = True
            self.playing = False
        self._kill_proc()
        self._publish()

    def resume(self):
        with self._lock:
            if not self.playlist:
                return
            if self.playing and not self.paused:
                return
            self.paused = False
            self.playing = True
            if self.index < 0:
                self.index = 0
            self.volume = int(config.get().get("jellyfin", {}).get("volume", 80))
        bluetooth_status_service.set_volume(self.volume)
        self._publish()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_current()
        with self._lock:
            self.playing = False
            self.paused = False
            self.current = None
        self._publish()

    def _stop_current(self):
        self._stop.set()
        self._kill_proc()
        if self._thread:
            self._thread.join(timeout=2)
        self._stop = threading.Event()

    def _kill_proc(self):
        proc = self._proc
        self._proc = None
        if not proc:
            return
        try:
            proc.send_signal(signal.SIGTERM)
        except Exception:
            pass
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
        except Exception:
            pass

    def _run(self):
        try:
            from jellyfin import jellyfin
        except ImportError:
            return
        while True:
            with self._lock:
                if self._stop.is_set() or self.paused:
                    return
                if self.index < 0 or self.index >= len(self.playlist):
                    self.playing = False
                    self.current = None
                    self._publish()
                    return
                track = self.playlist[self.index]
                self.current = track
            self._publish()
            url = jellyfin.stream_url(track["id"])
            device = bluetooth_status_service.output_alsa_device()
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-i",
                url,
                "-f",
                "alsa",
                device,
            ]
            attempts = 0
            while True:
                with self._lock:
                    if self._stop.is_set() or self.paused:
                        return
                try:
                    self.last_error = ""
                    log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False)
                    t0 = time.time()
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=log,
                        start_new_session=True,
                    )
                    self._proc = proc
                    rc = proc.wait()
                    elapsed = time.time() - t0
                    log.seek(0)
                    err = log.read().strip()[:400]
                    log.close()
                    try:
                        os.remove(log.name)
                    except OSError:
                        pass
                except Exception:
                    return
                with self._lock:
                    if self._stop.is_set() or self.paused:
                        return
                    if rc != 0 and elapsed < 8 and attempts < 3:
                        attempts += 1
                        self.last_error = err or "ffmpeg exited ({})".format(rc)
                        time.sleep(0.6)
                        continue
                    if rc != 0:
                        self.last_error = err or "ffmpeg exited ({})".format(rc)
                    break
            self._publish()
            with self._lock:
                if self._stop.is_set() or self.paused:
                    return
                self.index += 1
                if self.index >= len(self.playlist):
                    self.playing = False
                    self.current = None
                    self._publish()
                    return

    def state(self):
        with self._lock:
            return {
                "playing": self.playing and not self.paused,
                "paused": self.paused,
                "track": self.current,
                "index": self.index,
                "playlist_len": len(self.playlist),
                "volume": self.volume,
                "source": "Jellyfin" if (self.playing or self.paused) else "Idle",
                "last_error": self.last_error or "",
            }

    def _publish(self):
        try:
            from mqtt import mqtt_service

            mqtt_service.publish_media_state(self.state())
        except Exception:
            pass


player = Player()