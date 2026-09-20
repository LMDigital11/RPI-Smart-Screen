const Hass = {
  entities: [],
  dashboardUrl: null,
  addDeviceUrl: null,
  embedMode: false,

  icons: {
    light: "M12 3a9 9 0 0 0-3 17.5V22h6v-1.5A9 9 0 0 0 12 3zm1 15h-2v1h2v-1zm-1 3v1h2v-1h-2zm2.8-2.7c-.5.4-1 .7-1.5.9V18h-.5v1.2c-.3-.1-.6-.2-.8-.3-1-.5-1.8-1.2-2.4-2A7 7 0 1 1 15.8 18.3z",
    switch: "M13 5v14h6V5h-6zm-2 0H5v14h6V5z",
    fan: "M13 3a2 2 0 0 0-2 2v3.5c0 .4-.4.7-.8.6l-4-1.3a2 2 0 0 0-2.4.9 2 2 0 0 0 .7 2.7l3.3 2a.8.8 0 0 1 .3 1l-2 3.5A2 2 0 0 0 7.8 21a2 2 0 0 0 2.6 0l3-2.3c.3-.3.8-.2 1 .2l.7 4.1a2 2 0 0 0 2 1.6 2 2 0 0 0 1.9-1.4l-2.3-3.5a.8.8 0 0 1 .9-1l4.3.7a2 2 0 0 0 2.2-2.4 2 2 0 0 0-2-1.5h-3.5c-.4 0-.7-.4-.6-.8l1.3-4A2 2 0 0 0 20 4a2 2 0 0 0-2 0l-3.3 2a.8.8 0 0 1-1-.3l-2-3.5A2 2 0 0 0 13 3z",
    media_player: "M3 9v6h4l5 5V4L7 9H3zm13.5 3a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4zM14 3.2v1.9a6 6 0 0 1 0 11.8v1.9a8 8 0 0 0 0-15.6z",
    climate: "M17.7 10.3 21 7a1.4 1.4 0 0 0 0-2 1.4 1.4 0 0 0-2 0l-3.3 3.3a4.5 4.5 0 0 0-5.7 5.7L2 22h2l-1 1h.8l1-1h1l-1 1H5l1-1h1" 
  },

  async init() {
    const embedResp = await apiGet("/api/ha/embed").catch(() => ({ configured: false }));
    this.dashboardUrl = embedResp.url;
    this.addDeviceUrl = embedResp.add_device_url;
    this.render();
    setInterval(() => this.render(), 30000);
  },

  async render() {
    const container = document.getElementById("hass-native");
    const wrap = document.getElementById("hass-embed-wrap");
    const entities = await apiGet("/api/ha/states").catch(() => []);

    if (!entities || !entities.length) {
      container.innerHTML =
        '<div class="hass-empty"><span style="font-size:52px">🏠</span><p>Connect Home Assistant in the setup wizard to see your devices here.</p></div>';
      return;
    }

    this.entities = entities;
    wrap.classList.add("hidden");
    container.classList.remove("hidden");
    container.innerHTML =
      '<div class="card-grid">' +
      entities.map((e) => this.card(e)).join("") +
      "</div>";

    container.querySelectorAll(".ha-card").forEach((el) => {
      el.addEventListener("click", () => this.toggle(el.dataset.entity));
    });

    if (this.dashboardUrl) {
      let pair = document.querySelector(".hass-actions");
      if (!pair) {
        pair = document.createElement("div");
        pair.className = "hass-actions";
        const addBtn = document.createElement("button");
        addBtn.className = "btn block";
        addBtn.textContent = "＋ Add device to Home Assistant";
        addBtn.addEventListener("click", () => this.openAddDevice());
        const dashBtn = document.createElement("button");
        dashBtn.className = "hass-embed-toggle";
        dashBtn.textContent = "Full dashboards";
        dashBtn.addEventListener("click", () => this.toggleEmbed());
        pair.appendChild(addBtn);
        pair.appendChild(dashBtn);
        container.appendChild(pair);
      }
    }
  },

  card(e) {
    const isOn = e.state === "on";
    const icon = this.icons[e.domain] || this.icons.switch;
    let stateLabel = e.state === "on" ? "On" : e.state === "off" ? "Off" : e.state;
    if (e.domain === "light" && isOn && e.brightness_pct != null) stateLabel += " · " + e.brightness_pct + "%";
    if (e.domain === "climate") {
      stateLabel = (e.temperature || "--") + "°";
    }
    return (
      '<div class="ha-card ' + (isOn ? "on" : "off") + '" data-entity="' + e.entity_id + '">' +
        '<svg class="ha-icon" viewBox="0 0 24 24"><path d="' + icon + '"/></svg>' +
        '<div class="hc-name">' + this.esc(e.name) + "</div>" +
        '<div class="hc-state">' + this.esc(stateLabel) + "</div>" +
      "</div>"
    );
  },

  esc(s) {
    const div = document.createElement("div");
    div.textContent = String(s);
    return div.innerHTML;
  },

  async toggle(entityId) {
    const entity = this.entities.find((e) => e.entity_id === entityId);
    if (!entity) return;
    const el = document.querySelector('.ha-card[data-entity="' + entityId + '"]');
    if (el) el.classList.add("staging");
    if (entity.domain === "climate") {
      await apiPost("/api/ha/service", { domain: "climate", service: "toggle", entity_id: entityId });
    } else {
      const wantsOff = entity.state === "on";
      await apiPost("/api/ha/service", {
        domain: entity.domain,
        service: wantsOff ? "turn_off" : "turn_on",
        entity_id: entityId,
      });
    }
    await this.render();
  },

  toggleEmbed() {
    if (this.embedMode) {
      this.showControls();
      return;
    }
    if (this.dashboardUrl && this.dashboardUrl !== "None") {
      this.showEmbed(this.dashboardUrl, "Back to controls");
    }
  },

  openAddDevice() {
    if (!this.addDeviceUrl || this.addDeviceUrl === "None") return;
    this.showEmbed(this.addDeviceUrl, "Done");
  },

  showEmbed(url, toggleLabel) {
    this.embedMode = true;
    const container = document.getElementById("hass-native");
    const wrap = document.getElementById("hass-embed-wrap");
    container.classList.add("hidden");
    wrap.classList.remove("hidden");
    document.getElementById("hass-iframe").src = url || "";
    const toggle = document.querySelector(".hass-embed-toggle");
    if (toggle && toggleLabel) toggle.textContent = toggleLabel;
  },

  showControls() {
    this.embedMode = false;
    const container = document.getElementById("hass-native");
    const wrap = document.getElementById("hass-embed-wrap");
    container.classList.remove("hidden");
    wrap.classList.add("hidden");
    const toggle = document.querySelector(".hass-embed-toggle");
    if (toggle) toggle.textContent = "Full dashboards";
  },
};