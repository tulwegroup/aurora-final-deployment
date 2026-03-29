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
        <div className="grid grid-cols-10 gap-1">
          {Array(totalCells).fill(null).map((_, i) => {
            const cell = allCells[i];
            return (
              <div
                key={i}
                className={`aspect-square rounded transition-all ${cell ? tierColors[cell] : 'bg-slate-700 opacity-40'}`}
                title={cell ? `${cell}` : 'Pending'}
              />
            );
          })}
        </div>
      </div>

      {/* Compact stats */}
      <div className="grid grid-cols-3 gap-2 pt-1 text-xs border-t border-slate-700">
        <div className="text-center pt-2">
          <div className="text-slate-500 uppercase tracking-wide text-[10px]">Cells</div>
          <div className="text-lg font-bold text-emerald-400">{allCells.length}</div>
        </div>
        <div className="text-center pt-2">
          <div className="text-slate-500 uppercase tracking-wide text-[10px]">ACIF</div>
          <div className="text-lg font-bold text-blue-400">{(avgAcif * 100).toFixed(1)}%</div>
        </div>
        <div className="text-center pt-2">
          <div className="text-slate-500 uppercase tracking-wide text-[10px]">Tier 1</div>
          <div className="text-lg font-bold text-emerald-400">{scan.tier_1_count || 0}</div>
        </div>
      </div>
    </div>
  );
}