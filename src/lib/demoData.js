/**
 * Ghana Gold Demo — pre-baked canonical responses for demo mode.
 * These mirror the exact shape of Aurora API responses so the workflow
 * renders identically to production. No scientific computation here —
 * values are representative stored outputs only.
 */

export const DEMO_SCAN_ID = "DEMO-GHA-GOLD-001";

export const GHANA_AOI = {
  aoi_id: "aoi_ghana_ashanti_001",
  area_km2: 1240.5,
  environment_type: "onshore_tropical",
  geometry_hash: "a3f8c2d1e9b7045f3c8a",
  bbox: { min_lat: 5.8, max_lat: 7.2, min_lon: -2.6, max_lon: -1.1 },
  crs: "EPSG:4326",
  validated_at: new Date().toISOString(),
  cell_count_estimate: 4962,
};

export const GHANA_COST_ESTIMATE = {
  estimated_cells: 4962,
  cost_per_km2_usd: 0.0024,
  estimated_cost_usd: 2.98,
  cost_tier: "standard",
  cost_model_version: "v2.1.0",
};

export const GHANA_SCAN_RESULT = {
  scan_id: DEMO_SCAN_ID,
  status: "completed",
  system_status: "PASS_CONFIRMED",
  commodity: "gold",
  scan_tier: "TIER_1",
  acif_mean: 0.7841,
  veto_count: 47,
  total_cells: 4962,
  tier_counts: {
    TIER_1: 1823,
    TIER_2: 2108,
    TIER_3: 784,
    BELOW:  247,
  },
  completed_at: new Date().toISOString(),
  calibration_version_id: "cal_v3.2.1",
  mineral_system: "orogenic_gold",
  region: "Ashanti Belt, Ghana",
  notes: "Demo scan — Ashanti Belt greenstone terrain. Values are representative stored outputs.",
};

export const GHANA_PACKAGE = {
  package_id:            "pkg_ghana_ashanti_demo_001",
  package_hash:          "d4e9a1b2c3f8071e5a3d",
  calibration_version_id: "cal_v3.2.1",
  cost_model_version:    "v2.1.0",
  artifacts: [
    { artifact_id: "art_001", artifact_type: "canonical_scan_json",  sha256_hash: "3f8a1c2d9b4e7f06a1c3" },
    { artifact_id: "art_002", artifact_type: "geojson_layer",        sha256_hash: "9b4e7a1c3f8d2b0e6a4c" },
    { artifact_id: "art_003", artifact_type: "geological_report",    sha256_hash: "1c3f8a4e2b9d7c0f5a3e" },
    { artifact_id: "art_004", artifact_type: "audit_trail_bundle",   sha256_hash: "b2d9a3f1c8e4071b6a2c" },
  ],
};

export const GHANA_DELIVERY_LINK = {
  link_id:       "lnk_ghana_demo_001",
  status:        "ACTIVE",
  expires_at:    new Date(Date.now() + 48 * 3600 * 1000).toISOString(),
  max_downloads: null,
  access_url:    "https://data.aurora-osi.com/packages/demo/ghana-ashanti-gold-001",
};

// Pre-fill bbox coords for the AOI step
export const GHANA_BBOX = {
  minLat: "5.8",
  maxLat: "7.2",
  minLon: "-2.6",
  maxLon: "-1.1",
};