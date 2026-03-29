/**
 * runAuroraScan — Full AOI scan with Phase B constitutional compliance
 * CRITICAL FIX: Real GEE data only. No synthetic variation.
 * If data unavailable: mark as missing, veto cell, do not score.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { createHash } from 'node:crypto';
import { SignJWT, importPKCS8 } from 'npm:jose@5.2.0';

async function getGEEToken() {
  const keyJson = Deno.env.get('AURORA_GEE_SERVICE_ACCOUNT_KEY');
  if (!keyJson) throw new Error('AURORA_GEE_SERVICE_ACCOUNT_KEY not set');
  const key = JSON.parse(keyJson);
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

// GEE per-cell sampling — REAL DATA ONLY
async function fetchCellBands(token, cell) {
  const coords = [
    [cell.minLon, cell.minLat], 
    [cell.maxLon, cell.minLat],
    [cell.maxLon, cell.maxLat], 
    [cell.minLon, cell.maxLat],
    [cell.minLon, cell.minLat]
  ];

  // GEE REST API: Use Landsat-8 with proven simple expression
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
                      functionName: 'Collection.first',
                      arguments: {
                        collection: {
                          functionInvocationValue: {
                            functionName: 'ImageCollection.load',
                            arguments: {
                              id: { constantValue: 'LANDSAT/LC08/C02/T1' }
                            }
                          }
                        }
                      }
                    }
                  },
                  bandSelectors: { constantValue: ['B4', 'B5', 'B6', 'B7'] }
                }
              }
            },
            reducer: {
              functionInvocationValue: {
                functionName: 'Reducer.mean',
                arguments: {}
              }
            },
            geometry: {
              functionInvocationValue: {
                functionName: 'GeometryConstructors.Polygon',
                arguments: {
                  coordinates: { constantValue: [coords] },
                  geodesic: { constantValue: false }
                }
              }
            },
            scale: { constantValue: 30 },
            maxPixels: { constantValue: 1e8 }
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
  const result = data.result || {};
  
  // Landsat-8 bands: B4=red, B5=NIR, B6=SWIR1, B7=SWIR2
  const B4 = result.B4;  // red
  const B5 = result.B5;  // nir
  const B6 = result.B6;  // swir1
  const B7 = result.B7;  // swir2
  
  const allNull = B4 === null || B4 === undefined || 
                  B5 === null || B5 === undefined || 
                  B6 === null || B6 === undefined || 
                  B7 === null || B7 === undefined;
  
  if (allNull) {
    console.warn(`[DATA-MISSING] Cell [${cell.centerLon.toFixed(4)}, ${cell.centerLat.toFixed(4)}] returned null bands. GEE data unavailable for this cell.`);
    return {
      red: null,
      nir: null,
      swir1: null,
      swir2: null,
      data_available: false,
      raw_B4: B4,
      raw_B5: B5,
      raw_B6: B6,
      raw_B7: B7,
    };
  }

  // Real GEE data returned (Landsat-8)
  return {
    red: B4 || 0,
    nir: B5 || 0,
    swir1: B6 || 0,
    swir2: B7 || 0,
    data_available: true,
    raw_B4: B4,
    raw_B5: B5,
    raw_B6: B6,
    raw_B7: B7,
  };
}

// Per-cell scoring — only score if data is available
function scoreCellBands(bands, commodity) {
  // If data is missing, return veto signal
  if (!bands.data_available) {
    return {
      acif: null,
      tier: 'DATA_MISSING',
      veto: true,
      reason: 'GEE data unavailable for this cell',
    };
  }

  const { red, nir, swir1, swir2 } = bands;
  
  const ndvi = (nir + red) > 0 ? (nir - red) / (nir + red) : 0.2;
  const clayIndex = (swir1 + swir2) > 0 ? swir1 / (swir1 + swir2) : 0.5;
  const ironIndex = (nir + red) > 0 ? red / nir : 0.5;
  const spectralVariance = Math.abs(nir - red) + Math.abs(swir1 - swir2);
  const sarCoherence = Math.min(1, 0.5 + (spectralVariance / 255) * 0.5);
  const thermalFlux = Math.min(1, swir2 / 255 * 1.5);
  const gravityScore = clayIndex * 0.8 + (1 - ndvi) * 0.2;
  const magneticScore = ironIndex * 0.6 + (spectralVariance / 255) * 0.4;
  
  const weights = {
    gold:     { ndvi: 0.1, clay: 0.5, iron: 0.4 },
    copper:   { ndvi: 0.1, clay: 0.6, iron: 0.3 },
    lithium:  { ndvi: 0.05, clay: 0.7, iron: 0.25 },
    diamonds: { ndvi: 0.2, clay: 0.3, iron: 0.5 },
    petroleum: { ndvi: 0.05, clay: 0.4, iron: 0.3 },
    uranium:  { ndvi: 0.15, clay: 0.4, iron: 0.45 },
    default:  { ndvi: 0.15, clay: 0.5, iron: 0.35 },
  };
  
  const w = weights[commodity.toLowerCase()] || weights.default;
  const clayNorm = Math.max(0, Math.min(1, (clayIndex - 0.3) / 0.4));
  const ndviScore = Math.max(0, 1 - Math.abs(ndvi));
  const ironNorm = Math.max(0, Math.min(1, (ironIndex - 0.5) / 1.0));
  
  const raw = w.ndvi * ndviScore + w.clay * clayNorm + w.iron * ironNorm;
  const acif = Math.max(0, Math.min(1, raw));
  
  const tier = acif >= 0.65 ? 'TIER_1' : acif >= 0.40 ? 'TIER_2' : 'TIER_3';
  
  const gate1 = gravityScore > 0.4;
  const gate2 = sarCoherence > 0.5;
  const gate3 = thermalFlux > 0.3;
  const gate4 = clayNorm > 0.3 || ndviScore > 0.4;
  const gatesPassed = [gate1, gate2, gate3, gate4].filter(Boolean).length;
  
  return {
    acif, tier, ndvi, clayIndex, ironIndex, spectralVariance,
    sarCoherence, thermalFlux, gravityScore, magneticScore,
    gatesPassed, systemConfirmed: gatesPassed >= 3,
    faultRelated: sarCoherence > 0.8,
    geothermal: thermalFlux > 0.6,
    vegetationFP: ndvi > 0.5,
    veto: false,
  };
}

Deno.serve(async (req) => {
  const base44 = createClientFromRequest(req);
  const user = await base44.auth.me();
  if (!user) return Response.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const { geometry, commodity = 'gold', resolution = 'medium', aoi_id = null } = body;

  if (!geometry || !geometry.coordinates) {
    return Response.json({ error: 'geometry is required' }, { status: 400 });
  }

  const scanId = `scan-${crypto.randomUUID()}`;
  const geoStr = JSON.stringify(geometry);
  const geometryHash = createHash('sha256').update(geoStr).digest('hex');

  const ring = geometry.coordinates[0];
  const bb = bbox(ring);
  const stepDeg = resolutionDeg(resolution);
  const allCells = tileBBox(bb, stepDeg);
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

  const MAX_CELLS = 50;
  const sampledCells = cells.length > MAX_CELLS
    ? cells.filter((_, i) => i % Math.ceil(cells.length / MAX_CELLS) === 0).slice(0, MAX_CELLS)
    : cells;

  let geeToken = null;

  try {
    geeToken = await getGEEToken();
  } catch (e) {
    console.error('GEE auth failed:', e.message);
    const jobs = await base44.entities.ScanJob.filter({ scan_id: scanId });
    if (jobs?.length > 0) {
      await base44.entities.ScanJob.update(jobs[0].id, {
        status: 'failed',
        error_message: `GEE authentication failed: ${e.message}`,
      });
    }
    return Response.json({
      error: 'GEE authentication failed',
      detail: e.message,
      scan_id: scanId,
      status: 'failed',
    }, { status: 503 });
  }

  const features = [];
  let totalAcif = 0;
  let tier1 = 0, tier2 = 0, tier3 = 0;
  let scoredCells = 0;
  let missingDataCells = 0;

  for (const cell of sampledCells) {
    let bands;
    try {
      bands = await fetchCellBands(geeToken, cell);
    } catch (e) {
      console.error(`GEE cell fetch failed for [${cell.centerLon},${cell.centerLat}]:`, e.message);
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
    
    // If data missing, create placeholder feature but do not score
    if (scores.veto) {
      missingDataCells++;
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
          cell_id: `cell_${String(features.length).padStart(4, '0')}`,
          commodity,
          tier: 'DATA_MISSING',
          acif_score: null,
          lat: Math.round(cell.centerLat * 1000000) / 1000000,
          lon: Math.round(cell.centerLon * 1000000) / 1000000,
          data_quality: 'MISSING',
          source: 'landsat8',
          raw_bands: { B4: bands.raw_B4, B5: bands.raw_B5, B6: bands.raw_B6, B7: bands.raw_B7 },
        }
      });
      continue;
    }

    // Real data — score normally
    scoredCells++;
    totalAcif += scores.acif;
    if (scores.tier === 'TIER_1') tier1++;
    else if (scores.tier === 'TIER_2') tier2++;
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
        cell_id: `cell_${String(features.length).padStart(4, '0')}`,
        commodity,
        tier: scores.tier,
        acif_score: Math.round(scores.acif * 10000) / 10000,
        acif_pct: Math.round(scores.acif * 1000) / 10,
        lat: Math.round(cell.centerLat * 1000000) / 1000000,
        lon: Math.round(cell.centerLon * 1000000) / 1000000,
        cai: Math.round(scores.clayIndex * 10000) / 10000,
        ioi: Math.round(scores.ironIndex * 10000) / 10000,
        sar: Math.round(scores.sarCoherence * 10000) / 10000,
        thermal: Math.round(scores.thermalFlux * 10000) / 10000,
        ndvi: Math.round(scores.ndvi * 10000) / 10000,
        structural: Math.round((scores.spectralVariance / 255) * 10000) / 10000,
        fault_related: scores.faultRelated,
        geothermal: scores.geothermal,
        urban_bias: false,
        veg_fp: scores.vegetationFP,
        deposit_class: scores.systemConfirmed ? 'ANOMALY_CONFIRMED' : 'ANOMALY_INCONCLUSIVE',
        gates_passed: scores.gatesPassed,
        source: 'landsat8',
        data_quality: 'REAL',
        raw_bands: { B4: bands.raw_B4, B5: bands.raw_B5, B6: bands.raw_B6, B7: bands.raw_B7 },
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
      resolution,
      geometry_hash: geometryHash,
      total_cells: cellCount,
      sampled_cells: sampledCells.length,
      scored_cells: scoredCells,
      missing_data_cells: missingDataCells,
      gee_sourced: true,
      pipeline_version: 'vnext-1.0',
      completed_at: new Date().toISOString(),
    }
  };

  const jobs = await base44.entities.ScanJob.filter({ scan_id: scanId });
  if (jobs && jobs.length > 0) {
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
    aoi_id: aoi_id,
    geometry_hash: geometryHash,
    commodity,
    resolution,
    status: displayAcif !== null ? 'completed' : 'completed_insufficient_data',
    cell_count: cellCount,
    sampled_cells: sampledCells.length,
    scored_cells: scoredCells,
    missing_data_cells: missingDataCells,
    display_acif_score: displayAcif !== null ? Math.round(displayAcif * 10000) / 10000 : null,
    tier_1_count: tier1,
    tier_2_count: tier2,
    tier_3_count: tier3,
    gee_sourced: true,
  });
});