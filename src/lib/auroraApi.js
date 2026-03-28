/**
 * Aurora OSI vNext — API Client
 * Phase P §P.1
 *
 * Thin HTTP client wrapping all aurora_vnext FastAPI endpoints.
 * CONSTITUTIONAL RULE: This module performs ZERO scientific computation.
 * It only issues requests and returns responses verbatim.
 * No threshold defaults, no ACIF arithmetic, no tier recounting.
 */

// Route through Base44 backend proxy to bypass CORS
const BASE = '/api/functions/auroraApiProxy';

export const API_ROOT = 'https://api.aurora-osi.com';

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
  
  // Call proxy with path as query param
  const url = new URL(BASE, window.location.origin);
  url.searchParams.append('path', path);
  url.searchParams.append('method', method);
  
  const res = await fetch(url.toString(), {
    method: 'POST',
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

// AOI
export const aoi = {
  validate:   (geometry, maxAreaKm2)  => request("POST", "/aoi/validate", { geometry, max_area_km2: maxAreaKm2 }),
  save:       (body)                  => request("POST", "/aoi", body),
  get:        (aoiId)                 => request("GET",  `/aoi/${aoiId}`),
  estimate:   (aoiId)                 => request("GET",  `/aoi/${aoiId}/estimate`),
  submitScan: (aoiId, body)           => request("POST", `/aoi/${aoiId}/submit-scan`, body),
  verify:     (aoiId)                 => request("GET",  `/aoi/${aoiId}/verify`),
};

// Map Exports
export const mapExports = {
  layers:   ()              => request("GET",  "/exports/layers"),
  kml:      (scanId, body)  => request("POST", `/exports/${scanId}/kml`,     body),
  kmz:      (scanId, body)  => request("POST", `/exports/${scanId}/kmz`,     body),
  geojson:  (scanId, body)  => request("POST", `/exports/${scanId}/geojson`, body),
};

// Reports
export const reports = {
  generate: (scanId, audience) => request("POST", `/reports/${scanId}`, { audience }),
  list:     (scanId)           => request("GET",  `/reports/${scanId}`),
  get:      (scanId, reportId) => request("GET",  `/reports/${scanId}/${reportId}`),
  audit:    (scanId, reportId) => request("GET",  `/reports/${scanId}/${reportId}/audit`),
};

// Portfolio
export const portfolio = {
  list:        (params = {})     => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/portfolio${q ? "?" + q : ""}`);
  },
  snapshot:    (params = {})     => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/portfolio/snapshot${q ? "?" + q : ""}`);
  },
  weightConfig: ()               => request("GET",  "/portfolio/weight-config"),
  riskSummary:  (commodity)      => request("GET",  `/portfolio/risk-summary${commodity ? "?commodity=" + commodity : ""}`),
  get:          (entryId)        => request("GET",  `/portfolio/${entryId}`),
  assemble:     (body)           => request("POST", "/portfolio", body),
};

// Ground Truth Admin
export const groundTruth = {
  listRecords:    (params = {})        => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/gt/records${q ? "?" + q : ""}`);
  },
  getRecord:      (recordId)           => request("GET",  `/gt/records/${recordId}`),
  submitRecord:   (body)               => request("POST", "/gt/records", body),
  approveRecord:  (recordId, reason)   => request("POST", `/gt/records/${recordId}/approve`, { reason }),
  rejectRecord:   (recordId, reason)   => request("POST", `/gt/records/${recordId}/reject`,  { reason }),
  recordHistory:  (recordId)           => request("GET",  `/gt/records/${recordId}/history`),
  auditLog:       ()                   => request("GET",  "/gt/audit"),
  calVersions:    ()                   => request("GET",  "/gt/calibration/versions"),
  activateCal:    (versionId)          => request("POST", `/gt/calibration/versions/${versionId}/activate`),
  revokeCal:      (versionId, reason)  => request("POST", `/gt/calibration/versions/${versionId}/revoke`, { reason }),
};

// Canonical Export
export const canonicalExport = {
  json:    (scanId) => `${BASE}/export/${scanId}/json`,
  geojson: (scanId) => `${BASE}/export/${scanId}/geojson`,
  csv:     (scanId) => `${BASE}/export/${scanId}/csv`,
};

// Data Room
export const dataRoom = {
  createPackage: (body)       => request("POST",   "/data-room/packages", body),
  listPackages:  (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/data-room/packages${q ? "?" + q : ""}`);
  },
  getPackage:    (packageId)  => request("GET",    `/data-room/packages/${packageId}`),
  listArtifacts: (packageId)  => request("GET",    `/data-room/packages/${packageId}/artifacts`),
  createLink:    (packageId, body) => request("POST", `/data-room/packages/${packageId}/links`, body),
  revokeLink:    (linkId)     => request("DELETE",  `/data-room/links/${linkId}`),
  listLinks:     (packageId)  => request("GET",    `/data-room/links${packageId ? "?package_id=" + packageId : ""}`),
};