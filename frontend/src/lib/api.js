// In local dev, Vite's proxy (vite.config.js) forwards relative /api/v1
// calls to the backend — no env var needed. In production, the frontend
// and backend are typically deployed to different domains (e.g. Vercel +
// Railway), so VITE_API_BASE_URL must be set to the backend's full URL
// at build time. Falls back to the relative path if unset, which is
// correct for local dev but will 404 in a production build without it.
const API_BASE = `${import.meta.env.VITE_API_BASE_URL || ""}/api/v1`;

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export const api = {
  listPlots: () => request("/plots"),
  getTwin: (plotId) => request(`/plots/${plotId}/twin`),
  refreshSatellite: (plotId) =>
    request(`/plots/${plotId}/satellite/refresh`, { method: "POST" }),
  computeSoilScore: (plotId) =>
    request(`/plots/${plotId}/soil-score/compute`, { method: "POST" }),
  scanDisease: (plotId, file) => {
    const form = new FormData();
    form.append("image", file);
    return fetch(`${API_BASE}/plots/${plotId}/disease-scan`, {
      method: "POST",
      body: form,
    }).then((res) => {
      if (!res.ok) throw new Error(`Scan failed: ${res.status}`);
      return res.json();
    });
  },
  federationNodes: () => request("/federation/nodes"),
  voiceQuery: (payload) =>
    request("/voice/query", { method: "POST", body: JSON.stringify(payload) }),
};
