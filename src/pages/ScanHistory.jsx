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
import { history } from "../lib/auroraApi";
import { ScanStatusBadge, SystemStatusBadge } from "../components/ScanStatusBadge";
import MissingValue, { ValueOrMissing } from "../components/MissingValue";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, ChevronLeft, ChevronRight, ArrowRight } from "lucide-react";
import APIOffline from "../components/APIOffline";

export default function ScanHistory() {
  const [data, setData]         = useState(null);
  const [page, setPage]         = useState(1);
  const [commodity, setCommodity] = useState("");
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  async function load(p = page, c = commodity) {
    setLoading(true);
    setError(null);
    try {
      const params = { page: p, page_size: 20 };
      if (c) params.commodity = c;
      const d = await history.list(params);
      setData(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function handleSearch(e) {
    e.preventDefault();
    setPage(1);
    load(1, commodity);
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

      {!loading && data && (
        <>
          <div className="text-sm text-muted-foreground">{data.total} completed scans</div>

          <div className="space-y-2">
            {data.scans.length === 0 && (
              <Card><CardContent className="py-8 text-center text-muted-foreground text-sm">No completed scans found.</CardContent></Card>
            )}
            {data.scans.map(scan => (
              <Card key={scan.scan_id} className="hover:border-primary/40 transition-colors">
                <CardContent className="py-3 px-4 flex items-center gap-4">
                  <div className="flex-1 min-w-0 space-y-0.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium">{scan.commodity}</span>
                      <ScanStatusBadge status={scan.status} />
                      {scan.system_status && <SystemStatusBadge status={scan.system_status} />}
                    </div>
                    <div className="text-xs text-muted-foreground font-mono">{scan.scan_id}</div>
                  </div>

                  {/* ACIF score — verbatim from API, formatted for display only */}
                  <div className="text-right">
                    <div className="text-sm font-medium tabular-nums">
                      <ValueOrMissing
                        value={scan.display_acif_score}
                        format={v => `${(v * 100).toFixed(1)}%`}
                        label="ACIF score not available"
                      />
                    </div>
                    <div className="text-xs text-muted-foreground">ACIF</div>
                  </div>

                  {/* Tier 1 count — verbatim from API */}
                  <div className="text-right">
                    <div className="text-sm font-medium tabular-nums">
                      <ValueOrMissing value={scan.tier_1_count} label="Tier 1 count unavailable" />
                    </div>
                    <div className="text-xs text-muted-foreground">Tier 1 cells</div>
                  </div>

                  <div className="text-xs text-muted-foreground whitespace-nowrap">
                    {scan.completed_at ? new Date(scan.completed_at).toLocaleDateString() : <MissingValue inline />}
                  </div>

                  <Link to={`/history/${scan.scan_id}`}>
                    <Button variant="ghost" size="sm"><ArrowRight className="w-4 h-4" /></Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Pagination */}
          {data.total_pages > 1 && (
            <div className="flex items-center gap-2 justify-center">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => { setPage(p => p - 1); load(page - 1); }}>
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="text-sm text-muted-foreground">Page {page} of {data.total_pages}</span>
              <Button variant="outline" size="sm" disabled={page >= data.total_pages} onClick={() => { setPage(p => p + 1); load(page + 1); }}>
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}