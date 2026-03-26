/**
 * LayerOverlaySelector — canonical layer toggle panel
 * Phase AA §AA.12
 *
 * Allows users to select which canonical layers to display or export.
 * Each layer shows its source_field for full field-mapping auditability.
 *
 * CONSTITUTIONAL RULE: Layer definitions are read from LAYER_REGISTRY.
 * No layer derives tier membership or ACIF at display time.
 */
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Layers } from "lucide-react";

const LAYER_GROUPS = [
  {
    group: "AOI & Grid",
    layers: [
      { id: "aoi_polygon",    label: "AOI Boundary",     source: "scan.aoi_polygon" },
      { id: "scan_cell_grid", label: "Cell Grid",         source: "cell.lat/lon_center" },
    ],
  },
  {
    group: "Tier Cells (stored)",
    layers: [
      { id: "tier_1_cells", label: "Tier 1 Cells", source: "cell.tier = TIER_1 (stored)" },
      { id: "tier_2_cells", label: "Tier 2 Cells", source: "cell.tier = TIER_2 (stored)" },
      { id: "tier_3_cells", label: "Tier 3 Cells", source: "cell.tier = TIER_3 (stored)" },
      { id: "vetoed_cells", label: "Vetoed Cells", source: "cell.any_veto_fired (stored)" },
    ],
  },
  {
    group: "Features",
    layers: [
      { id: "voxel_surface",       label: "Voxel Surface",      source: "voxel.depth_m (stored)" },
      { id: "drill_candidates",    label: "Drill Candidates",   source: "drill_candidate.lat/lon" },
      { id: "ground_truth_points", label: "Ground Truth",       source: "gt_record.lat/lon (approved)" },
    ],
  },
];

export default function LayerOverlaySelector({ selectedLayers, onToggle, onExport, exportFormat = "geojson" }) {
  const selected = new Set(selectedLayers || []);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-1.5">
          <Layers className="w-4 h-4" /> Map Layers
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        {LAYER_GROUPS.map(({ group, layers }) => (
          <div key={group}>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
              {group}
            </div>
            <div className="space-y-1">
              {layers.map(({ id, label, source }) => (
                <label key={id} className="flex items-start gap-2 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={selected.has(id)}
                    onChange={() => onToggle?.(id)}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="text-xs font-medium">{label}</div>
                    <div className="text-[10px] text-muted-foreground font-mono">{source}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        ))}

        {onExport && selected.size > 0 && (
          <div className="border-t pt-2 space-y-1">
            <div className="text-[10px] text-muted-foreground">
              {selected.size} layer{selected.size !== 1 ? "s" : ""} selected
            </div>
            <button
              onClick={() => onExport([...selected], exportFormat)}
              className="w-full text-xs border rounded px-3 py-1.5 hover:bg-muted transition-colors"
            >
              Export {exportFormat.toUpperCase()}
            </button>
          </div>
        )}

        <p className="text-[10px] text-muted-foreground border-t pt-2">
          All layers sourced from stored canonical fields only.
          No tier derivation or ACIF evaluation occurs at render time.
        </p>
      </CardContent>
    </Card>
  );
}