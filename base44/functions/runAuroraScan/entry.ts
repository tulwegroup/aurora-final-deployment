/**
 * runAuroraScan — Full AOI scan pipeline
 *
 * 1. Tiles polygon AOI into grid cells
 * 2. For each cell, fetches GEE spectral composites via REST API
 * 3. Scores each cell via the Aurora scoring engine
 * 4. Saves ScanJob entity with full results GeoJSON
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { createHash } from 'node:crypto';
import { SignJWT, importPKCS8 } from 'npm:jose@5.2.0';

// ---------------------------------------------------------------------------
// GEE OAuth2 — service account JWT flow using jose for correct RS256 signing
// ---------------------------------------------------------------------------
async function getGEEToken() {
  const keyJson = Deno.env.get('AURORA_GEE_SERVICE_ACCOUNT_KEY');
  if (!keyJson) throw new Error('AURORA_GEE_SERVICE_ACCOUNT_KEY not set');

  const key = JSON.parse(keyJson);
  // Normalize PEM — secrets sometimes store \n as literal backslash-n
  const privateKeyPem = key.private_key.replace(/\\n/g, '\n');

  const privateKey = await importPKCS8(privateKeyPem, 'RS256');

  const jwt = await new SignJWT({
    scope: 'https://www.googleapis.com/auth/earthengine https://www.googleapis.com/auth/cloud-platform',
  })
    .setProtectedHeader({ alg: 'RS256' })
    .setIssuer(key.client_email)
    .setAudience('https://oauth2.googleapis.com/token')
    .setIssuedAt()
    .setExpirationTime('1h')
    .sign(privateKey);

  const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=${jwt}`,
  });
  const tokenData = await tokenRes.json();
  if (!tokenData.access_token) throw new Error(`GEE auth failed: ${JSON.stringify(tokenData)}`);
  return tokenData.access_token;
}

// ---------------------------------------------------------------------------
// Geometry utilities
// ---------------------------------------------------------------------------
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
  // Degrees per cell: fine ~1km, medium ~5km, coarse ~10km, survey ~25km
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

// ---------------------------------------------------------------------------
// GEE: fetch spectral composite for a cell bbox
// ---------------------------------------------------------------------------
async function fetchCellBands(token, cell, startDate, endDate) {
  const region = {
    type: 'Polygon',
    coordinates: [[
      [cell.minLon, cell.minLat], [cell.maxLon, cell.minLat],
      [cell.maxLon, cell.maxLat], [cell.minLon, cell.maxLat],
      [cell.minLon, cell.minLat]
    ]]
  };

  // Use GEE computeValue to get mean composite bands for the cell
  const expression = {
    result: '0',
    values: {
      '0': {
        functionInvocationValue: {
          functionName: 'Image.reduceRegion',
          arguments: {
            image: {
              functionInvocationValue: {
                functionName: 'Image.select',
                arguments: {
                  input: {
                    functionInvocationValue: {
                      functionName: 'ImageCollection.median',
                      arguments: {
                        collection: {
                          functionInvocationValue: {
                            functionName: 'ImageCollection.filterDate',
                            arguments: {
                              collection: {
                                functionInvocationValue: {
                                  functionName: 'ImageCollection.filterBounds',
                                  arguments: {
                                    collection: {
                                      functionInvocationValue: {
                                        functionName: 'ImageCollection.load',
                                        arguments: { id: { constantValue: 'COPERNICUS/S2_SR_HARMONIZED' } }
                                      }
                                    },
                                    geometry: { constantValue: region }
                                  }
                                }
                              },
                              start: { constantValue: startDate },
                              end: { constantValue: endDate }
                            }
                          }
                        }
                      }
                    }
                  },
                  bandSelectors: { constantValue: ['B4', 'B8', 'B11', 'B12'] }
                }
              }
            },
            reducer: {
              functionInvocationValue: {
                functionName: 'Reducer.mean',
                arguments: {}
              }
            },
            geometry: { constantValue: region },
            scale: { constantValue: 1000 },
            maxPixels: { constantValue: 1e6 }
          }
        }
      }
    }
  };

  const res = await fetch(
    'https://earthengine.googleapis.com/v1/projects/earthengine-public/value:compute',
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ expression }),
    }
  );

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`GEE cell fetch failed (${res.status}): ${err}`);
  }

  const data = await res.json();
  // result.result is a dict: {B4, B8, B11, B12}
  const bands = data.result || {};
  return {
    red: bands.B4 || 0,
    nir: bands.B8 || 0,
    swir1: bands.B11 || 0,
    swir2: bands.B12 || 0,
  };
}

// ---------------------------------------------------------------------------
// Aurora scoring engine (simplified constitutional version)
// Scores each cell 0–1 based on spectral proxies for mineralisation.
// ---------------------------------------------------------------------------
function scoreCellBands(bands, commodity) {
  const { red, nir, swir1, swir2 } = bands;

  // NDVI (vegetation / alteration proxy)
  const ndvi = (nir + red) > 0 ? (nir - red) / (nir + red) : 0;

  // Clay/alteration index (SWIR ratio — hallmark of hydrothermal systems)
  const clayIndex = (swir1 + swir2) > 0 ? swir1 / (swir1 + swir2) : 0.5;

  // Ferric oxide ratio (iron oxide — gossans / oxidised caps)
  const ferric = (nir + red) > 0 ? red / nir : 0.5;

  // Commodity-specific weights
  const weights = {
    gold:     { ndvi: 0.1, clay: 0.5, ferric: 0.4 },
    copper:   { ndvi: 0.1, clay: 0.6, ferric: 0.3 },
    lithium:  { ndvi: 0.05, clay: 0.7, ferric: 0.25 },
    diamonds: { ndvi: 0.2, clay: 0.3, ferric: 0.5 },
    uranium:  { ndvi: 0.15, clay: 0.4, ferric: 0.45 },
    default:  { ndvi: 0.15, clay: 0.5, ferric: 0.35 },
  };

  const w = weights[commodity] || weights.default;

  // Normalise clay to 0–1 range (typically 0.3–0.7)
  const clayNorm = Math.max(0, Math.min(1, (clayIndex - 0.3) / 0.4));
  // Low NDVI = more alteration
  const ndviScore = Math.max(0, 1 - Math.abs(ndvi));
  // Ferric 0.5–1.5 range normalised
  const ferricNorm = Math.max(0, Math.min(1, (ferric - 0.5) / 1.0));

  const raw = w.ndvi * ndviScore + w.clay * clayNorm + w.ferric * ferricNorm;

  // ACIF composite (0–1)
  const acif = Math.max(0, Math.min(1, raw));

  let tier;
  if (acif >= 0.65) tier = 1;
  else if (acif >= 0.40) tier = 2;
  else tier = 3;

  return { acif, tier, ndvi, clay_index: clayIndex, ferric_ratio: ferric };
}

// ---------------------------------------------------------------------------
// Main handler
// ---------------------------------------------------------------------------
Deno.serve(async (req) => {
  const base44 = createClientFromRequest(req);

  const user = await base44.auth.me();
  if (!user) return Response.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const { geometry, commodity = 'gold', resolution = 'medium', aoi_id = null } = body;

  if (!geometry || !geometry.coordinates) {
    return Response.json({ error: 'geometry is required' }, { status: 400 });
  }

  // Generate scan_id + geometry hash
  const scanId = `scan-${crypto.randomUUID()}`;
  const geoStr = JSON.stringify(geometry);
  const geometryHash = createHash('sha256').update(geoStr).digest('hex');

  // Create initial queued record
  const ring = geometry.coordinates[0];
  const bb = bbox(ring);
  const stepDeg = resolutionDeg(resolution);
  const allCells = tileBBox(bb, stepDeg);
  // Filter to cells whose centre is inside the polygon
  const cells = allCells.filter(c => pointInPolygon(c.centerLon, c.centerLat, ring));
  const cellCount = cells.length;

  await base44.entities.ScanJob.create({
    scan_id: scanId,
    status: 'running',
    commodity,
    resolution,
    aoi_id: aoi_id || null,
    geometry,
    geometry_hash: geometryHash,
    cell_count: cellCount,
    pipeline_version: 'vnext-1.0',
  });

  // Run pipeline in background (non-blocking response to client)
  // We do it synchronously here but cap cells to keep response time reasonable
  const MAX_CELLS = 50;
  const sampledCells = cells.length > MAX_CELLS
    ? cells.filter((_, i) => i % Math.ceil(cells.length / MAX_CELLS) === 0).slice(0, MAX_CELLS)
    : cells;

  let geeToken = null;

  try {
    geeToken = await getGEEToken();
  } catch (e) {
    console.error('GEE auth failed:', e.message);
    // Update entity to failed state
    const jobs = await base44.entities.ScanJob.filter({ scan_id: scanId });
    if (jobs?.length > 0) {
      await base44.entities.ScanJob.update(jobs[0].id, {
        status: 'failed',
        error_message: `GEE authentication failed: ${e.message}`,
      });
    }
    return Response.json({
      error: 'GEE authentication failed — cannot produce real satellite data.',
      detail: e.message,
      scan_id: scanId,
      status: 'failed',
    }, { status: 503 });
  }

  // Date range: last 12 months
  const endDate = new Date().toISOString().slice(0, 10);
  const startDate = new Date(Date.now() - 365 * 86400000).toISOString().slice(0, 10);

  const features = [];
  let totalAcif = 0;
  let tier1 = 0, tier2 = 0, tier3 = 0;

  for (const cell of sampledCells) {
    let bands;
    try {
      bands = await fetchCellBands(geeToken, cell, startDate, endDate);
    } catch (e) {
      console.error(`GEE cell fetch failed for [${cell.centerLon},${cell.centerLat}]:`, e.message);
      // Mark failed and abort — no synthetic fallback
      const jobs = await base44.entities.ScanJob.filter({ scan_id: scanId });
      if (jobs?.length > 0) {
        await base44.entities.ScanJob.update(jobs[0].id, {
          status: 'failed',
          error_message: `GEE cell fetch failed: ${e.message}`,
        });
      }
      return Response.json({ error: 'GEE cell fetch failed', detail: e.message, scan_id: scanId, status: 'failed' }, { status: 503 });
    }

    const scores = scoreCellBands(bands, commodity);
    totalAcif += scores.acif;
    if (scores.tier === 1) tier1++;
    else if (scores.tier === 2) tier2++;
    else tier3++;

    features.push({
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [cell.minLon, cell.minLat], [cell.maxLon, cell.minLat],
          [cell.maxLon, cell.maxLat], [cell.minLon, cell.maxLat],
          [cell.minLon, cell.minLat]
        ]]
      },
      properties: {
        cell_id: `${scanId}-${features.length}`,
        acif_score: Math.round(scores.acif * 10000) / 10000,
        tier: scores.tier,
        ndvi: Math.round(scores.ndvi * 10000) / 10000,
        clay_index: Math.round(scores.clay_index * 10000) / 10000,
        ferric_ratio: Math.round(scores.ferric_ratio * 10000) / 10000,
        commodity,
        center_lon: cell.centerLon,
        center_lat: cell.centerLat,
        source: 'gee',
        bands,
      }
    });
  }

  const displayAcif = sampledCells.length > 0 ? totalAcif / sampledCells.length : 0;
  const resultsGeojson = {
    type: 'FeatureCollection',
    features,
    metadata: {
      scan_id: scanId,
      commodity,
      resolution,
      geometry_hash: geometryHash,
      total_cells: cellCount,
      sampled_cells: sampledCells.length,
      gee_sourced: true,
      pipeline_version: 'vnext-1.0',
      completed_at: new Date().toISOString(),
    }
  };

  // Update entity with results
  const jobs = await base44.entities.ScanJob.filter({ scan_id: scanId });
  if (jobs && jobs.length > 0) {
    await base44.entities.ScanJob.update(jobs[0].id, {
      status: 'completed',
      completed_at: new Date().toISOString(),
      display_acif_score: Math.round(displayAcif * 10000) / 10000,
      tier_1_count: tier1,
      tier_2_count: tier2,
      tier_3_count: tier3,
      results_geojson: resultsGeojson,
    });
  }

  return Response.json({
    scan_id: scanId,
    aoi_id: aoi_id,
    geometry_hash: geometryHash,
    commodity,
    resolution,
    status: 'completed',
    cell_count: cellCount,
    sampled_cells: sampledCells.length,
    display_acif_score: Math.round(displayAcif * 10000) / 10000,
    tier_1_count: tier1,
    tier_2_count: tier2,
    tier_3_count: tier3,
    gee_sourced: true,
  });
});

// simulateBands removed — no synthetic fallback permitted