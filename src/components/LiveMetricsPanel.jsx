/**
 * LiveMetricsPanel — Real-time scan metrics display
 */
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const STATUS_COLORS = {
  INITIALIZING: "bg-slate-600",
  SCANNING: "bg-blue-600 animate-pulse",
  REFINING: "bg-yellow-600",
  FINALIZING: "bg-emerald-600",
  COMPLETE: "bg-emerald-500",
};

export default function LiveMetricsPanel({ metrics }) {
  const progress = Math.round((metrics.cells_processed / metrics.cells_total) * 100);

  return (
    <Card className="h-full flex flex-col bg-slate-900 border-slate-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-white">Live Metrics</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 space-y-3 overflow-auto text-white text-sm">
        {/* Status badge */}
        <div className="flex items-center gap-2">
          <Badge className={STATUS_COLORS[metrics.system_status]}>
            {metrics.system_status}
          </Badge>
          <span className="text-xs text-slate-400">{progress}%</span>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-slate-700 rounded-full overflow-hidden h-2">
          <div
            className="bg-gradient-to-r from-blue-500 to-purple-500 h-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Key metrics */}
        <div className="grid grid-cols-2 gap-3 text-center">
          <div className="bg-slate-800 rounded p-2">
            <div className="text-xs text-slate-400">Mean ACIF</div>
            <div className="text-lg font-bold">{metrics.mean_acif}</div>
          </div>
          <div className="bg-slate-800 rounded p-2">
            <div className="text-xs text-slate-400">Max ACIF</div>
            <div className="text-lg font-bold text-emerald-400">{metrics.max_acif}</div>
          </div>
        </div>

        {/* Cell count */}
        <div className="bg-slate-800 rounded p-2">
          <div className="text-xs text-slate-400">Cells Processed</div>
          <div className="text-lg font-bold">
            {metrics.cells_processed}/{metrics.cells_total}
          </div>
        </div>

        {/* Tier distribution */}
        <div className="space-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-slate-400">Tier 1</span>
            <span className="font-bold text-emerald-400">{metrics.tier_1}</span>
          </div>
          <div className="w-full bg-slate-700 rounded-full overflow-hidden h-1.5">
            <div
              className="bg-emerald-500 h-full"
              style={{ width: `${(metrics.tier_1 / Math.max(metrics.cells_processed, 1)) * 100}%` }}
            />
          </div>

          <div className="flex justify-between mt-2">
            <span className="text-slate-400">Tier 2</span>
            <span className="font-bold text-yellow-400">{metrics.tier_2}</span>
          </div>
          <div className="w-full bg-slate-700 rounded-full overflow-hidden h-1.5">
            <div
              className="bg-yellow-500 h-full"
              style={{ width: `${(metrics.tier_2 / Math.max(metrics.cells_processed, 1)) * 100}%` }}
            />
          </div>

          <div className="flex justify-between mt-2">
            <span className="text-slate-400">Tier 3</span>
            <span className="font-bold text-orange-400">{metrics.tier_3}</span>
          </div>
          <div className="w-full bg-slate-700 rounded-full overflow-hidden h-1.5">
            <div
              className="bg-orange-500 h-full"
              style={{ width: `${(metrics.tier_3 / Math.max(metrics.cells_processed, 1)) * 100}%` }}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}