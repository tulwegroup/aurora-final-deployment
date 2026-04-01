import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { base44 } from '@/api/base44Client';
import { history as historyApi } from "../lib/auroraApi";
import { Loader2, ArrowLeft } from "lucide-react";
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import ScanResultsMap from "../components/ScanResultsMap";

export default function ScanDetail() {
  const { scanId } = useParams();
  const [scan, setScan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchScan = async () => {
      try {
        const canonicalScan = await historyApi.get(scanId);
        setScan(canonicalScan);
        setError(null);
      } catch (e) {
        setError(`${e.message} (Must be a completed canonical scan)`);
      } finally {
        setLoading(false);
      }
    };
    fetchScan();
  }, [scanId]);

  if (!scan && loading) return <div className="p-6 flex items-center gap-2 text-slate-400"><Loader2 className="w-4 h-4 animate-spin" /> Loading scan…</div>;
  if (error) return <div className="p-6 text-red-400 text-sm">{error}</div>;
  if (!scan) return null;

  const geojson = scan.results_geojson;
  const tier1 = scan.tier_1_count ?? 0;
  const tier2 = scan.tier_2_count ?? 0;
  const tier3 = scan.tier_3_count ?? 0;
  const totalCells = tier1 + tier2 + tier3 || scan.cell_count || 0;

  const modalityChartData = scan.modality_contributions ? Object.entries(scan.modality_contributions).map(([name, value]) => ({
    name: name.replace(/_/g, ' ').toUpperCase(),
    value: value * 100,
  })) : [];

  return (
    <div className="bg-slate-950 text-slate-50 min-h-screen p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-700 pb-6">
        <div>
          <h1 className="text-3xl font-bold text-cyan-400">AURORA ACIF</h1>
          <p className="text-xs text-slate-400 mt-1">Scan ID: {scan.scan_id}</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-slate-300">{scan.commodity?.toUpperCase()} | {scan.resolution?.toUpperCase()}</p>
          <p className="text-xs text-slate-500 mt-1">{scan.completed_at ? new Date(scan.completed_at).toLocaleString() : '—'}</p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4 text-sm">
        <div className="border border-slate-700 p-4 rounded bg-slate-900/30">
          <div className="text-cyan-400 font-bold text-2xl">{(scan.display_acif_score * 100).toFixed(1)}%</div>
          <div className="text-xs text-slate-400 mt-2">ACIF Score</div>
        </div>
        <div className="border border-slate-700 p-4 rounded bg-slate-900/30">
          <div className="text-emerald-400 font-bold text-2xl">{tier1}</div>
          <div className="text-xs text-slate-400 mt-2">Tier 1 (High)</div>
        </div>
        <div className="border border-slate-700 p-4 rounded bg-slate-900/30">
          <div className="text-orange-400 font-bold text-2xl">{tier2}</div>
          <div className="text-xs text-slate-400 mt-2">Tier 2 (Moderate)</div>
        </div>
        <div className="border border-slate-700 p-4 rounded bg-slate-900/30">
          <div className="text-red-400 font-bold text-2xl">{tier3}</div>
          <div className="text-xs text-slate-400 mt-2">Tier 3 (Low)</div>
        </div>
      </div>

      {/* Geological Gates */}
      {scan.geological_gates && (
        <div className="border border-slate-700 rounded p-6 bg-slate-900/30">
          <h2 className="text-lg font-bold text-cyan-400 mb-4">GEOLOGICAL GATES</h2>
          <div className="space-y-2 max-w-2xl">
            {Object.entries(scan.geological_gates).map(([gateName, gateResult]) => {
              const isPass = gateResult.status === "PASS" || gateResult.pass_rate > 0.5;
              const confidence = gateResult.confidence || gateResult.pass_rate || 0;
              return (
                <div key={gateName} className="flex items-center justify-between text-sm border-b border-slate-700 py-2">
                  <span className="text-slate-300 capitalize">{gateName.replace(/_/g, ' ')}</span>
                  <span className={isPass ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>
                    {isPass ? '✓ PASS' : '✗ WEAK'} ({(confidence * 100).toFixed(0)}%)
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ACIF Modality Averages */}
      {modalityChartData.length > 0 && (
        <div className="border border-slate-700 rounded p-6 bg-slate-900/30">
          <h2 className="text-lg font-bold text-cyan-400 mb-4">ACIF MODALITY AVERAGES</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={modalityChartData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#94a3b8" style={{ fontSize: '12px' }} />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', color: '#e2e8f0' }} />
              <Bar dataKey="value" fill="#06b6d4" radius={[4, 4, 0, 0]}>
                {modalityChartData.map((entry, idx) => (
                  <Cell key={`cell-${idx}`} fill={['#06b6d4', '#f97316', '#ef4444', '#22c55e', '#a855f7'][idx % 5]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Spectral ACIF Heatmap */}
      {geojson?.features && (
        <div className="border border-slate-700 rounded p-6 bg-slate-900/30">
          <h2 className="text-lg font-bold text-cyan-400 mb-4">SPECTRAL ACIF HEATMAP - Mineralization Probability by Depth</h2>
          <div className="bg-slate-800 p-4 rounded overflow-auto max-h-64">
            <div className="grid gap-0.5" style={{ gridTemplateColumns: `repeat(auto-fit, minmax(8px, 1fr))` }}>
              {geojson.features.slice(0, 500).map((f, idx) => {
                const score = f.properties.acif_score || 0;
                const tier = f.properties.tier;
                let color = '#334155';
                if (tier === 'TIER_1') color = '#22c55e';
                else if (tier === 'TIER_2') color = '#f97316';
                else if (tier === 'TIER_3') color = '#ef4444';
                return (
                  <div
                    key={idx}
                    className="h-4 rounded cursor-pointer hover:opacity-100"
                    style={{ backgroundColor: color, opacity: 0.5 + score * 0.5 }}
                    title={`Cell ${idx}: ${(score * 100).toFixed(1)}% (${tier})`}
                  />
                );
              })}
            </div>
          </div>
          <div className="mt-4 flex gap-6 text-xs">
            <div className="flex items-center gap-2"><div className="w-4 h-4 rounded" style={{ backgroundColor: '#22c55e' }} /><span>Tier 1 — Excellent Prospectivity (&gt;0.75)</span></div>
            <div className="flex items-center gap-2"><div className="w-4 h-4 rounded" style={{ backgroundColor: '#f97316' }} /><span>Tier 2 — Good (0.50-0.75)</span></div>
            <div className="flex items-center gap-2"><div className="w-4 h-4 rounded" style={{ backgroundColor: '#ef4444' }} /><span>Tier 3 — Fair (&lt;0.50)</span></div>
          </div>
        </div>
      )}

      {/* Cell Map */}
      {geojson?.features?.length > 0 && (
        <div className="border border-slate-700 rounded p-6 bg-slate-900/30">
          <h2 className="text-lg font-bold text-cyan-400 mb-4">SPATIAL CELL DISTRIBUTION</h2>
          <div className="bg-slate-800 rounded overflow-hidden" style={{ height: '400px' }}>
            <ScanResultsMap geojson={geojson} geometry={scan.geometry} />
          </div>
        </div>
      )}

      {/* Top Cells Table */}
      {geojson?.features?.length > 0 && (
        <div className="border border-slate-700 rounded p-6 bg-slate-900/30">
          <h2 className="text-lg font-bold text-cyan-400 mb-4">TOP CELLS BY ACIF SCORE</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-slate-200">
              <thead>
                <tr className="border-b border-slate-600 text-slate-400">
                  <th className="text-left py-2 px-3">Rank</th>
                  <th className="text-left py-2 px-3">Tier</th>
                  <th className="text-right py-2 px-3">ACIF Score</th>
                  <th className="text-right py-2 px-3">Latitude</th>
                  <th className="text-right py-2 px-3">Longitude</th>
                </tr>
              </thead>
              <tbody>
                {[...geojson.features]
                  .filter(f => f.properties.tier !== 'DATA_MISSING')
                  .sort((a, b) => (b.properties.acif_score || 0) - (a.properties.acif_score || 0))
                  .slice(0, 20)
                  .map((f, i) => {
                    const p = f.properties;
                    const tierBg = p.tier === 'TIER_1' ? 'bg-emerald-900/40' : p.tier === 'TIER_2' ? 'bg-orange-900/40' : 'bg-red-900/40';
                    const tierColor = p.tier === 'TIER_1' ? 'text-emerald-400' : p.tier === 'TIER_2' ? 'text-orange-400' : 'text-red-400';
                    return (
                      <tr key={i} className={`border-b border-slate-700 ${tierBg}`}>
                        <td className="py-2 px-3 font-mono text-slate-400">{i + 1}</td>
                        <td className={`py-2 px-3 font-bold ${tierColor}`}>{p.tier}</td>
                        <td className="py-2 px-3 text-right font-bold text-cyan-400">{((p.acif_score || 0) * 100).toFixed(1)}%</td>
                        <td className="py-2 px-3 text-right font-mono">{f.geometry.coordinates[1]?.toFixed(4)}</td>
                        <td className="py-2 px-3 text-right font-mono">{f.geometry.coordinates[0]?.toFixed(4)}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Geographic & Pipeline Info */}
      <div className="border border-slate-700 rounded p-6 bg-slate-900/30 text-sm">
        <h3 className="text-cyan-400 font-bold mb-3">SYSTEM METADATA</h3>
        <div className="grid grid-cols-2 gap-4 text-slate-300">
          <div>
            <span className="text-slate-500">Bounds:</span> {scan.min_lat?.toFixed(3)}, {scan.min_lon?.toFixed(3)} → {scan.max_lat?.toFixed(3)}, {scan.max_lon?.toFixed(3)}
          </div>
          <div>
            <span className="text-slate-500">Pipeline:</span> {scan.pipeline_version}
          </div>
          <div>
            <span className="text-slate-500">Total Cells:</span> {totalCells}
          </div>
          <div>
            <span className="text-slate-500">Completed:</span> {scan.completed_at ? new Date(scan.completed_at).toLocaleString() : '—'}
          </div>
        </div>
      </div>

      {/* Back Button */}
      <div className="flex gap-3 pt-4 border-t border-slate-700">
        <Link to="/history" className="flex items-center gap-2 px-4 py-2 bg-slate-900 border border-slate-700 rounded text-slate-300 hover:bg-slate-800">
          <ArrowLeft className="w-4 h-4" /> Back to History
        </Link>
      </div>
    </div>
  );
}