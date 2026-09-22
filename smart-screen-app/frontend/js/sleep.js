const Sleep = {
  idleSeconds: 30,
  wakeSeconds: 20,
  enabled: true,
  scheduleEnabled: false,
  scheduleDays: null,
  powerOn: true,
  lastActivity: Date.now(),
  wakeUntil: 0,
  checkTimer: null,
  displaySupported: true,

  init() {
    document.addEventListener("touchstart", (e) => this.activity(e), { passive: true });
    document.addEventListener("mousedown", (e) => this.activity(e));
    this.checkTimer = setInterval(() => this.check(), 2000);
    apiGet("/api/display/status").then((s) => {
      this.displaySupported = s.supported;
      if (!s.supported) this.enabled = false;
    }).catch(() => {});
  },

  applyConfig(cfg) {
    const s = cfg.sleep || {};
    this.enabled = s.enabled !== false && this.displaySupported;
    this.idleSeconds = s.idle_seconds || 30;
    this.wakeSeconds = s.wake_seconds || 20;
    const sc = cfg.schedule || {};
    this.scheduleEnabled = sc.enabled === true;
    this.scheduleDays = sc.days || {};
  },

  activity(e) {
    this.lastActivity = Date.now();
    if (!this.powerOn) {
      this.wake();
      this.openAt(e);
    }
  },

  openAt(e) {
    const t = e && e.changedTouches && e.changedTouches[0] ? e.changedTouches[0] : e;
    if (!t || t.clientX == null) return;
    const btn = document.getElementById("btn-settings");
    const r = btn.getBoundingClientRect();
    if (t.clientX >= r.left && t.clientX <= r.right && t.clientY >= r.top && t.clientY <= r.bottom) {
      console.log("WAKE-openAt in gear rect");
      toast("wake+gear");
      setTimeout(() => Settings.open(), 200);
    }
  },

  check() {
    if (!this.enabled) return;
    const now = Date.now();
    const schedOff = this.scheduleEnabled && this.isScheduledOff();
    if (this.powerOn) {
      const idle = Math.floor((now - this.lastActivity) / 1000);
      if (schedOff || idle >= this.idleSeconds) {
        this.setPower(false);
      }
    } else if (now > this.wakeUntil) {
      this.setPower(false);
    }
  },

  isScheduledOff() {
    if (!this.scheduleDays) return false;
    const now = new Date();
    const isoDay = ((now.getDay() + 6) % 7) + 1;
    const minutes = now.getHours() * 60 + now.getMinutes();
    const ranges = this.scheduleDays[isoDay] || this.scheduleDays[String(isoDay)] || [];
    return ranges.some((r) => {
      if (!r || !r.start || !r.end) return false;
      const st = r.start.split(":").map(Number);
      const en = r.end.split(":").map(Number);
      if (st.length < 2 || en.length < 2 || isNaN(st[0]) || isNaN(en[0])) return false;
      const start = st[0] * 60 + st[1];
      const end = en[0] * 60 + en[1];
      if (start === end) return false;
      return start < end
        ? start <= minutes && minutes < end
        : minutes >= start || minutes < end;
    });
  },

  wake() {
    this.wakeUntil = Date.now() + this.wakeSeconds * 1000;
    this.lastActivity = Date.now();
    this.setPower(true);
  },

  setPower(powered) {
    this.powerOn = powered;
    if (!powered && window.Kbd) Kbd.hide();
    document.getElementById("app").classList.toggle("screen-off", !powered);
    apiPost("/api/display/power", { powered }).catch(() => {});
    if (powered) this.wakeUntil = Date.now() + this.wakeSeconds * 1000;
  },
};