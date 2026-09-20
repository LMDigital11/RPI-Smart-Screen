const App = {
  async init() {
    Clock.init();
    Weather.init();
    Slideshow.init();
    Slideshow.onPhotoShown = () => Weather.showCard();
    Sleep.init();
    Gesture.init();
    Gesture.onSwipeUp = () => this.openHass();
    Gesture.onSwipeDown = () => this.closeSheets();

    document.getElementById("btn-settings").addEventListener("click", () => Settings.open());
    document.getElementById("btn-settings-close").addEventListener("click", () => Settings.close());
    document.getElementById("btn-hass-close").addEventListener("click", () => this.closeHass());

    document.getElementById("wizard-next").addEventListener("click", () => Setup.next());
    document.getElementById("wizard-back").addEventListener("click", () => Setup.back());

    const status = await apiGet("/api/status");
    if (!status.setup_complete) {
      Sleep.enabled = false;
      Setup.start();
      return;
    }

    const cfg = await loadConfig();
    Sleep.applyConfig(cfg);
    Weather.refresh();
    await Slideshow.refresh();
    Slideshow.start();
    Hass.init();
    this.refreshStatusDots();
    setInterval(() => this.refreshStatusDots(), 45000);
    this.pollNotifications();
  },

  async pollNotifications() {
    try {
      const n = await apiGet("/api/notifications/latest");
      if (n && n.message && n.ts !== this._lastNotifTs) {
        this._lastNotifTs = n.ts;
        toast(n.message);
      }
    } catch (e) { /* ignore */ }
    setTimeout(() => this.pollNotifications(), 4000);
  },

  openHass() {
    Weather.hideCard();
    Slideshow.stop();
    document.getElementById("screen-hass").classList.add("active");
  },

  closeHass() {
    document.getElementById("screen-hass").classList.remove("active");
    Slideshow.start();
  },

  closeSheets() {
    if (Settings.open) Settings.close();
    else this.closeHass();
  },

  captureIdle(capture) {
    Sleep.enabled = !capture;
  },

  async reloadSlideshow() {
    await Slideshow.refresh();
    Slideshow.start();
  },

  async refreshStatusDots() {
    const status = await apiGet("/api/status").catch(() => ({}));
    const wifi = await apiGet("/api/wifi/status").catch(() => ({}));
    setDot("immich-dot", status.immich_configured ? "ok" : "off");
    setDot("ha-dot", status.home_assistant_configured ? "ok" : "off");
    setDot("wifi-dot", wifi.connected ? "ok" : wifi.stored_ssid ? "warn" : "off");
    document.getElementById("wifi-dot").title = wifi.ssid || "no WiFi";
  },
};

function setDot(id, state) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove("ok", "warn", "off");
  el.classList.add(state);
}

document.addEventListener("DOMContentLoaded", () => App.init());