/**
 * runAuroraScan — Multi-sensor Earth observation fusion (v2.0)
 * Sentinel-2 optical, Sentinel-1 SAR, Landsat 8 thermal, SRTM DEM
 * Per-cell independent sampling with explicit coverage reporting
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

async function geeCompute(token, expression) {
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
    throw new Error(`GEE compute failed (${res.status}): ${err}`);
  }
  return res.json();
}

// Sentinel-2 optical (first available image, any date)
async function fetchS2Bands(token, cell) {
  const coords = [
    [cell.minLon, cell.minLat], [cell.maxLon, cell.minLat],
    [cell.maxLon, cell.maxLat], [cell.minLon, cell.maxLat],
    [cell.minLon, cell.minLat]
  ];

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
                            functionName: 'ImageCollection.filterBounds',
                            arguments: {
                              collection: {
                                functionInvocationValue: {
                                  functionName: 'ImageCollection.load',
                                  arguments: {
                                    id: { constantValue: 'COPERNICUS/S2_SR_HARMONIZED' }
                                  }
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
                              }
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
            geometry: {
              functionInvocationValue: {
                functionName: 'GeometryConstructors.Polygon',
                arguments: {
                  coordinates: { constantValue: [coords] },
                  geodesic: { constantValue: false }
                }
              }
            },
            scale: { constantValue: 20 },
            maxPixels: { constantValue: 1e8 }
          }
        }
      }
    }
  };

  try {
    const data = await geeCompute(token, expression);
    const result = data.result || {};
    const valid = result.B4 !== null && result.B8 !== null && result.B11 !== null && result.B12 !== null;
    console.log(`[S2] cell [${cell.centerLon.toFixed(4)}, ${cell.centerLat.toFixed(4)}]: B4=${result.B4}, B8=${result.B8}, valid=${valid}`);
    return { B4: result.B4, B8: result.B8, B11: result.B11, B12: result.B12, valid };
  } catch (e) {
    console.warn(`[S2-FAIL] [${cell.centerLon.toFixed(4)}, ${cell.centerLat.toFixed(4)}]: ${e.message}`);
    return { valid: false, B4: null, B8: null, B11: null, B12: null };
  }
}

// Sentinel-1 SAR (first available image)
async function fetchS1Data(token, cell) {
  const coords = [
    [cell.minLon, cell.minLat], [cell.maxLon, cell.minLat],
    [cell.maxLon, cell.maxLat], [cell.minLon, cell.maxLat],
    [cell.minLon, cell.minLat]
  ];

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
                            functionName: 'ImageCollection.filterBounds',
                            arguments: {
                              collection: {
                                functionInvocationValue: {
                                  functionName: 'ImageCollection.load',
                                  arguments: {
                                    id: { constantValue: 'COPERNICUS/S1_GRD' }
                                  }
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
                              }
                            }
                          }
                        }
                      }
                    }
                  },
                  bandSelectors: { constantValue: ['VV', 'VH'] }
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
            scale: { constantValue: 10 },
            maxPixels: { constantValue: 1e8 }
          }
        }
      }
    }
  };

  try {
    const data = await geeCompute(token, expression);
    const result = data.result || {};
    const valid = result.VV !== null && result.VH !== null;
    console.log(`[S1] cell [${cell.centerLon.toFixed(4)}, ${cell.centerLat.toFixed(4)}]: VV=${result.VV}, VH=${result.VH}, valid=${valid}`);
    return { VV: result.VV, VH: result.VH, valid };
  } catch (e) {
    console.warn(`[S1-FAIL] [${cell.centerLon.toFixed(4)}, ${cell.centerLat.toFixed(4)}]: ${e.message}`);
    return { valid: false, VV: null, VH: null };
  }
}

// Landsat 8 thermal
async function fetchLandsat8Thermal(token, cell) {
  const coords = [
    [cell.minLon, cell.minLat], [cell.maxLon, cell.minLat],
    [cell.maxLon, cell.maxLat], [cell.minLon, cell.maxLat],
    [cell.minLon, cell.minLat]
  ];

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
                            functionName: 'ImageCollection.filterBounds',
                            arguments: {
                              collection: {
                                functionInvocationValue: {
                                  functionName: 'ImageCollection.load',
                                  arguments: {
                                    id: { constantValue: 'LANDSAT/LC08/C02/T1_L2' }
                                  }
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
                              }
                            }
                          }
                        }
                      }
                    }
                  },
                  bandSelectors: { constantValue: ['ST_B10'] }
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

  try {
    const data = await geeCompute(token, expression);
    const result = data.result || {};
    const valid = result.ST_B10 !== null;
    console.log(`[L8-TIRS] cell [${cell.centerLon.toFixed(4)}, ${cell.centerLat.toFixed(4)}]: B10=${result.ST_B10}, valid=${valid}`);
    return { B10: result.ST_B10, valid };
  } catch (e) {
    console.warn(`[L8-FAIL] [${cell.centerLon.toFixed(4)}, ${cell.centerLat.toFixed(4)}]: ${e.message}`);
    return { valid: false, B10: null };
  }
}

// SRTM DEM
async function fetchDEMFeatures(token, cell) {
  const coords = [
    [cell.minLon, cell.minLat], [cell.maxLon, cell.minLat],
    [cell.maxLon, cell.maxLat], [cell.minLon, cell.maxLat],
    [cell.minLon, cell.minLat]
  ];

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
                      functionName: 'Image.load',
                      arguments: {
                        id: { constantValue: 'USGS/SRTMGL1_Ellip/SRTMGL1_Ellip_srtm' }
                      }
                    }
                  },
                  bandSelectors: { constantValue: ['elevation'] }
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

  try {
    const data = await geeCompute(token, expression);
    const result = data.result || {};
    const valid = result.elevation !== null && result.elevation > -100;
    console.log(`[DEM] cell [${cell.centerLon.toFixed(4)}, ${cell.centerLat.toFixed(4)}]: elev=${result.elevation}, valid=${valid}`);
    return { elevation: result.elevation, valid };
  } catch (e) {
    console.warn(`[DEM-FAIL] [${cell.centerLon.toFixed(4)}, ${cell.centerLat.toFixed(4)}]: ${e.message}`);
    return { valid: false, elevation: null };
  }
}

function scoreCellMultiSensor(s2, s1, thermal, dem, commodity) {
  if (!s2.valid || !s1.valid) {
    return { veto: true, acif: null, tier: 'DATA_MISSING' };
  }

  const { B4, B8, B11, B12 } = s2;
  const { VV, VH } = s1;
  
  const ndvi = (B8 + B4) > 0 ? (B8 - B4) / (B8 + B4) : 0.2;
  const clayIndex = (B11 + B12) > 0 ? B11 / (B11 + B12) : 0.5;
  const ironIndex = (B4 + B8) > 0 ? B4 / B8 : 0.5;
  const sarRatio = VV !== 0 ? Math.abs(VV) / Math.max(Math.abs(VH), 1) : 1.0;
  const coherence = Math.min(1, 0.5 + (Math.abs(VH) / (Math.abs(VV) + 1)) * 0.5);
  const thermalFlux = thermal.valid && thermal.B10 ? Math.min(1, thermal.B10 / 300) : 0.3;

  const weights = {
    gold:     { ndvi: 0.1, clay: 0.5, iron: 0.4 },
    copper:   { ndvi: 0.1, clay: 0.6, iron: 0.3 },
    lithium:  { ndvi: 0.05, clay: 0.7, iron: 0.25 },
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

  return {
    veto: false,
    acif,
    tier,
    ndvi,
    clayIndex,
    ironIndex,
    sarRatio,
    coherence,
    thermalFlux,
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
    pipeline_version: 'vnext-2.0-multisensor',
  });

  const MAX_CELLS = 50;
  const sampledCells = cells.length > MAX_CELLS
    ? cells.filter((_, i) => i % Math.ceil(cells.length / MAX_CELLS) === 0).slice(0, MAX_CELLS)
    : cells;

  let geeToken = null;
  try {
    geeToken = await getGEEToken();
  } catch (e) {
    const jobs = await base44.entities.ScanJob.filter({ scan_id: scanId });
    if (jobs?.length > 0) {
      await base44.entities.ScanJob.update(jobs[0].id, { status: 'failed', error_message: e.message });
    }
    return Response.json({ error: 'GEE auth failed', scan_id: scanId, status: 'failed' }, { status: 503 });
  }

  const features = [];
  const forensicTrace = [];
  let totalAcif = 0, tier1 = 0, tier2 = 0, tier3 = 0, scoredCells = 0;
  let s2ValidCells = 0, s1ValidCells = 0, thermalValidCells = 0;

  for (const cell of sampledCells) {
    const s2 = await fetchS2Bands(geeToken, cell);
    const s1 = await fetchS1Data(geeToken, cell);
    const thermal = await fetchLandsat8Thermal(geeToken, cell);
    const dem = await fetchDEMFeatures(geeToken, cell);

    if (s2.valid) s2ValidCells++;
    if (s1.valid) s1ValidCells++;
    if (thermal.valid) thermalValidCells++;

    const scores = scoreCellMultiSensor(s2, s1, thermal, dem, commodity);

    if (scores.veto) {
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
          tier: 'DATA_MISSING',
          acif_score: null,
          lat: cell.centerLat,
          lon: cell.centerLon,
          s2_valid: s2.valid,
          s1_valid: s1.valid,
          thermal_valid: thermal.valid,
        }
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
        cell_id: `cell_${String(features.length).padStart(4, '0')}`,
        lat: cell.centerLat,
        lon: cell.centerLon,
        s2_raw: { B4: s2.B4, B8: s2.B8, B11: s2.B11, B12: s2.B12 },
        s1_raw: { VV: s1.VV, VH: s1.VH },
        thermal_raw: { B10: thermal.B10 },
        dem_elevation: dem.elevation,
        acif: Math.round(scores.acif * 10000) / 10000,
        tier: scores.tier,
      });
    }

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
        tier: scores.tier,
        acif_score: Math.round(scores.acif * 10000) / 10000,
        lat: cell.centerLat,
        lon: cell.centerLon,
        ndvi: Math.round(scores.ndvi * 10000) / 10000,
        clay: Math.round(scores.clayIndex * 10000) / 10000,
        iron: Math.round(scores.ironIndex * 10000) / 10000,
        sar_ratio: Math.round(scores.sarRatio * 10000) / 10000,
        coherence: Math.round(scores.coherence * 10000) / 10000,
        thermal_flux: Math.round(scores.thermalFlux * 10000) / 10000,
      }
    });
  }

  const displayAcif = scoredCells > 0 ? totalAcif / scoredCells : null;
  const scoreabilityRatio = sampledCells.length > 0 ? (scoredCells / sampledCells.length) : 0;
  const s2Coverage = sampledCells.length > 0 ? (s2ValidCells / sampledCells.length) : 0;
  const s1Coverage = sampledCells.length > 0 ? (s1ValidCells / sampledCells.length) : 0;
  const thermalCoverage = sampledCells.length > 0 ? (thermalValidCells / sampledCells.length) : 0;

  const resultsGeojson = {
    type: 'FeatureCollection',
    features,
    metadata: {
      scan_id: scanId,
      commodity,
      total_cells: cellCount,
      sampled_cells: sampledCells.length,
      scored_cells: scoredCells,
      sensor_coverage: {
        sentinel2_percent: Math.round(s2Coverage * 1000) / 10,
        sentinel1_percent: Math.round(s1Coverage * 1000) / 10,
        thermal_percent: Math.round(thermalCoverage * 1000) / 10,
      },
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
    sensor_coverage: {
      sentinel2_percent: Math.round(s2Coverage * 1000) / 10,
      sentinel1_percent: Math.round(s1Coverage * 1000) / 10,
      thermal_percent: Math.round(thermalCoverage * 1000) / 10,
    },
    display_acif_score: displayAcif !== null ? Math.round(displayAcif * 10000) / 10000 : null,
    tier_1_count: tier1,
    tier_2_count: tier2,
    tier_3_count: tier3,
    multisensor: true,
    forensic_10_cell_trace: forensicTrace,
  });
});