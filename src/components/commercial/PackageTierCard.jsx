/**
 * PackageTierCard — Phase AK package tier breakdown
 *
 * Three client packages:
 *   1. Sovereign — for governments, geological surveys, regulators
 *   2. Operator  — for exploration companies, technical teams
 *   3. Investor  — for funds, executives, due-diligence teams
 *
 * CONSTITUTIONAL RULE: Package tier governs delivery scope only.
 * No tier changes scientific depth, ACIF computation, or canonical record content.
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle, XCircle } from "lucide-react";

const PACKAGES = [
  {
    id: "sovereign",
    label: "Sovereign Package",
    audience: "Governments · Geological Survey Authorities · Regulators",
    color: "border-blue-400",
    headerColor: "bg-blue-50 text-blue-900",
    includes: [
      "Canonical scan record (JSON, full provenance)",
      "GeoJSON + KML map layers (all tiers)",
      "Digital twin (3D voxel, full depth profile)",
      "Geological report — sovereign/government edition",
      "Secure data-room package (30-day TTL)",
      "Audit trail (chain-of-custody, geometry hash)",
      "Calibration version certificate",
      "Source quality attestation",
      "Dedicated CSM onboarding session",
    ],
    excludes: [
      "Investor-facing executive summary (separate package)",
    ],
    report_audience: "Sovereign/Government",
    data_room_ttl: "30 days",
    support: "Priority + Dedicated CSM",
    pricing_note: "Enterprise / custom — contact Aurora",
  },
  {
    id: "operator",
    label: "Operator Package",
    audience: "Exploration Companies · Geologists · Technical Teams",
    color: "border-emerald-400",
    headerColor: "bg-emerald-50 text-emerald-900",
    includes: [
      "Canonical scan record (JSON, full provenance)",
      "GeoJSON + KML map layers (all tiers)",
      "Digital twin (3D voxel, full depth profile)",
      "Geological report — operator/technical edition",
      "Secure data-room package (7-day TTL)",
      "Audit trail (geometry hash, version lineage)",
      "API access to canonical outputs",
      "GIS-compatible exports (shapefile on request)",
    ],
    excludes: [
      "Calibration version certificate (available on upgrade)",
      "Executive summary (Investor package)",
    ],
    report_audience: "Operator/Technical",
    data_room_ttl: "7 days",
    support: "Standard",
    pricing_note: "Per-scan or Professional subscription",
  },
  {
    id: "investor",
    label: "Investor Package",
    audience: "Investment Funds · C-Suite · Due-Diligence Teams",
    color: "border-amber-400",
    headerColor: "bg-amber-50 text-amber-900",
    includes: [
      "Executive geological report (jargon-free, ≤ 8 pages)",
      "Exploration Priority Index summary (non-physical metric)",
      "Risk tier summary (LOW / MEDIUM / HIGH)",
      "Secure data-room package (48h TTL, single-use option)",
      "Portfolio comparison table (if multi-scan)",
      "Watermarked PDF for due-diligence sharing",
    ],
    excludes: [
      "Raw canonical JSON (Operator/Sovereign package)",
      "Digital twin (available on upgrade)",
      "Calibration lineage (available on upgrade)",
      "Full map layers (summary map only)",
    ],
    report_audience: "Investor/Executive",
    data_room_ttl: "48 hours",
    support: "Email",
    pricing_note: "Per-scan add-on or Enterprise subscription",
  },
];

function Item({ text, included }) {
  return (
    <div className={`flex items-start gap-2 text-xs py-1 ${included ? "" : "opacity-60"}`}>
      {included
        ? <CheckCircle className="w-3.5 h-3.5 text-emerald-600 mt-0.5 shrink-0" />
        : <XCircle className="w-3.5 h-3.5 text-muted-foreground mt-0.5 shrink-0" />}
      <span>{text}</span>
    </div>
  );
}

export default function PackageTierCard() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
      {PACKAGES.map((pkg) => (
        <Card key={pkg.id} className={`border-2 ${pkg.color} flex flex-col`}>
          <CardHeader className={`pb-3 rounded-t-xl ${pkg.headerColor}`}>
            <CardTitle className="text-base">{pkg.label}</CardTitle>
            <p className="text-xs mt-0.5">{pkg.audience}</p>
          </CardHeader>
          <CardContent className="flex-1 pt-4 space-y-4">
            <div>
              <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Included</div>
              {pkg.includes.map((item, i) => <Item key={i} text={item} included />)}
            </div>
            {pkg.excludes.length > 0 && (
              <div>
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Not Included</div>
                {pkg.excludes.map((item, i) => <Item key={i} text={item} included={false} />)}
              </div>
            )}
            <div className="border-t pt-3 space-y-1 text-xs">
              {[
                ["Report Edition", pkg.report_audience],
                ["Data-Room TTL", pkg.data_room_ttl],
                ["Support", pkg.support],
                ["Pricing", pkg.pricing_note],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-muted-foreground">{k}</span>
                  <span className="font-medium text-right max-w-[55%]">{v}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}