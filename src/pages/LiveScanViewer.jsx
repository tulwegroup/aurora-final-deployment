/**
 * LiveScanViewer — Real-Time Aurora Scan Observable
 * 4-panel layout: Map (L), Metrics + Feed + Targets (R)
 * 
 * Data flow: backend progressively streams cell data → panels update in real-time
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "react-router-dom";
import { base44 } from "@/api/base44Client";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, Play, Pause, RotateCcw, Download } from "lucide-react";
import ScanMapPanel from "../components/ScanMapPanel";
import LiveMetricsPanel from "../components/LiveMetricsPanel";
import LiveFeedPanel from "../components/LiveFeedPanel";
import TopTargetsPanel from "../components/TopTargetsPanel";

export default function LiveScanViewer() {
  const { scanId } = useParams();
  const [scanning, setScanning] = useState(false);
  const [paused, setPaused] = useState(false);
  const [cells, setCells] = useState([]);
  const [metrics, setMetrics] = useState({
    mean_acif: 0,
    max_acif: 0,
    cells_processed: 0,
    cells_total: 100,
    tier_1: 0,
    tier_2: 0,
    tier_3: 0,
    below: 0,
    system_status: "INITIALIZING",
  });
  const [feed, setFeed] = useState([]);
  const [topTargets, setTopTargets] = useState([]);
  const [aoiBounds, setAoiBounds] = useState(null);
  const [replayMode, setReplayMode] = useState(false);
  const [replaySpeed, setReplaySpeed] = useState(1);
  const scanIntervalRef = useRef(null);

  // Simulate progressive scan data from backend
  const startScan = useCallback(async () => {
    setScanning(true);
    setPaused(false);
    setCells([]);
    setFeed([]);
    setTopTargets([]);
    setMetrics(prev => ({ ...prev, cells_processed: 0, system_status: "SCANNING" }));

    // Simulate cell generation
    let cellIndex = 0;
    const totalCells = 100;

    const scanInterval = setInterval(() => {
      if (!paused && cellIndex < totalCells) {
        const newCell = {
          cell_id: `cell-${cellIndex}`,
          lat: -5.3 + Math.random() * 0.5,
          lon: -1.5 + Math.random() * 0.5,
          acif: Math.max(0.2, Math.random() * 0.9),
          tier: Math.random() > 0.7 ? "TIER_1" : Math.random() > 0.4 ? "TIER_2" : "TIER_3",
          signal: ["SAR", "THERMAL", "CAI", "IOI", "GRAV"][Math.floor(Math.random() * 5)],
        };

        setCells(prev => [...prev, newCell]);

        // Update metrics
        const allCells = [...cells, newCell];
        const acifs = allCells.map(c => c.acif);
        const tier1 = allCells.filter(c => c.tier === "TIER_1").length;
        const tier2 = allCells.filter(c => c.tier === "TIER_2").length;
        const tier3 = allCells.filter(c => c.tier === "TIER_3").length;

        setMetrics({
          mean_acif: (acifs.reduce((a, b) => a + b, 0) / acifs.length).toFixed(3),
          max_acif: Math.max(...acifs).toFixed(3),
          cells_processed: cellIndex + 1,
          cells_total: totalCells,
          tier_1: tier1,
          tier_2: tier2,
          tier_3: tier3,
          below: allCells.length - tier1 - tier2 - tier3,
          system_status: cellIndex < 30 ? "SCANNING" : cellIndex < 70 ? "REFINING" : "FINALIZING",
        });

        // Add feed event
        setFeed(prev => [
          {
            id: cellIndex,
            message: `Cell ${cellIndex} → ACIF ${newCell.acif.toFixed(3)} → ${newCell.tier}`,
            timestamp: new Date().toLocaleTimeString(),
            tier: newCell.tier,
          },
          ...prev.slice(0, 19),
        ]);

        // Update top targets
        setTopTargets(prev => {
          const updated = [...prev, newCell];
          return updated.sort((a, b) => b.acif - a.acif).slice(0, 5);
        });

        cellIndex++;
      } else if (cellIndex >= totalCells) {
        clearInterval(scanInterval);
        setScanning(false);
        setMetrics(prev => ({ ...prev, system_status: "COMPLETE" }));
      }
    }, 200 / replaySpeed);

    scanIntervalRef.current = scanInterval;
  }, [paused, cells, replaySpeed]);

  const togglePause = useCallback(() => {
    setPaused(!paused);
  }, [paused]);

  const reset = useCallback(() => {
    if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
    setScanning(false);
    setPaused(false);
    setCells([]);
    setFeed([]);
    setTopTargets([]);
    setReplayMode(false);
    setMetrics(prev => ({
      ...prev,
      cells_processed: 0,
      mean_acif: 0,
      max_acif: 0,
      tier_1: 0,
      tier_2: 0,
      tier_3: 0,
      below: 0,
      system_status: "READY",
    }));
  }, []);

  const exportAsVideo = useCallback(() => {
    alert("Video export would capture scan replay and encode as MP4/WebM");
  }, []);

  return (
    <div className="h-screen overflow-hidden flex flex-col bg-slate-950">
      {/* Top control bar */}
      <div className="bg-slate-900 border-b border-slate-800 px-4 py-3 flex items-center gap-3">
        <h1 className="text-lg font-bold text-white flex-1">Live Scan: {scanId || "demo"}</h1>
        <Button
          onClick={startScan}
          disabled={scanning}
          variant="default"
          className="gap-2"
        >
          <Play className="w-4 h-4" /> Start
        </Button>
        <Button
          onClick={togglePause}
          disabled={!scanning}
          variant="outline"
          className="gap-2"
        >
          {paused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
        </Button>
        <Button
          onClick={reset}
          variant="outline"
          className="gap-2"
        >
          <RotateCcw className="w-4 h-4" /> Reset
        </Button>
        {cells.length >= 100 && (
          <Button
            onClick={exportAsVideo}
            variant="outline"
            className="gap-2"
          >
            <Download className="w-4 h-4" /> Export
          </Button>
        )}

        {/* Replay speed control */}
        {cells.length > 0 && (
          <div className="flex items-center gap-2 ml-4 border-l border-slate-700 pl-4">
            <span className="text-xs text-slate-400">Speed:</span>
            <select
              className="text-xs bg-slate-800 text-white border border-slate-700 rounded px-2 py-1"
              value={replaySpeed}
              onChange={e => setReplaySpeed(parseFloat(e.target.value))}
            >
              <option value="1">1x</option>
              <option value="5">5x</option>
              <option value="10">10x</option>
            </select>
          </div>
        )}
      </div>

      {/* Main 4-panel layout */}
      <div className="flex flex-1 overflow-hidden gap-4 p-4">
        {/* Left: Map panel (65%) */}
        <div className="flex-1 min-w-0">
          <ScanMapPanel cells={cells} scanId={scanId} />
        </div>

        {/* Right: 3-panel stack (35%) */}
        <div className="w-[35%] flex flex-col gap-4 min-w-0 overflow-hidden">
          {/* Top: Metrics */}
          <div className="flex-1 min-h-0 overflow-hidden">
            <LiveMetricsPanel metrics={metrics} />
          </div>

          {/* Middle: Feed */}
          <div className="flex-1 min-h-0 overflow-hidden">
            <LiveFeedPanel feed={feed} />
          </div>

          {/* Bottom: Top targets */}
          <div className="flex-1 min-h-0 overflow-hidden">
            <TopTargetsPanel targets={topTargets} />
          </div>
        </div>
      </div>
    </div>
  );
}