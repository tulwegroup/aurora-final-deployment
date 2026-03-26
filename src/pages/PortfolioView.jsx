/**
 * PortfolioView — Portfolio & Territory Intelligence
 * Phase AD §AD.5
 *
 * Displays ranked portfolio snapshot across territory/commodity entries.
 * All data sourced from stored canonical outputs — no ACIF recomputed here.
 *
 * CONSTITUTIONAL RULE: portfolio_score is a display composite metric.
 * It is never presented as a scientific score, deposit certainty, or resource estimate.
 */
import { useState, useEffect } from "react";
import { base44 } from "@/api/base44Client";
import PortfolioRankingTable from "../components/PortfolioRankingTable";
import TerritoryCard from "../components/TerritoryCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, BarChart3, AlertTriangle, Info } from "lucide-react";

const COMMODITIES = ["", "gold", "copper", "lithium", "nickel"];
const TERRITORIES  = ["", "country", "basin", "block", "concession", "province"];

const RISK_STYLES = {
  low:    "bg-emerald-100 text-emerald-800",
  medium: "bg-amber-100 text-amber-800",
  high:   "bg-red-100 text-red-800",
};

export default function PortfolioView() {
  const [snapshot, setSnapshot]       = useState(null);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState(null);
  const [commodity, setCommodity]     = useState("");
  const [territory, setTerritory]     = useState("");
  const [riskAdjusted, setRiskAdjusted] = useState(true);
  const [selected, setSelected]       = useState(null);

  async function fetchSnapshot() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (commodity) params.set("commodity", commodity);
      if (territory) params.set("territory_type", territory);
      params.set("risk_adjusted", riskAdjusted);
      const res = await base44.functions.invoke("portfolioSnapshot", {
        commodity: commodity || null,
        territory_type: territory || null,
        risk_adjusted: riskAdjusted,
      });
      setSnapshot(res.data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchSnapshot(); }, [commodity, territory, riskAdjusted]);

  const riskDist = snapshot?.risk_summary || {};

  return (
    <div className="p-6 max-w-7xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BarChart3 className="w-6 h-6" /> Portfolio Intelligence
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Territory-level aggregation of stored canonical scan outputs.
        </p>
      </div>

      {/* Constitutional notice */}
      <div className="flex items-start gap-2 text-xs bg-blue-50 text-blue-800 border border-blue-200 rounded-lg px-4 py-2.5">
        <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        <span>
          Portfolio scores are composite display metrics assembled from stored canonical outputs (ACIF mean, Tier 1 density, veto rate).
          No ACIF is recomputed. No tier is reassigned. This view does not constitute geological resource classification.
        </span>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="py-3 flex flex-wrap items-center gap-4">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground uppercase tracking-wide">Commodity</label>
            <select className="text-sm border rounded px-2 py-1.5 bg-background"
              value={commodity} onChange={e => setCommodity(e.target.value)}>
              {COMMODITIES.map(c => <option key={c} value={c}>{c || "All commodities"}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground uppercase tracking-wide">Territory Type</label>
            <select className="text-sm border rounded px-2 py-1.5 bg-background"
              value={territory} onChange={e => setTerritory(e.target.value)}>
              {TERRITORIES.map(t => <option key={t} value={t}>{t || "All types"}</option>)}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer mt-4">
            <input type="checkbox" checked={riskAdjusted}
              onChange={e => setRiskAdjusted(e.target.checked)} />
            Risk-adjusted ranking
          </label>
        </CardContent>
      </Card>

      {/* Risk summary */}
      {snapshot && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { key: "LOW",    label: "Low Risk",    style: RISK_STYLES.low },
            { key: "MEDIUM", label: "Medium Risk", style: RISK_STYLES.medium },
            { key: "HIGH",   label: "High Risk",   style: RISK_STYLES.high },
          ].map(({ key, label, style }) => (
            <Card key={key}>
              <CardContent className="py-4 px-5">
                <div className={`text-xs font-medium px-2 py-0.5 rounded inline-block ${style}`}>{label}</div>
                <div className="text-3xl font-bold tabular-nums mt-1">{riskDist[key] || 0}</div>
                <div className="text-xs text-muted-foreground">territories</div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-destructive text-sm border border-destructive/30 bg-destructive/5 rounded-lg px-4 py-2">
          <AlertTriangle className="w-4 h-4" /> {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-12 gap-2 text-muted-foreground">
          <Loader2 className="w-5 h-5 animate-spin" /> Loading portfolio…
        </div>
      )}

      {!loading && snapshot && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2">
            <Tabs defaultValue="ranking">
              <TabsList>
                <TabsTrigger value="ranking">Ranked Table</TabsTrigger>
                <TabsTrigger value="cards">Territory Cards</TabsTrigger>
              </TabsList>

              <TabsContent value="ranking" className="mt-4">
                <PortfolioRankingTable
                  entries={snapshot.entries || []}
                  onSelect={setSelected}
                  selectedId={selected?.entry_id}
                />
              </TabsContent>

              <TabsContent value="cards" className="mt-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {(snapshot.entries || []).map(e => (
                    <TerritoryCard
                      key={e.entry_id}
                      entry={e}
                      selected={selected?.entry_id === e.entry_id}
                      onClick={() => setSelected(e)}
                    />
                  ))}
                  {(snapshot.entries || []).length === 0 && (
                    <div className="col-span-2 text-sm text-muted-foreground p-4 text-center border rounded-lg">
                      No portfolio entries yet. Assemble entries from completed scans.
                    </div>
                  )}
                </div>
              </TabsContent>
            </Tabs>

            {/* Methodology note */}
            <div className="mt-3 text-[10px] text-muted-foreground border rounded px-3 py-2 space-y-0.5">
              <div className="font-medium">Ranking methodology</div>
              <div>{snapshot.methodology_note}</div>
            </div>
          </div>

          {/* Detail panel */}
          <div>
            {selected ? (
              <TerritoryCard entry={selected} detailed />
            ) : (
              <div className="text-sm text-muted-foreground p-4 border rounded-lg text-center">
                Select a territory to view details.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}