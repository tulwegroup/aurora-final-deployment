/**
 * ProposalBuilder — Phase AK example commercial proposal structure
 *
 * Generates a structured commercial proposal summary based on:
 *   - selected client type (package tier)
 *   - AOI area (km²)
 *   - resolution
 *   - number of scans
 *
 * CONSTITUTIONAL RULE: Price calculation uses only area + resolution + package tier.
 * No ACIF value, commodity, tier count, or geological outcome enters pricing.
 */
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileText, ShieldCheck } from "lucide-react";

const SCAN_RATES = { survey: 4000, coarse: 12000, medium: 35000, fine: 95000 };
const PER_KM2    = { survey: 0.04, coarse: 0.12,  medium: 0.35,   fine: 0.95  };
const INCLUDED   = 100_000; // km² included in base

const PACKAGE_MULTIPLIERS = { sovereign: 1.4, operator: 1.0, investor: 0.3 };
const PACKAGE_LABELS = { sovereign: "Sovereign Package", operator: "Operator Package", investor: "Investor Package" };

const DELIVERABLES_BY_PACKAGE = {
  sovereign: ["Canonical scan JSON", "GeoJSON + KML layers", "Digital twin", "Geological report (sovereign ed.)", "Secure data-room (30d TTL)", "Audit trail + calibration certificate"],
  operator:  ["Canonical scan JSON", "GeoJSON + KML layers", "Digital twin", "Geological report (operator ed.)", "Secure data-room (7d TTL)", "API access"],
  investor:  ["Executive report (≤8 pages)", "EPI summary", "Risk tier summary", "Watermarked PDF", "Secure data-room (48h TTL, single-use)"],
};

const fmt = (n) => `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function ProposalBuilder() {
  const [clientType, setClientType] = useState("operator");
  const [resolution, setResolution] = useState("medium");
  const [areaKm2, setAreaKm2]       = useState(25000);
  const [numScans, setNumScans]     = useState(1);

  const basePrice   = SCAN_RATES[resolution] || 0;
  const overage     = Math.max(0, areaKm2 - INCLUDED) * (PER_KM2[resolution] || 0);
  const scanTotal   = (basePrice + overage) * numScans;
  const pkgMult     = PACKAGE_MULTIPLIERS[clientType] || 1;
  const packageFee  = scanTotal * pkgMult;
  const grandTotal  = scanTotal + packageFee;

  const proposalDate = new Date().toLocaleDateString("en-GB", { year: "numeric", month: "long", day: "numeric" });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Inputs */}
      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-sm">Configure Proposal</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground uppercase tracking-wide">Client Type</label>
            <div className="grid grid-cols-3 gap-2">
              {["sovereign","operator","investor"].map(t => (
                <button key={t} onClick={() => setClientType(t)}
                  className={`py-2 rounded-lg border text-xs font-medium capitalize transition-colors ${
                    clientType === t ? "border-primary bg-primary/5" : "border-border hover:bg-muted"
                  }`}>
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground uppercase tracking-wide">Resolution</label>
            <select className="w-full border rounded px-3 py-2 text-sm bg-background"
              value={resolution} onChange={e => setResolution(e.target.value)}>
              {Object.keys(SCAN_RATES).map(r => (
                <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground uppercase tracking-wide">AOI Area (km²)</label>
            <input type="number" min={1} value={areaKm2}
              onChange={e => setAreaKm2(Math.max(1, +e.target.value))}
              className="w-full border rounded px-3 py-2 text-sm" />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground uppercase tracking-wide">Number of Scans</label>
            <input type="number" min={1} max={50} value={numScans}
              onChange={e => setNumScans(Math.max(1, +e.target.value))}
              className="w-full border rounded px-3 py-2 text-sm" />
          </div>

          <div className="flex items-start gap-2 text-[10px] text-muted-foreground bg-muted/30 rounded px-3 py-2">
            <ShieldCheck className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            Pricing uses area + resolution + package tier only. Commodity, ACIF, and geological outcomes are not pricing variables.
          </div>
        </CardContent>
      </Card>

      {/* Generated proposal */}
      <Card className="border-primary/30">
        <CardHeader className="pb-2 bg-muted/30 rounded-t-xl">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-primary" />
            <CardTitle className="text-sm">Commercial Proposal — Aurora OSI vNext</CardTitle>
          </div>
          <p className="text-xs text-muted-foreground mt-1">{proposalDate} · Indicative</p>
        </CardHeader>
        <CardContent className="pt-4 space-y-4">
          {/* Client & scope */}
          <div className="space-y-1 text-sm">
            <div className="flex justify-between py-1 border-b">
              <span className="text-muted-foreground text-xs">Package</span>
              <span className="font-semibold">{PACKAGE_LABELS[clientType]}</span>
            </div>
            <div className="flex justify-between py-1 border-b">
              <span className="text-muted-foreground text-xs">Resolution</span>
              <span className="capitalize font-medium">{resolution}</span>
            </div>
            <div className="flex justify-between py-1 border-b">
              <span className="text-muted-foreground text-xs">AOI Area</span>
              <span className="font-mono">{areaKm2.toLocaleString()} km²</span>
            </div>
            <div className="flex justify-between py-1 border-b">
              <span className="text-muted-foreground text-xs">Number of Scans</span>
              <span className="font-mono">{numScans}</span>
            </div>
          </div>

          {/* Cost breakdown */}
          <div className="space-y-1 text-sm">
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Cost Breakdown</div>
            <div className="flex justify-between py-1">
              <span className="text-xs text-muted-foreground">Base scan ({resolution})</span>
              <span className="font-mono">{fmt(basePrice)} × {numScans}</span>
            </div>
            {overage > 0 && (
              <div className="flex justify-between py-1">
                <span className="text-xs text-muted-foreground">Area overage ({(areaKm2 - INCLUDED).toLocaleString()} km²)</span>
                <span className="font-mono">{fmt(overage * numScans)}</span>
              </div>
            )}
            <div className="flex justify-between py-1 border-t">
              <span className="text-xs text-muted-foreground">Scan subtotal</span>
              <span className="font-mono">{fmt(scanTotal)}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-xs text-muted-foreground">Package fee ({PACKAGE_LABELS[clientType]})</span>
              <span className="font-mono">{fmt(packageFee)}</span>
            </div>
            <div className="flex justify-between py-2 border-t mt-1 font-bold">
              <span>Total (indicative)</span>
              <span className="font-mono text-primary">{fmt(grandTotal)}</span>
            </div>
          </div>

          {/* Deliverables */}
          <div>
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Included Deliverables</div>
            {DELIVERABLES_BY_PACKAGE[clientType].map((d, i) => (
              <div key={i} className="text-xs flex items-start gap-1.5 py-0.5">
                <span className="text-emerald-600 mt-0.5">✓</span>
                <span>{d}</span>
              </div>
            ))}
          </div>

          <div className="text-[10px] text-muted-foreground border-t pt-2">
            This proposal is indicative only. Final pricing confirmed upon AOI submission and contract execution.
            Prices exclude VAT/taxes. Annual commitment discounts available on request.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}