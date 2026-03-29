import { Square, Pause, RotateCcw } from "lucide-react";

export default function ScanProgressVisualization({ scan }) {
  const cellsProcessed = scan.tier_1_count + scan.tier_2_count + scan.tier_3_count;
  const totalCells = scan.cell_count || 1;
  const progress = Math.round((cellsProcessed / totalCells) * 100);
  const avgAcif = cellsProcessed > 0 ? (scan.display_acif_score || 0) : 0;
  const maxAcif = 0.76; // Mock max for now
  
  return (
    <div className="bg-slate-900 text-white rounded-lg p-4 space-y-4">
      {/* Status dropdown */}
      <div className="flex items-center gap-2">
        <div className="flex-1">
          <select className="w-full bg-slate-800 text-white text-sm px-2 py-1 rounded border border-slate-700">
            <option>Streaming (live cells)</option>
          </select>
        </div>
      </div>

      {/* Progress bar */}
      <div className="space-y-2">
        <div className="h-3 bg-slate-800 rounded-full overflow-hidden">
          <div 
            className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="text-sm text-slate-400">{cellsProcessed} / {totalCells} cells</div>
      </div>

      {/* Action buttons */}
      <div className="space-y-2">
        <button className="w-full bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-3 rounded flex items-center justify-center gap-2 transition-colors">
          <Square className="w-4 h-4" /> Stop Scan
        </button>
        <button className="w-full bg-slate-700 hover:bg-slate-600 text-white font-medium py-2 px-3 rounded flex items-center justify-center gap-2 transition-colors">
          <Pause className="w-4 h-4" /> Pause
        </button>
        <button className="w-full bg-blue-700 hover:bg-blue-600 text-white font-medium py-2 px-3 rounded flex items-center justify-center gap-2 transition-colors">
          <RotateCcw className="w-4 h-4" /> Re-Scan (use last params)
        </button>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-700">
        <div className="text-center">
          <div className="text-xs text-slate-500 uppercase tracking-wide">CELLS</div>
          <div className="text-lg font-bold text-emerald-400">{cellsProcessed}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-slate-500 uppercase tracking-wide">MEAN ACIF</div>
          <div className="text-lg font-bold text-blue-400">{(avgAcif * 100).toFixed(1)}%</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-slate-500 uppercase tracking-wide">MAX ACIF</div>
          <div className="text-lg font-bold text-amber-400">{(maxAcif * 100).toFixed(1)}%</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-slate-500 uppercase tracking-wide">TIER 1</div>
          <div className="text-lg font-bold text-emerald-400">{scan.tier_1_count || 0}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-slate-500 uppercase tracking-wide">TIER 2</div>
          <div className="text-lg font-bold text-amber-400">{scan.tier_2_count || 0}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-slate-500 uppercase tracking-wide">SYSTEM</div>
          <div className="text-lg font-bold text-slate-400">—</div>
        </div>
      </div>
    </div>
  );
}