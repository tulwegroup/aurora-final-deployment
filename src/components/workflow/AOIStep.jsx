/**
 * AOIStep — Step 1: Define Area of Interest
 * Phase AI §AI.2
 */
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MapPin, Upload, Pencil, ChevronRight } from "lucide-react";
import { base44 } from "@/api/base44Client";

const INPUT_MODES = [
  { id: "draw",   label: "Draw on Map",        icon: Pencil },
  { id: "bbox",   label: "Bounding Box",        icon: MapPin },
  { id: "upload", label: "Upload KML/GeoJSON",  icon: Upload },
];

export default function AOIStep({ onDone }) {
  const [mode, setMode]             = useState("bbox");
  const [minLat, setMinLat]         = useState("");
  const [maxLat, setMaxLat]         = useState("");
  const [minLon, setMinLon]         = useState("");
  const [maxLon, setMaxLon]         = useState("");
  const [file, setFile]             = useState(null);
  const [validating, setValidating] = useState(false);
  const [error, setError]           = useState(null);
  const [result, setResult]         = useState(null);

  async function handleValidate() {
    setValidating(true);
    setError(null);
    try {
      let payload = { mode };
      if (mode === "bbox") {
        payload = { mode, min_lat: +minLat, max_lat: +maxLat, min_lon: +minLon, max_lon: +maxLon };
      } else if (mode === "upload" && file) {
        const { file_url } = await base44.integrations.Core.UploadFile({ file });
        payload = { mode, file_url };
      }
      const res = await base44.functions.invoke("validateAoi", payload);
      setResult(res.data);
    } catch (e) {
      setError(e.message);
    } finally {
      setValidating(false);
    }
  }

  const canValidate = mode === "bbox"
    ? [minLat, maxLat, minLon, maxLon].every(v => v !== "" && !isNaN(+v))
    : mode === "upload" ? !!file : false;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left: input */}
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Input Method</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {INPUT_MODES.map((m) => {
              const ModeIcon = m.icon;
              return (
                <button
                  key={m.id}
                  onClick={() => { setMode(m.id); setResult(null); setError(null); }}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg border text-sm transition-colors ${
                    mode === m.id ? "border-primary bg-primary/5 font-medium" : "border-border hover:bg-muted"
                  }`}
                >
                  <ModeIcon className="w-4 h-4 shrink-0" />{m.label}
                </button>
              );
            })}
          </CardContent>
        </Card>

        {mode === "bbox" && (
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-base">Bounding Box (WGS84)</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              {[["Min Lat", minLat, setMinLat], ["Max Lat", maxLat, setMaxLat],
                ["Min Lon", minLon, setMinLon], ["Max Lon", maxLon, setMaxLon]].map(([label, val, setter]) => (
                <div key={label} className="space-y-1">
                  <label className="text-xs text-muted-foreground">{label}</label>
                  <input
                    type="number" step="any"
                    value={val}
                    onChange={e => { setter(e.target.value); setResult(null); }}
                    className="w-full border rounded px-2 py-1.5 text-sm"
                    placeholder="0.0000"
                  />
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {mode === "upload" && (
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-base">Upload File</CardTitle></CardHeader>
            <CardContent>
              <input
                type="file" accept=".kml,.geojson,.json"
                onChange={e => { setFile(e.target.files[0]); setResult(null); }}
                className="text-sm"
              />
              {file && <p className="text-xs text-muted-foreground mt-2">{file.name}</p>}
            </CardContent>
          </Card>
        )}

        {mode === "draw" && (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground text-sm">
              Interactive map drawing is available in the{" "}
              <a href="/map-builder" className="underline text-primary">Map Builder</a>.
              Use bounding box or upload for this workflow.
            </CardContent>
          </Card>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        <Button
          className="w-full"
          disabled={!canValidate || validating}
          onClick={handleValidate}
        >
          {validating ? "Validating…" : "Validate AOI"}
        </Button>
      </div>

      {/* Right: AOI preview */}
      <div className="space-y-4">
        {result ? (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <MapPin className="w-4 h-4 text-emerald-600" /> AOI Validated
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                {[
                  ["AOI ID",        result.aoi_id?.slice(0, 12) + "…"],
                  ["Area",          `${result.area_km2?.toFixed(1)} km²`],
                  ["Environment",   result.environment_type || "—"],
                  ["Geometry Hash", result.geometry_hash?.slice(0, 10) + "…"],
                ].map(([k, v]) => (
                  <div key={k} className="bg-muted/40 rounded px-3 py-2">
                    <div className="text-xs text-muted-foreground">{k}</div>
                    <div className="text-sm font-medium font-mono">{v}</div>
                  </div>
                ))}
              </div>
              <Button className="w-full" onClick={() => onDone(result)}>
                Continue <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground text-sm">
              AOI preview will appear after validation.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}