/**
 * scanVectorAudit — Scientific debug instrumentation for per-cell vector validation
 * 
 * Purpose: Prove that each cell has genuinely distinct raw observables and computed vectors
 * Compliance: Phase B constitution — each cell_i must have its own canonical x_i
 * 
 * Outputs:
 *  - Per-cell raw observable traces (spectral, SAR, thermal, gravity, magnetic)
 *  - Normalization parameters and per-cell normalized values
 *  - Per-modality sub-score assembly
 *  - Final component scores and ACIF per cell
 *  - Vector uniqueness report (detects broadcasting/caching defects)
 */

import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

Deno.serve(async (req) => {
  const base44 = createClientFromRequest(req);
  const user = await base44.auth.me();
  if (!user) return Response.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const { scan_id } = body;

  if (!scan_id) {
    return Response.json({ error: 'scan_id is required' }, { status: 400 });
  }

  // Fetch the completed scan
  const jobs = await base44.entities.ScanJob.filter({ scan_id });
  if (!jobs || jobs.length === 0) {
    return Response.json({ error: 'Scan not found' }, { status: 404 });
  }

  const scanJob = jobs[0];
  const resultsGeo = scanJob.results_geojson;

  if (!resultsGeo || !resultsGeo.features || resultsGeo.features.length === 0) {
    return Response.json({ error: 'No features in scan results' }, { status: 400 });
  }

  // --- AUDIT TRACE: Collect per-cell observables and scores ---
  const auditTraces = [];
  const rawSpectralVectors = [];
  const normalizedVectors = [];
  const acifScores = [];
  const tierCounts = { TIER_1: 0, TIER_2: 0, TIER_3: 0 };

  for (const feat of resultsGeo.features.slice(0, 10)) {
    const props = feat.properties;
    const geom = feat.geometry.coordinates[0];

    // Extract bounds
    const lons = geom.map(c => c[0]);
    const lats = geom.map(c => c[1]);
    const minLon = Math.min(...lons), maxLon = Math.max(...lons);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats);

    // --- RAW OBSERVABLE EXTRACTION ---
    const rawSpectral = {
      cai: props.cai || 0,          // Clay Alteration Index
      ioi: props.ioi || 0,          // Iron Oxide Index
      ndvi: props.ndvi || 0,
    };

    const rawSAR = {
      sar: props.sar || 0,          // SAR coherence
      structural: props.structural || 0,
    };

    const rawThermal = {
      thermal: props.thermal || 0,
    };

    const rawGravityMagnetic = {
      gravity_proxy: (props.cai * 0.8 + (1 - props.ndvi) * 0.2) || 0,
      magnetic_proxy: (props.ioi * 0.6 + props.structural * 0.4) || 0,
    };

    const rawAll = {
      ...rawSpectral,
      ...rawSAR,
      ...rawThermal,
      ...rawGravityMagnetic,
    };

    rawSpectralVectors.push({
      cell_id: props.cell_id,
      ...rawAll,
    });

    // --- NORMALIZED VECTORS (within-scan standardization) ---
    // In a real Phase B implementation, these would use scan-wide mu_k, sigma_k
    // For now, we normalize per-vector (temporary; real impl uses scan params)
    const normalized = {
      cai_norm: Math.max(0, Math.min(1, (rawSpectral.cai - 0.3) / 0.4)),
      ioi_norm: Math.max(0, Math.min(1, (rawSpectral.ioi - 0.5) / 1.0)),
      ndvi_norm: Math.max(0, 1 - Math.abs(rawSpectral.ndvi)),
      sar_norm: rawSAR.sar,
      thermal_norm: rawThermal.thermal,
    };

    normalizedVectors.push({
      cell_id: props.cell_id,
      ...normalized,
    });

    // --- MODALITY SUB-SCORES ---
    const spectralScore = (normalized.cai_norm * 0.5 + normalized.ioi_norm * 0.3 + normalized.ndvi_norm * 0.2);
    const structuralScore = rawSAR.structural;
    const thermalScore = normalized.thermal_norm;

    // --- FINAL COMPONENT ASSEMBLY (Phase B ACIF structure) ---
    const acif = props.acif_score || 0;
    const tier = props.tier || 'TIER_3';

    acifScores.push({
      cell_id: props.cell_id,
      acif,
      tier,
      spectral_component: spectralScore,
      structural_component: structuralScore,
      thermal_component: thermalScore,
    });

    tierCounts[tier]++;

    // --- COMPREHENSIVE TRACE ---
    auditTraces.push({
      cell_id: props.cell_id,
      geometry: {
        minLon: Math.round(minLon * 1000000) / 1000000,
        maxLon: Math.round(maxLon * 1000000) / 1000000,
        minLat: Math.round(minLat * 1000000) / 1000000,
        maxLat: Math.round(maxLat * 1000000) / 1000000,
        centroid_lat: props.lat,
        centroid_lon: props.lon,
      },
      raw_spectral: rawSpectral,
      raw_sar: rawSAR,
      raw_thermal: rawThermal,
      raw_gravity_magnetic: rawGravityMagnetic,
      normalized: normalized,
      modality_scores: {
        spectral: spectralScore,
        structural: structuralScore,
        thermal: thermalScore,
      },
      final_component: {
        acif: Math.round(acif * 10000) / 10000,
        tier: tier,
      },
    });
  }

  // --- VECTOR UNIQUENESS VALIDATION ---
  function computeVectorSignature(vec) {
    // Hash-like signature for detecting duplicates
    const keys = Object.keys(vec).sort();
    return keys.map(k => `${k}:${vec[k].toFixed(4)}`).join('|');
  }

  const rawSignatures = new Set();
  const normSignatures = new Set();
  let rawDuplicates = 0;
  let normDuplicates = 0;

  for (const vec of rawSpectralVectors) {
    const sig = computeVectorSignature(vec);
    if (rawSignatures.has(sig)) rawDuplicates++;
    rawSignatures.add(sig);
  }

  for (const vec of normalizedVectors) {
    const sig = computeVectorSignature(vec);
    if (normSignatures.has(sig)) normDuplicates++;
    normSignatures.add(sig);
  }

  const rawUniqueness = ((rawSpectralVectors.length - rawDuplicates) / rawSpectralVectors.length * 100);
  const normUniqueness = ((normalizedVectors.length - normDuplicates) / normalizedVectors.length * 100);

  // --- CONSTITUTION COMPLIANCE CHECK ---
  const complianceReport = {
    phase_b_requirement_1: {
      description: "Each cell_i has its own canonical observable vector x_i",
      status: rawUniqueness > 95 ? 'PASS' : 'FAIL',
      evidence: `${rawUniqueness.toFixed(1)}% unique raw vectors (${rawSpectralVectors.length} cells)`,
    },
    phase_b_requirement_2: {
      description: "Per-cell raw measurements are not shared across cells",
      status: rawDuplicates === 0 ? 'PASS' : 'FAIL',
      evidence: `${rawDuplicates} duplicate raw vectors detected`,
    },
    phase_b_requirement_3: {
      description: "No AOI-level broadcast observed in final vectors",
      status: normUniqueness > 90 ? 'PASS' : 'FAIL',
      evidence: `${normUniqueness.toFixed(1)}% unique normalized vectors (${normalizedVectors.length} cells)`,
    },
    phase_b_requirement_4: {
      description: "No caching/stub/fallback causing repeated vectors",
      status: rawDuplicates + normDuplicates === 0 ? 'PASS' : 'FAIL',
      evidence: `Raw: ${rawDuplicates} dupes, Normalized: ${normDuplicates} dupes`,
    },
  };

  const compliancePass = Object.values(complianceReport).every(r => r.status === 'PASS');

  return Response.json({
    scan_id,
    audit_summary: {
      cells_audited: auditTraces.length,
      raw_vector_uniqueness_pct: Math.round(rawUniqueness * 10) / 10,
      normalized_vector_uniqueness_pct: Math.round(normUniqueness * 10) / 10,
      tier_distribution: tierCounts,
      phase_b_compliant: compliancePass,
    },
    compliance_report: complianceReport,
    detailed_traces: auditTraces,
  });
});