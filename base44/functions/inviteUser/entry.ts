import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (!user || user.role !== 'admin') {
      return Response.json({ error: 'Admin access required' }, { status: 403 });
    }

    const { email, role } = await req.json();

    if (!email) {
      return Response.json({ error: 'Missing email' }, { status: 400 });
    }

    await base44.users.inviteUser(email, role || 'user');

    return Response.json({
      status: 'success',
      message: `Invitation sent to ${email}`,
      role: role || 'user',
    });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});