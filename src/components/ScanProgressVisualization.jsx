import { Square, Pause, RotateCcw } from "lucide-react";

export default function ScanProgressVisualization({ scan }) {
  // Generate cell grid visualization
  const tier1Cells = Array(scan.tier_1_count || 0).fill('TIER_1');
  const tier2Cells = Array(scan.tier_2_count || 0).fill('TIER_2');
  const tier3Cells = Array(scan.tier_3_count || 0).fill('TIER_3');
  const allCells = [...tier1Cells, ...tier2Cells, ...tier3Cells];
  const totalCells = scan.cell_count || 1;
  const avgAcif = allCells.length > 0 ? (scan.display_acif_score || 0) : 0;
  
  const tierColors = {
    TIER_1: 'bg-emerald-500 hover:bg-emerald-600',
    TIER_2: 'bg-amber-400 hover:bg-amber-500',
    TIER_3: 'bg-red-500 hover:bg-red-600',
  };

  return (
    <div className="bg-slate-900 text-white rounded-lg p-3 space-y-3">
      {/* Action buttons — compact row */}
      <div className="flex gap-1">
        <button className="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-1.5 px-2 rounded text-xs flex items-center justify-center gap-1 transition-colors">
          <Square className="w-3 h-3" /> Stop
        </button>
        <button className="flex-1 bg-slate-700 hover:bg-slate-600 text-white font-medium py-1.5 px-2 rounded text-xs flex items-center justify-center gap-1 transition-colors">
          <Pause className="w-3 h-3" /> Pause
        </button>
        <button className="flex-1 bg-blue-700 hover:bg-blue-600 text-white font-medium py-1.5 px-2 rounded text-xs flex items-center justify-center gap-1 transition-colors">
          <RotateCcw className="w-3 h-3" /> Re-Scan
        </button>
      </div>

      {/* Cell grid visualization */}
      <div className="bg-slate-800 rounded p-3 space-y-2">
        <div className="text-xs font-semibold text-slate-300">Cell Progress: {allCells.length} / {totalCells}</div>
        <div className="overflow-auto max-h-48">
          <div className="grid gap-1" style={{
            gridTemplateColumns: `repeat(auto-fill, minmax(12px, 1fr))`,
            minWidth: 'fit-content'
          }}>
            {Array(totalCells).fill(null).map((_, i) => {
              const cell = allCells[i];
              return (
                <div
                  key={i}
                  className={`w-3 h-3 rounded transition-all ${cell ? tierColors[cell] : 'bg-slate-700 opacity-40'}`}
                  title={cell ? `${cell}` : 'Pending'}
                />
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}