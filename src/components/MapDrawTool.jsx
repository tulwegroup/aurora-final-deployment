/**
 * MapDrawTool — Google Maps-based AOI drawing surface
 * Phase AA §AA.10
 *
 * Provides: polygon draw, rectangle draw, KML/GeoJSON file upload.
 * On geometry ready → calls onGeometryReady(geoJsonGeometry).
 *
 * CONSTITUTIONAL RULES:
 *   - This component only captures and reports geometry.
 *   - No scoring, tier derivation, or ACIF computation.
 *   - Geometry passed verbatim to parent — no modification.
 *   - File uploads are parsed client-side and passed as GeoJSON.
 *
 * Google Maps API: loaded dynamically. Requires REACT_APP_GMAPS_KEY env var
 * or equivalent configuration. Falls back to coordinate input if maps unavailable.
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Upload, Pen, Square, AlertTriangle } from "lucide-react";

const DRAW_MODES = [
  { id: "polygon",   label: "Polygon",   icon: Pen },
  { id: "rectangle", label: "Rectangle", icon: Square },
];

function parseKML(text) {
  const parser = new DOMParser();
  const doc    = parser.parseFromString(text, "application/xml");
  const coords = doc.querySelector("coordinates");
  if (!coords) return null;
  const pairs = coords.textContent.trim().split(/\s+/).map(c => {
    const [lon, lat] = c.split(",").map(Number);
    return [lon, lat];
  });
  if (pairs.length < 3) return null;
  if (pairs[0][0] !== pairs[pairs.length - 1][0] ||
      pairs[0][1] !== pairs[pairs.length - 1][1]) {
    pairs.push(pairs[0]);
  }
  return { type: "Polygon", coordinates: [pairs] };
}

function parseGeoJSON(text) {
  const obj = JSON.parse(text);
  if (obj.type === "Polygon") return obj;
  if (obj.type === "Feature" && obj.geometry?.type === "Polygon") return obj.geometry;
  if (obj.type === "FeatureCollection") {
    const poly = obj.features?.find(f => f.geometry?.type === "Polygon");
    if (poly) return poly.geometry;
  }
  return null;
}

// Manual coordinate input fallback
function ManualCoordInput({ onGeometryReady }) {
  const [text, setText] = useState("");
  const [err, setErr]   = useState(null);

  function handleParse() {
    try {
      const lines = text.trim().split("\n").map(l => {
        const [lat, lon] = l.split(",").map(Number);
        if (isNaN(lat) || isNaN(lon)) throw new Error("Invalid coordinate pair");
        return [lon, lat];
      });
      if (lines.length < 3) throw new Error("Need at least 3 coordinate pairs");
      const ring = [...lines];
      if (ring[0][0] !== ring[ring.length - 1][0] ||
          ring[0][1] !== ring[ring.length - 1][1]) {
        ring.push(ring[0]);
      }
      setErr(null);
      onGeometryReady({ type: "Polygon", coordinates: [ring] });
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div className="space-y-2 p-4">
      <p className="text-xs text-muted-foreground">
        Enter coordinates as lat,lon pairs (one per line):
      </p>
      <textarea
        className="w-full h-32 text-xs font-mono border rounded px-2 py-1 resize-none"
        placeholder={"-33.8688, 151.2093\n-33.9, 151.25\n-33.85, 151.3\n-33.8688, 151.2093"}
        value={text}
        onChange={e => setText(e.target.value)}
      />
      {err && <p className="text-xs text-destructive">{err}</p>}
      <Button size="sm" onClick={handleParse} disabled={!text.trim()}>
        Use These Coordinates
      </Button>
    </div>
  );
}

export default function MapDrawTool({ onGeometryReady, savedAOI }) {
  const mapRef    = useRef(null);
  const gmapsRef  = useRef(null);
  const [drawMode, setDrawMode] = useState("polygon");
  const [mapReady, setMapReady] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState(null);

  // Attempt to load Google Maps
  useEffect(() => {
    const key = window.__GMAPS_KEY__ || import.meta?.env?.VITE_GMAPS_KEY;
    if (!key) {
      setMapReady(false);
      return;
    }
    if (window.google?.maps) {
      setMapReady(true);
      return;
    }
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${key}&libraries=drawing`;
    script.async = true;
    script.onload  = () => setMapReady(true);
    script.onerror = () => setMapReady(false);
    document.head.appendChild(script);
  }, []);

  // Initialise map + drawing manager
  useEffect(() => {
    if (!mapReady || !mapRef.current || gmapsRef.current) return;
    const map = new window.google.maps.Map(mapRef.current, {
      center: { lat: 0, lng: 20 },
      zoom: 3,
      mapTypeId: "terrain",
    });

    const dm = new window.google.maps.drawing.DrawingManager({
      drawingMode: window.google.maps.drawing.OverlayType.POLYGON,
      drawingControl: false,
      polygonOptions:   { editable: true, fillOpacity: 0.2, strokeColor: "#0000ff" },
      rectangleOptions: { editable: true, fillOpacity: 0.2, strokeColor: "#0000ff" },
    });
    dm.setMap(map);
    gmapsRef.current = { map, dm };

    window.google.maps.event.addListener(dm, "overlaycomplete", (e) => {
      dm.setDrawingMode(null);
      let geometry;
      if (e.type === window.google.maps.drawing.OverlayType.POLYGON) {
        const path = e.overlay.getPath().getArray();
        const coords = path.map(p => [p.lng(), p.lat()]);
        coords.push(coords[0]); // close ring
        geometry = { type: "Polygon", coordinates: [coords] };
      } else if (e.type === window.google.maps.drawing.OverlayType.RECTANGLE) {
        const b = e.overlay.getBounds();
        const ne = b.getNorthEast(), sw = b.getSouthWest();
        const coords = [
          [sw.lng(), sw.lat()], [ne.lng(), sw.lat()],
          [ne.lng(), ne.lat()], [sw.lng(), ne.lat()],
          [sw.lng(), sw.lat()],
        ];
        geometry = { type: "Polygon", coordinates: [coords] };
      }
      if (geometry) onGeometryReady(geometry);
    });
  }, [mapReady, onGeometryReady]);

  // Update draw mode
  useEffect(() => {
    if (!gmapsRef.current) return;
    const { dm } = gmapsRef.current;
    const modeMap = {
      polygon:   window.google?.maps?.drawing?.OverlayType?.POLYGON,
      rectangle: window.google?.maps?.drawing?.OverlayType?.RECTANGLE,
    };
    dm?.setDrawingMode(modeMap[drawMode]);
  }, [drawMode, mapReady]);

  function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadErr(null);
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const text = ev.target.result;
        let geometry = null;
        if (file.name.endsWith(".kml") || file.name.endsWith(".kmz")) {
          geometry = parseKML(text);
        } else {
          geometry = parseGeoJSON(text);
        }
        if (!geometry) throw new Error("Could not extract polygon geometry from file.");
        onGeometryReady(geometry);
      } catch (err) {
        setUploadErr(err.message);
      } finally {
        setUploading(false);
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        {DRAW_MODES.map(({ id, label, icon: Icon }) => (
          <Button
            key={id}
            size="sm"
            variant={drawMode === id ? "default" : "outline"}
            onClick={() => setDrawMode(id)}
            disabled={!mapReady}
          >
            <Icon className="w-3.5 h-3.5 mr-1" />{label}
          </Button>
        ))}
        <label className="cursor-pointer">
          <Button size="sm" variant="outline" asChild>
            <span>
              <Upload className="w-3.5 h-3.5 mr-1" />
              {uploading ? "Uploading…" : "Upload KML/GeoJSON"}
            </span>
          </Button>
          <input type="file" accept=".kml,.kmz,.geojson,.json" className="hidden"
            onChange={handleFileUpload} />
        </label>
      </div>

      {uploadErr && (
        <div className="flex items-center gap-1 text-xs text-destructive">
          <AlertTriangle className="w-3 h-3" />{uploadErr}
        </div>
      )}

      {savedAOI && (
        <div className="text-xs bg-emerald-50 text-emerald-700 rounded px-2 py-1">
          AOI saved · hash: <span className="font-mono">{savedAOI.geometry_hash?.slice(0,16)}…</span>
        </div>
      )}

      {/* Map canvas or fallback */}
      {mapReady ? (
        <div ref={mapRef} className="w-full h-96 rounded-lg border bg-muted/20" />
      ) : (
        <div className="border rounded-lg bg-muted/10">
          <div className="px-4 py-2 border-b text-xs text-muted-foreground flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            Google Maps not configured. Enter coordinates manually below.
          </div>
          <ManualCoordInput onGeometryReady={onGeometryReady} />
        </div>
      )}

      <p className="text-[10px] text-muted-foreground">
        Geometry is never modified after saving. A SHA-256 hash is stored at creation for integrity verification.
      </p>
    </div>
  );
}