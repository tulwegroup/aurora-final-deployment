/**
 * PricingTable — Phase AK pricing model
 *
 * Pricing basis:
 *   1. Per-scan by resolution (compute cost driver)
 *   2. Per-km² overage (area cost driver)
 *   3. Portfolio / subscription (value tier)
 *
 * CONSTITUTIONAL RULE: Prices are infrastructure-cost-derived.
 * No ACIF, tier count, or geological outcome affects pricing.
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Info } from "lucide-react";

const SCAN_PRICING = [
  {
    resolution: "Survey",
    cell_size: "~100 km²/cell",
    base_price_usd: 4_000,
    per_km2: 0.04,
    included_km2: 100_000,
    turnaround: "24h",
    notes: "Regional assessment, national-scale mapping",
  },
  {
    resolution: "Coarse",
    cell_size: "~25 km²/cell",
    base_price_usd: 12_000,
    per_km2: 0.12,
    included_km2: 100_000,
    turnaround: "48h",
    notes: "Basin-level targeting, exploration screening",
  },
  {
    resolution: "Medium",
    cell_size: "~5 km²/cell",
    base_price_usd: 35_000,
    per_km2: 0.35,
    included_km2: 100_000,
    turnaround: "72h",
    notes: "Block-level assessment, feasibility support",
  },
  {
    resolution: "Fine",
    cell_size: "~1 km²/cell",
    base_price_usd: 95_000,
    per_km2: 0.95,
    included_km2: 100_000,
    turnaround: "5 days",
    notes: "Prospect-level detail, drill-target ranking",
  },
];

const SUBSCRIPTION_PRICING = [
  {
    tier: "Starter",
    desc: "1 scan/month up to 50,000 km² · Medium resolution",
    price_usd_month: 28_000,
    annual_saving_pct: 15,
  },
  {
    tier: "Professional",
    desc: "3 scans/month up to 100,000 km² · Fine resolution",
    price_usd_month: 72_000,
    annual_saving_pct: 20,
  },
  {
    tier: "Enterprise / Sovereign",
    desc: "Unlimited scans · All resolutions · Priority queue · Dedicated CSM",
    price_usd_month: null,
    annual_saving_pct: null,
    custom: true,
  },
];

const fmt = (n) => n != null ? `$${n.toLocaleString()}` : "—";

export default function PricingTable() {
  return (
    <div className="space-y-6">
      {/* Per-scan pricing */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Per-Scan Pricing — by Resolution</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  {["Resolution", "Cell Size", "Base Price", "Per km² (overage)", "Included Area", "Turnaround", "Use Case"].map(h => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {SCAN_PRICING.map((row) => (
                  <tr key={row.resolution} className="border-b last:border-0 hover:bg-muted/20">
                    <td className="px-4 py-3 font-semibold">{row.resolution}</td>
                    <td className="px-4 py-3 font-mono text-xs">{row.cell_size}</td>
                    <td className="px-4 py-3 font-mono font-medium">{fmt(row.base_price_usd)}</td>
                    <td className="px-4 py-3 font-mono">{fmt(row.per_km2)}</td>
                    <td className="px-4 py-3 font-mono">{row.included_km2.toLocaleString()} km²</td>
                    <td className="px-4 py-3">{row.turnaround}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{row.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Portfolio / subscription */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Portfolio / Subscription Pricing</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {SUBSCRIPTION_PRICING.map((sub) => (
              <div key={sub.tier} className={`rounded-xl border-2 p-4 space-y-2 ${sub.custom ? "border-primary" : "border-border"}`}>
                <div className="font-semibold text-sm">{sub.tier}</div>
                <div className="text-xs text-muted-foreground leading-relaxed">{sub.desc}</div>
                <div className="pt-1">
                  {sub.custom ? (
                    <span className="text-base font-bold">Custom pricing</span>
                  ) : (
                    <>
                      <span className="text-xl font-bold">{fmt(sub.price_usd_month)}</span>
                      <span className="text-xs text-muted-foreground"> / month</span>
                    </>
                  )}
                </div>
                {sub.annual_saving_pct && (
                  <div className="text-xs text-emerald-700 bg-emerald-50 rounded px-2 py-1">
                    Save {sub.annual_saving_pct}% with annual commitment
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Pricing basis note */}
      <div className="flex items-start gap-2 text-xs text-muted-foreground border rounded-lg px-4 py-3 bg-muted/20">
        <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        <span>
          <strong>Pricing basis:</strong> Base price reflects compute cost (cell count × resolution multiplier × cloud-compute benchmark).
          Per-km² rate reflects area-proportional infrastructure cost beyond the included area.
          Prices do not vary with ACIF scores, detected tier counts, commodity type, or geological outcome.
          Commodity or geographic selection is not a pricing variable.
        </span>
      </div>
    </div>
  );
}