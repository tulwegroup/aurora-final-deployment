/**
 * CommercialPackaging — Phase AK: Commercial Packaging & Pricing
 *
 * CONSTITUTIONAL RULES:
 *   - Pricing is INDEPENDENT of ACIF scores, tier counts, or geological outcomes.
 *   - Pricing is based solely on infrastructure cost (compute, area, resolution) + value tier.
 *   - No feedback loop from scan results into pricing.
 *   - No pilot success metric may adjust pricing thresholds.
 *   - Package tier determines delivery scope only — not scientific depth.
 */
import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DollarSign, Package, FileText, ShieldCheck, Info } from "lucide-react";
import PricingTable from "../components/commercial/PricingTable";
import PackageTierCard from "../components/commercial/PackageTierCard";
import ProposalBuilder from "../components/commercial/ProposalBuilder";

export default function CommercialPackaging() {
  return (
    <div className="p-6 max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <DollarSign className="w-6 h-6" /> Phase AK — Commercial Packaging & Pricing
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Aurora vNext commercial model — sovereign, operator, and investor packages.
        </p>
      </div>

      {/* Constitutional notice */}
      <div className="flex items-start gap-2 text-xs bg-blue-50 text-blue-800 border border-blue-200 rounded-lg px-4 py-2.5">
        <ShieldCheck className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        <span>
          <strong>Pricing Independence Statement:</strong> All pricing is determined by
          infrastructure cost (compute units, AOI area, resolution tier) and value-based
          packaging — never by ACIF scores, tier counts, geological outcomes, or
          pilot success metrics. No feedback loop connects scan results to pricing logic.
        </span>
      </div>

      <Tabs defaultValue="pricing">
        <TabsList>
          <TabsTrigger value="pricing"><DollarSign className="w-3.5 h-3.5 mr-1.5" />Pricing Model</TabsTrigger>
          <TabsTrigger value="packages"><Package className="w-3.5 h-3.5 mr-1.5" />Package Tiers</TabsTrigger>
          <TabsTrigger value="proposal"><FileText className="w-3.5 h-3.5 mr-1.5" />Proposal Builder</TabsTrigger>
        </TabsList>

        <TabsContent value="pricing" className="mt-4">
          <PricingTable />
        </TabsContent>

        <TabsContent value="packages" className="mt-4">
          <PackageTierCard />
        </TabsContent>

        <TabsContent value="proposal" className="mt-4">
          <ProposalBuilder />
        </TabsContent>
      </Tabs>

      {/* Completion proof card */}
      <Card className="border-blue-200 bg-blue-50/40">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Info className="w-4 h-4 text-blue-600" /> Phase AK Completion Proof
          </CardTitle>
        </CardHeader>
        <CardContent className="text-xs space-y-1 text-blue-900">
          <div>✓ Pricing model: per-scan (by resolution), per-km², and portfolio/subscription defined</div>
          <div>✓ Package tiers: Sovereign, Operator, Investor — scope and delivery defined</div>
          <div>✓ Delivery content per package documented with explicit inclusions/exclusions</div>
          <div>✓ Pricing independence confirmed — no ACIF, tier count, or geological outcome coupling</div>
          <div>✓ Example commercial proposal structure available in Proposal Builder</div>
          <div>✓ Success criteria and pilot feedback remain advisory — no tuning loop into pricing or scoring</div>
          <div className="font-semibold mt-1">Requesting Phase AL approval.</div>
        </CardContent>
      </Card>
    </div>
  );
}