/**
 * ScanMapPanel — Interactive map with cell grid overlay
 * Cells animate and color by tier
 */
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

const TIER_COLORS = {
  TIER_1: "#22c55e", // green
  TIER_2: "#eab308", // yellow
  TIER_3: "#f97316", // orange
  UNSCANNED: "#64748b", // slate
};

export default function ScanMapPanel({ cells, scanId }) {
  // Normalize coords to canvas
  const minLat = -5.8, maxLat = -4.8, minLon = -2.0, maxLon = -1.0;
  const width = 500, height = 500;

  const cellToPixel = (lat, lon) => ({
    x: ((lon - minLon) / (maxLon - minLon)) * width,
    y: ((maxLat - lat) / (maxLat - minLat)) * height,
  });

  return (
    <Card className="h-full flex flex-col bg-slate-900 border-slate-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-white">Scan Grid ({cells.length} cells)</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-auto p-0">
        <svg
          width={width}
          height={height}
          className="bg-slate-950 border border-slate-700 rounded"
          viewBox={`0 0 ${width} ${height}`}
          style={{ aspectRatio: "1 / 1" }}
        >
          {/* Grid background */}
          <defs>
            <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
              <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#1e293b" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width={width} height={height} fill="url(#grid)" />

          {/* AOI boundary */}
          <rect
            x={0}
            y={0}
            width={width}
            height={height}
            fill="none"
            stroke="#3b82f6"
            strokeWidth="2"
            strokeDasharray="5,5"
          />

          {/* Cells */}
          {cells.map(cell => {
            const { x, y } = cellToPixel(cell.lat, cell.lon);
            const color = TIER_COLORS[cell.tier] || TIER_COLORS.UNSCANNED;
            return (
              <g key={cell.cell_id} className="group cursor-pointer">
                {/* Glow animation */}
                <circle
                  cx={x}
                  cy={y}
                  r="8"
                  fill={color}
                  opacity="0.3"
                  className="animate-pulse"
                />
                {/* Main cell */}
                <circle
                  cx={x}
                  cy={y}
                  r="5"
                  fill={color}
                  stroke="white"
                  strokeWidth="1"
                  className="transition-all group-hover:r-7"
                />
                {/* Tooltip on hover */}
                <title>
                  {cell.cell_id} | ACIF: {cell.acif.toFixed(3)} | {cell.tier} | Signal: {cell.signal}
                </title>
              </g>
            );
          })}
        </svg>

        {/* Legend */}
        <div className="p-3 bg-slate-900 border-t border-slate-800 text-xs space-y-1 text-slate-300">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded" style={{ backgroundColor: TIER_COLORS.TIER_1 }} />
            <span>Tier 1 (high)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded" style={{ backgroundColor: TIER_COLORS.TIER_2 }} />
            <span>Tier 2 (moderate)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded" style={{ backgroundColor: TIER_COLORS.TIER_3 }} />
            <span>Tier 3 (weak)</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}