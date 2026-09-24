const Settings = {
  cfg: null,
  activeSection: null,
  isOpen: false,
  usbDrives: [],

  sections() {
    const s = this.cfg;
    return [
      {
        id: "general",
        label: "General",
        render: () => [
          this.textField("device_name", "Device name", s.device_name),
          this.button("Re-run first boot setup", "danger", "rerun"),
        ],
      },
      {
        id: "photos",
        label: "Photos",
        render: () => [
          this.selectField("slideshow.source", "Photo source", s.slideshow.source, [
            ["auto", "Auto (Immich first, USB fallback)"],
            ["immich", "Immich only"],
            ["usb", "USB stick only"],
          ]),
          this.selectField("slideshow.usb_drive", "USB stick", s.slideshow.usb_drive, [
            ["", "None"],
          ].concat(this.usbDrives.map((d) => [d.device, d.label + " (" + d.size + ")"])),
            "Plug in a USB stick, pick it here, and the slideshow shows every photo on it."),
          this.textField("immich.server_url", "Immich server", s.immich.server_url, "e.g. http://192.168.1.20:2283"),
          this.passwordField("immich.api_key", "Immich API key", s.immich.api_key),
          this.numberField("immich.refresh_minutes", "Check for new photos every (minutes)", s.immich.refresh_minutes),
          this.numberField("slideshow.photo_duration_sec", "Photo duration (seconds)", s.slideshow.photo_duration_sec),
          this.numberField("slideshow.weather_every_n_photos", "Weather card every N photos", s.slideshow.weather_every_n_photos),
          this.toggleField("slideshow.shuffle", "Shuffle photos", s.slideshow.shuffle),
          this.button("Refresh photos now", "primary block", "refresh"),
        ],
      },
      {
        id: "weather",
        label: "Weather",
        render: () => [
          this.textField("weather.latitude", "Latitude", s.weather.latitude, "e.g. 51.5072"),
          this.textField("weather.longitude", "Longitude", s.weather.longitude, "e.g. -0.1276"),
          this.selectField("weather.unit", "Unit", s.weather.unit, [
            ["celsius", "Celsius"],
            ["fahrenheit", "Fahrenheit"],
          ]),
          this.button("Test weather", "primary block", "test_weather"),
        ],
      },
      {
        id: "home-assistant",
        label: "Home Assistant",
        render: () => [
          this.textField("home_assistant.server_url", "Home Assistant URL", s.home_assistant.server_url, "e.g. http://homeassistant.local:8123"),
          this.passwordField("home_assistant.token", "Long-lived access token", s.home_assistant.token),
          this.textField("home_assistant.dashboard_path", "Dashboard path", s.home_assistant.dashboard_path, "leave empty for the default dashboard, or e.g. 'lovelace/kitchen'"),
          this.button("Test Home Assistant", "primary block", "test_ha"),
        ],
      },
      {
        id: "ha-device",
        label: "HA device",
        render: () => [
          this.note("Register this screen with Home Assistant so it shows up as its own device, controllable from your dashboards. It needs an MQTT broker running on your HA server (Settings → Devices & Services → MQTT)."),
          this.toggleField("mqtt.enabled", "Registered as an HA device", (s.mqtt || {}).enabled),
          this.textField("mqtt.host", "MQTT broker host", (s.mqtt || {}).host, "The IP/hostname of your Home Assistant server, e.g. 192.168.1.10"),
          this.numberField("mqtt.port", "MQTT port", (s.mqtt || {}).port, { max: 65535 }),
          this.textField("mqtt.username", "MQTT username", (s.mqtt || {}).username, "e.g. the username you set in HA's Mosquitto broker"),
          this.passwordField("mqtt.password", "MQTT password", (s.mqtt || {}).password),
          this.button("Register / check with Home Assistant", "primary block", "mqtt_reg"),
          '<div id="mqtt-status" class="test-result"></div>',
          this.button("Add devices to Home Assistant", "block", "ha_add_device"),
        ],
      },
      {
        id: "sleep",
        label: "Sleep & display",
        render: () => [
          this.toggleField("sleep.enabled", "Auto sleep (idle)", s.sleep.enabled, "Turns the screen off after the inactivity timer below."),
          this.numberField("sleep.idle_seconds", "Screen off after idle (seconds)", s.sleep.idle_seconds),
          this.numberField("sleep.wake_seconds", "Stay awake after touch (seconds)", s.sleep.wake_seconds),
          this.sliderField("display.brightness", "Screen brightness", (s.display || {}).brightness ?? 100),
          this.toggleField("schedule.enabled", "Scheduled screen-off", (s.schedule || {}).enabled, "Keeps the screen off at set times each day, e.g. Monday 12 AM – 3:30 PM."),
          this.scheduleEditorHtml(),
          this.button("Test: sleep now", "block", "sleep_now"),
        ],
      },
      {
        id: "alarm",
        label: "Alarm",
        render: () => [
          this.toggleField("alarm.enabled", "Alarm enabled", s.alarm.enabled),
          this.timeField("alarm.time", "Time", s.alarm.time),
          this.daysField("alarm.days", "Days", s.alarm.days),
          this.toggleField("alarm.light_ramp", "Wake with light", s.alarm.light_ramp, "Slowly brightens a smart bulb to wake you gradually."),
          this.textField("alarm.light_entity", "Light entity", s.alarm.light_entity, "e.g. light.bedroom_lamp"),
          this.numberField("alarm.ramp_minutes", "Light ramp duration (minutes)", s.alarm.ramp_minutes),
          this.button("Test alarm sound", "block", "test_alarm"),
        ],
      },
      {
        id: "audio",
        label: "Audio",
        render: () => [
          this.numberField("_volume", "Volume (%)", 80, { max: 100, key: "volume" }),
          this.button("Play test tone", "primary block", "test_tone"),
          this.button("Stop sound", "block", "stop_tone"),
          this.note("Sounds play through the audio jack (AUX). The system forces audio to the 3.5mm jack."),
        ],
      },
      {
        id: "bluetooth",
        label: "Bluetooth speaker",
        render: () => [
          this.toggleField("bluetooth_mode", "Connect to a Bluetooth speaker", (s.bluetooth || {}).mode === "connect", "Turn ON to stream the Pi's audio to an external Bluetooth speaker instead. This turns OFF the Pi being a speaker that phones pair with."),
          '<div id="bt-mode-body">' + ((s.bluetooth || {}).mode === "connect"
            ? [
                '<div id="bt-connect-status" class="test-result"></div>',
                this.button("Scan for Bluetooth speakers", "primary block", "bt_scan"),
                '<div id="bt-scan-list"></div>',
                this.button("Disconnect speaker", "block", "bt_disconnect"),
              ].join("")
            : [
                this.toggleField("bluetooth.discoverable", "Discoverable", s.bluetooth.discoverable),
                this.textField("bluetooth.speaker_name", "Speaker name", s.bluetooth.speaker_name),
                this.note("From your phone's Bluetooth menu, pair with this device — music then plays through the selected audio output."),
              ].join("")) + "</div>",
          this.button("Check status", "block", "bt_status"),
        ],
      },
      {
        id: "music",
        label: "Music",
        render: () => [
          this.note("Play music from a Jellyfin server through the audio jack. Enter your server and account, save, then open the Music button on the home screen to pick albums."),
          this.textField("jellyfin.server_url", "Jellyfin server", (s.jellyfin || {}).server_url, "e.g. http://192.168.1.93:8096"),
          this.textField("jellyfin.username", "Username", (s.jellyfin || {}).username),
          this.passwordField("jellyfin.password", "Password", (s.jellyfin || {}).password),
          this.passwordField("jellyfin.api_key", "API key (optional)", (s.jellyfin || {}).api_key, "Only if password login is disabled on the server."),
          this.numberField("jellyfin.volume", "Playback volume (%)", (s.jellyfin || {}).volume, { max: 100 }),
          this.button("Test music", "primary block", "test_music"),
          '<div id="music-status" class="test-result"></div>',
        ],
      },
      {
        id: "update",
        label: "Software update",
        render: () => [
          this.note("Updates come from a git repo you control. Commit and push new code, then check here — it pulls onto the device in place. Your settings (in /etc/smart-screen) are kept, only the app is replaced. Private repos: embed a token in the URL, e.g. https://TOKEN@github.com/you/the-repo."),
          this.textField("update.repo_url", "Git repo URL", (s.update || {}).repo_url, "e.g. https://github.com/you/the-smart-screen"),
          this.textField("update.branch", "Branch", (s.update || {}).branch, "defaults to main"),
          '<div id="update-status" class="test-result"></div>',
          this.button("Check for updates", "primary block", "update_check"),
          '<div id="update-actions"></div>',
        ],
      },
    ];
  },

  async open() {
    try {
      this.cfg = await loadConfig();
      this.usbDrives = (await apiGet("/api/drives").catch(() => ({}))).drives || [];
    } catch (err) {
      this.cfg = this.cfg || {
        device_name: "",
        setup_complete: true,
        wifi: {},
        immich: {},
        weather: {},
        slideshow: {},
        home_assistant: {},
        mqtt: {},
        sleep: {},
        schedule: { days: {} },
        alarm: {},
        bluetooth: {},
        update: {},
        display: {},
      };
    }
    this.isOpen = true;
    document.getElementById("screen-settings").classList.add("active");
    this.renderNav();
    this.openSection("general");
    App.captureIdle?.(true);
  },

  close() {
    document.getElementById("screen-settings").classList.remove("active");
    this.isOpen = false;
    const a = document.activeElement;
    if (a && a.blur) a.blur();
    App.captureIdle?.(false);
    App.refreshStatusDots();
  },

  renderNav() {
    const nav = document.getElementById("settings-nav");
    nav.innerHTML = "";
    this.sections().forEach((sec) => {
      const b = document.createElement("button");
      b.textContent = sec.label;
      b.dataset.sec = sec.id;
      b.addEventListener("click", () => this.openSection(sec.id));
      nav.appendChild(b);
    });
  },

  openSection(id) {
    this.activeSection = id;
    document.querySelectorAll("#settings-nav button").forEach((b) =>
      b.classList.toggle("active", b.dataset.sec === id));
    const sec = this.sections().find((x) => x.id === id);
    const content = document.getElementById("settings-content");
    content.innerHTML = "";
    if (sec.heading) content.insertAdjacentHTML("beforeend", "<h3>" + sec.heading + "</h3>");
    content.insertAdjacentHTML("beforeend", sec.render().join(""));
    this.wire(content);
    if (id === "update") {
      apiGet("/api/update/status").then((r) => {
        const el = document.getElementById("update-status");
        if (el && r) el.textContent = "Installed: " + (r.current_version || "?") + (r.repo_configured ? " — repo configured" : " — no repo set yet");
      }).catch(() => {});
    }
    if (id === "bluetooth") {
      apiGet("/api/bluetooth/status").then((r) => {
        const el = document.getElementById("bt-connect-status");
        if (el && r) {
          el.className = "test-result" + (r.bt_connected ? " ok" : "");
          el.textContent = r.bt_connected
            ? "Connected to " + (r.bt_speaker_name || r.bt_speaker) + " — audio goes to it"
            : (r.mode === "connect" ? "Not connected — scan below to connect a Bluetooth speaker" : "Pi is a Bluetooth speaker");
        }
      }).catch(() => {});
    }
    App.captureIdle?.(true);
  },

  wire(root) {
    root.querySelectorAll('[data-key="display.brightness"]').forEach((el) => {
      el.addEventListener("input", () => {
        const ro = el.parentElement.querySelector("[data-bri-readout]");
        if (ro) ro.textContent = el.value + "%";
      }, { passive: true });
    });

    root.querySelectorAll("[data-key]").forEach((el) => {
      const key = el.dataset.key;
      const push = () => {
        if (key === "volume") {
          apiPost("/api/audio/volume", { percent: parseInt(el.value, 10) || 0 });
          return;
        }
        if (key === "display.brightness") {
          apiPost("/api/display/brightness", { percent: parseInt(el.value, 10) || 0 });
        }
        if (key === "bluetooth.discoverable") {
          const on = !!this.readValue(el);
          apiPost("/api/bluetooth/discoverable", { on }).then((st) => {
            toast(st && st.powered
              ? (st.discoverable ? "Discoverable — pair from your phone now" : "Not discoverable")
              : "Bluetooth is powered off on the Pi");
          });
        }
        if (key === "bluetooth_mode") {
          const mode = el.classList.contains("on") ? "connect" : "speaker";
          apiPost("/api/bluetooth/mode", { mode }).then((st) => {
            toast(st && st.mode === "connect"
              ? "Now streaming to a Bluetooth speaker — scan above and connect one"
              : "Pi is a Bluetooth speaker again");
            Settings.openSection("bluetooth");
          });
          return;
        }
        const path = key.split(".");
        const patch = {};
        let ref = patch;
        for (let i = 0; i < path.length - 1; i++) {
          ref[path[i]] = {};
          ref = ref[path[i]];
        }
        ref[path[path.length - 1]] = this.readValue(el);
        saveConfig(patch).then(() => {
          loadConfig().then((cfg) => {
            this.cfg = cfg;
            Sleep.applyConfig(cfg);
          });
        });
        App.captureIdle?.(true);
      };
      whenChanged(el, push);
    });

    root.querySelectorAll("[data-action]").forEach((el) => {
      el.addEventListener("click", () => this.runAction(el.dataset.action, el), { passive: true });
    });

    root.querySelectorAll(".toggle").forEach((el) => {
      el.addEventListener("click", () => {
        el.classList.toggle("on");
        el.dispatchEvent(new Event("change"));
      }, { passive: true });
    });

    root.querySelectorAll(".day-pill").forEach((el) => {
      el.addEventListener("click", () => {
        el.classList.toggle("on");
        const row = el.parentElement;
        row.dispatchEvent(new Event("change"));
      }, { passive: true });
    });

    this.bindSchedule(root);
  },

  bindSchedule(root) {
    const list = root.querySelector(".sched-list");
    if (!list) return;
    list.querySelectorAll(".sched-editor").forEach((ed) => {
      this.drawStrip(ed, this.collectDayRanges(ed));
    });

    list.addEventListener("click", (e) => {
      const head = e.target.closest(".sched-day-head");
      if (head) {
        head.parentElement.classList.toggle("open");
        return;
      }
      const add = e.target.closest(".sched-add");
      if (add) {
        const dayEl = add.closest(".sched-day");
        add.insertAdjacentHTML("beforebegin", this.rangeRow(dayEl.dataset.day, dayEl.querySelectorAll(".sched-range").length, { start: "00:00", end: "00:00" }));
        this.applyDayChange(dayEl);
        return;
      }
      const del = e.target.closest(".sched-x");
      if (del) {
        const dayEl = del.closest(".sched-day");
        del.closest(".sched-range").remove();
        this.applyDayChange(dayEl);
      }
    }, { passive: true });

    list.addEventListener("change", (e) => {
      if (e.target.closest(".tpick")) {
        const dayEl = e.target.closest(".sched-day");
        this.applyDayChange(dayEl);
      }
    }, { passive: true });
  },

  applyDayChange(dayEl) {
    const day = parseInt(dayEl.dataset.day, 10);
    const ranges = this.collectDayRanges(dayEl);
    this.drawStrip(dayEl, ranges);
    this.updateSummary(dayEl);
    const patch = { schedule: { days: {} } };
    patch.schedule.days[String(day)] = ranges;
    saveConfig(patch).then(() => loadConfig()).then((cfg) => {
      this.cfg = cfg;
      Sleep.applyConfig(cfg);
    });
    App.captureIdle?.(true);
  },

  collectDayRanges(dayEl) {
    const ranges = [];
    dayEl.querySelectorAll(".sched-range").forEach((row) => {
      const start = this.readRowTime(row, "start");
      const end = this.readRowTime(row, "end");
      if (start && end && start !== end) {
        ranges.push({ start, end });
      }
    });
    ranges.sort((a, b) => a.start.localeCompare(b.start));
    return ranges;
  },

  readRowTime(row, which) {
    const tpick = row.querySelector('.tpick[data-tpick="' + which + '"]');
    if (!tpick) return "";
    const h = tpick.querySelector(".t-h").value;
    const m = tpick.querySelector(".t-m").value;
    const ap = tpick.querySelector(".t-a").value;
    return this.to24(h, m, ap);
  },

  drawStrip(editor, ranges) {
    const strip = editor.querySelector(".sched-strip");
    if (!strip) return;
    strip.innerHTML = "";
    const addMark = (s, e) => {
      const mark = document.createElement("div");
      mark.className = "sched-mark";
      mark.style.left = (s / 1440 * 100) + "%";
      mark.style.width = Math.max(0.6, (e - s) / 1440 * 100) + "%";
      strip.appendChild(mark);
    };
    ranges.forEach((r) => {
      const st = r.start.split(":").map(Number);
      const en = r.end.split(":").map(Number);
      if (st.length < 2 || en.length < 2) return;
      let s = st[0] * 60 + st[1];
      let e = en[0] * 60 + en[1];
      if (s === e) return;
      if (e <= s) {
        addMark(s, 1440);
        addMark(0, e);
      } else {
        addMark(s, e);
      }
    });
  },

  updateSummary(dayEl) {
    const sum = dayEl.querySelector(".sched-summary");
    if (!sum) return;
    const ranges = this.collectDayRanges(dayEl);
    sum.textContent = ranges.length
      ? ranges.map((r) => this.fmt12(r.start) + " – " + this.fmt12(r.end)).join(" · ")
      : "Never off";
  },

  scheduleDays() {
    return (this.cfg.schedule && this.cfg.schedule.days) || {};
  },

  getDayRanges(day) {
    const days = this.scheduleDays();
    return days[day] || days[String(day)] || [];
  },

  scheduleEditorHtml() {
    const names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    let html = '<div class="field"><label>Scheduled off times</label><div class="sched-list">';
    for (let i = 1; i <= 7; i++) {
      const ranges = this.getDayRanges(i);
      html +=
        '<div class="sched-day" data-day="' + i + '">' +
        '<button class="sched-day-head">' +
          '<span class="sched-day-name">' + names[i - 1] + "</span>" +
          '<span class="sched-summary">' + (ranges.length
            ? ranges.map((r) => this.fmt12(r.start) + " – " + this.fmt12(r.end)).join(" · ")
            : "Never off") + "</span>" +
        "</button>" +
        '<div class="sched-editor">' +
          '<div class="sched-strip" data-strip="' + i + '"></div>' +
          ranges.map((r, idx) => this.rangeRow(i, idx, r)).join("") +
          '<button class="btn sched-add" data-add="' + i + '">+ Add time</button>' +
        "</div>" +
        "</div>";
    }
    html += "</div></div>";
    return html;
  },

  rangeRow(day, idx, r) {
    return (
      '<div class="sched-range" data-range="' + day + "-" + idx + '">' +
      this.timePick("start", day, idx, r.start) +
      '<span class="sched-to">to</span>' +
      this.timePick("end", day, idx, r.end) +
      '<button class="sched-x" title="Remove">✕</button>' +
      "</div>"
    );
  },

  timePick(which, day, idx, t24) {
    const parts = String(t24 || "07:00").split(":");
    let h = parseInt(parts[0], 10);
    const m = parseInt(parts[1], 10);
    if (isNaN(h)) h = 0;
    const am = h < 12;
    const hr12 = h % 12 || 12;
    const minutes = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55];
    const minOpts = minutes
      .map((v) => '<option value="' + v + '"' + (v === m ? " selected" : "") + ">" + String(v).padStart(2, "0") + "</option>")
      .join("");
    let hrOpts = "";
    for (let v = 1; v <= 12; v++) hrOpts += '<option value="' + v + '"' + (v === hr12 ? " selected" : "") + ">" + v + "</option>";
    return (
      '<div class="tpick" data-tpick="' + which + '">' +
      '<select class="t-h">' + hrOpts + "</select>" +
      '<select class="t-m">' + minOpts + "</select>" +
      '<select class="t-a"><option value="AM"' + (am ? " selected" : "") + ">AM</option>" +
      '<option value="PM"' + (!am ? " selected" : "") + ">PM</option></select></div>"
    );
  },

  to24(hr12, min, ap) {
    let h = parseInt(hr12, 10) % 12;
    if (ap === "PM") h += 12;
    return String(h).padStart(2, "0") + ":" + String(parseInt(min, 10)).padStart(2, "0");
  },

  fmt12(t24) {
    if (!t24) return "--:--";
    const p = String(t24).split(":");
    let h = parseInt(p[0], 10);
    const m = parseInt(p[1], 10);
    if (isNaN(h)) return "--:--";
    const ap = h < 12 ? "AM" : "PM";
    h = h % 12 || 12;
    return h + ":" + String(m).padStart(2, "0") + " " + ap;
  },

  runAction(id, el) {
    switch (id) {
      case "rerun":
        saveConfig({ setup_complete: false }).then(() => window.location.reload());
        break;
      case "refresh":
        apiPost("/api/immich/refresh").then(() => {
          toast("Photos refreshed");
          App.reloadSlideshow();
        });
        break;
      case "test_weather":
        Weather.refresh().then(() => {
          toast(Weather.last && Weather.last.available ? "Weather works" : "Could not fetch weather — check location");
        });
        break;
      case "test_ha": {
        apiGet("/api/ha/states").then((st) =>
          toast(st.length ? "Connected — " + st.length + " devices found" : "HA connected but no devices"));
        break;
      }
      case "sleep_now":
        Sleep.setPower(false);
        break;
      case "test_alarm":
        apiPost("/api/alarm/test");
        break;
      case "test_tone":
        apiPost("/api/audio/test");
        break;
      case "stop_tone":
        apiPost("/api/audio/test", { stop: true });
        break;
      case "bt_status":
        apiGet("/api/bluetooth/status").then((st) =>
          toast("Bluetooth " + (st.powered ? "on" : "off") + " · mode: " + (st.bt_connected ? "streaming to " + (st.bt_speaker_name || st.bt_speaker) : (st.mode === "connect" ? "connecting to a speaker" : "speaker" + (st.discoverable ? " (discoverable)" : ""))) + " · paired: " + (st.aliases.length || "none")));
        break;
      case "bt_scan": {
        const listEl = document.getElementById("bt-scan-list");
        const statusEl = document.getElementById("bt-connect-status");
        if (listEl) listEl.innerHTML = "";
        if (statusEl) { statusEl.className = "test-result"; statusEl.textContent = "Scanning for 12 seconds…"; }
        apiPost("/api/bluetooth/scan", { duration: 12 }).then((r) => {
          const list = (r && r.devices) || [];
          if (statusEl) {
            statusEl.className = "test-result " + (list.length ? "ok" : "bad");
            statusEl.textContent = list.length ? list.length + " device(s) found — tap one to connect" : "No speakers found — put your speaker in pairing mode and scan again";
          }
          if (listEl) {
            listEl.innerHTML = list.map((d) =>
              '<div class="field bt-row"><label>' + this.esc(d.name) + " <span class='hint'>" + d.mac + (d.speaker ? " · speaker" : "") + (d.connected ? " · connected" : d.paired ? " · paired" : "") + "</span></label>" +
              '<button class="btn" data-action="bt_connect" data-mac="' + this.esc(d.mac) + '" data-name="' + this.esc(d.name) + '">Connect</button></div>').join("") ||
              "";
            listEl.querySelectorAll("[data-action]").forEach((b) => b.addEventListener("click", () => this.runAction(b.dataset.action, b), { passive: true }));
          }
        }).catch(() => { if (statusEl) { statusEl.className = "test-result bad"; statusEl.textContent = "Scan failed"; } });
        break;
      }
      case "bt_connect": {
        const statusEl = document.getElementById("bt-connect-status");
        const mac = el && el.dataset.mac;
        if (!mac) break;
        if (statusEl) { statusEl.className = "test-result"; statusEl.textContent = "Connecting to " + ((el && el.dataset.name) || mac) + "…"; }
        apiPost("/api/bluetooth/connect", { mac, name: (el && el.dataset.name) || "" }).then((st) => {
          if (statusEl) {
            statusEl.className = "test-result " + (st && st.bt_connected ? "ok" : "bad");
            statusEl.textContent = st && st.bt_connected
              ? "Connected to " + (st.bt_speaker_name || st.bt_speaker) + " — audio now goes to it"
              : (st && st.bt_error) || "Couldn't connect — is the speaker powered on and in pairing mode?";
          }
        });
        break;
      }
      case "bt_disconnect": {
        const statusEl = document.getElementById("bt-connect-status");
        apiPost("/api/bluetooth/disconnect").then((st) => {
          if (statusEl) { statusEl.className = "test-result ok"; statusEl.textContent = "Disconnected — audio back to the audio jack (AUX)."; }
        });
        break;
      }
      case "test_music": {
        const statusEl = document.getElementById("music-status");
        if (statusEl) { statusEl.className = "test-result"; statusEl.textContent = "Connecting…"; }
        apiGet("/api/jellyfin/status").then((st) => {
          let msg = "";
          let cls = "bad";
          if (!st.enabled) {
            msg = "Fill in the Jellyfin server URL and account details above.";
          } else if (!st.server_name) {
            msg = "Could not reach the Jellyfin server at " + (st.server_url || "?");
          } else if (!st.authenticated) {
            msg = "Signed in failed: " + (st.error || "check username/password or API key");
          } else {
            if (st.version) msg = "Connected to " + st.server_name + " (v" + st.version + ")";
            else msg = "Connected to " + st.server_name;
            if (st.user) msg += " · signed in as " + st.user;
            cls = "ok";
          }
          if (statusEl) { statusEl.textContent = msg; statusEl.className = "test-result " + cls; }
          toast(msg);
        });
        break;
      }
      case "mqtt_reg": {
        const statusEl = document.getElementById("mqtt-status");
        if (statusEl) { statusEl.className = "test-result"; statusEl.textContent = "Connecting…"; }
        apiPost("/api/mqtt/reload").then(() => new Promise((r) => setTimeout(r, 1500))).then(() =>
          Promise.all([apiGet("/api/mqtt/status"), apiGet("/api/ha/embed").catch(() => ({}))])
        ).then(([st, embed]) => {
          let msg = "";
          let cls = "bad";
          if (st.connected) {
            if (embed.registered) {
              msg = "Device found in Home Assistant. It's registered.";
              cls = "ok";
            } else {
              msg = "Connected to MQTT. The screen has published itself — it should appear in your HA devices list shortly.";
              cls = "ok";
            }
          } else {
            msg = "Not connected: " + (st.last_error || "check broker details, then save this section.");
          }
          if (statusEl) { statusEl.textContent = msg; statusEl.className = "test-result " + cls; }
          toast(msg);
        });
        break;
      }
      case "ha_add_device":
        Settings.close();
        App.openHass();
        Hass.openAddDevice();
        break;
      case "update_check": {
        const statusEl = document.getElementById("update-status");
        const actEl = document.getElementById("update-actions");
        if (statusEl) { statusEl.className = "test-result"; statusEl.textContent = "Checking…"; }
        if (actEl) actEl.innerHTML = "";
        apiPost("/api/update/check").then((r) => {
          let msg = "";
          let cls = "ok";
          if (!r.repo_configured) {
            msg = "Enter a repo URL (and branch if needed) above, then save this section and check again.";
            cls = "bad";
          } else if (!r.git_available) {
            msg = "git is not installed on this device.";
            cls = "bad";
          } else if (!r.script_present) {
            msg = "Updater script is missing — run deploy/install.sh once or rebuild the image.";
            cls = "bad";
          } else if (!r.remote_commit) {
            msg = "Could not reach the repo: " + (r.last_error || "check the URL, branch and network.");
            cls = "bad";
          } else if (r.update_available) {
            msg = "New version available: " + r.remote_commit + " (you have " + r.current_version + ")";
            if (actEl) { actEl.innerHTML = Settings.button("Apply update & restart the app", "primary block", "update_apply"); Settings.wire(actEl); }
          } else {
            msg = "You're on the latest (" + r.remote_commit + ").";
          }
          if (statusEl) { statusEl.textContent = msg; statusEl.className = "test-result " + cls; }
          toast(msg);
        });
        break;
      }
      case "update_apply": {
        const actEl = document.getElementById("update-actions");
        const statusEl = document.getElementById("update-status");
        if (actEl) actEl.innerHTML = "";
        if (statusEl) { statusEl.className = "test-result"; statusEl.textContent = "Updating… the app will restart when done."; }
        apiPost("/api/update/apply").then((r) => {
          if (!r.ok && r.error) {
            if (statusEl) { statusEl.className = "test-result bad"; statusEl.textContent = r.error; }
            toast("Update failed");
            return;
          }
          if (statusEl) { statusEl.className = "test-result ok"; statusEl.textContent = "Updated — app is restarting…"; }
          waitForApp(40000).then(() => window.location.reload());
        }).catch(() => {
          if (statusEl) { statusEl.className = "test-result ok"; statusEl.textContent = "Updated — app is restarting…"; }
          waitForApp(40000).then(() => window.location.reload());
        });
        break;
      }
    }
  },

  readValue(el) {
    if (el.dataset.type === "toggle") return el.classList.contains("on");
    if (el.dataset.type === "days") {
      return Array.from(el.querySelectorAll(".day-pill.on")).map((p) => parseInt(p.dataset.day, 10));
    }
    if (el.dataset.type === "number") return parseFloat(el.value) || 0;
    if (el.dataset.type === "slider") return parseInt(el.value, 10) || 0;
    if (el.dataset.type === "time") return el.value;
    return el.value;
  },

  textField(key, label, value, hint) {
    return '<div class="field"><label>' + label + '</label><input type="text" data-key="' + key + '" value="' + this.esc(value ?? "") + '">' +
      (hint ? '<div class="hint">' + hint + "</div>" : "") + "</div>";
  },

  passwordField(key, label, value) {
    return '<div class="field"><label>' + label + '</label><input type="password" data-key="' + key + '" value="' + this.esc(value ?? "") + '"></div>';
  },

  numberField(key, label, value, opts) {
    opts = opts || {};
    const actualKey = opts.key || key;
    return '<div class="field"><label>' + label + '</label><input type="number" data-type="number" data-key="' + actualKey + '" value="' + this.esc(value ?? "") + '"' +
      (opts.max ? " max=" + opts.max : "") + "></div>";
  },

  sliderField(key, label, value) {
    const v = Math.max(0, Math.min(100, parseInt(value, 10) || 100));
    return '<div class="field"><label>' + label + '</label><div class="slider-row">' +
      '<input type="range" min="0" max="100" step="1" data-type="slider" data-key="' + key + '" value="' + v + '">' +
      '<span class="bri-readout" data-bri-readout>' + v + "%</span></div></div>";
  },

  timeField(key, label, value) {
    return '<div class="field"><label>' + label + '</label><input type="time" data-type="time" data-key="' + key + '" value="' + this.esc(value || "07:00") + '"></div>';
  },

  selectField(key, label, value, options, hint) {
    return '<div class="field"><label>' + label + '</label><select data-key="' + key + '">' +
      options.map(([v, l]) => '<option value="' + this.esc(v) + '"' + (String(v) === String(value) ? " selected" : "") + ">" + l + "</option>").join("") +
      "</select>" + (hint ? '<div class="hint">' + hint + "</div>" : "") + "</div>";
  },

  toggleField(key, label, value, hint) {
    return '<div class="row"><div class="field"><label>' + label + "</label>" +
      (hint ? '<div class="hint">' + hint + "</div>" : "") + "</div>" +
      '<div class="toggle' + (value ? " on" : "") + '" data-type="toggle" data-key="' + key + '" role="switch"></div></div>';
  },

  daysField(key, label, value) {
    const names = ["M", "T", "W", "T", "F", "S", "S"];
    const days = Array.isArray(value) ? value : [];
    return '<div class="field"><label>' + label + '</label><div class="days-row" data-type="days" data-key="' + key + '">' +
      names.map((n, i) => {
        const day = i + 1;
        return '<div class="day-pill' + (days.includes(day) ? " on" : "") + '" data-day="' + day + '">' + n + "</div>";
      }).join("") + "</div></div>";
  },

  button(label, cls, action) {
    return '<button class="btn ' + cls + '" data-action="' + action + '">' + label + "</button>";
  },

  note(text) {
    return '<div class="hint" style="margin-top:10px">' + text + "</div>";
  },

  esc(s) {
    const div = document.createElement("div");
    div.textContent = String(s);
    return div.innerHTML;
  },
};

function whenChanged(el, fn) {
  if (el.type === "number" || el.type === "time") {
    el.addEventListener("change", fn, { passive: true });
  } else if (el.tagName === "SELECT" || el.type === "text" || el.type === "password") {
    el.addEventListener("change", fn, { passive: true });
  } else {
    el.addEventListener("change", fn, { passive: true });
  }
}

function waitForApp(ms) {
  const deadline = Date.now() + ms;
  return new Promise((resolve) => {
    const tick = () => {
      fetch("/api/status")
        .then((res) => (res.ok ? resolve() : setTimeout(tick, 1000)))
        .catch(() => {
          if (Date.now() > deadline) resolve();
          else setTimeout(tick, 1000);
        });
    };
    tick();
  });
}