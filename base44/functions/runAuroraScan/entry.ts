import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { createHash } from 'node:crypto';

function bbox(coords) {
  let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
  for (const [lon, lat] of coords) {
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
  }
  return { minLon, maxLon, minLat, maxLat };
}

function resolutionDeg(resolution) {
  const map = { fine: 0.01, medium: 0.05, coarse: 0.1, survey: 0.25 };
  return map[resolution] || 0.05;
}

function tileBBox(bb, stepDeg) {
  const cells = [];
  for (let lat = bb.minLat; lat < bb.maxLat; lat += stepDeg) {
    for (let lon = bb.minLon; lon < bb.maxLon; lon += stepDeg) {
      cells.push({
        minLon: lon, maxLon: Math.min(lon + stepDeg, bb.maxLon),
        minLat: lat, maxLat: Math.min(lat + stepDeg, bb.maxLat),
        centerLon: lon + stepDeg / 2,
        centerLat: lat + stepDeg / 2,
      });
    }
  }
  return cells;
}

function pointInPolygon(lon, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if (((yi > lat) !== (yj > lat)) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

async function invokePythonWorker(cells, commodity, dateRange) {
  const geeKey = Deno.env.get('AURORA_GEE_SERVICE_ACCOUNT_KEY');
  if (!geeKey) throw new Error('AURORA_GEE_SERVICE_ACCOUNT_KEY not set');

  const payload = { cells, commodity, date_range: dateRange };
  let tempDir;

  try {
    tempDir = await Deno.makeTempDir();
    const payloadFile = `${tempDir}/payload.json`;
    await Deno.writeTextFile(payloadFile, JSON.stringify(payload));

    const cmd = new Deno.Command('python3', {
      args: ['geeWorker/gee_sensor_pipeline.py', payloadFile],
      env: { ...Deno.env.toObject(), AURORA_GEE_SERVICE_ACCOUNT_KEY: geeKey },
      stdout: 'piped',
      stderr: 'piped',
    });

    const { stdout, stderr, success } = await cmd.output();
    if (!success) {
      const err = new TextDecoder().decode(stderr);
      throw new Error(`Python worker error: ${err}`);
    }

    return JSON.parse(new TextDecoder().decode(stdout));
  } finally {
    if (tempDir) await Deno.remove(tempDir, { recursive: true }).catch(() => {});
  }
}

function scoreCell(result, commodity) {
  const s2 = result.s2;
  const s1 = result.s1;

  if (!s2.valid || !s1.valid) {
    return { veto: true, acif: null, tier: 'DATA_MISSING' };
  }

  const { B4, B8, B11, B12 } = s2;
  const { VV, VH } = s1;

  const ndvi = (B8 + B4) > 0 ? (B8 - B4) / (B8 + B4) : 0.2;
  const clayIndex = (B11 + B12) > 0 ? B11 / (B11 + B12) : 0.5;
  const ironIndex = (B4 + B8) > 0 ? B4 / B8 : 0.5;

  const weights = {
    gold: { ndvi: 0.1, clay: 0.5, iron: 0.4 },
    copper: { ndvi: 0.1, clay: 0.6, iron: 0.3 },
    lithium: { ndvi: 0.05, clay: 0.7, iron: 0.25 },
    uranium: { ndvi: 0.15, clay: 0.4, iron: 0.45 },
    default: { ndvi: 0.15, clay: 0.5, iron: 0.35 },
  };

  const w = weights[commodity.toLowerCase()] || weights.default;
  const clayNorm = Math.max(0, Math.min(1, (clayIndex - 0.3) / 0.4));
  const ndviScore = Math.max(0, 1 - Math.abs(ndvi));
  const ironNorm = Math.max(0, Math.min(1, (ironIndex - 0.5) / 1.0));

  const raw = w.ndvi * ndviScore + w.clay * clayNorm + w.iron * ironNorm;
  const acif = Math.max(0, Math.min(1, raw));
  const tier = acif >= 0.65 ? 'TIER_1' : acif >= 0.40 ? 'TIER_2' : 'TIER_3';

  return { veto: false, acif, tier };
}

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

    const scanId = `scan-${crypto.randomUUID()}`;
    const geometryHash = createHash('sha256').update(JSON.stringify(geometry)).digest('hex');

    const ring = geometry.coordinates[0];
    const bb = bbox(ring);
    const stepDeg = resolutionDeg(resolution);
    const allCells = tileBBox(bb, stepDeg);
    const cells = allCells.filter(c => pointInPolygon(c.centerLon, c.centerLat, ring));

    await base44.entities.ScanJob.create({
      scan_id: scanId,
      status: 'running',
      commodity,
      resolution,
      aoi_id: aoi_id || null,
      geometry,
      geometry_hash: geometryHash,
      cell_count: cells.length,
      pipeline_version: 'vnext-3.0-python-gee',
    });

    const MAX_CELLS = 50;
    const sampledCells = cells.length > MAX_CELLS
      ? cells.filter((_, i) => i % Math.ceil(cells.length / MAX_CELLS) === 0).slice(0, MAX_CELLS)
      : cells;

    const dateRange = {
      end: new Date().toISOString().split('T')[0],
      start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    };

    const results = await invokePythonWorker(sampledCells, commodity, dateRange);

    const features = [];
    const forensicTrace = [];
    let totalAcif = 0, tier1 = 0, tier2 = 0, tier3 = 0, scoredCells = 0;

    for (const result of results.results) {
      const scores = scoreCell(result, commodity);

      if (scores.veto) {
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [result.center_lon, result.center_lat] },
          properties: { cell_id: result.cell_id, tier: 'DATA_MISSING', acif_score: null }
        });
        continue;
      }

      scoredCells++;
      totalAcif += scores.acif;
      if (scores.tier === 'TIER_1') tier1++;
      else if (scores.tier === 'TIER_2') tier2++;
      else tier3++;

      if (forensicTrace.length < 10) {
        forensicTrace.push({
          cell_id: result.cell_id,
          lat: result.center_lat,
          lon: result.center_lon,
          s2_raw: { B4: result.s2.B4, B8: result.s2.B8, B11: result.s2.B11, B12: result.s2.B12 },
          s1_raw: { VV: result.s1.VV, VH: result.s1.VH },
          thermal_raw: { B10: result.thermal.B10 },
          dem_elevation: result.dem.elevation,
          acif: Math.round(scores.acif * 10000) / 10000,
          tier: scores.tier,
        });
      }

      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [result.center_lon, result.center_lat] },
        properties: {
          cell_id: result.cell_id,
          tier: scores.tier,
          acif_score: Math.round(scores.acif * 10000) / 10000,
        }
      });
    }

    const displayAcif = scoredCells > 0 ? totalAcif / scoredCells : null;
    const resultsGeojson = {
      type: 'FeatureCollection',
      features,
      metadata: {
        scan_id: scanId,
        commodity,
        total_cells: cells.length,
        sampled_cells: sampledCells.length,
        scored_cells: scoredCells,
        sensor_coverage: results.coverage,
        multisensor: true,
        forensic_10_cell_trace: forensicTrace,
      }
    };

    const jobs = await base44.entities.ScanJob.filter({ scan_id: scanId });
    if (jobs?.length > 0) {
      await base44.entities.ScanJob.update(jobs[0].id, {
        status: displayAcif !== null ? 'completed' : 'completed_insufficient_data',
        completed_at: new Date().toISOString(),
        display_acif_score: displayAcif !== null ? Math.round(displayAcif * 10000) / 10000 : null,
        tier_1_count: tier1,
        tier_2_count: tier2,
        tier_3_count: tier3,
        results_geojson: resultsGeojson,
      });
    }

    return Response.json({
      scan_id: scanId,
      status: displayAcif !== null ? 'completed' : 'completed_insufficient_data',
      sampled_cells: sampledCells.length,
      scored_cells: scoredCells,
      sensor_coverage: results.coverage,
      display_acif_score: displayAcif,
      tier_1_count: tier1,
      tier_2_count: tier2,
      tier_3_count: tier3,
      multisensor: true,
      forensic_10_cell_trace: forensicTrace,
    });
  } catch (e) {
    console.error('[SCAN-ERROR]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});