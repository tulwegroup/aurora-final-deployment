/**
 * LiveFeedPanel — Scrolling event log showing scan progression
 */
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

const TIER_BADGE_COLORS = {
  TIER_1: "bg-emerald-500/20 text-emerald-300",
  TIER_2: "bg-yellow-500/20 text-yellow-300",
  TIER_3: "bg-orange-500/20 text-orange-300",
};

export default function LiveFeedPanel({ feed }) {
  return (
    <Card className="h-full flex flex-col bg-slate-900 border-slate-800">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-white">Live Feed ({feed.length})</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto p-2 space-y-1">
        {feed.length === 0 ? (
          <div className="text-xs text-slate-500 italic">Waiting for scan to start…</div>
        ) : (
          feed.map(event => (
            <div
              key={event.id}
              className="text-xs bg-slate-800 rounded px-2 py-1.5 border-l-2 border-slate-700 hover:border-slate-500 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-slate-300 flex-1">{event.message}</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${TIER_BADGE_COLORS[event.tier] || "bg-slate-700 text-slate-300"}`}>
                  {event.tier}
                </span>
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">{event.timestamp}</div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}