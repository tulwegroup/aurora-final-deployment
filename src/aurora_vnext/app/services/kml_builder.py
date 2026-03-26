"""
Aurora OSI vNext — KML Builder
Phase AA §AA.6

Builds KML/KMZ documents from canonical stored records.

CONSTITUTIONAL RULES:
  Rule 1: All geometry is sourced verbatim from stored canonical fields.
          Coordinate precision is preserved to full IEEE 754 float64.
          No smoothing or simplification unless simplification_version is set.
  Rule 2: No tier derivation at build time. Layer filters use stored cell.tier only.
  Rule 3: KML ExtendedData embeds geometry_hash for all AOI-derived polygons,
          enabling field verification.
  Rule 4: No import from core/*.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any, Optional

from app.models.map_export_model import LayerType, LayerDefinition, LAYER_REGISTRY


# ---------------------------------------------------------------------------
# KML style templates
# ---------------------------------------------------------------------------

_KML_STYLES = """
  <Style id="aoi_style">
    <LineStyle><color>ff0000ff</color><width>3</width></LineStyle>
    <PolyStyle><color>330000ff</color></PolyStyle>
  </Style>
  <Style id="tier1_style">
    <IconStyle><color>ff00aa00</color><scale>0.6</scale></IconStyle>
    <PolyStyle><color>8800aa00</color></PolyStyle>
  </Style>
  <Style id="tier2_style">
    <IconStyle><color>ff00aaff</color><scale>0.5</scale></IconStyle>
    <PolyStyle><color>8800aaff</color></PolyStyle>
  </Style>
  <Style id="tier3_style">
    <IconStyle><color>ff0000ff</color><scale>0.4</scale></IconStyle>
    <PolyStyle><color>880000ff</color></PolyStyle>
  </Style>
  <Style id="veto_style">
    <IconStyle><color>ff0000aa</color><scale>0.4</scale></IconStyle>
    <PolyStyle><color>880000aa</color></PolyStyle>
  </Style>
  <Style id="grid_style">
    <IconStyle><color>ffaaaaaa</color><scale>0.3</scale></IconStyle>
  </Style>
  <Style id="gt_style">
    <IconStyle><color>ffffff00</color><scale>0.7</scale></IconStyle>
  </Style>
  <Style id="drill_style">
    <IconStyle><color>ffff0000</color><scale>0.8</scale></IconStyle>
  </Style>
  <Style id="voxel_style">
    <IconStyle><color>ffff8800</color><scale>0.4</scale></IconStyle>
  </Style>
"""


def _extended_data(**kwargs) -> str:
    """Emit KML ExtendedData block with key-value pairs."""
    items = "\n    ".join(
        f'<Data name="{k}"><value>{v}</value></Data>'
        for k, v in kwargs.items()
        if v is not None
    )
    return f"  <ExtendedData>\n    {items}\n  </ExtendedData>" if items else ""


def _placemark_point(
    name: str, lat: float, lon: float,
    style_id: str = "grid_style",
    description: str = "",
    extra: Optional[dict] = None,
) -> str:
    """Emit a KML Point Placemark. Coordinates verbatim — full precision."""
    ext = _extended_data(**(extra or {}))
    return (
        f'<Placemark>\n'
        f'  <name>{name}</name>\n'
        f'  <description>{description}</description>\n'
        f'  <styleUrl>#{style_id}</styleUrl>\n'
        f'{ext}\n'
        f'  <Point><coordinates>{lon},{lat},0</coordinates></Point>\n'
        f'</Placemark>\n'
    )


def _placemark_polygon(
    name: str, coords: list[tuple[float, float]],
    style_id: str = "aoi_style",
    description: str = "",
    extra: Optional[dict] = None,
) -> str:
    """
    Emit a KML Polygon Placemark.
    Coordinates are verbatim from stored geometry — full IEEE 754 precision.
    """
    coord_str = " ".join(f"{lon},{lat},0" for lon, lat in coords)
    ext = _extended_data(**(extra or {}))
    return (
        f'<Placemark>\n'
        f'  <name>{name}</name>\n'
        f'  <description>{description}</description>\n'
        f'  <styleUrl>#{style_id}</styleUrl>\n'
        f'{ext}\n'
        f'  <Polygon>\n'
        f'    <outerBoundaryIs>\n'
        f'      <LinearRing><coordinates>{coord_str}</coordinates></LinearRing>\n'
        f'    </outerBoundaryIs>\n'
        f'  </Polygon>\n'
        f'</Placemark>\n'
    )


def build_kml(
    scan_id: str,
    layers: list[LayerType],
    layer_data: dict[LayerType, list[dict[str, Any]]],
    geometry_hash: Optional[str] = None,
    include_hash: bool = True,
) -> str:
    """
    Build a KML document for the requested layers.

    layer_data: {LayerType: [feature_dict, ...]}
    Each feature_dict must have fields as specified in LAYER_REGISTRY[layer].source_field.
    Coordinates preserved verbatim — no simplification.
    """
    placemarks: list[str] = []

    for layer_type in layers:
        defn = LAYER_REGISTRY.get(layer_type)
        if not defn:
            continue

        features = layer_data.get(layer_type, [])
        style_id = defn.kml_style_id or "grid_style"

        for feature in features:
            extra: dict = {}
            if include_hash and geometry_hash:
                extra["aurora_geometry_hash"]   = geometry_hash
                extra["aurora_scan_id"]         = scan_id
                extra["aurora_layer"]           = layer_type.value
                extra["aurora_source_field"]    = defn.source_field

            if "geometry" in feature:
                # Polygon feature — extract exterior ring coords (lon, lat)
                geom  = feature["geometry"]
                ring  = geom.get("coordinates", [[]])[0]
                coords = [(c[0], c[1]) for c in ring]
                placemarks.append(_placemark_polygon(
                    name       = feature.get("name", layer_type.value),
                    coords     = coords,
                    style_id   = style_id,
                    description = defn.description,
                    extra      = {**feature.get("properties", {}), **extra},
                ))
            elif "lat" in feature and "lon" in feature:
                placemarks.append(_placemark_point(
                    name       = feature.get("name", layer_type.value),
                    lat        = feature["lat"],
                    lon        = feature["lon"],
                    style_id   = style_id,
                    description = defn.description,
                    extra      = {**{k: v for k, v in feature.items()
                                    if k not in ("lat", "lon", "name")}, **extra},
                ))

    kml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        '<Document>\n'
        f'  <name>Aurora Scan {scan_id}</name>\n'
        f'{_KML_STYLES}\n'
        + "\n".join(placemarks)
        + '\n</Document>\n</kml>'
    )
    return kml


def build_kmz(
    scan_id: str,
    layers: list[LayerType],
    layer_data: dict[LayerType, list[dict]],
    geometry_hash: Optional[str] = None,
    include_hash: bool = True,
) -> bytes:
    """Wrap KML in a KMZ (zipped) archive."""
    kml_str = build_kml(scan_id, layers, layer_data, geometry_hash, include_hash)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml_str.encode("utf-8"))
    return buf.getvalue()