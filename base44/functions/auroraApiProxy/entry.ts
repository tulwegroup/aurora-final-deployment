/**
 * auroraApiProxy — Proxy all Aurora API requests
 * Eliminates CORS issues by routing through Base44 backend
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

const AURORA_API = (Deno.env.get('AURORA_API_URL') || Deno.env.get('AURORA_DB_HOST') || 'http://localhost:8000') + '/api/v1';

Deno.serve(async (req) => {
  try {

    const url = new URL(req.url);
    const path = url.searchParams.get('path') || url.pathname.replace('/auroraApiProxy', '');
    const method = url.searchParams.get('method') || req.method;
    const query = new URL(req.url).search.split('&').filter(p => !p.startsWith('path=') && !p.startsWith('method=')).join('&');
    const body = method !== 'GET' && method !== 'HEAD' ? await req.text() : null;

    const auroraUrl = `${AURORA_API}${path}${query}`;
    console.log('Proxying:', auroraUrl);
    const headers = new Headers(req.headers);
    headers.delete('host');
    headers.delete('cookie');
    headers.delete('origin');

    const auroraRes = await fetch(auroraUrl, {
      method,
      headers,
      body,
    });

    const responseBody = await auroraRes.text();
    
    // Log all responses for debugging
    console.log(`Aurora API ${method} ${path} -> ${auroraRes.status}`);
    if (!auroraRes.ok) {
      console.error(`Error response:`, responseBody.substring(0, 500));
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