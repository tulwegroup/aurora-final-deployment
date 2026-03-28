/**
 * TopTargetsPanel — Dynamically updated top 5 anomalies
 */
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function TopTargetsPanel({ targets }) {
  return (
    <Card className="h-full flex flex-col bg-slate-900 border-slate-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-white">Top 5 Targets</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto space-y-2">
        {targets.length === 0 ? (
          <div className="text-xs text-slate-500 italic">Targets appear as scan progresses…</div>
        ) : (
          targets.map((target, idx) => (
            <div
              key={target.cell_id}
              className="bg-slate-800 rounded p-2 border border-slate-700 hover:border-slate-500 transition-colors"
            >
              <div className="flex items-start justify-between gap-2 text-xs">
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-white">#{idx + 1}</div>
                  <div className="text-slate-400 text-[10px] mt-0.5">{target.cell_id}</div>
                  <div className="text-slate-400 text-[10px]">
                    {target.lat.toFixed(4)}, {target.lon.toFixed(4)}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold text-emerald-400">
                    {target.acif.toFixed(3)}
                  </div>
                  <Badge
                    variant="outline"
                    className="text-[10px] mt-1 border-slate-600 text-slate-300"
                  >
                    {target.tier}
                  </Badge>
                </div>
              </div>
              <div className="w-full bg-slate-700 rounded-full overflow-hidden h-1.5 mt-1.5">
                <div
                  className="bg-emerald-500 h-full"
                  style={{ width: `${target.acif * 100}%` }}
                />
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}