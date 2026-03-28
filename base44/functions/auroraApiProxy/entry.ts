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
    let path = url.pathname.replace('/auroraApiProxy', '');
    // Remove duplicate /api/v1 if present in path
    if (path.startsWith('/api/v1')) {
      path = path.substring(7);
    }
    const query = url.search;
    const method = req.method;
    const body = method !== 'GET' && method !== 'HEAD' ? await req.text() : null;

    const auroraUrl = `${AURORA_API}${path}${query}`;
    console.log('Proxying:', auroraUrl);
    const headers = new Headers(req.headers);
    headers.delete('host');
    headers.delete('cookie');

    const auroraRes = await fetch(auroraUrl, {
      method,
      headers,
      body,
    });

    const responseBody = await auroraRes.text();
    
    // Log error responses for debugging
    if (!auroraRes.ok) {
      console.error(`Aurora API error ${auroraRes.status}:`, responseBody.substring(0, 500));
    }
    
    // Return raw response
    return new Response(responseBody, {
      status: auroraRes.status,
      statusText: auroraRes.statusText,
      headers: new Headers({
        'Content-Type': auroraRes.headers.get('content-type') || 'application/json',
        'Access-Control-Allow-Origin': '*',
      }),
    });
  } catch (error) {
    console.error('Proxy error:', error.message);
    return Response.json({ error: error.message }, { status: 500 });
  }
});