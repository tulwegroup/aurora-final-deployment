/**
 * AOIPreviewPanel — AOI metadata and workload preview
 * Phase AA §AA.11
 *
 * Displays: area, cell count per resolution, cost tier, environment,
 * geometry_hash (truncated), aoi_id, validation status.
 *
 * CONSTITUTIONAL RULE: displays stored infrastructure metadata only.
 * No ACIF, no tier assignment, no scientific output.
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle, Shield } from "lucide-react";

const ENV_STYLES = {
  onshore:  "bg-green-50 text-green-700",
  offshore: "bg-blue-50 text-blue-700",
  mixed:    "bg-amber-50 text-amber-700",
  unknown:  "bg-slate-50 text-slate-600",
};

const COST_STYLES = {
  micro:  "bg-slate-50 text-slate-600",
  small:  "bg-emerald-50 text-emerald-700",
  medium: "bg-amber-50 text-amber-700",
  large:  "bg-orange-50 text-orange-700",
  xlarge: "bg-red-50 text-red-700",
};

function Stat({ label, value, mono = false, badge = null }) {
  return (
    <div className="flex justify-between items-center py-1 border-b last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="flex items-center gap-1">
        {badge && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${badge.style}`}>
            {badge.label}
          </span>
        )}
        {value !== null && value !== undefined && (
          <span className={`text-xs font-medium ${mono ? "font-mono" : ""}`}>{value}</span>
        )}
      </div>
    </div>
  );
}

export default function AOIPreviewPanel({ aoi, estimate }) {
  if (!aoi) return null;

  const defaultOption = estimate?.options?.find(o => o.resolution === estimate.default_resolution)
    || estimate?.options?.[1];

  return (
    <div className="space-y-3">
      {/* AOI identity + integrity */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xs flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5 text-primary" />
            AOI Identity & Integrity
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <Stat label="AOI ID"     value={`${aoi.aoi_id?.slice(0,8)}…`} mono />
          <Stat label="Version"    value={`v${aoi.aoi_version}`} />
          <Stat label="Projection" value={aoi.map_projection} mono />
          <Stat label="Geometry Hash"
            value={`${aoi.geometry_hash?.slice(0,16)}…`} mono />
          <div className="mt-1 flex items-center gap-1 text-[10px] text-emerald-700">
            <CheckCircle className="w-3 h-3" />
            SHA-256 stored at creation — immutable after save
          </div>
        </CardContent>
      </Card>

      {/* Geometry metadata */}
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-xs">AOI Geometry</CardTitle></CardHeader>
        <CardContent className="pt-0">
          <Stat label="Area"
            value={aoi.area_km2 != null ? `${aoi.area_km2.toFixed(2)} km²` : "—"} />
          <Stat label="Environment"
            badge={aoi.environment ? {
              label: aoi.environment, style: ENV_STYLES[aoi.environment] || ""
            } : null}
            value={null}
          />
          <Stat label="Validation"
            badge={{ label: "Valid", style: "bg-emerald-50 text-emerald-700" }}
            value={null}
          />
          {aoi.centroid && (
            <Stat
              label="Centroid"
              value={`${aoi.centroid.lat?.toFixed(4)}, ${aoi.centroid.lon?.toFixed(4)}`}
              mono
            />
          )}
        </CardContent>
      </Card>

      {/* Workload estimates */}
      {estimate && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-xs">Workload Estimate</CardTitle></CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-1">
              {estimate.options?.map(opt => (
                <div key={opt.resolution}
                  className={`flex items-center justify-between rounded px-2 py-1 text-xs
                    ${opt.resolution === estimate.default_resolution ? "bg-primary/10 font-semibold" : ""}`}>
                  <span className="capitalize">{opt.resolution}</span>
                  <span className="tabular-nums">{opt.estimated_cells.toLocaleString()} cells</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${COST_STYLES[opt.cost_tier] || ""}`}>
                    {opt.cost_tier}
                  </span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-muted-foreground mt-2">
              * Cell counts are infrastructure estimates only — not scientific outputs.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}