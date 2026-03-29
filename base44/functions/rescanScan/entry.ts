import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (!user) return Response.json({ error: 'Unauthorized' }, { status: 401 });

    const body = await req.json().catch(() => ({}));
    const { scan_id } = body;
    if (!scan_id) return Response.json({ error: 'scan_id required' }, { status: 400 });

    const jobs = await base44.entities.ScanJob.filter({ scan_id });
    if (!jobs?.length) return Response.json({ error: 'Scan not found' }, { status: 404 });

    const job = jobs[0];
    await base44.entities.ScanJob.update(job.id, { 
      status: 'running',
      tier_1_count: 0,
      tier_2_count: 0,
      tier_3_count: 0,
      display_acif_score: null,
      completed_at: null,
      results_geojson: null
    });
    return Response.json({ status: 'running' });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});