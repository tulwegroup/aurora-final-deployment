/**
 * Aurora OSI vNext — API Client
 * Phase P §P.1
 *
 * Thin HTTP client wrapping all aurora_vnext FastAPI endpoints.
 * CONSTITUTIONAL RULE: This module performs ZERO scientific computation.
 * It only issues requests and returns responses verbatim.
 * No threshold defaults, no ACIF arithmetic, no tier recounting.
 */

// Determine API base URL: use env var, production domain, or default to localhost
const BASE = (() => {
  const envUrl = import.meta.env.VITE_AURORA_API_URL;
  if (envUrl) return envUrl;
  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host === 'aurora-osi.io' || host === 'api.aurora-osi.io') {
      return 'https://api.aurora-osi.io/api/v1';
    }
  }
  return 'http://localhost:8000/api/v1';
})();

let _accessToken = null;

export function setAccessToken(token) {
  _accessToken = token;
}

export function clearAccessToken() {
  _accessToken = null;
}

async function request(method, path, body = null) {
  const headers = { "Content-Type": "application/json" };
  if (_accessToken) headers["Authorization"] = `Bearer ${_accessToken}`;
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const error = new Error(err.detail || "Request failed");
    error.status = res.status;
    throw error;
  }
  return res.json();
}

// Auth
export const auth = {
  login:  (email, password) => request("POST", "/auth/login",  { email, password }),
  logout: ()                 => request("POST", "/auth/logout"),
  me:     ()                 => request("GET",  "/auth/me"),
};

// Scans
export const scans = {
  submitGrid:    (body)    => request("POST", "/scan/grid",         body),
  submitPolygon: (body)    => request("POST", "/scan/polygon",      body),
  status:        (scanId)  => request("GET",  `/scan/status/${scanId}`),
  active:        ()        => request("GET",  "/scan/active"),
  cancel:        (scanId)  => request("POST", `/scan/${scanId}/cancel`),
};

// History
export const history = {
  list:      (params = {})           => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/history${q ? "?" + q : ""}`);
  },
  get:       (scanId)                => request("GET",    `/history/${scanId}`),
  cells:     (scanId, params = {})   => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/history/${scanId}/cells${q ? "?" + q : ""}`);
  },
  cell:      (scanId, cellId)        => request("GET",    `/history/${scanId}/cells/${cellId}`),
  delete:    (scanId, reason)        => request("DELETE", `/history/${scanId}?reason=${encodeURIComponent(reason)}`),
  reprocess: (scanId, deltaH, reason) =>
    request("POST", `/history/${scanId}/reprocess?new_delta_h_m=${deltaH}&reason=${encodeURIComponent(reason)}`),
};

// Datasets
export const datasets = {
  summary:    (scanId)           => request("GET", `/datasets/summary/${scanId}`),
  geojson:    (scanId, params={})=> {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/datasets/geojson/${scanId}${q ? "?" + q : ""}`);
  },
  rasterSpec: (scanId)           => request("GET", `/datasets/raster-spec/${scanId}`),
  exportData: (scanId, fmt="json")=> request("GET", `/datasets/export/${scanId}?format=${fmt}`),
};

// Twin
export const twin = {
  metadata: (scanId)        => request("GET",  `/twin/${scanId}`),
  query:    (scanId, body)  => request("POST", `/twin/${scanId}/query`, body),
  slice:    (scanId, depth, tol=50) =>
    request("GET", `/twin/${scanId}/slice?depth_m=${depth}&depth_tolerance_m=${tol}`),
  voxel:    (scanId, voxelId) => request("GET", `/twin/${scanId}/voxel/${voxelId}`),
  history:  (scanId)          => request("GET", `/twin/${scanId}/history`),
};

// Admin
export const admin = {
  listUsers:  ()                      => request("GET",   "/admin/users"),
  createUser: (body)                  => request("POST",  "/admin/users", body),
  updateRole: (userId, role, reason)  => request("PATCH", `/admin/users/${userId}/role`, { user_id: userId, new_role: role, reason }),
  auditLog:   (params = {})           => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/admin/audit${q ? "?" + q : ""}`);
  },
  bootstrapStatus: () => request("GET", "/admin/bootstrap-status"),
};