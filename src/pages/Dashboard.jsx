/**
 * Dashboard — Active scans overview + quick-action landing page
 */
import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { scans } from "../lib/auroraApi";
import { ScanStatusBadge } from "../components/ScanStatusBadge";
import MissingValue from "../components/MissingValue";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Loader2, RefreshCw, ArrowRight,
  Workflow, History, BarChart3, FileText, Lock, Map, FlaskConical
} from "lucide-react";
import { Link as RouterLink } from "react-router-dom";
import APIOffline from "../components/APIOffline";

const QUICK_ACTIONS = [
  { to: "/workflow",    icon: Workflow,  label: "New Scan",     desc: "Submit a new AOI scan workflow" },
  { to: "/history",     icon: History,   label: "Scan History", desc: "View completed canonical records" },
  { to: "/portfolio",   icon: BarChart3, label: "Portfolio",    desc: "Territory-level intelligence" },
  { to: "/reports",     icon: FileText,  label: "Reports",      desc: "Generate geological reports" },
  { to: "/data-room",   icon: Lock,      label: "Data Room",    desc: "Secure access packages" },
  { to: "/map-builder", icon: Map,       label: "Map Builder",  desc: "Draw AOI and initiate scan" },
];

export default function Dashboard() {
  const { user }              = useOutletContext() || {};
  const [active, setActive]   = useState(null);
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

  const greeting = user?.full_name
    ? `Welcome, ${user.full_name.split(" ")[0]}`
    : "Aurora OSI Dashboard";

  return (
    <div className="p-6 space-y-7 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{greeting}</h1>
          <p className="text-muted-foreground text-sm mt-1">Aurora Orbital Scan Intelligence — vNext</p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Ghana Gold demo banner */}
      <RouterLink to="/workflow?demo=ghana-gold">
        <div className="rounded-xl border border-amber-300 bg-amber-50 px-5 py-4 flex items-center gap-4 hover:bg-amber-100 transition-colors cursor-pointer">
          <FlaskConical className="w-8 h-8 text-amber-600 shrink-0" />
          <div className="flex-1">
            <div className="font-semibold text-amber-900 text-sm">🇬🇭 Ghana Gold Demo — Ashanti Belt</div>
            <div className="text-xs text-amber-700 mt-0.5">Run a full end-to-end scan workflow with pre-loaded Ashanti Belt data. No backend required.</div>
          </div>
          <span className="text-xs bg-amber-200 text-amber-800 px-2.5 py-1 rounded-full font-medium shrink-0">Launch Demo →</span>
        </div>
      </RouterLink>

      {/* Quick actions */}

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Active Scan Queue</h2>
          {active && <span className="text-xs text-muted-foreground">{active.total} running</span>}
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-muted-foreground text-sm py-4">
            <Loader2 className="w-4 h-4 animate-spin" /> Checking scan queue…
          </div>
        )}

        {error && <APIOffline error={error} endpoint="GET /api/v1/scan/active" onRetry={load} />}

        {!loading && !error && !active && (
          <APIOffline endpoint="GET /api/v1/scan/active" onRetry={load} hint="Aurora API not yet responding." />
        )}

        {!loading && active && (
          <>
            {(!active.active_scans || active.active_scans.length === 0) ? (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground text-sm space-y-2">
                  <div className="text-3xl">🛰</div>
                  <p>No active scans in queue.</p>
                  <p className="text-xs">
                    <Link to="/workflow" className="underline text-primary">Start a new scan workflow →</Link>
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-2">
                {active.active_scans.map(scan => (
                  <Card key={scan.scan_id} className="hover:border-primary/30 transition-colors">
                    <CardContent className="py-3 px-4 flex items-center gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs text-muted-foreground truncate">{scan.scan_id}</span>
                          <ScanStatusBadge status={scan.status} />
                        </div>
                        <div className="text-sm mt-0.5">
                          <span className="font-medium capitalize">{scan.commodity || <MissingValue inline />}</span>
                          {scan.scan_tier && <span className="text-muted-foreground ml-2">{scan.scan_tier}</span>}
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

      <p className="text-[11px] text-muted-foreground border-t pt-4">
        Aurora OSI vNext · All displayed values sourced verbatim from canonical API records.
      </p>
    </div>
  );
}