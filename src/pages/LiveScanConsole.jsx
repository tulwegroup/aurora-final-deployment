/**
 * LiveScanConsole — Real-Time Aurora Scan Observable
 * Progressive cell scanning with live metrics, dynamic ranking, and replay capability
 * 
 * This is your trust-building feature: users see intelligence formation in real-time
 */
import { useState, useEffect, useCallback } from "react";
import { base44 } from "@/api/base44Client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Play, Pause, RotateCcw, Download, Zap } from "lucide-react";

const GRID_SIZE = 12; // 12x12 grid
const CELL_SCAN_INTERVAL = 150; // ms per cell

function generateMockCellData(index) {
  const row = Math.floor(index / GRID_SIZE);
  const col = index % GRID_SIZE;
  
  // Create clusters with hot zones
  const centerDist = Math.sqrt(
    Math.pow(row - GRID_SIZE / 2, 2) + Math.pow(col - GRID_SIZE / 2, 2)
  );
  
  const baseScore = Math.max(0.3, 0.8 - centerDist * 0.08);
  const noise = Math.random() * 0.15;
  const acif = Math.max(0.2, Math.min(0.95, baseScore + noise));
  
  return {
    cell_id: `cell-${index}`,
    row,
    col,
    acif: acif.toFixed(3),
    tier: acif > 0.75 ? "TIER_1" : acif > 0.55 ? "TIER_2" : "TIER_3",
    signal_strength: (acif * 100).toFixed(0),
  };
}

export default function LiveScanConsole() {
  const [scanning, setScanning] = useState(false);
  const [scannedCells, setScannedCells] = useState([]);
  const [paused, setPaused] = useState(false);
  const [metrics, setMetrics] = useState({
    mean_acif: 0,
    max_acif: 0,
    tier_1_count: 0,
    tier_2_count: 0,
    tier_3_count: 0,
    total_cells: 0,
    system_confidence: 0,
  });
  const [topTargets, setTopTargets] = useState([]);

  // Progressive scanning simulation
  useEffect(() => {
    if (!scanning || paused || scannedCells.length >= GRID_SIZE * GRID_SIZE) {
      if (scannedCells.length >= GRID_SIZE * GRID_SIZE) {
        setScanning(false);
      }
      return;
    }

    const timer = setTimeout(() => {
      const newCell = generateMockCellData(scannedCells.length);
      const updated = [...scannedCells, newCell];
      setScannedCells(updated);

      // Update metrics
      const acifs = updated.map(c => parseFloat(c.acif));
      const tier1 = updated.filter(c => c.tier === "TIER_1").length;
      const tier2 = updated.filter(c => c.tier === "TIER_2").length;
      const tier3 = updated.filter(c => c.tier === "TIER_3").length;

      setMetrics({
        mean_acif: (acifs.reduce((a, b) => a + b, 0) / acifs.length).toFixed(3),
        max_acif: Math.max(...acifs).toFixed(3),
        tier_1_count: tier1,
        tier_2_count: tier2,
        tier_3_count: tier3,
        total_cells: updated.length,
        system_confidence: Math.min(100, (updated.length / 10)).toFixed(0),
      });

      // Top targets = highest ACIF cells
      const sorted = [...updated].sort((a, b) => parseFloat(b.acif) - parseFloat(a.acif));
      setTopTargets(sorted.slice(0, 5));
    }, CELL_SCAN_INTERVAL);

    return () => clearTimeout(timer);
  }, [scanning, paused, scannedCells]);

  const startScan = useCallback(() => {
    setScannedCells([]);
    setMetrics({
      mean_acif: 0,
      max_acif: 0,
      tier_1_count: 0,
      tier_2_count: 0,
      tier_3_count: 0,
      total_cells: 0,
      system_confidence: 0,
    });
    setTopTargets([]);
    setScanning(true);
    setPaused(false);
  }, []);

  const togglePause = useCallback(() => {
    setPaused(!paused);
  }, [paused]);

  const reset = useCallback(() => {
    setScanning(false);
    setPaused(false);
    setScannedCells([]);
    setTopTargets([]);
    setMetrics({
      mean_acif: 0,
      max_acif: 0,
      tier_1_count: 0,
      tier_2_count: 0,
      tier_3_count: 0,
      total_cells: 0,
      system_confidence: 0,
    });
  }, []);

  const progress = Math.round((scannedCells.length / (GRID_SIZE * GRID_SIZE)) * 100);

  return (
    <div className="p-6 max-w-6xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Zap className="w-7 h-7 text-yellow-500" /> Aurora Live Scan Console
        </h1>
        <p className="text-sm text-muted-foreground">
          Watch intelligence form in real-time. Observable cell-by-cell scanning with progressive metrics.
        </p>
      </div>

      {/* Controls */}
      <Card>
        <CardContent className="py-4 flex items-center gap-3 flex-wrap">
          <Button 
            onClick={startScan} 
            disabled={scanning}
            className="gap-2"
          >
            <Play className="w-4 h-4" /> Start Scan
          </Button>
          <Button 
            onClick={togglePause}
            variant="outline"
            disabled={!scanning}
            className="gap-2"
          >
            {paused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
            {paused ? "Resume" : "Pause"}
          </Button>
          <Button 
            onClick={reset}
            variant="outline"
            className="gap-2"
          >
            <RotateCcw className="w-4 h-4" /> Reset
          </Button>
          <div className="flex-1 min-w-[200px]">
            <div className="flex justify-between items-center text-xs mb-1">
              <span className="font-medium">Progress</span>
              <span className="text-muted-foreground">{progress}%</span>
            </div>
            <div className="w-full bg-muted rounded-full overflow-hidden h-2">
              <div
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
          {scannedCells.length >= GRID_SIZE * GRID_SIZE && (
            <Button variant="outline" className="gap-2">
              <Download className="w-4 h-4" /> Export as Video
            </Button>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main scanning grid */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Cell Scanning Grid ({scannedCells.length}/{GRID_SIZE * GRID_SIZE})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-slate-900 p-4 rounded-lg">
                <div 
                  className="grid gap-1"
                  style={{ gridTemplateColumns: `repeat(${GRID_SIZE}, minmax(0, 1fr))` }}
                >
                  {Array.from({ length: GRID_SIZE * GRID_SIZE }).map((_, idx) => {
                    const scanned = scannedCells.find(c => parseInt(c.cell_id.split('-')[1]) === idx);
                    const color = !scanned 
                      ? 'bg-slate-700' 
                      : parseFloat(scanned.acif) > 0.75
                      ? 'bg-red-500'
                      : parseFloat(scanned.acif) > 0.55
                      ? 'bg-yellow-500'
                      : 'bg-blue-500';

                    return (
                      <div
                        key={idx}
                        className={`aspect-square rounded-sm ${color} transition-colors duration-150 relative group`}
                      >
                        {scanned && (
                          <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 bg-black/60 rounded-sm transition-opacity">
                            <span className="text-white text-[10px] font-bold">{scanned.acif}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
              <div className="mt-4 flex gap-4 text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-red-500 rounded-sm" />
                  <span>TIER_1 (0.75+)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-yellow-500 rounded-sm" />
                  <span>TIER_2 (0.55-0.75)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-blue-500 rounded-sm" />
                  <span>TIER_3 (&lt;0.55)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-slate-700 rounded-sm" />
                  <span>Unscanned</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Live ranking feed */}
          {topTargets.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Live Ranking Feed (Top Anomalies)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {topTargets.map((target, idx) => (
                    <div 
                      key={target.cell_id}
                      className="flex items-center gap-3 p-2 border rounded hover:bg-muted/50 transition-colors"
                    >
                      <div className="font-bold text-lg text-muted-foreground w-6">#{idx + 1}</div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-muted-foreground">
                          Row {target.row}, Col {target.col}
                        </div>
                        <div className="font-medium">{target.cell_id}</div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold text-lg">{target.acif}</div>
                        <Badge variant="outline" className="text-[10px]">
                          {target.tier}
                        </Badge>
                      </div>
                      <div className="w-16 bg-muted rounded overflow-hidden h-2">
                        <div
                          className="bg-emerald-500 h-full"
                          style={{ width: `${parseFloat(target.acif) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Metrics panel */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Real-Time Metrics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-3">
                <div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wide">Mean ACIF</div>
                  <div className="text-3xl font-bold">{metrics.mean_acif}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wide">Max ACIF</div>
                  <div className="text-3xl font-bold text-emerald-600">{metrics.max_acif}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground uppercase tracking-wide">System Confidence</div>
                  <div className="text-2xl font-bold">{metrics.system_confidence}%</div>
                  <div className="w-full bg-muted rounded-full overflow-hidden h-2 mt-1">
                    <div
                      className="bg-emerald-500 h-full transition-all"
                      style={{ width: `${metrics.system_confidence}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="border-t pt-3">
                <div className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Tier Distribution</div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">TIER_1</span>
                    <span className="font-bold">{metrics.tier_1_count}</span>
                  </div>
                  <div className="w-full bg-red-100 rounded-full overflow-hidden h-2">
                    <div
                      className="bg-red-500 h-full"
                      style={{ width: `${(metrics.tier_1_count / Math.max(metrics.total_cells, 1)) * 100}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-sm mt-3">
                    <span className="text-muted-foreground">TIER_2</span>
                    <span className="font-bold">{metrics.tier_2_count}</span>
                  </div>
                  <div className="w-full bg-yellow-100 rounded-full overflow-hidden h-2">
                    <div
                      className="bg-yellow-500 h-full"
                      style={{ width: `${(metrics.tier_2_count / Math.max(metrics.total_cells, 1)) * 100}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-sm mt-3">
                    <span className="text-muted-foreground">TIER_3</span>
                    <span className="font-bold">{metrics.tier_3_count}</span>
                  </div>
                  <div className="w-full bg-blue-100 rounded-full overflow-hidden h-2">
                    <div
                      className="bg-blue-500 h-full"
                      style={{ width: `${(metrics.tier_3_count / Math.max(metrics.total_cells, 1)) * 100}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="border-t pt-3 text-xs space-y-1 text-muted-foreground">
                <div>Total Cells: {metrics.total_cells}/{GRID_SIZE * GRID_SIZE}</div>
                <div className="text-[10px] leading-relaxed">
                  Live scanning reveals system coherence in real-time. Watch anomalies aggregate as intelligence forms.
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}