/**
 * Dashboard — active scans overview
 * Phase P §P.2
 *
 * CONSTITUTIONAL RULES:
 *  - Renders active scan list from GET /scan/active (execution state only).
 *  - No score fields appear on this page (active scans have none).
 *  - No ACIF arithmetic, no tier threshold references.
 *  - Missing fields render MissingValue.
 */
import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { scans } from "../lib/auroraApi";
import { ScanStatusBadge } from "../components/ScanStatusBadge";
import MissingValue from "../components/MissingValue";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, RefreshCw, ArrowRight } from "lucide-react";

export default function Dashboard() {
  const { user }          = useOutletContext() || {};
  const [active, setActive] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await scans.active();
      setActive(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground text-sm mt-1">Active scan queue</p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </div>
      )}

      {error && (
        <div className="text-sm text-destructive border border-destructive/30 rounded p-3">{error}</div>
      )}

      {!loading && active && (
        <>
          <div className="text-sm text-muted-foreground">
            {active.total} active scan{active.total !== 1 ? "s" : ""}
          </div>

          {active.active_scans.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground text-sm">
                No active scans. <Link to="/history" className="underline">View completed scans →</Link>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {active.active_scans.map(scan => (
                <Card key={scan.scan_id}>
                  <CardContent className="py-3 px-4 flex items-center gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-muted-foreground truncate">{scan.scan_id}</span>
                        <ScanStatusBadge status={scan.status} />
                      </div>
                      <div className="text-sm mt-0.5">
                        <span className="font-medium">{scan.commodity || <MissingValue inline />}</span>
                        <span className="text-muted-foreground ml-2">{scan.scan_tier} · {scan.environment}</span>
                      </div>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {scan.submitted_at ? new Date(scan.submitted_at).toLocaleString() : <MissingValue inline />}
                    </div>
                    <Link to={`/history/${scan.scan_id}`}>
                      <Button variant="ghost" size="sm"><ArrowRight className="w-4 h-4" /></Button>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}