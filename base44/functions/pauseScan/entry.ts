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

    await base44.entities.ScanJob.update(jobs[0].id, { status: 'paused' });
    return Response.json({ status: 'paused' });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});