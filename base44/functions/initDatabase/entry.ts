/**
 * initDatabase — Initialize Aurora database schema, indexes, and seed data
 * Runs PostgreSQL migrations for canonical scans, twins, and audit tables
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

const DB_HOST = Deno.env.get('AURORA_DB_HOST');
const DB_PORT = Deno.env.get('AURORA_DB_PORT') || '5432';
const DB_NAME = Deno.env.get('AURORA_DB_NAME') || 'aurora_db';
const DB_USER = Deno.env.get('AURORA_DB_USER') || 'aurora_admin';
const DB_PASSWORD = Deno.env.get('AURORA_DB_PASSWORD');

async function executeSQL(sql) {
  const client = new Deno.Command('psql', {
    args: [
      `-h`, DB_HOST,
      `-p`, DB_PORT,
      `-U`, DB_USER,
      `-d`, DB_NAME,
      `-c`, sql
    ],
    env: { PGPASSWORD: DB_PASSWORD },
    stdin: 'null',
    stdout: 'piped',
    stderr: 'piped'
  });

  const proc = client.spawn();
  const output = await proc.output();
  const status = proc.status;

  if (!status.success) {
    const err = new TextDecoder().decode(output.stderr);
    throw new Error(`SQL error: ${err}`);
  }

  return new TextDecoder().decode(output.stdout);
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (user?.role !== 'admin') {
      return Response.json({ error: 'Forbidden: Admin access required' }, { status: 403 });
    }

    if (!DB_HOST || !DB_PASSWORD) {
      return Response.json({ error: 'Missing AURORA_DB_HOST or AURORA_DB_PASSWORD' }, { status: 400 });
    }

    const migrations = [
      // Canonical scans table
      `CREATE TABLE IF NOT EXISTS canonical_scans (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        scan_id VARCHAR(255) NOT NULL UNIQUE,
        commodity VARCHAR(100) NOT NULL,
        aoi_geojson JSONB NOT NULL,
        status VARCHAR(50) DEFAULT 'processing',
        total_voxels INT,
        mean_acif_score FLOAT,
        acif_variance FLOAT,
        tier_distribution JSONB,
        veto_stats JSONB,
        created_date TIMESTAMPTZ DEFAULT NOW(),
        updated_date TIMESTAMPTZ DEFAULT NOW(),
        created_by VARCHAR(255)
      );`,

      // Digital twin voxels table
      `CREATE TABLE IF NOT EXISTS voxels (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        scan_id VARCHAR(255) NOT NULL,
        voxel_id VARCHAR(255) NOT NULL,
        depth_m FLOAT,
        lat_center FLOAT,
        lon_center FLOAT,
        commodity_probs JSONB,
        kernel_weight FLOAT,
        expected_density FLOAT,
        temporal_score FLOAT,
        physics_residual FLOAT,
        uncertainty FLOAT,
        source_cell_id VARCHAR(255),
        created_date TIMESTAMPTZ DEFAULT NOW()
      );`,

      // Audit log table
      `CREATE TABLE IF NOT EXISTS audit_log (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_email VARCHAR(255),
        action VARCHAR(100) NOT NULL,
        resource_type VARCHAR(100),
        resource_id VARCHAR(255),
        details JSONB,
        created_date TIMESTAMPTZ DEFAULT NOW()
      );`,

      // Indexes for performance
      `CREATE INDEX IF NOT EXISTS idx_scans_commodity ON canonical_scans(commodity);`,
      `CREATE INDEX IF NOT EXISTS idx_scans_status ON canonical_scans(status);`,
      `CREATE INDEX IF NOT EXISTS idx_voxels_scan_id ON voxels(scan_id);`,
      `CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_email);`,
      `CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);`,
    ];

    const results = [];
    for (const migration of migrations) {
      try {
        await executeSQL(migration);
        results.push({ migration: migration.slice(0, 50) + '...', status: 'ok' });
      } catch (e) {
        results.push({ migration: migration.slice(0, 50) + '...', error: e.message });
      }
    }

    return Response.json({
      status: 'success',
      message: 'Database initialization complete',
      migrations_applied: results.filter(r => r.status === 'ok').length,
      total: results.length,
      details: results
    });

  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});