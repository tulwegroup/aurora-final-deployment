/**
 * ExportStep — Step 4: Export & Share via Data Room
 * Phase AI §AI.5
 *
 * CONSTITUTIONAL RULE: All exported data is verbatim canonical — no recomputation.
 * Package hash and artifact hashes are displayed from server response.
 * TTL defaults: 48h standard, 24h sensitive (single-use).
 */
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, Shield, Link, Copy, CheckCircle, RotateCcw, Lock } from "lucide-react";
import { base44 } from "@/api/base44Client";

const ARTIFACT_LABELS = {
  canonical_scan_json:  "Canonical Scan JSON",
  geojson_layer:        "GeoJSON Layer(s)",
  kml_export:           "KML Export",
  digital_twin_dataset: "Digital Twin Dataset",
  geological_report:    "Geological Report",
  audit_trail_bundle:   "Audit Trail Bundle",
};

const TTL_OPTIONS = [
  { value: "24h",  label: "24 hours (sensitive)" },
  { value: "48h",  label: "48 hours (standard)" },
  { value: "7d",   label: "7 days" },
  { value: "30d",  label: "30 days" },
];

export default function ExportStep({ scanId, onRestart }) {
  const [ttl,          setTtl]        = useState("48h");
  const [singleUse,    setSingleUse]  = useState(false);
  const [watermark,    setWatermark]  = useState(true);
  const [building,     setBuilding]   = useState(false);
  const [pkg,          setPkg]        = useState(null);
  const [link,         setLink]       = useState(null);
  const [copied,       setCopied]     = useState(false);
  const [revoking,     setRevoking]   = useState(false);
  const [revoked,      setRevoked]    = useState(false);
  const [error,        setError]      = useState(null);

  async function handleBuild() {
    setBuilding(true);
    setError(null);
    try {
      const res = await base44.functions.invoke("buildDataRoom", {
        scan_id:    scanId,
        ttl:        ttl,
        single_use: singleUse,
        watermark:  watermark,
      });
      setPkg(res.data.package);
      setLink(res.data.link);
    } catch (e) {
      setError(e.message);
    } finally {
      setBuilding(false);
    }
  }

  async function handleRevoke() {
    if (!link) return;
    setRevoking(true);
    try {
      await base44.functions.invoke("revokeDeliveryLink", { link_id: link.link_id });
      setRevoked(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setRevoking(false);
    }
  }

  function copyLink() {
    if (link?.access_url) {
      navigator.clipboard.writeText(link.access_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Config */}
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2">
            <Shield className="w-4 h-4" /> Delivery Options
          </CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground uppercase tracking-wide">Link TTL</label>
              <select className="w-full border rounded px-3 py-2 text-sm bg-background"
                value={ttl} onChange={e => setTtl(e.target.value)}>
                {TTL_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <label className="flex items-center gap-3 cursor-pointer">
              <input type="checkbox" checked={singleUse} onChange={e => setSingleUse(e.target.checked)} />
              <div>
                <div className="text-sm font-medium flex items-center gap-1">
                  <Lock className="w-3.5 h-3.5" /> Single-use link
                </div>
                <div className="text-xs text-muted-foreground">Link expires after first download</div>
              </div>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input type="checkbox" checked={watermark} onChange={e => setWatermark(e.target.checked)} />
              <div>
                <div className="text-sm font-medium">Watermark artifacts</div>
                <div className="text-xs text-muted-foreground">Adds recipient label to JSON/report (non-destructive)</div>
              </div>
            </label>
          </CardContent>
        </Card>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <Button className="w-full" disabled={building || !!pkg} onClick={handleBuild}>
          {building ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Building package…</> : "Build Data Room Package"}
        </Button>

        <Button variant="outline" className="w-full" onClick={onRestart}>
          <RotateCcw className="w-4 h-4 mr-2" /> Start New Scan
        </Button>
      </div>

      {/* Package details */}
      <div className="space-y-4">
        {pkg && (
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-600" /> Package Ready
            </CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1.5 text-xs">
                {[
                  ["Package ID",   pkg.package_id?.slice(0, 20) + "…"],
                  ["Package Hash", pkg.package_hash?.slice(0, 16) + "…"],
                  ["Artifacts",    pkg.artifacts?.length],
                  ["Cal version",  pkg.calibration_version_id],
                  ["Cost model",   pkg.cost_model_version],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-muted-foreground">{k}</span>
                    <span className="font-mono">{v}</span>
                  </div>
                ))}
              </div>

              <div className="border-t pt-3 space-y-1">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Artifacts</p>
                {(pkg.artifacts || []).map(a => (
                  <div key={a.artifact_id} className="flex justify-between text-xs">
                    <span>{ARTIFACT_LABELS[a.artifact_type] || a.artifact_type}</span>
                    <span className="font-mono text-muted-foreground">{a.sha256_hash?.slice(0, 8)}…</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {link && (
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2">
              <Link className="w-4 h-4" /> Delivery Link
            </CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {revoked ? (
                <div className="text-sm text-destructive flex items-center gap-2">
                  <Shield className="w-4 h-4" /> Link revoked. No further access.
                </div>
              ) : (
                <>
                  <div className="space-y-1 text-xs">
                    {[
                      ["Status",   link.status],
                      ["Expires",  link.expires_at?.slice(0, 19).replace("T", " ") + " UTC"],
                      ["Max downloads", link.max_downloads ?? "Unlimited"],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-muted-foreground">{k}</span>
                        <span className="font-medium capitalize">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" className="flex-1" onClick={copyLink}>
                      {copied ? <CheckCircle className="w-3.5 h-3.5 mr-1.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5 mr-1.5" />}
                      {copied ? "Copied!" : "Copy Link"}
                    </Button>
                    <Button size="sm" variant="destructive" onClick={handleRevoke} disabled={revoking}>
                      {revoking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Revoke"}
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        )}

        {!pkg && !building && (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground text-sm">
              Configure delivery options and build the package.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}