const Slideshow = {
  photos: [],
  index: 0,
  shown: 0,
  timer: null,
  imgA: null,
  imgB: null,
  current: "a",
  onPhotoShown: null,

  init() {
    this.imgA = document.getElementById("photo-a");
    this.imgB = document.getElementById("photo-b");
  },

  async refresh(mode) {
    const data = await apiGet("/api/slideshow/photos");
    this.photos = data.photos || [];
    this.durationSec = data.photo_duration_sec || 12;
    this.weatherEveryN = data.weather_every_n_photos || 5;
  },

  start() {
    this.stop();
    if (!this.photos.length) return;
    this.showNext();
    this.timer = setInterval(() => this.showNext(), this.durationSec * 1000);
  },

  stop() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  },

  showNext() {
    if (!this.photos.length) return;
    const url = this.photos[this.index % this.photos.length];
    this.index += 1;

    const incoming = this.current === "a" ? this.imgB : this.imgA;
    const outgoing = this.current === "a" ? this.imgA : this.imgB;
    this.current = this.current === "a" ? "b" : "a";

    incoming.onload = () => {
      incoming.classList.add("show");
      outgoing.classList.remove("show");
    };
    incoming.onerror = () => {
      this.showNext();
    };
    incoming.src = url;

    this.shown += 1;
    if (this.onPhotoShown && (this.shown % this.weatherEveryN === 0)) {
      this.onPhotoShown();
    }
  },
};