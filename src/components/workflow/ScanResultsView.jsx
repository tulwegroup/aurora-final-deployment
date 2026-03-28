/**
 * ScanResultsView — Step 3: View Canonical Outputs
 * Phase AI §AI.4
 *
 * CONSTITUTIONAL RULE: All values displayed are read verbatim from stored
 * canonical outputs. No ACIF formula, no tier derivation, no recomputation.
 * This component is pure display — it reads and renders, never computes.
 */
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Loader2, Map, Box, FileText, ChevronRight, ExternalLink, AlertTriangle } from "lucide-react";
import { base44 } from "@/api/base44Client";
import { GHANA_SCAN_RESULT } from "../../lib/demoData";

const TIER_STYLES = {
  TIER_1: "bg-emerald-100 text-emerald-800",
  TIER_2: "bg-blue-100 text-blue-800",
  TIER_3: "bg-amber-100 text-amber-800",
};

export default function ScanResultsView({ scanId, aoi, onExport, demoMode }) {
  const [scan,    setScan]    = useState(demoMode ? GHANA_SCAN_RESULT : null);
  const [loading, setLoading] = useState(!demoMode);
  const [error,   setError]   = useState(null);
  const [polling, setPolling] = useState(!demoMode);

  useEffect(() => {
    if (demoMode || !scanId) return;
    let timer;
    async function poll() {
      try {
        const res = await base44.functions.invoke("getScanStatus", { scan_id: scanId });
        const s = res.data;
        setScan(s);
        if (s.status === "completed" || s.status === "failed") {
          setPolling(false);
        } else {
          timer = setTimeout(poll, 4000);
        }
      } catch (e) {
        setError(e.message);
        setPolling(false);
      } finally {
        setLoading(false);
      }
    }
    poll();
    return () => clearTimeout(timer);
  }, [scanId, demoMode]);

  if (loading) return (
    <div className="flex items-center justify-center py-24 gap-2 text-muted-foreground">
      <Loader2 className="w-5 h-5 animate-spin" /> Loading scan…
    </div>
  );
  if (error) return <p className="text-destructive text-sm">{error}</p>;
  if (!scan) return null;

  const isPending   = scan.status !== "completed" && scan.status !== "failed";
  const tierCounts  = scan.tier_counts || {};

  return (
    <div className="space-y-5">
      {/* Status bar */}
      <Card>
        <CardContent className="py-3 flex flex-wrap items-center gap-4">
          <div>
            <div className="text-xs text-muted-foreground">Scan ID</div>
            <div className="font-mono text-xs">{scanId?.slice(0, 20)}…</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Status</div>
            <div className={`text-sm font-medium ${
              scan.status === "completed" ? "text-emerald-600" :
              scan.status === "failed"    ? "text-destructive" : "text-amber-600"
            }`}>
              {scan.status?.toUpperCase()}
              {isPending && <Loader2 className="w-3 h-3 inline ml-1 animate-spin" />}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">System Status</div>
            <div className="text-sm font-medium">{scan.system_status || "—"}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">ACIF Mean (stored)</div>
            <div className="text-sm font-mono">{scan.acif_mean?.toFixed(4) ?? "—"}</div>
          </div>
        </CardContent>
      </Card>

      {isPending && (
        <div className="text-sm text-muted-foreground border rounded-lg px-4 py-3 flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" /> Scan in progress — auto-refreshing every 4s…
        </div>
      )}

      {scan.status === "failed" && (
        <div className="text-sm text-destructive border border-destructive/30 bg-destructive/5 rounded-lg px-4 py-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" /> Scan failed. Please re-submit.
        </div>
      )}

      {scan.status === "completed" && (
        <Tabs defaultValue="summary">
          <TabsList>
            <TabsTrigger value="summary">Summary</TabsTrigger>
            <TabsTrigger value="layers"><Map className="w-3.5 h-3.5 mr-1" />Map Layers</TabsTrigger>
            <TabsTrigger value="twin"><Box className="w-3.5 h-3.5 mr-1" />Digital Twin</TabsTrigger>
            <TabsTrigger value="report"><FileText className="w-3.5 h-3.5 mr-1" />Report</TabsTrigger>
          </TabsList>

          {/* Summary */}
          <TabsContent value="summary" className="mt-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(tierCounts).map(([tier, count]) => (
                <Card key={tier}>
                  <CardContent className="py-3 px-4">
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${TIER_STYLES[tier] || "bg-muted"}`}>{tier}</span>
                    <div className="text-2xl font-bold tabular-nums mt-1">{count}</div>
                    <div className="text-xs text-muted-foreground">cells</div>
                  </CardContent>
                </Card>
              ))}
              <Card>
                <CardContent className="py-3 px-4">
                  <div className="text-xs text-muted-foreground">Veto Cells</div>
                  <div className="text-2xl font-bold tabular-nums mt-1">{scan.veto_count ?? "—"}</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="py-3 px-4">
                  <div className="text-xs text-muted-foreground">Total Cells</div>
                  <div className="text-2xl font-bold tabular-nums mt-1">{scan.total_cells?.toLocaleString() ?? "—"}</div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Map Layers */}
          <TabsContent value="layers" className="mt-4">
            <Card>
              <CardContent className="py-6 space-y-3">
                <p className="text-sm text-muted-foreground">
                  Interactive map layers and export tools are available in the dedicated viewers.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Link to={`/datasets/${scanId}`}>
                    <Button variant="outline" size="sm"><ExternalLink className="w-3.5 h-3.5 mr-1.5" />Dataset View</Button>
                  </Link>
                  <Link to={`/map-export/${scanId}`}>
                    <Button variant="outline" size="sm"><Map className="w-3.5 h-3.5 mr-1.5" />Map Export</Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Digital Twin */}
          <TabsContent value="twin" className="mt-4">
            <Card>
              <CardContent className="py-6 space-y-3">
                <p className="text-sm text-muted-foreground">
                  3D voxel visualisation available in the Digital Twin viewer.
                </p>
                <Link to={`/twin/${scanId}`}>
                  <Button variant="outline" size="sm"><Box className="w-3.5 h-3.5 mr-1.5" />Open Digital Twin</Button>
                </Link>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Report */}
          <TabsContent value="report" className="mt-4">
            <Card>
              <CardContent className="py-6 space-y-3">
                <p className="text-sm text-muted-foreground">
                  Geological interpretation report grounded on stored canonical outputs.
                </p>
                <Link to={`/reports/${scanId}`}>
                  <Button variant="outline" size="sm"><FileText className="w-3.5 h-3.5 mr-1.5" />View Report</Button>
                </Link>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}

      {scan.status === "completed" && (
        <div className="flex justify-end">
          <Button onClick={onExport}>
            Proceed to Export <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      )}
    </div>
  );
}