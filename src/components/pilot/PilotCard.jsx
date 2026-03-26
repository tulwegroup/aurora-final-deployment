/**
 * PilotCard — AOI & objective detail for a single pilot
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MapPin, Layers, Database } from "lucide-react";

const CONFIDENCE_STYLES = {
  HIGH:   "bg-emerald-100 text-emerald-800 border-emerald-300",
  MEDIUM: "bg-amber-100 text-amber-800 border-amber-300",
  LOW:    "bg-red-100 text-red-800 border-red-300",
};

export default function PilotCard({ pilot }) {
  const { aoi, commodity, resolution, scan_tier, ground_truth } = pilot;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* AOI */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <MapPin className="w-4 h-4" /> Area of Interest
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <div className="text-xs text-muted-foreground">Name</div>
            <div className="text-sm font-medium">{aoi.name}</div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              ["Min Lat", aoi.bbox.min_lat],
              ["Max Lat", aoi.bbox.max_lat],
              ["Min Lon", aoi.bbox.min_lon],
              ["Max Lon", aoi.bbox.max_lon],
            ].map(([k, v]) => (
              <div key={k} className="bg-muted/40 rounded px-2 py-1.5">
                <div className="text-muted-foreground">{k}</div>
                <div className="font-mono font-medium">{v}°</div>
              </div>
            ))}
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Area (approx)</div>
            <div className="text-sm font-medium">{aoi.area_km2_approx.toLocaleString()} km²</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Environment</div>
            <div className="text-sm font-mono">{aoi.environment_type}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Description</div>
            <div className="text-xs leading-relaxed mt-0.5">{aoi.description}</div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {/* Scan parameters */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Layers className="w-4 h-4" /> Scan Parameters
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {[
              ["Commodity",  commodity],
              ["Resolution", resolution],
              ["Scan Tier",  scan_tier],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between items-center py-1 border-b last:border-0">
                <span className="text-muted-foreground text-xs">{k}</span>
                <span className="font-medium capitalize">{v}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Ground truth */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Database className="w-4 h-4" /> Ground Truth Context
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Confidence</span>
              <Badge className={`text-xs border ${CONFIDENCE_STYLES[ground_truth.confidence]}`}>
                {ground_truth.confidence}
              </Badge>
            </div>
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Sources</div>
              {ground_truth.sources.map((s, i) => (
                <div key={i} className="text-xs flex items-start gap-1.5">
                  <span className="text-muted-foreground mt-0.5">·</span>
                  <span>{s}</span>
                </div>
              ))}
            </div>
            {ground_truth.notes && (
              <div className="text-xs bg-muted/40 rounded px-2 py-1.5 leading-relaxed">
                {ground_truth.notes}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}