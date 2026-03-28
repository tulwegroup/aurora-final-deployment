/**
 * auroraRouteInventory — Production route catalog
 * Exposes safe metadata about mounted Aurora API routes
 * Useful for diagnosing route/ALB target routing mismatches
 */

const AURORA_CANONICAL = 'https://api.aurora-osi.io';

// Expected mounted routes based on Aurora FastAPI schema
const EXPECTED_ROUTES = {
  health: [
    { method: 'GET', path: '/health', description: 'Liveness check' },
    { method: 'GET', path: '/api/v1/health', description: 'Health endpoint' },
  ],
  auth: [
    { method: 'POST', path: '/api/v1/auth/login', description: 'User login' },
    { method: 'POST', path: '/api/v1/auth/logout', description: 'User logout' },
    { method: 'GET', path: '/api/v1/auth/me', description: 'Current user' },
  ],
  scans: [
    { method: 'POST', path: '/api/v1/scan/grid', description: 'Submit grid scan' },
    { method: 'POST', path: '/api/v1/scan/polygon', description: 'Submit polygon scan' },
    { method: 'GET', path: '/api/v1/scan/active', description: 'Active scans queue' },
    { method: 'GET', path: '/api/v1/scan/status/{scanId}', description: 'Scan status' },
    { method: 'POST', path: '/api/v1/scan/{scanId}/cancel', description: 'Cancel scan' },
  ],
  history: [
    { method: 'GET', path: '/api/v1/history', description: 'List scans' },
    { method: 'GET', path: '/api/v1/history/{scanId}', description: 'Get scan record' },
    { method: 'GET', path: '/api/v1/history/{scanId}/cells', description: 'Scan cells' },
    { method: 'DELETE', path: '/api/v1/history/{scanId}', description: 'Delete scan' },
  ],
  datasets: [
    { method: 'GET', path: '/api/v1/datasets/summary/{scanId}', description: 'Dataset summary' },
    { method: 'GET', path: '/api/v1/datasets/geojson/{scanId}', description: 'GeoJSON export' },
    { method: 'GET', path: '/api/v1/datasets/raster-spec/{scanId}', description: 'Raster spec' },
  ],
  twin: [
    { method: 'GET', path: '/api/v1/twin/{scanId}', description: 'Twin metadata' },
    { method: 'POST', path: '/api/v1/twin/{scanId}/query', description: 'Query twin' },
    { method: 'GET', path: '/api/v1/twin/{scanId}/slice', description: 'Twin slice' },
  ],
  reports: [
    { method: 'POST', path: '/api/v1/reports/{scanId}', description: 'Generate report' },
    { method: 'GET', path: '/api/v1/reports/{scanId}', description: 'List reports' },
    { method: 'GET', path: '/api/v1/reports/{scanId}/{reportId}', description: 'Get report' },
  ],
  portfolio: [
    { method: 'GET', path: '/api/v1/portfolio', description: 'Portfolio list' },
    { method: 'GET', path: '/api/v1/portfolio/snapshot', description: 'Portfolio snapshot' },
    { method: 'POST', path: '/api/v1/portfolio', description: 'Assemble portfolio' },
  ],
  groundTruth: [
    { method: 'GET', path: '/api/v1/gt/records', description: 'Ground truth records' },
    { method: 'POST', path: '/api/v1/gt/records', description: 'Submit GT record' },
    { method: 'POST', path: '/api/v1/gt/records/{recordId}/approve', description: 'Approve GT' },
    { method: 'GET', path: '/api/v1/gt/calibration/versions', description: 'Calibration versions' },
  ],
  dataRoom: [
    { method: 'POST', path: '/api/v1/data-room/packages', description: 'Create package' },
    { method: 'GET', path: '/api/v1/data-room/packages', description: 'List packages' },
    { method: 'GET', path: '/api/v1/data-room/packages/{packageId}', description: 'Get package' },
    { method: 'POST', path: '/api/v1/data-room/packages/{packageId}/links', description: 'Create link' },
  ],
  admin: [
    { method: 'GET', path: '/api/v1/admin/users', description: 'List users' },
    { method: 'POST', path: '/api/v1/admin/users', description: 'Create user' },
    { method: 'PATCH', path: '/api/v1/admin/users/{userId}/role', description: 'Update role' },
    { method: 'GET', path: '/api/v1/admin/audit', description: 'Audit log' },
  ],
  aoi: [
    { method: 'POST', path: '/api/v1/aoi/validate', description: 'Validate AOI' },
    { method: 'POST', path: '/api/v1/aoi', description: 'Save AOI' },
    { method: 'GET', path: '/api/v1/aoi/{aoiId}', description: 'Get AOI' },
    { method: 'POST', path: '/api/v1/aoi/{aoiId}/submit-scan', description: 'Submit scan' },
  ],
  mapExports: [
    { method: 'GET', path: '/api/v1/exports/layers', description: 'Export layers' },
    { method: 'POST', path: '/api/v1/exports/{scanId}/kml', description: 'KML export' },
    { method: 'POST', path: '/api/v1/exports/{scanId}/geojson', description: 'GeoJSON export' },
  ],
};

Deno.serve(async (req) => {
  try {
    // Count total expected routes
    let total = 0;
    Object.values(EXPECTED_ROUTES).forEach(group => {
      total += group.length;
    });

    return Response.json({
      canonical_base: AURORA_CANONICAL,
      api_version: 'v1',
      catalog_generated: new Date().toISOString(),
      summary: {
        total_expected_routes: total,
        route_groups: Object.keys(EXPECTED_ROUTES).length,
      },
      routes_by_domain: EXPECTED_ROUTES,
      deployment_notes: {
        frontend_base_url: 'https://api.aurora-osi.io/api/v1',
        protocol: 'https',
        cors_origin: 'Frontend origin to be configured in Aurora FastAPI app.add_middleware()',
        alb_target_group: 'aurora-api-tg pointing to ECS service',
        route_mounting: 'All routes mounted at FastAPI root; no additional prefix required',
      },
      diagnostics_guide: {
        step_1: 'Verify ALB target health in AWS Console',
        step_2: 'Check FastAPI app.include_router() mounts in main.py',
        step_3: 'Confirm api.aurora-osi.io DNS points to ALB',
        step_4: 'Test: curl https://api.aurora-osi.io/health',
        step_5: 'If 404: check route prefix in FastAPI routers',
        step_6: 'If connection refused: verify ALB listens on 443 with HTTPS',
      },
    });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});