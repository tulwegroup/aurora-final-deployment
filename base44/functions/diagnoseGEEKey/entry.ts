import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { importPKCS8, SignJWT } from 'npm:jose@5.2.0';

Deno.serve(async (req) => {
  const base44 = createClientFromRequest(req);
  const user = await base44.auth.me();
  if (!user || user.role !== 'admin') return Response.json({ error: 'Admin only' }, { status: 403 });

  const keyJson = Deno.env.get('AURORA_GEE_SERVICE_ACCOUNT_KEY');
  if (!keyJson) return Response.json({ error: 'Secret not set' }, { status: 500 });

  const diag = {};

  let key;
  try {
    key = JSON.parse(keyJson);
    diag.json_parse = 'ok';
  } catch (e) {
    return Response.json({ error: 'JSON parse failed', detail: e.message }, { status: 500 });
  }

  diag.type = key.type;
  diag.project_id = key.project_id;
  diag.client_email = key.client_email;
  diag.private_key_id = key.private_key_id;
  diag.private_key_length = key.private_key?.length;
  diag.has_literal_backslash_n = key.private_key?.includes('\\n');
  diag.has_real_newlines = key.private_key?.includes('\n');
  diag.pem_preview = key.private_key?.substring(0, 60);

  const pem = key.private_key?.replace(/\\n/g, '\n');
  diag.pem_starts_ok = pem?.startsWith('-----BEGIN PRIVATE KEY-----');
  diag.pem_ends_ok = pem?.trimEnd().endsWith('-----END PRIVATE KEY-----');

  try {
    const privateKey = await importPKCS8(pem, 'RS256');
    diag.key_import = 'ok';

    const jwt = await new SignJWT({ scope: 'https://www.googleapis.com/auth/earthengine' })
      .setProtectedHeader({ alg: 'RS256' })
      .setIssuer(key.client_email)
      .setAudience('https://oauth2.googleapis.com/token')
      .setIssuedAt()
      .setExpirationTime('1h')
      .sign(privateKey);
    diag.jwt_sign = 'ok';

    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=${jwt}`,
    });
    const tokenData = await tokenRes.json();
    diag.gee_token_result = tokenData.access_token ? 'SUCCESS' : 'FAILED';
    if (!tokenData.access_token) diag.gee_error = tokenData;
  } catch (e) {
    diag.key_import = `FAILED: ${e.message}`;
  }

  return Response.json(diag);
});