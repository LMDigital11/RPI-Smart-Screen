const Setup = {
  step: 0,
  networks: [],
  selectedSsid: "",
  configDraft: null,

  steps: [
    { title: "Welcome", sub: "Let's get your smart screen going." },
    { title: "WiFi", sub: "Connect to your network." },
    { title: "Photos", sub: "Where should your slideshow pull photos from?" },
    { title: "Weather", sub: "Your location, for the weather cards." },
    { title: "Home Assistant", sub: "Connect your smart home." },
    { title: "All set", sub: "You can change any of this later from Settings." },
  ],

  async start() {
    if (!confirmSetup) return;
    this.configDraft = await loadConfig();
    document.getElementById("screen-setup").classList.add("active");
    document.getElementById("wizard-back").classList.remove("hidden");
    this.showStep(0);
  },

  showStep(i) {
    this.step = i;
    const meta = this.steps[i];
    document.getElementById("wizard-step").textContent = (i + 1) + " / " + this.steps.length;
    document.getElementById("wizard-title").textContent = meta.title;
    document.getElementById("wizard-subtitle").textContent = meta.sub;
    const body = document.getElementById("wizard-body");
    body.innerHTML = "";

    switch (i) {
      case 0: this.renderWelcome(body); break;
      case 1: this.renderWifi(body); break;
      case 2: this.renderPhotos(body); break;
      case 3: this.renderWeather(body); break;
      case 4: this.renderHome(body); break;
      case 5: this.renderDone(body); break;
    }

    document.getElementById("wizard-back").classList.toggle("hidden", i === 0);
    const next = document.getElementById("wizard-next");
    next.textContent = i === this.steps.length - 1 ? "Start using it" : "Continue";
  },

  renderWelcome(body) {
    body.innerHTML =
      '<div style="text-align:center;padding:20px 0">' +
      '<div style="font-size:64px">🖥️</div>' +
      "<p class=\"center-note\">This device shows your photos, the weather, and gives you full control of your smart home — right from the 7\" screen.</p>" +
      '<p class="center-note">We\'ll walk you through the essentials now. Everything can be changed later in Settings.</p>' +
      "</div>";
  },

  async renderWifi(body) {
    body.innerHTML = '<div class="spinner"></div><p class="center-note">Scanning for networks…</p>';
    try {
      const data = await apiGet("/api/wifi/scan");
      this.networks = data.networks || [];
    } catch (e) { this.networks = []; }

    body.innerHTML = "";
    if (!this.networks.length) {
      body.innerHTML = '<p class="center-note" style="font-size:30px">📡</p><p class="center-note">No networks found.</p>';
      return;
    }
    const list = document.createElement("div");
    list.className = "wifi-list";
    this.networks.forEach((net) => {
      const item = document.createElement("div");
      item.className = "wifi-item" + (net.ssid === this.selectedSsid ? " active" : "");
      item.innerHTML = '<span class="wi-name">' + escHtml(net.ssid) + "</span>" +
        '<span class="wi-signal">' + bars(net.signal) + "</span>";
      item.dataset.ssid = net.ssid;
      item.addEventListener("click", () => {
        this.selectedSsid = net.ssid;
        this.renderWifi(body);
        document.getElementById("wifi-password").focus();
      }, { passive: true });
      list.appendChild(item);
    });
    body.appendChild(list);

    const pwRow = document.createElement("div");
    pwRow.className = "field pw-row";
    pwRow.innerHTML = '<label>Password</label><input type="password" id="wifi-password" value="">';
    body.appendChild(pwRow);
  },

  renderPhotos(body) {
    const flow = document.createElement("div");

    const mode = this.mode || "immich";
    const src = document.createElement("div");
    src.className = "row";
    src.innerHTML = '<div class="field"><label>Photo source</label><select id="photo-source">' +
      '<option value="immich"' + (mode === "immich" ? " selected" : "") + ">Immich server</option>" +
      '<option value="usb"' + (mode === "usb" ? " selected" : "") + ">USB stick</option>" +
      "</select></div>";
    flow.appendChild(src);

    const immichBox = document.createElement("div");
    immichBox.dataset.flow = "immich";
    immichBox.innerHTML =
      this.inp("server_url", "Immich server", "http://192.168.1.20:2283") +
      this.inp("api_key", "Immich API key") +
      '<button class="btn block" data-test="immich">Test connection</button><div class="field test-result hidden" data-flow="immich"></div>';

    const usbBox = document.createElement("div");
    usbBox.dataset.flow = "usb";
    usbBox.className = "hidden";
    usbBox.innerHTML = '<p class="center-note">Plug a USB stick with photos into the Pi, then pick it from the dropdown in Settings → Photos.</p>';

    flow.appendChild(immichBox);
    flow.appendChild(usbBox);
    body.appendChild(flow);

    src.querySelector("select").addEventListener("change", (e) => {
      this.mode = e.target.value;
      flow.querySelectorAll('[data-flow]').forEach((el) => el.classList.toggle("hidden", el.dataset.flow !== this.mode));
    }, { passive: true });

    const testBtn = immichBox.querySelector("[data-test=immich]");
    testBtn.addEventListener("click", async () => {
      const res = flow.querySelector('[data-flow="immich"]');
      res.textContent = "Testing…";
      res.classList.remove("hidden");
      try {
        await apiPost("/api/immich/refresh", {});
        const n = await apiGet("/api/immich/photos");
        res.textContent = n.count ? "Connected — " + n.count + " photos" : "Connected, no photos found";
        res.className = "field test-result ok";
      } catch (e) {
        res.textContent = "Could not reach that server. Check the URL and API key.";
        res.className = "field test-result bad";
      }
    }, { passive: true });
  },

  renderWeather(body) {
    body.innerHTML =
      '<div class="location-row">' +
        this.inp("lat", "Latitude", "e.g. 51.5072") +
        this.inp("lon", "Longitude", "e.g. -0.1276") +
      "</div>" +
      '<div class="field"><label>Unit</label><select id="weather-unit">' +
      '<option value="celsius" selected>Celsius</option><option value="fahrenheit">Fahrenheit</option>' +
      "</select></div>" +
      '<button class="btn block" data-action="lookup">Use my location</button>' +
      '<div id="ll-res" class="test-result"></div>';
    body.querySelector("[data-action=lookup]").addEventListener("click", () => {
      const res = body.querySelector("#ll-res");
      res.className = "test-result";
      res.textContent = "Finding location…";
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition((pos) => {
          body.querySelector("#lat").value = pos.coords.latitude.toFixed(4);
          body.querySelector("#lon").value = pos.coords.longitude.toFixed(4);
          res.textContent = "Location found";
          res.className = "test-result ok";
        }, () => {
          res.textContent = "Couldn't get location — type it manually above.";
          res.className = "test-result bad";
        }, { timeout: 10000 });
      } else {
        res.textContent = "Location is blocked — type it manually above.";
        res.className = "test-result bad";
      }
    }, { passive: true });
  },

  renderHome(body) {
    body.innerHTML =
      this.inp("ha_url", "Home Assistant URL", "http://homeassistant.local:8123") +
      this.inp("ha_token", "Long-lived access token") +
      '<button class="btn block" data-action="test">Test connection</button>' +
      '<div id="ha-res" class="test-result"></div>';
    body.querySelector("[data-action=test]").addEventListener("click", async () => {
      const res = body.querySelector("#ha-res");
      res.className = "test-result";
      res.textContent = "Testing…";
      const url = body.querySelector("#ha_url").value.trim();
      const token = body.querySelector("#ha_token").value.trim();
      await saveConfig({ home_assistant: { server_url: url, token: token } });
      const states = await apiGet("/api/ha/states").catch(() => null);
      if (states && Array.isArray(states)) {
        res.textContent = "Connected — " + states.length + " devices found";
        res.classList.add("ok");
      } else {
        res.textContent = "No connection. Check the URL and token.";
        res.classList.add("bad");
      }
    }, { passive: true });
  },

  renderDone(body) {
    body.innerHTML =
      '<div style="text-align:center;padding:20px 0">' +
      '<div style="font-size:64px">🎉</div>' +
      '<p class="center-note">That\'s it! Your smart screen will start showing photos and keep the time.</p>' +
      '<p class="center-note">Swipe up any time for smart home, tap the gear for settings, and set an alarm to wake with light.</p>' +
      "</div>";
  },

  inp(id, label, placeholder) {
    return '<div class="field"><label>' + label + '</label><input type="text" id="' + id + '" placeholder="' + (placeholder || "") + '"></div>';
  },

  next() {
    this.commit();
    if (this.step >= this.steps.length - 1) {
      this.finish();
    } else {
      this.showStep(this.step + 1);
    }
  },

  back() {
    if (this.step > 0) this.showStep(this.step - 1);
  },

  commit() {
    const c = this.configDraft;
    if (this.step === 1) {
      c.wifi.ssid = this.selectedSsid;
    }
    if (this.step === 2) {
      c.immich.server_url = val("#server_url");
      c.immich.api_key = val("#api_key");
      c.slideshow.source = this.mode || "immich";
    }
    if (this.step === 3) {
      c.weather.latitude = parseFloat(val("#lat")) || c.weather.latitude;
      c.weather.longitude = parseFloat(val("#lon")) || c.weather.longitude;
      c.weather.unit = document.getElementById("weather-unit")?.value || "celsius";
    }
    if (this.step === 4) {
      const url = val("#ha_url");
      const token = val("#ha_token");
      if (url) c.home_assistant.server_url = url;
      if (token) c.home_assistant.token = token;
    }
    this.configDraft = c;
  },

  async finish() {
    const hits = {};
    for (const [key] of Object.entries(this.configDraft)) {
      if (key.match(/^(wifi|immich|weather|slideshow|home_assistant)$/)) {
        hits[key] = this.configDraft[key];
      }
    }
    await saveConfig(hits);
    await apiPost("/api/config/setup-complete", {});
    window.location.reload();
  },
};

function val(sel) {
  const el = document.querySelector(sel);
  return el ? el.value.trim() : "";
}

function escHtml(s) {
  const div = document.createElement("div");
  div.textContent = String(s);
  return div.innerHTML;
}

function bars(signal) {
  const n = signal >= 80 ? 4 : signal >= 60 ? 3 : signal >= 40 ? 2 : 1;
  return "▁".repeat(n) + "▂".repeat(Math.max(0, 4 - n));
}

function confirmSetup() {
  return true;
}