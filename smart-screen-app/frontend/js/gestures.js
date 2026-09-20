const Gesture = {
  onSwipeUp: null,
  onSwipeDown: null,

  init() {
    const el = document.getElementById("app");
    let startY = 0;
    let startX = 0;
    let tracking = false;

    el.addEventListener("touchstart", (e) => {
      const t = e.changedTouches[0];
      startY = t.clientY;
      startX = t.clientX;
      tracking = true;
    }, { passive: true });

    el.addEventListener("touchmove", (e) => {
      if (!tracking) return;
      const t = e.changedTouches[0];
      const dy = t.clientY - startY;
      const dx = t.clientX - startX;
      if (Math.abs(dy) > 80 && Math.abs(dy) > Math.abs(dx) * 1.5 && !this._consumed) {
        this._consumed = true;
        tracking = false;
        if (dy < 0 && this.onSwipeUp) this.onSwipeUp();
        if (dy > 0 && this.onSwipeDown) this.onSwipeDown();
        return;
      }
      if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5 && !this._consumed) {
        this._consumed = true;
        tracking = false;
      }
    }, { passive: true });

    el.addEventListener("touchend", () => { tracking = false; this._consumed = false; }, { passive: true });
  },
};