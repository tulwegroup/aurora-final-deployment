/**
 * VoxelControls — renderer settings panel
 * Phase Q §Q.3
 *
 * CONSTITUTIONAL RULES:
 *   - decimationStride: integer stride — subsamples voxels by index only.
 *     Does NOT alter individual voxel values.
 *   - depthScaleFactor: visual Y-axis scaling only — cosmetic, not physics.
 *   - Version selector: switches between stored twin versions (read-only).
 *   - Export button: triggers VoxelRenderer.exportSnapshot() — canvas capture.
 *   - No scientific controls: no threshold slider, no probability remapping.
 */
export default function VoxelControls({
  decimationStride,
  onDecimationChange,
  depthScaleFactor,
  onDepthScaleChange,
  twinVersions = [],
  selectedVersion,
  onVersionChange,
  onExport,
  loading,
}) {
  return (
    <div className="space-y-4 text-sm">
      {/* Version selector — read-only switch between stored versions */}
      {twinVersions.length > 1 && (
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
            Twin Version
          </label>
          <select
            className="w-full text-sm border rounded px-2 py-1 bg-background"
            value={selectedVersion}
            onChange={e => onVersionChange(Number(e.target.value))}
          >
            {twinVersions.map(v => (
              <option key={v.version} value={v.version}>
                v{v.version} — {v.voxel_count} voxels ({v.trigger})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Decimation stride — subsampling control (Rule: values unchanged) */}
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
          Decimation (display every Nth voxel)
        </label>
        <div className="flex items-center gap-2">
          <input
            type="range" min={1} max={20} step={1}
            value={decimationStride}
            onChange={e => onDecimationChange(Number(e.target.value))}
            className="flex-1"
          />
          <span className="tabular-nums w-6 text-right">{decimationStride}</span>
        </div>
        <p className="text-[10px] text-muted-foreground/70">
          Subsample by index only — voxel values are unchanged.
        </p>
      </div>

      {/* Depth scale — visual Y-axis compression (cosmetic only) */}
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
          Depth Scale (visual only)
        </label>
        <div className="flex items-center gap-2">
          <input
            type="range" min={0.01} max={0.2} step={0.01}
            value={depthScaleFactor}
            onChange={e => onDepthScaleChange(Number(e.target.value))}
            className="flex-1"
          />
          <span className="tabular-nums w-10 text-right">{depthScaleFactor.toFixed(2)}×</span>
        </div>
        <p className="text-[10px] text-muted-foreground/70">
          Cosmetic Y-axis compression. Does not alter depth_m values.
        </p>
      </div>

      {/* Snapshot export — deterministic canvas capture */}
      <button
        onClick={onExport}
        disabled={loading}
        className="w-full text-xs border rounded px-3 py-1.5 hover:bg-muted transition-colors disabled:opacity-50"
      >
        Export PNG Snapshot
      </button>
    </div>
  );
}