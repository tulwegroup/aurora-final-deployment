/**
 * auroraApiProxy — Proxy all Aurora API requests
 * Eliminates CORS issues by routing through Base44 backend
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

const AURORA_API = 'https://api.aurora-osi.com/api/v1';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (!user) {
      return Response.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const url = new URL(req.url);
    const path = url.pathname.replace('/auroraApiProxy', '');
    const query = url.search;
    const method = req.method;
    const body = method !== 'GET' && method !== 'HEAD' ? await req.text() : null;

    const auroraUrl = `${AURORA_API}${path}${query}`;
    const headers = new Headers(req.headers);
    headers.delete('host');
    headers.delete('cookie');

    const auroraRes = await fetch(auroraUrl, {
      method,
      headers,
      body,
    });

    const responseBody = await auroraRes.text();
    return new Response(responseBody, {
      status: auroraRes.status,
      headers: new Headers({
        'Content-Type': auroraRes.headers.get('content-type') || 'application/json',
      }),
    });
  } catch (error) {
    console.error('Proxy error:', error.message);
    return Response.json({ error: error.message }, { status: 500 });
  }
});