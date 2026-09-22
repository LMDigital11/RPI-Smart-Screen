const Kbd = {
  el: null,
  field: null,
  shift: false,
  sym: false,
  hideTimer: null,

  init() {
    this.el = document.getElementById("kbd");

    document.addEventListener("focusin", (e) => {
      const t = e.target;
      if (this.isEditable(t)) this.show(t);
    });

    document.addEventListener("focusout", (e) => {
      if (!this.isEditable(e.target)) return;
      clearTimeout(this.hideTimer);
      this.hideTimer = setTimeout(() => this.hide(), 150);
    });

    this.render();
    window.Kbd = this;
  },

  isEditable(t) {
    if (!t || t === this.el) return false;
    if (t.tagName === "INPUT") {
      const ty = (t.type || "text").toLowerCase();
      if (["checkbox", "radio", "range", "button", "submit", "reset", "hidden"].includes(ty)) return false;
      return !t.readOnly && !t.disabled;
    }
    if (t.tagName === "TEXTAREA") return !t.readOnly && !t.disabled;
    return false;
  },

  show(field) {
    this.field = field;
    this.el.classList.remove("hidden");
    field.scrollIntoView({ block: "center" });
  },

  hide() {
    this.el.classList.add("hidden");
  },

  toggleShift() {
    this.shift = !this.shift;
    this.render();
  },

  toggleSym() {
    this.sym = !this.sym;
    this.shift = false;
    this.render();
  },

  keys() {
    const shift = this.shift;
    const letters = (s) => s.split("").map((c) => (shift ? c.toUpperCase() : c));
    if (this.sym) {
      return [
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
        ["@", "/", ":", ".", "-", "_", "?", "="],
        ["abc", "&", "#", "+", "*", "(", ")", "!", "bs"],
        ["sym", "space", "done"],
      ];
    }
    return [
      letters("qwertyuiop"),
      letters("asdfghjkl"),
      ["shift", ...letters("zxcvbnm"), "bs"],
      ["sym", "space", "done"],
    ];
  },

  render() {
    this.el.textContent = "";
    this.keys().forEach((row) => {
      const r = document.createElement("div");
      r.className = "kbd-row";
      row.forEach((k) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "kbd-key";
        if (k.indexOf(" ") === -1 && k !== "done" && k !== "bs") b.classList.add("kbd-ch");
        if (k === "space") b.className += " kbd-space";
        if (k === "shift" || k === "sym" || k === "abc") b.className += " kbd-fn";
        if ((k === "shift" && this.shift) || (k === "sym" && this.sym)) b.classList.add("kbd-on");
        b.textContent = this.label(k);
        b.addEventListener("touchstart", (e) => {
          e.preventDefault();
          this.tap(k);
        }, { passive: false });
        b.addEventListener("mousedown", (e) => {
          e.preventDefault();
          this.tap(k);
        }, { passive: false });
        r.appendChild(b);
      });
      this.el.appendChild(r);
    });
  },

  label(k) {
    if (k === "space") return "\u2423";
    if (k === "bs") return "\u232b";
    if (k === "done") return "Done";
    if (k === "shift") return "\u21e7";
    if (k === "abc") return "abc";
    if (k === "sym") return this.sym ? "ABC" : "?123";
    return k;
  },

  tap(k) {
    if (!this.field) return;
    if (k === "shift") return this.toggleShift();
    if (k === "sym") return this.toggleSym();
    if (k === "abc") { this.sym = false; this.render(); return; }
    if (k === "bs") return this.backspace();
    if (k === "done") {
      this.hide();
      const f = this.field;
      this.field = null;
      f.blur();
      return;
    }
    this.insert(k === "space" ? " " : k);
  },

  insert(ch) {
    const el = this.field;
    const v = el.value || "";
    const s = el.selectionStart == null ? v.length : el.selectionStart;
    const e = el.selectionEnd == null ? s : el.selectionEnd;
    const next = v.slice(0, s) + ch + v.slice(e);
    this.apply(el, next, s + ch.length);
    if (this.shift) {
      this.shift = false;
      this.render();
    }
  },

  backspace() {
    const el = this.field;
    const v = el.value || "";
    const s = el.selectionStart == null ? v.length : el.selectionStart;
    const e = el.selectionEnd == null ? s : el.selectionEnd;
    if (s !== e) {
      this.apply(el, v.slice(0, s) + v.slice(e), s);
    } else if (s > 0) {
      this.apply(el, v.slice(0, s - 1) + v.slice(s), s - 1);
    }
  },

  apply(el, value, caret) {
    el.value = value;
    try {
      el.setSelectionRange(caret, caret);
    } catch (x) {}
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  },
};

Kbd.init();