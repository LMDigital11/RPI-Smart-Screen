async function api(path, options) {
  const resp = await fetch(path, options);
  if (!resp.ok && resp.status !== 200) {
    throw new Error("HTTP " + resp.status);
  }
  return resp.json();
}

const apiGet = (path) => api(path);
const apiPost = (path, body) =>
  api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });

async function loadConfig() {
  return apiGet("/api/config");
}

async function saveConfig(patch) {
  return apiPost("/api/config", patch);
}

function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.remove("hidden");
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => el.classList.add("hidden"), 2400);
}