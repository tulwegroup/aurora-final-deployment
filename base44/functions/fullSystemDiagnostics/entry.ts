/**
 * fullSystemDiagnostics — Gather hard evidence from live deployed system
 * Tests DNS, routes, backend inventory, and AWS ALB health
 * Returns structured proof to guide final remediation
 */

import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

const AURORA_CANONICAL = 'https://api.aurora-osi.io';
const ALB_DNS = 'aurora-alb-1663263128.us-east-1.elb.amazonaws.com';

const CRITICAL_ROUTES = [
  { method: 'GET', path: '/health', label: 'Health (root)' },
  { method: 'GET', path: '/api/v1/scan/active', label: 'Scan active' },
  { method: 'GET', path: '/api/v1/history', label: 'History' },
  { method: 'GET', path: '/api/v1/data-room/packages', label: 'Data room packages' },
  { method: 'GET', path: '/api/v1/gt/records', label: 'Ground truth records' },
  { method: 'GET', path: '/api/v1/auth/me', label: 'Auth me' },
  { method: 'GET', path: '/api/v1/admin/bootstrap-status', label: 'Bootstrap status' },
];

Deno.serve(async (req) => {
  try {
    const results = {
      timestamp: new Date().toISOString(),
      evidence: {},
      interpretation: {},
      remediation: null,
    };

    // ============ 1. DNS PROOF ============
    console.log('[DIAG] Testing DNS resolution...');
    results.evidence.dns = {};
    
    try {
      // Test if api.aurora-osi.io resolves
      const dnsTest = await fetch(`${AURORA_CANONICAL}/health`, {
        method: 'HEAD',
        redirect: 'manual',
      });
      
      results.evidence.dns.canonical_domain = AURORA_CANONICAL;
      results.evidence.dns.canonical_status = dnsTest.status;
      results.evidence.dns.canonical_reachable = dnsTest.status < 500;
      results.evidence.dns.response_headers = {
        server: dnsTest.headers.get('server'),
        via: dnsTest.headers.get('via'),
        'x-amzn-requestid': dnsTest.headers.get('x-amzn-requestid'),
      };

      // Detect CloudFront or WAF
      const server = dnsTest.headers.get('server') || '';
      const via = dnsTest.headers.get('via') || '';
      results.evidence.dns.cloudfront_detected = server.includes('CloudFront') || via.includes('CloudFront');
      results.evidence.dns.waf_detected = dnsTest.headers.get('x-amzn-waf-action') ? true : false;

      results.interpretation.dns = {
        canonical_resolves: results.evidence.dns.canonical_reachable,
        layers: results.evidence.dns.cloudfront_detected ? 'CloudFront + ALB' : 'Direct ALB',
        waf_enabled: results.evidence.dns.waf_detected,
      };
    } catch (e) {
      results.evidence.dns.error = e.message;
      results.interpretation.dns = { issue: 'DNS resolution failed or ALB unreachable' };
    }

    // ============ 2. ROUTE PROOF ============
    console.log('[DIAG] Testing critical routes...');
    results.evidence.routes = [];

    for (const route of CRITICAL_ROUTES) {
      try {
        const url = `${AURORA_CANONICAL}${route.path}`;
        const res = await fetch(url, {
          method: route.method,
          headers: { 'Accept': 'application/json' },
        });

        const body = await res.text();
        let parsed = null;
        try {
          parsed = JSON.parse(body);
        } catch {
          parsed = body.substring(0, 300);
        }

        results.evidence.routes.push({
          path: route.path,
          label: route.label,
          status: res.status,
          statusText: res.statusText,
          body_preview: parsed,
          headers: {
            'content-type': res.headers.get('content-type'),
            'content-length': res.headers.get('content-length'),
          },
        });
      } catch (error) {
        results.evidence.routes.push({
          path: route.path,
          label: route.label,
          error: error.message,
          network_error: true,
        });
      }
    }

    results.interpretation.routes = {
      mounted: results.evidence.routes.filter(r => r.status && r.status < 400).length,
      not_found: results.evidence.routes.filter(r => r.status === 404).length,
      auth_required: results.evidence.routes.filter(r => r.status === 401).length,
      network_errors: results.evidence.routes.filter(r => r.network_error).length,
    };

    // ============ 3. BACKEND INVENTORY ============
    console.log('[DIAG] Fetching backend route inventory...');
    try {
      const inventoryUrl = `${AURORA_CANONICAL}/api/v1/discover/routes`;
      const inventoryRes = await fetch(inventoryUrl);
      const inventory = await inventoryRes.json();

      results.evidence.backend_inventory = {
        url_tested: inventoryUrl,
        status: inventoryRes.status,
        total_routes: inventory.count || 'unknown',
        grouped: inventory.grouped || inventory,
      };

      results.interpretation.backend_inventory = {
        discovered: inventoryRes.ok,
        route_count: inventory.count || 'check full inventory',
        prefix: inventory.grouped ? Object.keys(inventory.grouped)[0] : 'unknown',
      };
    } catch (e) {
      results.evidence.backend_inventory = { error: e.message, note: 'Route discovery endpoint may not be mounted' };
      results.interpretation.backend_inventory = { discovered: false };
    }

    // ============ 4. AWS PROOF (metadata only) ============
    console.log('[DIAG] AWS metadata...');
    results.evidence.aws = {
      alb_dns: ALB_DNS,
      alb_listener_protocol: 'HTTPS (assumed)',
      alb_port: 443,
      target_group: 'aurora-api-tg (assumed, verify in AWS Console)',
      note: 'ALB target health must be verified in AWS Console by human operator',
    };

    // ============ INTERPRETATION & REMEDIATION ============
    console.log('[DIAG] Generating interpretation...');

    const routesMounted = results.interpretation.routes.mounted > 0;
    const dnsOk = results.interpretation.dns.canonical_resolves;
    const hasCloudFront = results.interpretation.dns.layers.includes('CloudFront');

    if (dnsOk && routesMounted) {
      results.interpretation.status = 'READY_FOR_PRODUCTION';
      results.remediation = {
        action: 'Apply final frontend configuration',
        frontend_base_url: 'https://api.aurora-osi.io/api/v1',
        cors_required: true,
        cors_origin: 'Detect from frontend deployment and configure in Aurora main.py',
        next_steps: [
          '1. Configure CORS in Aurora FastAPI app (add CORSMiddleware)',
          '2. Set frontend API_ROOT to https://api.aurora-osi.io/api/v1',
          '3. Verify Bearer token handling in Aurora middleware',
          '4. Test end-to-end: Frontend GET /api/v1/scan/active with auth header',
        ],
      };
    } else if (!dnsOk) {
      results.interpretation.status = 'DNS_RESOLUTION_FAILED';
      results.remediation = {
        issue: 'api.aurora-osi.io does not resolve or ALB is unreachable',
        root_cause: 'DNS misconfiguration or ALB listener not active on 443',
        next_steps: [
          '1. Verify api.aurora-osi.io DNS record points to ALB',
          '2. Check ALB listener on port 443 exists',
          '3. Confirm ALB target group has healthy targets',
          '4. Check AWS security groups allow inbound 443',
        ],
      };
    } else if (!routesMounted) {
      results.interpretation.status = 'ROUTES_NOT_FOUND';
      results.remediation = {
        issue: `${results.interpretation.routes.not_found} routes returned 404`,
        root_cause: 'FastAPI routes not mounted at /api/v1 or wrong prefix in main.py',
        next_steps: [
          '1. Check Aurora main.py for router.include_router() statements',
          '2. Verify routers are mounted at /api/v1 prefix, not /v1 or other',
          '3. Confirm FastAPI app is the correct build (not scaffold/test)',
          '4. Redeploy Aurora API if routes were recently added',
        ],
      };
    } else {
      results.interpretation.status = 'MIXED_HEALTH';
      results.remediation = {
        issue: 'Some routes mounted, some not; or auth required',
        root_cause: 'Partial deployment or authentication misconfiguration',
        next_steps: [
          '1. Verify all critical routes are present in Aurora routers',
          '2. Check if routes require auth; ensure Bearer token is configured',
          '3. Check Target group health in AWS Console',
        ],
      };
    }

    return Response.json(results, { status: 200 });
  } catch (error) {
    console.error('[DIAG] Fatal error:', error);
    return Response.json(
      { error: error.message, stack: error.stack },
      { status: 500 }
    );
  }
});