/**
 * DynamicReportRenderer — Modular report section renderer
 * Each section is independently rendered from canonical data
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import DigitalTwinVisuals from "./DigitalTwinVisuals";

export default function DynamicReportRenderer({ report }) {
  if (!report) return null;

  const renderSection = (section) => {
    switch (section.section_type) {
      case "executive_intelligence":
        return <ExecutiveIntelligenceSection data={section.data} />;
      case "spatial_intelligence":
        return <SpatialIntelligenceSection data={section.data} />;
      case "system_model":
        return <SystemModelSection data={section.data} />;
      case "ranked_targets":
        return <RankedTargetsSection data={section.data} />;
      case "digital_twin":
        return <DigitalTwinSection data={section.data} />;
      case "resource_economic":
        return <ResourceEconomicSection data={section.data} />;
      case "ground_truth_validation":
        return <GroundTruthSection data={section.data} />;
      case "uncertainty_risk":
        return <UncertaintyRiskSection data={section.data} />;
      case "strategy":
        return <StrategySection data={section.data} />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {report.sections.map(section => (
        <div key={section.section_type}>
          <h2 className="text-2xl font-bold mb-3">{section.title}</h2>
          {renderSection(section)}
        </div>
      ))}
    </div>
  );
}

function ExecutiveIntelligenceSection({ data }) {
  const gradeColor = {
    "Investment Grade": "bg-emerald-100 text-emerald-800",
    "Prospective": "bg-blue-100 text-blue-800",
    "Tier 3 Monitor": "bg-amber-100 text-amber-800",
    "Early Stage": "bg-slate-100 text-slate-600",
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Card>
        <CardContent className="pt-6 space-y-3 text-sm">
          <div>
            <div className="text-xs text-muted-foreground">Mean ACIF</div>
            <div className="text-2xl font-bold">{data.acif_score}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Max ACIF</div>
            <div className="text-lg font-bold">{data.key_metrics?.max_acif}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Tier-1 Coverage</div>
            <div className="text-lg font-bold">{data.key_metrics?.tier_1_coverage}%</div>
          </div>
          <Badge className={gradeColor[data.investment_grade] || ""}>
            {data.investment_grade}
          </Badge>
        </CardContent>
      </Card>

      <Card className="md:col-span-2">
        <CardContent className="pt-6 text-sm leading-relaxed space-y-2">
          <p>{data.narrative}</p>
          <div className="bg-blue-50 border border-blue-200 rounded p-3 text-xs text-blue-900">
            <strong>Investment Implication:</strong> The anomaly exhibits characteristics consistent with {
              data.investment_grade.includes("Investment") ? "near-term monetization" :
              data.investment_grade.includes("Prospective") ? "exploration upside" :
              "validation requirement"
            } scenarios.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function SpatialIntelligenceSection({ data }) {
  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        <p className="text-sm">{data.summary}</p>
        {data.clusters && data.clusters.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data.clusters.slice(0, 4).map(c => (
              <div key={c.id} className="border rounded p-3 text-sm space-y-1">
                <div className="font-bold">{c.id}</div>
                <div className="text-xs text-muted-foreground">
                  Lat: {c.centroid?.lat?.toFixed(4)}, Lon: {c.centroid?.lon?.toFixed(4)}
                </div>
                <div className="text-xs">Cells: {c.cell_count} | ACIF: {c.avg_acif}</div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SystemModelSection({ data }) {
  const system = data.system;
  return (
    <Card>
      <CardContent className="pt-6">
        <table className="w-full text-sm">
          <tbody>
            <tr className="border-b">
              <td className="font-medium text-muted-foreground py-2 px-3">System</td>
              <td className="py-2 px-3">{system?.system_name}</td>
            </tr>
            <tr className="border-b">
              <td className="font-medium text-muted-foreground py-2 px-3">Source</td>
              <td className="py-2 px-3">{system?.source}</td>
            </tr>
            <tr className="border-b">
              <td className="font-medium text-muted-foreground py-2 px-3">Migration</td>
              <td className="py-2 px-3">{system?.migration}</td>
            </tr>
            <tr className="border-b">
              <td className="font-medium text-muted-foreground py-2 px-3">Trap</td>
              <td className="py-2 px-3">{system?.trap}</td>
            </tr>
            <tr>
              <td className="font-medium text-muted-foreground py-2 px-3">Seal</td>
              <td className="py-2 px-3">{system?.seal}</td>
            </tr>
          </tbody>
        </table>
        <p className="text-sm mt-4">{data.narrative}</p>
      </CardContent>
    </Card>
  );
}

function RankedTargetsSection({ data }) {
  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b bg-muted/40">
                <th className="px-3 py-2 text-left">Rank</th>
                <th className="px-3 py-2 text-left">ACIF</th>
                <th className="px-3 py-2 text-left">Signal</th>
                <th className="px-3 py-2 text-left">Depth</th>
                <th className="px-3 py-2 text-left">Priority</th>
              </tr>
            </thead>
            <tbody>
              {data.targets?.map(t => (
                <tr key={t.target_id} className="border-b hover:bg-muted/20">
                  <td className="px-3 py-2 font-bold">{t.rank}</td>
                  <td className="px-3 py-2 font-bold">{t.acif}</td>
                  <td className="px-3 py-2">{t.dominant_signal}</td>
                  <td className="px-3 py-2 font-mono text-[10px]">{t.depth_window_m}</td>
                  <td className="px-3 py-2">
                    <Badge variant="outline">{t.drilling_priority}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-sm">{data.drill_sequence_logic}</p>
      </CardContent>
    </Card>
  );
}

function DigitalTwinSection({ data }) {
  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        <p className="text-sm">{data.narrative}</p>
        <DigitalTwinVisuals twin={data.twin} />
      </CardContent>
    </Card>
  );
}

function ResourceEconomicSection({ data }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Tonnage (Monte Carlo)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span>P10:</span>
            <span className="font-bold">{(data.tonnage?.p10_tonnes / 1e6).toFixed(1)}M t</span>
          </div>
          <div className="flex justify-between">
            <span>P50:</span>
            <span className="font-bold">{(data.tonnage?.p50_tonnes / 1e6).toFixed(1)}M t</span>
          </div>
          <div className="flex justify-between">
            <span>P90:</span>
            <span className="font-bold">{(data.tonnage?.p90_tonnes / 1e6).toFixed(1)}M t</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">EPVI</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <div className="text-2xl font-bold text-emerald-600">
            ${(data.epvi?.epvi_usd / 1e9).toFixed(2)}B
          </div>
          <p className="text-xs text-muted-foreground mt-2">{data.narrative}</p>
        </CardContent>
      </Card>
    </div>
  );
}

function GroundTruthSection({ data }) {
  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b bg-muted/40">
                <th className="px-3 py-2 text-left">Analog System</th>
                <th className="px-3 py-2 text-left">Country</th>
                <th className="px-3 py-2 text-left">Similarity</th>
              </tr>
            </thead>
            <tbody>
              {data.analogs?.map(a => (
                <tr key={a.name} className="border-b hover:bg-muted/20">
                  <td className="px-3 py-2 font-medium">{a.name}</td>
                  <td className="px-3 py-2">{a.country}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div className="w-12 bg-muted rounded overflow-hidden h-2">
                        <div
                          className="bg-green-500 h-full"
                          style={{ width: `${a.similarity * 100}%` }}
                        />
                      </div>
                      <span className="font-bold">{(a.similarity * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="bg-emerald-50 border border-emerald-200 rounded p-3 text-sm text-emerald-900">
          {data.narrative}
        </div>
      </CardContent>
    </Card>
  );
}

function UncertaintyRiskSection({ data }) {
  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="border rounded p-3">
            <div className="text-xs text-muted-foreground">Spatial</div>
            <div className="font-bold">±{data.uncertainty?.spatial_uncertainty_km} km</div>
          </div>
          <div className="border rounded p-3">
            <div className="text-xs text-muted-foreground">Depth</div>
            <div className="font-bold">±{data.uncertainty?.depth_uncertainty_m} m</div>
          </div>
        </div>
        <p className="text-sm">{data.narrative}</p>
      </CardContent>
    </Card>
  );
}

function StrategySection({ data }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Operator Action</CardTitle>
        </CardHeader>
        <CardContent className="text-sm leading-relaxed">
          {data.operator}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Investor Thesis</CardTitle>
        </CardHeader>
        <CardContent className="text-sm leading-relaxed">
          {data.investor}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Sovereign Strategy</CardTitle>
        </CardHeader>
        <CardContent className="text-sm leading-relaxed">
          {data.sovereign}
        </CardContent>
      </Card>
    </div>
  );
}