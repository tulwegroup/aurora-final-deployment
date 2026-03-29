#!/usr/bin/env python3
"""
Earth Engine Multi-Sensor Acquisition Service
Uses official Earth Engine Python API for real sensor data:
- Sentinel-2 optical (B4, B8, B11, B12) with cloud filtering + median composite
- Sentinel-1 SAR (VV, VH) with proper band extraction  
- Landsat 8/9 thermal (B10)
- SRTM DEM (elevation, slope)

Called from Deno: `python3 gee_sensor_pipeline.py <payload_file>`
Outputs JSON to stdout for orchestrator to consume.
"""

import ee
import json
import sys
import os


def init_ee():
    """Initialize Earth Engine with service account credentials."""
    credentials_json = os.environ.get("AURORA_GEE_SERVICE_ACCOUNT_KEY")
    if not credentials_json:
        raise ValueError("AURORA_GEE_SERVICE_ACCOUNT_KEY not set")
    
    credentials_dict = json.loads(credentials_json)
    credentials = ee.ServiceAccountCredentials(
        credentials_dict['client_email'],
        key_data=json.dumps(credentials_dict)
    )
    ee.Initialize(credentials)


def get_cell_bounds(cell):
    """Convert cell dict to GEE geometry polygon."""
    coords = [
        [cell['minLon'], cell['minLat']],
        [cell['maxLon'], cell['minLat']],
        [cell['maxLon'], cell['maxLat']],
        [cell['minLon'], cell['maxLat']],
        [cell['minLon'], cell['minLat']]
    ]
    return ee.Geometry.Polygon([coords])


def fetch_sentinel2(cell, date_range):
    """Sentinel-2 L2A optical with cloud filtering + median composite."""
    try:
        geometry = get_cell_bounds(cell)
        
        s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
              .filterBounds(geometry)
              .filterDate(date_range['start'], date_range['end'])
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)))
        
        size = s2.size().getInfo()
        if size == 0:
            sys.stderr.write(f"[S2-WARN] No images found for cell [{cell['centerLon']}, {cell['centerLat']}]\n")
            return {'valid': False, 'B4': None, 'B8': None, 'B11': None, 'B12': None, 'cloud_pct': 100}
        
        composite = s2.select(['B4', 'B8', 'B11', 'B12']).median()
        point = ee.Geometry.Point([cell['centerLon'], cell['centerLat']])
        sample = composite.sample(geometry=point, scale=20).first()
        
        if sample is None:
            sys.stderr.write(f"[S2-WARN] Sample returned None for cell [{cell['centerLon']}, {cell['centerLat']}]\n")
            return {'valid': False, 'B4': None, 'B8': None, 'B11': None, 'B12': None, 'cloud_pct': None}
        
        values = sample.getInfo()['properties']
        b4 = values.get('B4')
        b8 = values.get('B8')
        b11 = values.get('B11')
        b12 = values.get('B12')
        
        if None in [b4, b8, b11, b12]:
            sys.stderr.write(f"[S2-WARN] Missing bands for cell [{cell['centerLon']}, {cell['centerLat']}]: B4={b4}, B8={b8}, B11={b11}, B12={b12}\n")
            return {'valid': False, 'B4': b4, 'B8': b8, 'B11': b11, 'B12': b12, 'cloud_pct': None}
        
        return {
            'valid': True,
            'B4': float(b4),
            'B8': float(b8),
            'B11': float(b11),
            'B12': float(b12),
            'cloud_pct': 20,
        }
    except Exception as e:
        sys.stderr.write(f"[S2-ERROR] cell [{cell['centerLon']}, {cell['centerLat']}]: {str(e)}\n")
        return {'valid': False, 'B4': None, 'B8': None, 'B11': None, 'B12': None, 'cloud_pct': None}


def fetch_sentinel1(cell, date_range):
    """Sentinel-1 GRD SAR dual-pol."""
    try:
        geometry = get_cell_bounds(cell)
        
        s1 = (ee.ImageCollection('COPERNICUS/S1_GRD')
              .filterBounds(geometry)
              .filterDate(date_range['start'], date_range['end'])
              .filter(ee.Filter.eq('instrumentMode', 'IW'))
              .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING')))
        
        size = s1.size().getInfo()
        if size == 0:
            sys.stderr.write(f"[S1-WARN] No images found for cell [{cell['centerLon']}, {cell['centerLat']}]\n")
            return {'valid': False, 'VV': None, 'VH': None}
        
        composite = s1.select(['VV', 'VH']).mean()
        point = ee.Geometry.Point([cell['centerLon'], cell['centerLat']])
        sample = composite.sample(geometry=point, scale=10).first()
        
        if sample is None:
            sys.stderr.write(f"[S1-WARN] Sample returned None for cell [{cell['centerLon']}, {cell['centerLat']}]\n")
            return {'valid': False, 'VV': None, 'VH': None}
        
        values = sample.getInfo()['properties']
        vv = values.get('VV')
        vh = values.get('VH')
        
        if None in [vv, vh]:
            sys.stderr.write(f"[S1-WARN] Missing bands for cell [{cell['centerLon']}, {cell['centerLat']}]: VV={vv}, VH={vh}\n")
            return {'valid': False, 'VV': vv, 'VH': vh}
        
        return {
            'valid': True,
            'VV': float(vv),
            'VH': float(vh),
        }
    except Exception as e:
        sys.stderr.write(f"[S1-ERROR] cell [{cell['centerLon']}, {cell['centerLat']}]: {str(e)}\n")
        return {'valid': False, 'VV': None, 'VH': None}


def fetch_landsat8_thermal(cell, date_range):
    """Landsat 8/9 thermal infrared Band 10 (Kelvin)."""
    try:
        geometry = get_cell_bounds(cell)
        
        l8 = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
              .filterBounds(geometry)
              .filterDate(date_range['start'], date_range['end']))
        
        size = l8.size().getInfo()
        if size == 0:
            sys.stderr.write(f"[L8-WARN] No images found for cell [{cell['centerLon']}, {cell['centerLat']}]\n")
            return {'valid': False, 'B10': None}
        
        composite = l8.select(['ST_B10']).median()
        point = ee.Geometry.Point([cell['centerLon'], cell['centerLat']])
        sample = composite.sample(geometry=point, scale=30).first()
        
        if sample is None:
            sys.stderr.write(f"[L8-WARN] Sample returned None for cell [{cell['centerLon']}, {cell['centerLat']}]\n")
            return {'valid': False, 'B10': None}
        
        values = sample.getInfo()['properties']
        b10 = values.get('ST_B10')
        
        if b10 is None:
            sys.stderr.write(f"[L8-WARN] Missing band for cell [{cell['centerLon']}, {cell['centerLat']}]: ST_B10={b10}\n")
            return {'valid': False, 'B10': None}
        
        return {
            'valid': True,
            'B10': float(b10),
        }
    except Exception as e:
        sys.stderr.write(f"[L8-ERROR] cell [{cell['centerLon']}, {cell['centerLat']}]: {str(e)}\n")
        return {'valid': False, 'B10': None}


def fetch_dem_features(cell):
    """SRTM DEM elevation and slope."""
    try:
        geometry = get_cell_bounds(cell)
        dem = ee.Image('USGS/SRTMGL1_Ellip/SRTMGL1_Ellip_srtm')
        slope = ee.Terrain.slope(dem)
        
        point = ee.Geometry.Point([cell['centerLon'], cell['centerLat']])
        
        elev_sample = dem.sample(geometry=point, scale=30).first()
        slope_sample = slope.sample(geometry=point, scale=30).first()
        
        if elev_sample is None or slope_sample is None:
            sys.stderr.write(f"[DEM-WARN] Sample returned None for cell [{cell['centerLon']}, {cell['centerLat']}]\n")
            return {'valid': False, 'elevation': None, 'slope': None}
        
        elev_vals = elev_sample.getInfo()['properties']
        slope_vals = slope_sample.getInfo()['properties']
        
        elevation = elev_vals.get('elevation')
        slope_val = slope_vals.get('slope')
        
        if elevation is None or slope_val is None:
            sys.stderr.write(f"[DEM-WARN] Missing fields for cell [{cell['centerLon']}, {cell['centerLat']}]: elev={elevation}, slope={slope_val}\n")
            return {'valid': False, 'elevation': elevation, 'slope': slope_val}
        
        return {
            'valid': elevation is not None and -100 < elevation < 9000,
            'elevation': float(elevation) if elevation else None,
            'slope': float(slope_val) if slope_val else None,
        }
    except Exception as e:
        sys.stderr.write(f"[DEM-ERROR] cell [{cell['centerLon']}, {cell['centerLat']}]: {str(e)}\n")
        return {'valid': False, 'elevation': None, 'slope': None}


def process_cell_batch(cells, commodity, date_range):
    """Process cells through multi-sensor pipeline."""
    init_ee()
    
    results = []
    s2_valid_count = 0
    s1_valid_count = 0
    thermal_valid_count = 0
    dem_valid_count = 0
    
    for i, cell in enumerate(cells):
        s2_data = fetch_sentinel2(cell, date_range)
        s1_data = fetch_sentinel1(cell, date_range)
        thermal_data = fetch_landsat8_thermal(cell, date_range)
        dem_data = fetch_dem_features(cell)
        
        if s2_data['valid']:
            s2_valid_count += 1
        if s1_data['valid']:
            s1_valid_count += 1
        if thermal_data['valid']:
            thermal_valid_count += 1
        if dem_data['valid']:
            dem_valid_count += 1
        
        result = {
            'cell_id': f"cell_{i:04d}",
            'center_lat': cell['centerLat'],
            'center_lon': cell['centerLon'],
            's2': s2_data,
            's1': s1_data,
            'thermal': thermal_data,
            'dem': dem_data,
        }
        
        results.append(result)
    
    return {
        'results': results,
        'coverage': {
            's2_percent': round((s2_valid_count / len(cells)) * 100, 1) if cells else 0,
            's1_percent': round((s1_valid_count / len(cells)) * 100, 1) if cells else 0,
            'thermal_percent': round((thermal_valid_count / len(cells)) * 100, 1) if cells else 0,
            'dem_percent': round((dem_valid_count / len(cells)) * 100, 1) if cells else 0,
        }
    }


if __name__ == '__main__':
    # Load payload from file passed by Deno
    if len(sys.argv) > 1:
        payload_file = sys.argv[1]
        with open(payload_file, 'r') as f:
            payload = json.load(f)
        cells = payload['cells']
        commodity = payload['commodity']
        date_range = payload['date_range']
    else:
        # Fallback for testing
        cells = [
            {
                'minLon': -111.495, 'maxLon': -111.485,
                'minLat': 36.485, 'maxLat': 36.495,
                'centerLon': -111.49, 'centerLat': 36.49,
            },
        ]
        commodity = 'uranium'
        date_range = {'start': '2023-06-01', 'end': '2023-08-31'}
    
    try:
        result = process_cell_batch(cells, commodity, date_range)
        # Output JSON to stdout for Deno to consume
        print(json.dumps(result))
    except Exception as e:
        sys.stderr.write(f"FATAL: {str(e)}\n")
        sys.exit(1)