/**
 * ProvenancePanel — provenance and confidence detail panel
 * Phase Z §Z.4
 *
 * Displays all provenance fields verbatim from the ground-truth record.
 * Shows confidence weighting components and composite score.
 * No scientific output (ACIF, tier) is rendered.
 */
import { ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function Field({ label, value, mono = false }) {
  if (!value && value !== 0) return null;
  return (
    <div className="flex justify-between gap-2 py-1 border-b last:border-0">
      <span className="text-xs text-muted-foreground shrink-0">{label}</span>
      <span className={`text-xs text-right ${mono ? "font-mono" : ""} break-all`}>{value}</span>
    </div>
  );
}

function ConfidenceBar({ label, value }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{label}</span>
        <span className="tabular-nums">{pct}%</span>
      </div>
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-400"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function ProvenancePanel({ record }) {
  if (!record) return null;

  const p = record.provenance || record;
  const c = record.confidence || {};

  return (
    <div className="space-y-3">
      {/* Provenance */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground">Provenance</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <Field label="Source"    value={p.source_name} />
          <Field label="Country"   value={p.country} />
          <Field label="Commodity" value={p.commodity} />
          <Field label="License"   value={p.license_note} />
          <Field label="Ingested"  value={p.ingestion_timestamp?.slice(0,19)} mono />
          {p.source_identifier && (
            <div className="flex justify-between gap-2 py-1">
              <span className="text-xs text-muted-foreground">Identifier</span>
              {p.source_identifier.startsWith("http") ? (
                <a
                  href={p.source_identifier}
                  target="_blank" rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline flex items-center gap-0.5"
                >
                  Link <ExternalLink className="w-3 h-3" />
                </a>
              ) : (
                <span className="text-xs font-mono">{p.source_identifier}</span>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Confidence weighting */}
      {c.source_confidence !== undefined && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground">
              Confidence Weighting
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0 space-y-2">
            <ConfidenceBar label="Source confidence"           value={c.source_confidence} />
            <ConfidenceBar label="Spatial accuracy"            value={c.spatial_accuracy} />
            <ConfidenceBar label="Temporal relevance"          value={c.temporal_relevance} />
            <ConfidenceBar label="Geological context strength" value={c.geological_context_strength} />
            <div className="border-t pt-2 flex justify-between text-xs">
              <span className="text-muted-foreground">Composite (geometric mean)</span>
              <span className="font-bold tabular-nums">
                {c.composite !== undefined ? `${(c.composite * 100).toFixed(1)}%` : "—"}
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Record metadata */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground">Record</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <Field label="ID"     value={record.record_id} mono />
          <Field label="Type"   value={record.geological_data_type} />
          <Field label="Status" value={record.status} />
          <Field label="Lat"    value={record.lat != null ? record.lat.toFixed(6) : null} mono />
          <Field label="Lon"    value={record.lon != null ? record.lon.toFixed(6) : null} mono />
          {record.rejection_reason && (
            <div className="mt-2 text-xs bg-red-50 text-red-700 rounded px-2 py-1.5">
              <span className="font-medium">Rejection reason: </span>{record.rejection_reason}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}