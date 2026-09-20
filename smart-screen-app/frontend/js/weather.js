const Weather = {
  last: null,
  cardTimer: null,

  init() {
    this.pill = document.getElementById("weather-pill");
    this.pillTemp = document.getElementById("pill-temp");
    this.pillCondition = document.getElementById("pill-condition");
    this.card = document.getElementById("weather-card");
    this.icons = {
      clear: "☀️", mostly_clear: "🌤️", partly_cloudy: "⛅", overcast: "☁️",
      fog: "🌫️", drizzle: "🌦️", rain: "🌧️", snow: "🌨️", storm: "⛈️",
    };
  },

  async refresh() {
    try {
      this.last = await apiGet("/api/weather");
      this.updatePill();
    } catch (e) { /* weather optional */ }
  },

  isDay(fallback) { return this.last ? this.last.is_day : fallback; },

  updatePill() {
    if (!this.last || !this.last.available) {
      this.pill.classList.add("hidden");
      return;
    }
    this.pill.classList.remove("hidden");
    const unit = this.last.unit === "fahrenheit" ? "°F" : "°C";
    this.pillTemp.textContent = Math.round(this.last.temperature) + unit;
    this.pillCondition.textContent = this.last.condition;
  },

  showCard() {
    if (!this.last || !this.last.available) return;
    const w = this.last;
    const unit = w.unit === "fahrenheit" ? "°F" : "°C";
    document.getElementById("wc-condition-label").textContent = w.condition;
    document.getElementById("wc-icon").textContent =
      this.icons[w.icon] || this.icons.clear;
    document.getElementById("wc-temp").textContent = Math.round(w.temperature) + unit;
    document.getElementById("wc-highlow").textContent =
      "H " + Math.round(w.high) + "°  ·  L " + Math.round(w.low) + "°";
    document.getElementById("wc-extra").textContent =
      "Feels " + Math.round(w.feels_like) + "°  ·  " + w.humidity + "% humidity  ·  wind " +
      Math.round(w.wind_kmh) + " km/h" + (w.rain_chance ? "  ·  rain " + w.rain_chance + "%" : "");
    document.getElementById("wc-sun").textContent =
      "Sunrise " + this.hhmm(w.sunrise) + "  ·  Sunset " + this.hhmm(w.sunset);
    this.card.classList.remove("hidden");
    clearTimeout(this.cardTimer);
    this.cardTimer = setTimeout(() => this.card.classList.add("hidden"), 9000);
  },

  hideCard() { this.card.classList.add("hidden"); },

  hhmm(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  },
};