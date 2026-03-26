/**
 * MapExport — canonical layer export page
 * Phase AA §AA.13
 *
 * Allows export of canonical scan layers as KML, KMZ, or GeoJSON.
 * Layer field mapping displayed for full auditability.
 *
 * CONSTITUTIONAL RULES:
 *   - All layers sourced from stored canonical fields.
 *   - No tier derivation at export time.
 *   - geometry_hash embedded in every export.
 */
import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { base44 } from "@/api/base44Client";
import LayerOverlaySelector from "../components/LayerOverlaySelector";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Download, ArrowLeft, Loader2 } from "lucide-react";

const FORMATS = [
  { id: "kml",     label: "KML",     desc: "Google Earth compatible" },
  { id: "kmz",     label: "KMZ",     desc: "Zipped KML archive" },
  { id: "geojson", label: "GeoJSON", desc: "Google Maps overlay" },
];

export default function MapExport() {
  const { scanId } = useParams();
  const [selectedLayers, setSelectedLayers] = useState([]);
  const [format, setFormat]                 = useState("kml");
  const [loading, setLoading]               = useState(false);
  const [error, setError]                   = useState(null);
  const [exported, setExported]             = useState(null);

  function toggleLayer(id) {
    setSelectedLayers(prev =>
      prev.includes(id) ? prev.filter(l => l !== id) : [...prev, id]
    );
  }

  async function handleExport() {
    if (!selectedLayers.length) return;
    setLoading(true);
    setError(null);
    try {
      const res = await base44.functions.invoke("mapExport", {
        scan_id: scanId,
        format,
        layers: selectedLayers,
        include_hash: true,
      });
      setExported(res.data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl space-y-5">
      <div className="flex items-center gap-3">
        {scanId && (
          <Link to={`/history/${scanId}`} className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="w-4 h-4" />
          </Link>
        )}
        <div>
          <h1 className="text-xl font-bold">Map Export</h1>
          {scanId && (
            <p className="text-xs font-mono text-muted-foreground mt-0.5">{scanId}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Layer selector */}
        <div className="md:col-span-2">
          <LayerOverlaySelector
            selectedLayers={selectedLayers}
            onToggle={toggleLayer}
          />
        </div>

        {/* Export controls */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Export Format</CardTitle></CardHeader>
            <CardContent className="pt-0 space-y-2">
              {FORMATS.map(f => (
                <label key={f.id} className="flex items-center gap-2 cursor-pointer">
                  <input type="radio" name="format" value={f.id}
                    checked={format === f.id} onChange={() => setFormat(f.id)} />
                  <div>
                    <div className="text-sm font-medium">{f.label}</div>
                    <div className="text-xs text-muted-foreground">{f.desc}</div>
                  </div>
                </label>
              ))}
            </CardContent>
          </Card>

          <Button
            className="w-full"
            disabled={!selectedLayers.length || loading}
            onClick={handleExport}
          >
            {loading
              ? <Loader2 className="w-4 h-4 animate-spin mr-1" />
              : <Download className="w-4 h-4 mr-1" />
            }
            Export {format.toUpperCase()}
          </Button>

          {error && (
            <p className="text-xs text-destructive">{error}</p>
          )}

          {exported && (
            <div className="text-xs bg-emerald-50 text-emerald-800 rounded px-3 py-2 space-y-1">
              <div className="font-medium">Export ready</div>
              <div>Format: {exported.format}</div>
              <div>Layers: {exported.layer_count}</div>
              {exported.geometry_hash && (
                <div className="font-mono text-[10px]">
                  hash: {exported.geometry_hash.slice(0, 16)}…
                </div>
              )}
            </div>
          )}

          <div className="text-[10px] text-muted-foreground border rounded p-2 space-y-1">
            <div className="font-medium">Coordinate precision</div>
            <div>Full IEEE 754 float64 — no rounding or simplification.</div>
            <div className="font-medium mt-1">Geometry hash</div>
            <div>SHA-256 embedded in every export for field verification.</div>
          </div>
        </div>
      </div>
    </div>
  );
}