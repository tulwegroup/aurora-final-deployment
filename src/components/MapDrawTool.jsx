/**
 * MapDrawTool — Leaflet-based AOI drawing surface
 * Uses react-leaflet (already installed). No Google Maps API key required.
 * Supports: rectangle draw, polygon draw (manual coords), KML/GeoJSON upload.
 *
 * CONSTITUTIONAL RULES:
 *   - Captures and reports geometry only. No scoring/computation.
 *   - Geometry passed verbatim to parent — no modification.
 */
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Upload, Square, AlertTriangle, Hexagon } from "lucide-react";

// Parse KML into GeoJSON polygon geometry
function parseKML(text) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(text, "application/xml");
  const coords = doc.querySelector("coordinates");
  if (!coords) return null;
  const pairs = coords.textContent.trim().split(/\s+/).map(c => {
    const [lon, lat] = c.split(",").map(Number);
    return [lon, lat];
  });
  if (pairs.length < 3) return null;
  if (pairs[0][0] !== pairs[pairs.length - 1][0] || pairs[0][1] !== pairs[pairs.length - 1][1]) {
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

// BBox input for quick AOI definition (always available, no map needed for this path)
function BBoxInput({ onGeometryReady, defaultBbox }) {
  const [minLat, setMinLat] = useState(defaultBbox?.minLat || "");
  const [maxLat, setMaxLat] = useState(defaultBbox?.maxLat || "");
  const [minLon, setMinLon] = useState(defaultBbox?.minLon || "");
  const [maxLon, setMaxLon] = useState(defaultBbox?.maxLon || "");
  const [err, setErr] = useState(null);

  function submit() {
    const vals = [+minLat, +maxLat, +minLon, +maxLon];
    if (vals.some(isNaN)) { setErr("All fields must be valid numbers."); return; }
    if (+minLat >= +maxLat) { setErr("Min Lat must be less than Max Lat."); return; }
    if (+minLon >= +maxLon) { setErr("Min Lon must be less than Max Lon."); return; }
    setErr(null);
    const mnLa = +minLat, mxLa = +maxLat, mnLo = +minLon, mxLo = +maxLon;
    onGeometryReady({
      type: "Polygon",
      coordinates: [[
        [mnLo, mnLa], [mxLo, mnLa], [mxLo, mxLa], [mnLo, mxLa], [mnLo, mnLa]
      ]]
    });
  }

  return (
    <div className="space-y-3 p-4">
      <p className="text-xs text-muted-foreground font-medium">Enter bounding box coordinates (WGS84):</p>
      <div className="grid grid-cols-2 gap-2">
        {[["Min Lat", minLat, setMinLat, "-90 to 90"], ["Max Lat", maxLat, setMaxLat, "-90 to 90"],
          ["Min Lon", minLon, setMinLon, "-180 to 180"], ["Max Lon", maxLon, setMaxLon, "-180 to 180"]].map(([lbl, val, setter, ph]) => (
          <div key={lbl} className="space-y-1">
            <label className="text-[10px] text-muted-foreground uppercase tracking-wide">{lbl}</label>
            <input type="number" step="any" value={val} onChange={e => setter(e.target.value)}
              placeholder={ph} className="w-full border rounded px-2 py-1.5 text-sm" />
          </div>
        ))}
      </div>
      {err && <p className="text-xs text-destructive">{err}</p>}
      <Button size="sm" onClick={submit}
        disabled={[minLat, maxLat, minLon, maxLon].some(v => v === "")}>
        Use Bounding Box
      </Button>
    </div>
  );
}

// Leaflet map component
function LeafletMap({ onGeometryReady, center = [7, -1.5] }) {
  const mapRef = useRef(null);
  const leafletRef = useRef(null);
  const [drawMode, setDrawMode] = useState(null);
  const [polyCount, setPolyCount] = useState(0);
  const polyPtsRef = useRef([]);

  useEffect(() => {
    if (leafletRef.current || !mapRef.current) return;
    import("leaflet").then(L => {
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      });
      const map = L.map(mapRef.current).setView(center, 5);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors", maxZoom: 18,
      }).addTo(map);

      leafletRef.current = { L, map, _rectMode: false, _polyMode: false };

      // ---- RECTANGLE ----
      let startLL = null, rectLayer = null;
      map.on("mousedown", e => {
        if (!leafletRef.current._rectMode) return;
        map.dragging.disable(); startLL = e.latlng;
        if (rectLayer) { map.removeLayer(rectLayer); rectLayer = null; }
      });
      map.on("mousemove", e => {
        if (!startLL || !leafletRef.current._rectMode) return;
        if (rectLayer) map.removeLayer(rectLayer);
        rectLayer = L.rectangle([startLL, e.latlng], { color: "#3b82f6", fillOpacity: 0.2, weight: 2 }).addTo(map);
      });
      map.on("mouseup", e => {
        if (!startLL || !leafletRef.current._rectMode) return;
        map.dragging.enable();
        if (!rectLayer) { startLL = null; return; }
        const b = rectLayer.getBounds();
        const sw = b.getSouthWest(), ne = b.getNorthEast();
        const coords = [[sw.lng,sw.lat],[ne.lng,sw.lat],[ne.lng,ne.lat],[sw.lng,ne.lat],[sw.lng,sw.lat]];
        onGeometryReady({ type: "Polygon", coordinates: [coords] });
        startLL = null;
        leafletRef.current._rectMode = false;
        map.getContainer().style.cursor = "";
      });

      // ---- POLYGON ----
      let polyMarkers = [], polyLine = null, previewLine = null;
      function onPolyMove(e) {
        const pts = polyPtsRef.current;
        if (!leafletRef.current._polyMode || pts.length === 0) return;
        const last = pts[pts.length - 1];
        if (previewLine) map.removeLayer(previewLine);
        previewLine = L.polyline([[last[1],last[0]], [e.latlng.lat,e.latlng.lng]],
          { color: '#3b82f6', dashArray: '4 4', weight: 1.5 }).addTo(map);
      }
      function finishPoly() {
        const pts = polyPtsRef.current;
        if (pts.length < 3) return;
        polyMarkers.forEach(m => map.removeLayer(m)); polyMarkers = [];
        if (polyLine) { map.removeLayer(polyLine); polyLine = null; }
        if (previewLine) { map.removeLayer(previewLine); previewLine = null; }
        map.off('mousemove', onPolyMove);
        const ring = [...pts, pts[0]];
        polyPtsRef.current = [];
        setPolyCount(0);
        leafletRef.current._polyMode = false;
        map.getContainer().style.cursor = '';
        onGeometryReady({ type: 'Polygon', coordinates: [ring] });
      }
      leafletRef.current._finishPoly = finishPoly;
      map.on('click', e => {
        if (!leafletRef.current._polyMode) return;
        const pt = [e.latlng.lng, e.latlng.lat];
        polyPtsRef.current = [...polyPtsRef.current, pt];
        setPolyCount(polyPtsRef.current.length);
        const m = L.circleMarker([e.latlng.lat, e.latlng.lng],
          { radius: 5, color: '#3b82f6', fillOpacity: 1 }).addTo(map);
        polyMarkers.push(m);
        if (polyLine) map.removeLayer(polyLine);
        if (polyPtsRef.current.length > 1)
          polyLine = L.polyline(polyPtsRef.current.map(p=>[p[1],p[0]]), { color:'#3b82f6', weight:2 }).addTo(map);
        map.on('mousemove', onPolyMove);
      });
      map.on('dblclick', e => {
        if (!leafletRef.current._polyMode) return;
        L.DomEvent.stop(e);
        finishPoly();
      });
    });
    return () => {
      if (leafletRef.current?.map) { leafletRef.current.map.remove(); leafletRef.current = null; }
    };
  }, []);

  function startRectDraw() {
    if (!leafletRef.current) return;
    leafletRef.current._rectMode = true;
    leafletRef.current._polyMode = false;
    leafletRef.current.map.getContainer().style.cursor = 'crosshair';
    setDrawMode('rectangle'); polyPtsRef.current = []; setPolyCount(0);
  }
  function startPolyDraw() {
    if (!leafletRef.current) return;
    leafletRef.current._polyMode = true;
    leafletRef.current._rectMode = false;
    leafletRef.current.map.getContainer().style.cursor = 'crosshair';
    setDrawMode('polygon'); polyPtsRef.current = []; setPolyCount(0);
  }
  function finishPolyBtn() {
    if (leafletRef.current?._finishPoly) leafletRef.current._finishPoly();
    setDrawMode(null);
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2 items-center">
        <Button size="sm" variant={drawMode === 'rectangle' ? 'default' : 'outline'} onClick={startRectDraw}>
          <Square className="w-3.5 h-3.5 mr-1" /> Draw Rectangle
        </Button>
        <Button size="sm" variant={drawMode === 'polygon' ? 'default' : 'outline'} onClick={startPolyDraw}>
          <Hexagon className="w-3.5 h-3.5 mr-1" /> Draw Polygon
        </Button>
        {drawMode === 'polygon' && polyCount >= 3 && (
          <Button size="sm" variant="secondary" onClick={finishPolyBtn}>
            Finish ({polyCount} pts)
          </Button>
        )}
        <span className="text-xs text-muted-foreground">
          {drawMode === 'rectangle' ? 'Click and drag to draw rectangle' :
           drawMode === 'polygon' ? 'Click to add points · double-click or Finish to close' : ''}
        </span>
      </div>
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
      <div ref={mapRef} className="w-full rounded-lg border bg-muted/20" style={{ height: 420 }} />
    </div>
  );
}

export default function MapDrawTool({ onGeometryReady, savedAOI, defaultBbox }) {
  const [activeTab, setActiveTab] = useState("map");
  const [uploadErr, setUploadErr] = useState(null);
  const [uploading, setUploading] = useState(false);

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
        if (!geometry) throw new Error("Could not extract polygon from file.");
        onGeometryReady(geometry);
        setActiveTab("map");
      } catch (err) {
        setUploadErr(err.message);
      } finally {
        setUploading(false);
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  const TABS = [
    { id: "map",   label: "🗺 Map Draw" },
    { id: "bbox",  label: "⬜ Bounding Box" },
    { id: "upload", label: "📁 Upload KML/GeoJSON" },
  ];

  return (
    <div className="space-y-3">
      {/* Tab bar */}
      <div className="flex gap-1 border-b pb-2">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
              activeTab === t.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === "map" && (
        <LeafletMap onGeometryReady={onGeometryReady} center={defaultBbox ? [(+defaultBbox.minLat + +defaultBbox.maxLat) / 2, (+defaultBbox.minLon + +defaultBbox.maxLon) / 2] : [7, -1.5]} />
      )}

      {activeTab === "bbox" && (
        <BBoxInput onGeometryReady={onGeometryReady} defaultBbox={defaultBbox} />
      )}

      {activeTab === "upload" && (
        <div className="p-4 space-y-3">
          <p className="text-xs text-muted-foreground">Upload a KML or GeoJSON file containing a polygon geometry.</p>
          <label className="cursor-pointer">
            <Button size="sm" variant="outline" asChild>
              <span>
                <Upload className="w-3.5 h-3.5 mr-1" />
                {uploading ? "Parsing…" : "Choose File"}
              </span>
            </Button>
            <input type="file" accept=".kml,.kmz,.geojson,.json" className="hidden" onChange={handleFileUpload} />
          </label>
          {uploadErr && (
            <div className="flex items-center gap-1 text-xs text-destructive">
              <AlertTriangle className="w-3 h-3" />{uploadErr}
            </div>
          )}
        </div>
      )}

      {savedAOI && (
        <div className="text-xs bg-emerald-50 text-emerald-700 rounded px-3 py-2 border border-emerald-200">
          ✓ AOI saved · hash: <span className="font-mono">{savedAOI.geometry_hash?.slice(0, 16)}…</span>
        </div>
      )}

      <p className="text-[10px] text-muted-foreground">
        Geometry is never modified after saving. A SHA-256 hash is stored at creation for integrity verification.
      </p>
    </div>
  );
}