/**
 * VoxelLegend — colour scale legend for voxel renderer
 * Phase Q §Q.2
 *
 * CONSTITUTIONAL RULE:
 *   Displays the direct linear mapping from probability [0 → 1] to colour.
 *   No threshold lines, no tier boundaries, no percentile markers.
 *   Low → deep blue (#1a5276),  High → amber-gold (#f39c12)
 *   These colours exactly match COLOUR_LOW and COLOUR_HIGH in VoxelRenderer.jsx.
 *
 * Displayed values are the probability endpoints: 0.0 and 1.0 from the
 * stored commodity_probs field. No axis rescaling occurs.
 */
export default function VoxelLegend({ commodity, voxelCount, twinVersion, displayedCount }) {
  return (
    <div className="space-y-2 text-xs">
      <div className="font-medium text-sm">{commodity} probability</div>

      {/* Linear gradient — exactly matches linearColour() in VoxelRenderer */}
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground tabular-nums w-6">0.0</span>
        <div
          className="flex-1 h-3 rounded"
          style={{ background: "linear-gradient(to right, #1a5276, #f39c12)" }}
        />
        <span className="text-muted-foreground tabular-nums w-6">1.0</span>
      </div>
      <div className="flex justify-between text-muted-foreground">
        <span>Low</span>
        <span>High</span>
      </div>

      {/* Metadata */}
      <div className="border-t pt-2 space-y-1 text-muted-foreground">
        <div className="flex justify-between">
          <span>Twin version</span>
          <span className="font-mono">{twinVersion ?? "—"}</span>
        </div>
        <div className="flex justify-between">
          <span>Stored voxels</span>
          <span className="font-mono">{voxelCount ?? "—"}</span>
        </div>
        {displayedCount !== voxelCount && displayedCount != null && (
          <div className="flex justify-between text-amber-600">
            <span>Displayed (decimated)</span>
            <span className="font-mono">{displayedCount}</span>
          </div>
        )}
      </div>

      <div className="text-muted-foreground/70 text-[10px] border-t pt-1">
        Colour = direct linear map of stored commodity_probs.
        No log / percentile / histogram scaling applied.
      </div>
    </div>
  );
}