/**
 * diagnoseAuroraRoutes — Test mounted Aurora API routes against production canonical domain
 * Diagnostic only: tests https://api.aurora-osi.io for route mounting and ALB target health
 * Safe to call from frontend; returns route availability + response codes
 */

const AURORA_CANONICAL = 'https://api.aurora-osi.io';

const ROUTES_TO_TEST = [
  { method: 'GET', path: '/health' },
  { method: 'GET', path: '/api/v1/health' },
  { method: 'GET', path: '/api/v1/scan/active' },
  { method: 'GET', path: '/api/v1/history' },
  { method: 'GET', path: '/api/v1/data-room/packages' },
  { method: 'GET', path: '/api/v1/gt/records' },
  { method: 'GET', path: '/api/v1/auth/me' },
  { method: 'GET', path: '/api/v1/admin/users' },
];

Deno.serve(async (req) => {
  try {
    const results = [];

    for (const route of ROUTES_TO_TEST) {
      try {
        const url = `${AURORA_CANONICAL}${route.path}`;
        const res = await fetch(url, {
          method: route.method,
          headers: {
            'Accept': 'application/json',
            'User-Agent': 'Aurora-Diagnostics/1.0',
          },
        });

        const body = await res.text();
        let parsed = null;
        try {
          parsed = JSON.parse(body);
        } catch {
          parsed = body.substring(0, 200);
        }

        results.push({
          path: route.path,
          method: route.method,
          status: res.status,
          statusText: res.statusText,
          contentType: res.headers.get('content-type'),
          body: parsed,
          url: url,
        });
      } catch (error) {
        results.push({
          path: route.path,
          method: route.method,
          error: error.message,
        });
      }
    }

    return Response.json({
      aurora_canonical: AURORA_CANONICAL,
      tested_at: new Date().toISOString(),
      routes: results,
      summary: {
        total: results.length,
        mounted: results.filter(r => r.status && r.status < 400).length,
        not_found: results.filter(r => r.status === 404).length,
        errors: results.filter(r => r.error).length,
      },
    });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});