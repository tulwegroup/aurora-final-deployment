import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (!user) return Response.json({ error: 'Unauthorized' }, { status: 401 });

    const body = await req.json().catch(() => ({}));
    const { geometry, commodity = 'gold', resolution = 'medium', aoi_id = null } = body;

    if (!geometry?.coordinates) {
      return Response.json({ error: 'geometry required' }, { status: 400 });
    }

    // Get Aurora backend URL from environment or default to local dev
    const auroraBackendUrl = Deno.env.get('AURORA_BACKEND_URL') || 'http://localhost:8000';

    // Construct the scan request payload for Aurora backend
    const scanRequest = {
      commodity,
      scan_tier: resolution || 'medium',
      environment: 'onshore', // TODO: infer from geometry
      aoi_polygon: {
        type: 'Polygon',
        coordinates: geometry.coordinates,
      },
    };

    // Call Aurora backend /api/v1/scan/polygon endpoint
    const response = await fetch(`${auroraBackendUrl}/api/v1/scan/polygon`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${user.email}`, // Pass user identity for audit trail
      },
      body: JSON.stringify(scanRequest),
    });

    if (!response.ok) {
      const errText = await response.text();
      console.error('[SCAN-BACKEND-ERROR]', response.status, errText);
      return Response.json(
        { error: `Aurora backend error: ${response.status}`, detail: errText },
        { status: response.status }
      );
    }

    const result = await response.json();

    // Return scan submission response to frontend
    return Response.json({
      scan_id: result.scan_id,
      scan_job_id: result.scan_job_id,
      status: result.status,
      submitted_at: result.submitted_at,
    });
  } catch (e) {
    console.error('[SCAN-ERROR]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});