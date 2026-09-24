const Music = {
  isOpen: false,
  loaded: false,
  configured: false,
  shuffle: false,
  albums: [],
  pollTimer: null,
  lastState: null,

  init() {
    document.getElementById("btn-music").addEventListener("click", () => this.open(), true);
    document.getElementById("btn-music-close").addEventListener("click", () => this.close(), true);
    document.getElementById("btn-shuffle").addEventListener("click", () => this.toggleShuffle(), true);
    document.getElementById("mn-pause").addEventListener("click", () => {
      apiPost("/api/jellyfin/pause").then((r) => {
        this.lastState = r.state;
        this.updateNow();
      });
    }, true);
    document.getElementById("mn-stop").addEventListener("click", () => {
      apiPost("/api/jellyfin/stop").then(() => {
        document.getElementById("music-now").classList.add("hidden");
      });
    }, true);
    document.getElementById("mn-prev").addEventListener("click", () => {
      apiPost("/api/jellyfin/prev").then((r) => {
        this.lastState = r.state;
        this.updateNow();
      });
    }, true);
    document.getElementById("mn-next").addEventListener("click", () => {
      apiPost("/api/jellyfin/next").then((r) => {
        this.lastState = r.state;
        this.updateNow();
      });
    }, true);
    const seekEl = document.getElementById("mn-seek");
    seekEl.addEventListener("input", (e) => {
      this._scrubbing = true;
      document.getElementById("mn-pos").textContent = this.fmt(parseInt(e.target.value, 10) || 0);
    }, { passive: true });
    seekEl.addEventListener("change", (e) => {
      apiPost("/api/jellyfin/seek", { position: parseInt(e.target.value, 10) || 0 }).then((r) => {
        this._scrubbing = false;
        if (r && r.state) {
          this.lastState = r.state;
          this.updateNow();
        }
      });
    });
    document.getElementById("mn-vol").addEventListener("input", (e) => {
      const p = parseInt(e.target.value, 10);
      document.getElementById("mn-vol-r").textContent = p + "%";
      apiPost("/api/jellyfin/volume", { percent: p });
    }, { passive: true });
  },

  toggleShuffle() {
    this.shuffle = !this.shuffle;
    document.getElementById("btn-shuffle").classList.toggle("on", this.shuffle);
    toast(this.shuffle ? "Shuffle on — albums play in random order" : "Shuffle off");
  },

  async open() {
    this.isOpen = true;
    document.getElementById("screen-music").classList.add("active");
    App.captureIdle?.(true);
    await this.loadAlbums();
    this.renderAlbums();
    this.startPoll();
  },

  close() {
    this.isOpen = false;
    document.getElementById("screen-music").classList.remove("active");
    const a = document.activeElement;
    if (a && a.blur) a.blur();
    App.captureIdle?.(false);
    this.stopPoll();
  },

  async loadAlbums() {
    const empty = document.getElementById("music-empty");
    const DEFAULT_EMPTY = "Jellyfin isn't set up yet — open Settings → Music to add your server.";
    empty.classList.remove("hidden");
    empty.textContent = "Loading…";
    try {
      const res = await apiGet("/api/jellyfin/browse");
      this.configured = !!res.enabled;
      this.albums = res.albums || [];
      this.loaded = true;
      if (this.configured) {
        empty.classList.add("hidden");
      } else {
        empty.textContent = DEFAULT_EMPTY;
      }
      if (res.error && !res.albums.length) toast(res.error);
    } catch (err) {
      this.configured = false;
      this.albums = [];
      this.loaded = true;
      empty.textContent = DEFAULT_EMPTY;
    }
  },

  renderAlbums() {
    const view = document.getElementById("music-view");
    const empty = document.getElementById("music-empty");
    const now = document.getElementById("music-now");
    if (!this.configured || !this.albums.length) {
      view.innerHTML = "";
      now.classList.add("hidden");
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");
    view.innerHTML = "";
    const grid = document.createElement("div");
    grid.className = "album-grid";
    this.albums.forEach((album) => {
      const card = document.createElement("div");
      card.className = "album-card";
      const art = `<img src="/api/jellyfin/image/${encodeURIComponent(album.id)}?w=256" alt="" onerror="this.style.visibility='hidden'">`;
      card.innerHTML =
        art +
        '<div class="ac-name">' + this.esc(album.name) + "</div>" +
        '<div class="ac-artist">' + this.esc(album.artist || "") + "</div>";
      card.addEventListener("click", () => this.showTracks(album), { passive: true });
      grid.appendChild(card);
    });
    view.appendChild(grid);
  },

  showTracks(album) {
    const view = document.getElementById("music-view");
    view.innerHTML = "";
    const head = document.createElement("div");
    head.className = "music-subhead";
    head.innerHTML = '<button class="btn" id="mn-back">‹ Back</button><h3>' + this.esc(album.name) + "</h3>";
    view.appendChild(head);
    document.getElementById("mn-back").addEventListener("click", () => this.renderAlbums(), true);

    const list = document.createElement("div");
    list.className = "track-list";
    album.tracks.forEach((t, i) => {
      const row = document.createElement("div");
      row.className = "track-row";
      row.dataset.tid = t.id;
      row.dataset.i = i;
      row.innerHTML =
        '<span class="tr-num">' + (i + 1) + "</span>" +
        '<div class="tr-name"><b>' + this.esc(t.name) + "</b>" +
        '<span>' + this.esc(t.artist || album.artist || "") + "</span></div>" +
        '<span class="tr-dur">' + this.fmt(t.seconds) + "</span>";
      row.addEventListener("click", () => this.playAlbum(album, i), { passive: true });
      list.appendChild(row);
    });
    view.appendChild(list);
    if (this.lastState && this.lastState.track) this.markPlayingId(this.lastState.track.id);
  },

  async playAlbum(album, index) {
    const r = await apiPost("/api/jellyfin/play", { album_id: album.key || album.id, index, shuffle: this.shuffle });
    if (r && !r.ok) {
      toast((r && r.error) || "Play failed");
      return;
    }
    this.lastState = r.state;
    this.updateNow();
    this.markPlayingId(r.state.track && r.state.track.id);
    if (r.state && r.state.last_error) toast("Playback issue: " + r.state.last_error);
  },

  markPlayingId(trackId) {
    if (!trackId) return;
    document.querySelectorAll(".track-row").forEach((el) => {
      el.classList.toggle("playing", String(el.dataset.tid) === String(trackId));
    });
  },

  startPoll() {
    this.stopPoll();
    this.pollTimer = setInterval(() => this.poll(), 3000);
    this.poll();
  },

  stopPoll() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  },

  async poll() {
    try {
      const st = await apiGet("/api/jellyfin/now");
      if (st.last_error && st.last_error !== this._notifiedErr) {
        this._notifiedErr = st.last_error;
        toast("Playback issue: " + st.last_error);
      }
      this.lastState = st;
      if (st.track && (st.playing || st.paused)) {
        if (st.track.id !== this._lastTrackId) {
          this._lastTrackId = st.track.id;
          this._scrubbing = false;
        }
        this.updateNow();
        this.markPlayingId(st.track.id);
      } else {
        this._lastTrackId = null;
        this._scrubbing = false;
        document.getElementById("music-now").classList.add("hidden");
      }
    } catch (e) { /* ignore */ }
  },

  updateNow() {
    const now = document.getElementById("music-now");
    const st = this.lastState;
    if (!st || !st.track) {
      now.classList.add("hidden");
      return;
    }
    now.classList.remove("hidden");
    document.getElementById("mn-title").textContent = st.track.name || "—";
    document.getElementById("mn-sub").textContent =
      [st.track.artist, st.track.album].filter(Boolean).join(" · ") || "—";
    const art = document.getElementById("mn-art");
    if (st.track.album_id) {
      art.src = "/api/jellyfin/image/" + encodeURIComponent(st.track.album_id) + "?w=128";
    } else {
      art.removeAttribute("src");
    }
    const vol = st.volume != null ? st.volume : 80;
    document.getElementById("mn-vol").value = vol;
    document.getElementById("mn-vol-r").textContent = vol + "%";
    document.getElementById("mn-pause").textContent = st.paused ? "▶" : "⏸";
    const seekEl = document.getElementById("mn-seek");
    const dur = st.track.seconds || 0;
    const pos = Math.min(st.position || 0, dur || (st.position || 0));
    const max = dur || 1;
    if (seekEl.max !== String(max)) seekEl.max = max;
    if (this._scrubbing) {
      document.getElementById("mn-dur").textContent = this.fmt(dur);
    } else {
      seekEl.value = String(Math.min(pos, max));
      document.getElementById("mn-pos").textContent = this.fmt(pos);
      document.getElementById("mn-dur").textContent = this.fmt(dur);
    }
  },

  fmt(sec) {
    if (!sec) return "--:--";
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return m + ":" + String(s).padStart(2, "0");
  },

  esc(s) {
    const div = document.createElement("div");
    div.textContent = String(s == null ? "" : s);
    return div.innerHTML;
  },
};