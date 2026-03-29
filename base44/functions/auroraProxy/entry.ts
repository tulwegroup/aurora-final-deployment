/**
 * Aurora API Proxy
 * Forwards all requests to the Aurora backend server-to-server,
 * eliminating browser CORS issues entirely.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

const AURORA_BASE = (Deno.env.get('AURORA_BACKEND_URL') || '').trim() || 'https://api.aurora-osi.com';
const normalizedBase = (() => {
  let url = AURORA_BASE.replace(/\/$/, ''); // Remove trailing slash
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    url = `https://${url}`; // Add protocol if missing
  }
  return url;
})();

Deno.serve(async (req) => {
  const base44 = createClientFromRequest(req);

  // Parse the target path and method from the request body
  const body = await req.json().catch(() => ({}));
  const { method = 'GET', path = '/', payload = null, token = null } = body;

  const url = `${normalizedBase}${path}`;

  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const fetchOptions = {
    method,
    headers,
    body: payload ? JSON.stringify(payload) : undefined,
  };

  console.log(`[auroraProxy] ${method} ${url}`);
  const res = await fetch(url, fetchOptions);
  const contentType = res.headers.get('content-type') || '';

  let data;
  if (contentType.includes('application/json')) {
    data = await res.json();
  } else {
    data = await res.text();
  }

  console.log(`[auroraProxy] Response: ${res.status}`);
  return Response.json(
    { data, status: res.status, ok: res.ok },
    { status: 200 }
  );
});