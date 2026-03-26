/**
 * PresentationLayer — Phase AL
 *
 * Multi-audience briefing deck interface:
 *   - Sovereign Briefing Pack (governments, regulators)
 *   - Investor Pitch Deck (funds, C-suite)
 *   - Technical Annex (geologists, engineers, scientists)
 */
import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import SovereignBriefingPack from "../components/presentation/SovereignBriefingPack";
import InvestorPitchDeck from "../components/presentation/InvestorPitchDeck";
import TechnicalAnnex from "../components/presentation/TechnicalAnnex";
import { Shield, TrendingUp, FlaskConical, AlertTriangle } from "lucide-react";

export default function PresentationLayer() {
  return (
    <div className="p-6 max-w-6xl space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Presentation Layer</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Audience-specific briefing decks for Aurora OSI Phase AL
        </p>
      </div>

      {/* Positioning Statement */}
      <Card className="border-2 border-emerald-300 bg-emerald-50">
        <CardContent className="py-4 flex items-start gap-3">
          <AlertTriangle className="w-6 h-6 text-emerald-700 mt-0.5 shrink-0" />
          <div>
            <div className="font-semibold text-emerald-900">Positioning Statement (All Audiences)</div>
            <div className="text-sm text-emerald-800 mt-1">
              <strong>Aurora is a screening and prioritisation system, not a replacement for drilling or field validation.</strong>
            </div>
            <div className="text-xs text-emerald-700 mt-2">
              This statement appears prominently in all three briefing materials. Aurora outputs require independent geological and drilling validation before resource estimation or economic decisions.
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="sovereign" className="space-y-4">
        <TabsList className="grid grid-cols-3 gap-2">
          <TabsTrigger value="sovereign" className="gap-2">
            <Shield className="w-4 h-4" />
            <span>Sovereign</span>
          </TabsTrigger>
          <TabsTrigger value="investor" className="gap-2">
            <TrendingUp className="w-4 h-4" />
            <span>Investor</span>
          </TabsTrigger>
          <TabsTrigger value="technical" className="gap-2">
            <FlaskConical className="w-4 h-4" />
            <span>Technical</span>
          </TabsTrigger>
        </TabsList>

        {/* Sovereign Briefing Pack */}
        <TabsContent value="sovereign">
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Sovereign Briefing Pack</CardTitle>
                <p className="text-sm text-muted-foreground mt-2">
                  6-slide structured briefing for governments, geological surveys, and regulators.
                </p>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 text-sm">
                  <div>
                    <strong>Purpose:</strong> Emphasise governance, audit trail, and regulatory compliance.
                  </div>
                  <div>
                    <strong>Key messaging:</strong> Aurora delivers auditable, versioned geophysical assessments with full provenance and deterministic outputs.
                  </div>
                  <div>
                    <strong>Caveats:</strong> Explicit disclaimers on every slide. No resource claims. Drilling required before exploration commitment.
                  </div>
                </div>
              </CardContent>
            </Card>
            <SovereignBriefingPack />
          </div>
        </TabsContent>

        {/* Investor Pitch Deck */}
        <TabsContent value="investor">
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Investor Pitch Deck</CardTitle>
                <p className="text-sm text-muted-foreground mt-2">
                  6-slide deck for investment funds, C-suite, and due-diligence teams.
                </p>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 text-sm">
                  <div>
                    <strong>Purpose:</strong> Speed to market, portfolio screening, and risk-adjusted prioritisation.
                  </div>
                  <div>
                    <strong>Key messaging:</strong> EPI (Exploration Priority Index) is a non-physical aggregation metric for portfolio ranking, not a resource estimate.
                  </div>
                  <div>
                    <strong>Caveats:</strong> Screening tool only. No JORC/NI 43-101 basis. Requires field validation and drilling confirmation.
                  </div>
                </div>
              </CardContent>
            </Card>
            <InvestorPitchDeck />
          </div>
        </TabsContent>

        {/* Technical Annex */}
        <TabsContent value="technical">
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Technical Annex</CardTitle>
                <p className="text-sm text-muted-foreground mt-2">
                  6-section technical reference for geologists, engineers, and scientists.
                </p>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 text-sm">
                  <div>
                    <strong>Purpose:</strong> Full transparency on ACIF formula, tier assignment, uncertainty propagation, and calibration lineage.
                  </div>
                  <div>
                    <strong>Key messaging:</strong> ACIF is a dimensionless geophysical anomaly scoring function. Tiers are calibration-version-locked classifications. All outputs include uncertainty bounds.
                  </div>
                  <div>
                    <strong>Pilot detail:</strong> Ghana, Zambia, Senegal cases documented with cell counts, ACIF ranges, veto rates, and calibration versions. No drill confirmation claimed.
                  </div>
                </div>
              </CardContent>
            </Card>
            <TechnicalAnnex />
          </div>
        </TabsContent>
      </Tabs>

      {/* Footer */}
      <Card className="border border-slate-200 bg-slate-50">
        <CardContent className="py-4 text-xs text-muted-foreground space-y-2">
          <div>
            <strong>Phase AL Completion:</strong> All three presentation materials have been finalized with consistent positioning, uncertainty framing, and no-resource-claims safeguards.
          </div>
          <div>
            <strong>Next Phase (AM):</strong> Production launch. AWS deployment, operational readiness, monitoring, and SLA definition.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}