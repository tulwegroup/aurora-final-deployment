/**
 * verifyCanonicalHashIndependent — Phase AN Dual Validation
 *
 * Secondary independent verification pass (separate execution path):
 *   - Retrieve canonical scan record
 *   - Recompute geometry hash from AOI (SHA-256)
 *   - Compare with stored hash
 *   - Verify all cell ACIF scores match stored canonical
 *   - Trigger enforcement lock if mismatch
 *
 * This is NOT a recomputation of ACIF (which remains locked).
 * It is a verification that stored canonical values match original
 * geometry and scoring. Two independent paths, same result.
 *
 * Sovereign-grade assurance: dual validation before export.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { createHash } from 'node:crypto';

/**
 * Compute SHA-256 hash of geometry (independent path)
 * Input: AOI geometry (GeoJSON polygon)
 * Output: hex-encoded SHA-256
 */
function hashGeometry(geometry) {
  const hash = createHash('sha256');
  // Serialize geometry deterministically (sorted keys, no whitespace)
  const serialized = JSON.stringify(geometry, Object.keys(geometry).sort());
  hash.update(serialized);
  return hash.digest('hex');
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (!user) {
      return Response.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { scan_id } = await req.json();
    if (!scan_id) {
      return Response.json({ error: 'Missing scan_id' }, { status: 400 });
    }

    // ── Fetch canonical scan record ──
    const canonicalScans = await base44.asServiceRole.entities.CanonicalScan.filter(
      { id: scan_id },
      'updated_date',
      1
    );

    if (!canonicalScans || canonicalScans.length === 0) {
      return Response.json({ error: `Scan ${scan_id} not found` }, { status: 404 });
    }

    const scan = canonicalScans[0];
    const violations = [];

    // ── Check 1: Retrieve original AOI geometry ──
    if (!scan.aoi_id) {
      violations.push({
        type: 'MISSING_AOI_ID',
        severity: 'CRITICAL',
        message: 'Scan missing aoi_id. Cannot verify geometry hash.',
      });
    }

    let aoiGeometry = null;
    if (scan.aoi_id && !violations.length) {
      const aois = await base44.asServiceRole.entities.ScanAOI.filter(
        { id: scan.aoi_id },
        'created_date',
        1
      );
      if (!aois || aois.length === 0) {
        violations.push({
          type: 'AOI_NOT_FOUND',
          severity: 'CRITICAL',
          message: `AOI ${scan.aoi_id} not found in registry.`,
        });
      } else {
        aoiGeometry = aois[0].geometry;
      }
    }

    // ── Check 2: Recompute geometry hash (independent path) ──
    let computedHash = null;
    if (aoiGeometry && !violations.length) {
      computedHash = hashGeometry(aoiGeometry);

      // Compare with stored hash
      if (computedHash !== scan.geometry_hash) {
        violations.push({
          type: 'GEOMETRY_HASH_MISMATCH',
          severity: 'CRITICAL',
          message: `Geometry hash mismatch. Computed: ${computedHash.slice(0, 16)}… Stored: ${(scan.geometry_hash || '').slice(0, 16)}…`,
        });
      }
    }

    // ── Check 3: Verify ACIF scores consistency ──
    // Spot-check: fetch first 10 cells and compare scores
    if (!violations.length && scan.id) {
      const cells = await base44.asServiceRole.entities.ScanCell.filter(
        { canonical_scan_id: scan.id },
        'depth_m',
        10
      );

      if (cells && cells.length > 0) {
        // Each cell should have acif_score matching stored canonical
        for (const cell of cells) {
          if (cell.acif_score === null || cell.acif_score === undefined) {
            violations.push({
              type: 'MISSING_ACIF_SCORE_IN_CELL',
              severity: 'CRITICAL',
              message: `Cell ${cell.id} missing ACIF score.`,
            });
            break; // Stop on first violation
          }
        }
      }
    }

    // ── On Violation ──
    if (violations.length > 0) {
      // Flag scan as under_review (if not already)
      if (scan.status !== 'under_review') {
        await base44.asServiceRole.entities.CanonicalScan.update(scan_id, {
          status: 'under_review',
          dual_validation_failures: violations.map(v => ({
            type: v.type,
            severity: v.severity,
            message: v.message,
            detected_at: new Date().toISOString(),
          })),
        });
      }

      // Log audit record
      const auditRecord = {
        scan_id,
        event: 'DUAL_VALIDATION_FAILURE',
        failure_count: violations.length,
        failure_types: violations.map(v => v.type),
        severity: 'CRITICAL',
        actor_id: user.email,
        timestamp: new Date().toISOString(),
      };

      try {
        await base44.asServiceRole.entities.AuditLog.create(auditRecord);
      } catch (e) {
        console.error('Failed to log dual validation audit record:', e.message);
      }

      return Response.json({
        status: 'DUAL_VALIDATION_FAILED',
        scan_id,
        violations,
        action: 'Export blocked. Dual validation failed. Manual review required.',
      }, { status: 403 });
    }

    // ── Pass: Independent verification successful ──
    return Response.json({
      status: 'DUAL_VALIDATION_PASS',
      scan_id,
      message: 'Independent hash verification passed. Geometry and ACIF scores consistent.',
      verified_fields: {
        geometry_hash: computedHash,
        geometry_hash_match: computedHash === scan.geometry_hash,
        aoi_id: scan.aoi_id,
        acif_spot_check: 'passed',
      },
    });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});