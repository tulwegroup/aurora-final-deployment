/**
 * probeAPI — Directly probe the ALB and API endpoints to diagnose connectivity
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') {
      return Response.json({ error: 'Forbidden' }, { status: 403 });
    }

    const ALB_DNS = 'aurora-alb-1663263128.us-east-1.elb.amazonaws.com';
    const results = {};

    // Probe ALB directly (HTTP, no cert needed)
    const albTargets = [
      { label: 'ALB HTTP root', url: `http://${ALB_DNS}/` },
      { label: 'ALB HTTP health', url: `http://${ALB_DNS}/health/live` },
      { label: 'API HTTPS root', url: 'https://api.aurora-osi.com/' },
      { label: 'API HTTPS health', url: 'https://api.aurora-osi.com/health/live' },
    ];

    for (const target of albTargets) {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 8000);
        const res = await fetch(target.url, { signal: controller.signal, redirect: 'follow' });
        clearTimeout(timer);
        const body = await res.text().catch(() => '');
        results[target.label] = {
          status: res.status,
          ok: res.ok,
          body: body.slice(0, 200),
        };
      } catch (e) {
        results[target.label] = { error: e.message, ok: false };
      }
    }

    return Response.json({ results, timestamp: new Date().toISOString() });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});