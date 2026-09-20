const Clock = {
  elTime: null,
  elDate: null,

  init() {
    this.elTime = document.getElementById("time");
    this.elDate = document.getElementById("date");
    this.tick();
    setInterval(() => this.tick(), 1000);
  },

  tick() {
    const now = new Date();
    this.elTime.textContent = this.fmt(now.getHours()) + ":" + this.fmt(now.getMinutes());
    const days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
    const months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
    this.elDate.textContent =
      days[now.getDay()] + ", " + months[now.getMonth()] + " " + now.getDate();
  },

  fmt(n) { return String(n).padStart(2, "0"); },
};