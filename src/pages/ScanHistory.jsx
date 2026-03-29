/**
 * ScanHistory — paginated list of completed CanonicalScan summaries
 * Phase P §P.3
 *
 * CONSTITUTIONAL RULES:
 *  - All data from GET /history (CanonicalScanSummary records only).
 *  - display_acif_score shown as (value × 100)% — display formatting, not arithmetic.
 *  - system_status, tier_1_count rendered verbatim from API fields.
 *  - No threshold comparison, no tier recounting.
 *  - Null fields render MissingValue.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { base44 } from '@/api/base44Client';
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, ArrowRight } from "lucide-react";

export default function ScanHistory() {
  const [scans, setScans]       = useState([]);
  const [commodity, setCommodity] = useState("");
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const jobs = await base44.entities.ScanJob.list('-created_date', 100);
      setScans(jobs || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function handleSearch(e) {
    e.preventDefault();
  }

  return (
    <div className="p-6 space-y-5 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">Scan History</h1>
        <p className="text-muted-foreground text-sm mt-1">Completed canonical scan records</p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <Input
          placeholder="Filter by commodity…"
          value={commodity}
          onChange={e => setCommodity(e.target.value)}
          className="max-w-xs"
        />
        <Button type="submit" variant="outline">Search</Button>
      </form>

      {loading && <div className="flex items-center gap-2 text-muted-foreground text-sm"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>}
      {error && <APIOffline error={error} endpoint="GET /api/v1/history" onRetry={() => load()} />}

      {!loading && (
        <>
          <div className="text-sm text-muted-foreground">
            {(commodity ? scans.filter(s => s.commodity?.includes(commodity)) : scans).length} scans
          </div>
          <div className="space-y-2">
            {(commodity ? scans.filter(s => s.commodity?.includes(commodity)) : scans).length === 0 && (
              <Card><CardContent className="py-8 text-center text-muted-foreground text-sm">No scans found. Submit one from Map Builder.</CardContent></Card>
            )}
            {(commodity ? scans.filter(s => s.commodity?.includes(commodity)) : scans).map(scan => (
              <Card key={scan.id} className="hover:border-primary/40 transition-colors">
                <CardContent className="py-3 px-4 flex items-center gap-4">
                  <div className="flex-1 min-w-0 space-y-0.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium capitalize">{scan.commodity}</span>
                      <Badge variant={scan.status === 'completed' ? 'default' : scan.status === 'failed' ? 'destructive' : 'secondary'}>
                        {scan.status}
                      </Badge>
                      {scan.gee_sourced === false && <Badge variant="outline" className="text-[10px]">simulated</Badge>}
                    </div>
                    <div className="text-xs text-muted-foreground font-mono">{scan.scan_id || scan.id}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium tabular-nums">
                      {scan.display_acif_score != null ? `${(scan.display_acif_score * 100).toFixed(1)}%` : '—'}
                    </div>
                    <div className="text-xs text-muted-foreground">ACIF</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium tabular-nums">{scan.tier_1_count ?? '—'}</div>
                    <div className="text-xs text-muted-foreground">Tier 1 cells</div>
                  </div>
                  <div className="text-xs text-muted-foreground whitespace-nowrap">
                    {scan.completed_at ? new Date(scan.completed_at).toLocaleDateString() : scan.created_date ? new Date(scan.created_date).toLocaleDateString() : '—'}
                  </div>
                  <Link to={`/history/${scan.scan_id || scan.id}`}>
                    <Button variant="ghost" size="sm"><ArrowRight className="w-4 h-4" /></Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}