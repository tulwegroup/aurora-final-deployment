/**
 * Aurora OSI vNext — API Client
 *
 * All browser requests route through the Base44 auroraProxy backend function
 * to avoid CORS entirely. The proxy forwards server-to-server to Aurora.
 */
import { base44 } from '@/api/base44Client';

export const API_ROOT = 'https://api.aurora-osi.com';

let _accessToken = null;

export function setAccessToken(token) {
  _accessToken = token;
}

export function clearAccessToken() {
  _accessToken = null;
}

async function request(method, path, body = null) {
  console.log(`[Aurora Proxy] ${method} ${path}`);
  const res = await base44.functions.invoke('auroraProxy', {
    method,
    path,
    payload: body,
    token: _accessToken,
  });
  const { data, status, ok } = res.data;
  console.log(`[Aurora Proxy] ${method} ${path} -> ${status}`);
  if (!ok) {
    const detail = (typeof data === 'object' && data?.detail) ? data.detail : `Request failed with ${status}`;
    const error = new Error(detail);
    error.status = status;
    throw error;
  }
  return data;
}

// Auth
export const auth = {
  login:  (email, password) => request("POST", "/auth/login",  { email, password }),
  logout: ()                 => request("POST", "/auth/logout"),
  me:     ()                 => request("GET",  "/auth/me"),
};

// Scans
export const scans = {
  submitGrid:    (body)    => request("POST", "/api/v1/scan/grid",         body),
  submitPolygon: (body)    => request("POST", "/api/v1/scan/polygon",      body),
  status:        (scanId)  => request("GET",  `/api/v1/scan/status/${scanId}`),
  active:        ()        => request("GET",  "/api/v1/scan/active"),
  cancel:        (scanId)  => request("POST", `/api/v1/scan/${scanId}/cancel`),
};

// History
export const history = {
  list:      (params = {})           => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/api/v1/history${q ? "?" + q : ""}`);
  },
  get:       (scanId)                => request("GET",    `/api/v1/history/${scanId}`),
  cells:     (scanId, params = {})   => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/api/v1/history/${scanId}/cells${q ? "?" + q : ""}`);
  },
  cell:      (scanId, cellId)        => request("GET",    `/api/v1/history/${scanId}/cells/${cellId}`),
  delete:    (scanId, reason)        => request("DELETE", `/api/v1/history/${scanId}?reason=${encodeURIComponent(reason)}`),
  reprocess: (scanId, deltaH, reason) =>
    request("POST", `/api/v1/history/${scanId}/reprocess?new_delta_h_m=${deltaH}&reason=${encodeURIComponent(reason)}`),
};

// Datasets
export const datasets = {
  summary:    (scanId)           => request("GET", `/api/v1/datasets/summary/${scanId}`),
  geojson:    (scanId, params={})=> {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/api/v1/datasets/geojson/${scanId}${q ? "?" + q : ""}`);
  },
  rasterSpec: (scanId)           => request("GET", `/api/v1/datasets/raster-spec/${scanId}`),
  exportData: (scanId, fmt="json")=> request("GET", `/api/v1/datasets/export/${scanId}?format=${fmt}`),
};

// Twin
export const twin = {
  metadata: (scanId)        => request("GET",  `/api/v1/twin/${scanId}`),
  query:    (scanId, body)  => request("POST", `/api/v1/twin/${scanId}/query`, body),
  slice:    (scanId, depth, tol=50) =>
    request("GET", `/api/v1/twin/${scanId}/slice?depth_m=${depth}&depth_tolerance_m=${tol}`),
  voxel:    (scanId, voxelId) => request("GET", `/api/v1/twin/${scanId}/voxel/${voxelId}`),
  history:  (scanId)          => request("GET", `/api/v1/twin/${scanId}/history`),
};

// Admin
export const admin = {
  listUsers:  ()                      => request("GET",   "/api/v1/admin/users"),
  createUser: (body)                  => request("POST",  "/api/v1/admin/users", body),
  updateRole: (userId, role, reason)  => request("PATCH", `/api/v1/admin/users/${userId}/role`, { user_id: userId, new_role: role, reason }),
  auditLog:   (params = {})           => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/api/v1/admin/audit${q ? "?" + q : ""}`);
  },
  bootstrapStatus: () => request("GET", "/api/v1/admin/bootstrap-status"),
};

// AOI
export const aoi = {
  validate:   (geometry, maxAreaKm2)  => request("POST", "/api/v1/aoi/validate", { geometry, max_area_km2: maxAreaKm2 }),
  save:       (body)                  => request("POST", "/api/v1/aoi", body),
  get:        (aoiId)                 => request("GET",  `/api/v1/aoi/${aoiId}`),
  estimate:   (aoiId)                 => request("GET",  `/api/v1/aoi/${aoiId}/estimate`),
  submitScan: (aoiId, body)           => request("POST", `/api/v1/aoi/${aoiId}/submit-scan`, body),
  verify:     (aoiId)                 => request("GET",  `/api/v1/aoi/${aoiId}/verify`),
};

// Map Exports
export const mapExports = {
  layers:   ()              => request("GET",  "/api/v1/exports/layers"),
  kml:      (scanId, body)  => request("POST", `/api/v1/exports/${scanId}/kml`,     body),
  kmz:      (scanId, body)  => request("POST", `/api/v1/exports/${scanId}/kmz`,     body),
  geojson:  (scanId, body)  => request("POST", `/api/v1/exports/${scanId}/geojson`, body),
};

// Reports
export const reports = {
  generate: (scanId, audience) => request("POST", `/api/v1/reports/${scanId}`, { audience }),
  list:     (scanId)           => request("GET",  `/api/v1/reports/${scanId}`),
  get:      (scanId, reportId) => request("GET",  `/api/v1/reports/${scanId}/${reportId}`),
  audit:    (scanId, reportId) => request("GET",  `/api/v1/reports/${scanId}/${reportId}/audit`),
};

// Portfolio
export const portfolio = {
  list:        (params = {})     => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/api/v1/portfolio${q ? "?" + q : ""}`);
  },
  snapshot:    (params = {})     => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/api/v1/portfolio/snapshot${q ? "?" + q : ""}`);
  },
  weightConfig: ()               => request("GET",  "/api/v1/portfolio/weight-config"),
  riskSummary:  (commodity)      => request("GET",  `/api/v1/portfolio/risk-summary${commodity ? "?commodity=" + commodity : ""}`),
  get:          (entryId)        => request("GET",  `/api/v1/portfolio/${entryId}`),
  assemble:     (body)           => request("POST", "/api/v1/portfolio", body),
};

// Ground Truth Admin
export const groundTruth = {
  listRecords:    (params = {})        => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/api/v1/gt/records${q ? "?" + q : ""}`);
  },
  getRecord:      (recordId)           => request("GET",  `/api/v1/gt/records/${recordId}`),
  submitRecord:   (body)               => request("POST", "/api/v1/gt/records", body),
  approveRecord:  (recordId, reason)   => request("POST", `/api/v1/gt/records/${recordId}/approve`, { reason }),
  rejectRecord:   (recordId, reason)   => request("POST", `/api/v1/gt/records/${recordId}/reject`,  { reason }),
  recordHistory:  (recordId)           => request("GET",  `/api/v1/gt/records/${recordId}/history`),
  auditLog:       ()                   => request("GET",  "/api/v1/gt/audit"),
  calVersions:    ()                   => request("GET",  "/api/v1/gt/calibration/versions"),
  activateCal:    (versionId)          => request("POST", `/api/v1/gt/calibration/versions/${versionId}/activate`),
  revokeCal:      (versionId, reason)  => request("POST", `/api/v1/gt/calibration/versions/${versionId}/revoke`, { reason }),
};

// Canonical Export
export const canonicalExport = {
  json:    (scanId) => `${BASE}/export/${scanId}/json`,
  geojson: (scanId) => `${BASE}/export/${scanId}/geojson`,
  csv:     (scanId) => `${BASE}/export/${scanId}/csv`,
};

// Data Room
export const dataRoom = {
  createPackage: (body)       => request("POST",   "/api/v1/data-room/packages", body),
  listPackages:  (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request("GET", `/api/v1/data-room/packages${q ? "?" + q : ""}`);
  },
  getPackage:    (packageId)  => request("GET",    `/api/v1/data-room/packages/${packageId}`),
  listArtifacts: (packageId)  => request("GET",    `/api/v1/data-room/packages/${packageId}/artifacts`),
  createLink:    (packageId, body) => request("POST", `/api/v1/data-room/packages/${packageId}/links`, body),
  revokeLink:    (linkId)     => request("DELETE",  `/api/v1/data-room/links/${linkId}`),
  listLinks:     (packageId)  => request("GET",    `/api/v1/data-room/links${packageId ? "?package_id=" + packageId : ""}`),
};