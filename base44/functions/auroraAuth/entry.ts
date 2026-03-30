/**
 * auroraAuth — Obtain and cache an Aurora RS256 JWT
 *
 * Logs in to the Aurora backend using service account credentials
 * stored in secrets, returns an access token for use by auroraProxy.
 *
 * Secrets required:
 *   AURORA_BACKEND_URL
 *   AURORA_SERVICE_EMAIL     (e.g. admin@aurora.dev)
 *   AURORA_SERVICE_PASSWORD
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

// Module-level token cache (lives for duration of isolate warm period)
let _cachedToken = null;
let _tokenExpiry = 0;

const AURORA_BASE = (() => {
  let url = (Deno.env.get('AURORA_BACKEND_URL') || 'https://api.aurora-osi.com').trim().replace(/\/$/, '');
  if (!url.startsWith('http')) url = 'https://' + url;
  return url;
})();

async function getAuroraToken() {
  const now = Date.now() / 1000;
  if (_cachedToken && _tokenExpiry > now + 60) {
    return _cachedToken;
  }

  const email    = Deno.env.get('AURORA_SERVICE_EMAIL');
  const password = Deno.env.get('AURORA_SERVICE_PASSWORD');

  if (!email || !password) {
    throw new Error('AURORA_SERVICE_EMAIL and AURORA_SERVICE_PASSWORD secrets required');
  }

  const res = await fetch(`${AURORA_BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Aurora login failed (${res.status}): ${text}`);
  }

  const data = await res.json();
  _cachedToken = data.access_token;
  // Aurora tokens are 15-min by default (900s); cache for 14 min
  _tokenExpiry = now + (data.expires_in || 840);

  console.log('[auroraAuth] Token obtained, expires in', data.expires_in || 840, 'seconds');
  return _cachedToken;
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (!user) return Response.json({ error: 'Unauthorized' }, { status: 401 });

    const token = await getAuroraToken();
    return Response.json({ access_token: token });
  } catch (e) {
    console.error('[auroraAuth] Error:', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});