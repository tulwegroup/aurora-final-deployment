/**
 * LiveScanConsole — Real backend-driven live scan monitoring
 * 
 * CONSTITUTIONAL RULES:
 * - All displayed data sourced from real backend job-progress events or polling
 * - No fake cell generation or mock animations
 * - Tier colors: TIER_1 = green, TIER_2 = amber, TIER_3 = red
 * - Cell data includes: cell_id, lat/lon, acif, tier, modalities
 * - Transitions to completed scan detail on freeze
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { scans as scansApi, history as historyApi } from "../lib/auroraApi";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Play, Pause, RefreshCw, ArrowRight } from "lucide-react";
import APIOffline from "@/components/APIOffline";
import ScanMapPanel from "@/components/ScanMapPanel";
import LiveMetricsPanel from "@/components/LiveMetricsPanel";
import LiveFeedPanel from "@/components/LiveFeedPanel";
import TopTargetsPanel from "@/components/TopTargetsPanel";

const TIER_COLORS = {
  TIER_1: "bg-emerald-500",
  TIER_2: "bg-amber-400",
  TIER_3: "bg-red-500",
  DATA_MISSING: "bg-slate-300",
};

export default function LiveScanConsole() {
  const { jobId, scanId } = useParams();
  const navigate = useNavigate();
  const identifier = jobId || scanId;

  // State
  const [jobStatus, setJobStatus] = useState(null);
  const [cells, setCells] = useState([]);
  const [metrics, setMetrics] = useState({
    cells_processed: 0,
    cells_total: 0,
    mean_acif: 0,
    max_acif: 0,
    tier_1: 0,
    tier_2: 0,
    tier_3: 0,
    data_missing: 0,
    system_status: "INITIALIZING",
  });
  const [feed, setFeed] = useState([]);
  const [topTargets, setTopTargets] = useState([]);
  const [polling, setPolling] = useState(true);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const pollingIntervalRef = useRef(null);

  // Fetch real job status from backend
  const pollJobStatus = useCallback(async () => {
    try {
      const status = await scansApi.status(identifier);
      setJobStatus(status);
      setError(null);

      // Parse tier counts from status
      const tier1 = status.tier_1_count || 0;
      const tier2 = status.tier_2_count || 0;
      const tier3 = status.tier_3_count || 0;
      const missing = status.data_missing_count || 0;
      const processed = tier1 + tier2 + tier3 + missing;
      const total = status.cell_count || 0;

      setMetrics({
        cells_processed: processed,
        cells_total: total,
        mean_acif: status.display_acif_score || 0,
        max_acif: status.max_acif_score || 0,
        tier_1: tier1,
        tier_2: tier2,
        tier_3: tier3,
        data_missing: missing,
        system_status: status.status || "UNKNOWN",
      });

      // If completed, fetch cells data and show canonical results
      if (status.status === "completed") {
        setPolling(false);
        // Fetch canonical scan details
        try {
          const canonical = await historyApi.get(identifier);
          const cellsData = canonical.results_geojson?.features || [];
          setCells(
            cellsData.map((f) => ({
              cell_id: f.properties.cell_id || f.id,
              lat: f.geometry.coordinates[1],
              lon: f.geometry.coordinates[0],
              acif: f.properties.acif_score || 0,
              tier: f.properties.tier || "DATA_MISSING",
              modalities: f.properties.data_sources || [],
            }))
          );
        } catch (e) {
          console.warn("Could not fetch canonical cells:", e.message);
        }
      } else if (status.status === "failed") {
        setPolling(false);
        setError(status.error_message || "Scan failed");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [identifier]);

  // Initial load and setup polling
  useEffect(() => {
    pollJobStatus();
    if (polling) {
      pollingIntervalRef.current = setInterval(pollJobStatus, 2000);
    }
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [pollJobStatus, polling]);

  // Update top targets when cells change
  useEffect(() => {
    if (cells.length > 0) {
      const sorted = [...cells]
        .filter((c) => c.tier !== "DATA_MISSING")
        .sort((a, b) => b.acif - a.acif)
        .slice(0, 5);
      setTopTargets(sorted);
    }
  }, [cells]);

  // Handle completion -> redirect to detail page
  const handleViewCompleted = () => {
    navigate(`/history/${identifier}`);
  };

  if (loading && !jobStatus) {
    return (
      <div className="flex items-center justify-center h-screen gap-2 text-muted-foreground">
        <Loader2 className="w-5 h-5 animate-spin" /> Loading scan status…
      </div>
    );
  }

  const isCompleted =
    jobStatus?.status === "completed" ||
    metrics.system_status === "completed";
  const isFailed = jobStatus?.status === "failed";

  return (
    <div className="h-screen overflow-hidden flex flex-col bg-slate-950">
      {/* Header */}
      <div className="bg-slate-900 border-b border-slate-800 px-4 py-3 flex items-center gap-3">
        <h1 className="text-lg font-bold text-white flex-1">
          Live Scan: {identifier.slice(0, 12)}…
        </h1>
        <Badge
          variant={
            isCompleted ? "default" : isFailed ? "destructive" : "secondary"
          }
        >
          {metrics.system_status === "SCANNING"
            ? "Scanning"
            : metrics.system_status === "COMPLETED"
              ? "Completed"
              : metrics.system_status === "FAILED"
                ? "Failed"
                : metrics.system_status}
        </Badge>
        {isCompleted && (
          <Button onClick={handleViewCompleted} className="gap-2">
            View Results <ArrowRight className="w-4 h-4" />
          </Button>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={pollJobStatus}
          disabled={!polling}
        >
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Error state */}
      {error && (
        <div className="px-4 py-3 bg-red-50 border-b border-red-200">
          <APIOffline
            error={error}
            endpoint={`GET /api/v1/scan/status/${identifier}`}
            onRetry={pollJobStatus}
          />
        </div>
      )}

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden gap-4 p-4">
        {/* Left: Map panel */}
        <div className="flex-1 min-w-0">
          <ScanMapPanel cells={cells} scanId={identifier} />
        </div>

        {/* Right: Metrics, Feed, Targets */}
        <div className="w-[35%] flex flex-col gap-4 min-w-0 overflow-hidden">
          <div className="flex-1 min-h-0 overflow-hidden">
            <LiveMetricsPanel metrics={metrics} />
          </div>

          <div className="flex-1 min-h-0 overflow-hidden">
            <LiveFeedPanel feed={feed} />
          </div>

          <div className="flex-1 min-h-0 overflow-hidden">
            <TopTargetsPanel targets={topTargets} />
          </div>
        </div>
      </div>
    </div>
  );
}