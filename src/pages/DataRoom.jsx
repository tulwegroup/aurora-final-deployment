/**
 * DataRoom — Secure Data Package Management
 * Phase AH §AH.6
 *
 * CONSTITUTIONAL RULES:
 *   - No scientific computation here.
 *   - All package contents source from stored canonical outputs verbatim.
 *   - Package hash, artifact hash, geometry hash displayed verbatim from API.
 *   - Pricing/TTL are infrastructure parameters only — not coupled to ACIF.
 *   - Single-use and watermark flags stored at creation; not modifiable after.
 */
import { useState, useEffect, useCallback } from "react";
import { base44 } from "@/api/base44Client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  Lock, Package, Copy, Trash2, Plus, Loader2, CheckCircle,
  Clock, Shield, AlertTriangle, ExternalLink, Hash, RefreshCw
} from "lucide-react";
import APIOffline from "../components/APIOffline";

const TTL_OPTIONS = [
  { value: 3600,    label: "1 hour" },
  { value: 86400,   label: "24 hours" },
  { value: 604800,  label: "7 days" },
  { value: 2592000, label: "30 days" },
];

const AUDIENCE_OPTIONS = [
  { value: "sovereign_government", label: "Sovereign / Government" },
  { value: "operator_technical",   label: "Operator / Technical" },
  { value: "investor_executive",   label: "Investor / Executive" },
];

const PACKAGE_STATUS_STYLES = {
  active:  "bg-emerald-100 text-emerald-800 border-emerald-300",
  expired: "bg-slate-100 text-slate-600 border-slate-300",
  revoked: "bg-red-100 text-red-800 border-red-300",
};

function PackageRow({ pkg, onCopy, onRevoke }) {
  const isActive = pkg.status === "active" && (!pkg.expires_at || new Date(pkg.expires_at) > new Date());
  const statusKey = !isActive ? "expired" : pkg.status;

  return (
    <Card className="hover:border-primary/30 transition-colors">
      <CardContent className="py-3 px-4">
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0 space-y-1.5">
            {/* Top row */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-sm">{pkg.audience_label || pkg.audience}</span>
              <Badge className={`text-xs border ${PACKAGE_STATUS_STYLES[statusKey] || PACKAGE_STATUS_STYLES.active}`}>
                {statusKey}
              </Badge>
              {pkg.single_use && (
                <span className="text-xs bg-purple-50 text-purple-700 border border-purple-200 rounded px-1.5 py-0.5">
                  single-use
                </span>
              )}
              {pkg.watermarked && (
                <span className="text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded px-1.5 py-0.5">
                  watermarked
                </span>
              )}
            </div>

            {/* Scan ID */}
            <div className="text-xs font-mono text-muted-foreground truncate">
              scan: {pkg.scan_id || "—"}
            </div>

            {/* Hashes */}
            {pkg.package_hash && (
              <div className="flex items-center gap-1.5 text-xs">
                <Hash className="w-3 h-3 text-muted-foreground shrink-0" />
                <span className="font-mono text-muted-foreground">{pkg.package_hash.slice(0, 24)}…</span>
              </div>
            )}

            {/* Expiry */}
            {pkg.expires_at && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Clock className="w-3 h-3 shrink-0" />
                Expires: {new Date(pkg.expires_at).toLocaleString()}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-1.5 shrink-0">
            {isActive && pkg.access_url && (
              <Button size="sm" variant="outline" className="gap-1.5 h-7 text-xs"
                onClick={() => onCopy(pkg.access_url)}>
                <Copy className="w-3 h-3" /> Copy Link
              </Button>
            )}
            {isActive && (
              <Button size="sm" variant="outline" className="gap-1.5 h-7 text-xs text-destructive hover:text-destructive"
                onClick={() => onRevoke(pkg.package_id)}>
                <Trash2 className="w-3 h-3" /> Revoke
              </Button>
            )}
            {pkg.access_url && (
              <a href={pkg.access_url} target="_blank" rel="noopener noreferrer">
                <Button size="sm" variant="ghost" className="gap-1.5 h-7 text-xs w-full">
                  <ExternalLink className="w-3 h-3" /> Open
                </Button>
              </a>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function CreatePackageForm({ onCreated }) {
  const [scanId, setScanId]       = useState("");
  const [audience, setAudience]   = useState("operator_technical");
  const [ttl, setTtl]             = useState(86400);
  const [singleUse, setSingleUse] = useState(false);
  const [watermark, setWatermark] = useState(true);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);
  const [created, setCreated]     = useState(null);
  const [copied, setCopied]       = useState(false);

  async function handleCreate() {
    if (!scanId.trim()) return;
    setLoading(true);
    setError(null);
    setCreated(null);
    try {
      const res = await base44.functions.invoke("dataRoomCreate", {
        scan_id:    scanId.trim(),
        audience,
        ttl_seconds: ttl,
        single_use: singleUse,
        watermarked: watermark,
      });
      setCreated(res.data);
      if (onCreated) onCreated(res.data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function copyLink() {
    if (!created?.access_url) return;
    navigator.clipboard.writeText(created.access_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="space-y-4">
      {/* Scan ID input */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Scan ID <span className="text-destructive">*</span>
        </label>
        <input
          type="text"
          placeholder="e.g. scan-abc123…"
          value={scanId}
          onChange={e => setScanId(e.target.value)}
          className="w-full text-sm border rounded-md px-3 py-2 bg-background font-mono"
        />
        <p className="text-xs text-muted-foreground">
          Packages can only be created from a completed canonical scan record.
        </p>
      </div>

      {/* Audience */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Audience</label>
        <div className="flex gap-2 flex-wrap">
          {AUDIENCE_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setAudience(opt.value)}
              className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                audience === opt.value
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-input hover:bg-muted"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* TTL */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Access Window (TTL)</label>
        <div className="flex gap-2 flex-wrap">
          {TTL_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setTtl(opt.value)}
              className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                ttl === opt.value
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-input hover:bg-muted"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Flags */}
      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={singleUse} onChange={e => setSingleUse(e.target.checked)} />
          <span>Single-use link</span>
          <span className="text-xs text-muted-foreground">(revoked after first access)</span>
        </label>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={watermark} onChange={e => setWatermark(e.target.checked)} />
          <span>Watermark</span>
          <span className="text-xs text-muted-foreground">(embed recipient ID in PDF/report)</span>
        </label>
      </div>

      {error && (
        <APIOffline
          error={error}
          endpoint="POST /api/v1/data-room/packages"
          hint="The data room backend function (dataRoomCreate) needs to be deployed and wired to the Aurora API."
        />
      )}

      {created && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3 space-y-2">
          <div className="flex items-center gap-2 text-emerald-800 font-medium text-sm">
            <CheckCircle className="w-4 h-4" /> Package Created
          </div>
          <div className="text-xs space-y-1 font-mono text-emerald-900">
            <div>ID: {created.package_id}</div>
            {created.package_hash && <div>Hash: {created.package_hash.slice(0, 32)}…</div>}
            {created.expires_at && <div>Expires: {new Date(created.expires_at).toLocaleString()}</div>}
          </div>
          {created.access_url && (
            <Button size="sm" className="gap-1.5" onClick={copyLink}>
              {copied ? <CheckCircle className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
              {copied ? "Copied!" : "Copy Access Link"}
            </Button>
          )}
        </div>
      )}

      <Button
        disabled={!scanId.trim() || loading}
        onClick={handleCreate}
        className="gap-2"
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
        Create Package
      </Button>
    </div>
  );
}

export default function DataRoom() {
  const [packages, setPackages] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [copiedMsg, setCopiedMsg] = useState(null);

  const loadPackages = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await base44.functions.invoke("dataRoomList", {});
      setPackages(res.data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadPackages(); }, []);

  function handleCopyLink(url) {
    navigator.clipboard.writeText(url);
    setCopiedMsg("Link copied to clipboard");
    setTimeout(() => setCopiedMsg(null), 2000);
  }

  async function handleRevoke(packageId) {
    if (!confirm("Revoke this access package? The link will immediately stop working.")) return;
    try {
      await base44.functions.invoke("dataRoomRevoke", { package_id: packageId });
      await loadPackages();
    } catch (e) {
      alert("Revoke failed: " + e.message);
    }
  }

  const active  = (packages?.packages || []).filter(p => p.status === "active");
  const expired = (packages?.packages || []).filter(p => p.status !== "active");

  return (
    <div className="p-6 max-w-5xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Lock className="w-6 h-6" /> Secure Data Room
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Create and manage time-limited, tamper-evident access packages for canonical scan outputs.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadPackages} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Security notice */}
      <div className="flex items-start gap-2 text-xs bg-blue-50 text-blue-800 border border-blue-200 rounded-lg px-4 py-2.5">
        <Shield className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        <span>
          All packages are <strong>read-only views</strong> of frozen canonical scan outputs.
          Package content cannot be modified after creation. Every package embeds a
          <strong> SHA-256 package hash</strong> and <strong>artifact hash</strong> for tamper detection.
          Geometry hash is propagated verbatim from the source scan record.
        </span>
      </div>

      {copiedMsg && (
        <div className="flex items-center gap-2 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-3 py-2">
          <CheckCircle className="w-4 h-4" /> {copiedMsg}
        </div>
      )}

      <Tabs defaultValue="packages">
        <TabsList>
          <TabsTrigger value="packages" className="gap-1.5">
            <Package className="w-3.5 h-3.5" /> Packages
            {active.length > 0 && (
              <span className="ml-1 bg-primary text-primary-foreground text-[10px] rounded-full px-1.5 py-0.5">
                {active.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="create" className="gap-1.5">
            <Plus className="w-3.5 h-3.5" /> Create New
          </TabsTrigger>
        </TabsList>

        {/* Packages list */}
        <TabsContent value="packages" className="mt-4 space-y-4">
          {loading && (
            <div className="flex items-center gap-2 text-muted-foreground py-4">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading packages…
            </div>
          )}

          {error && (
            <APIOffline
              error={error}
              endpoint="GET /api/v1/data-room/packages"
              onRetry={loadPackages}
              hint="The dataRoomList backend function is not yet deployed. Wire it to the Aurora API data room router."
            />
          )}

          {!loading && !error && (
            <>
              {/* Active */}
              {active.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Active ({active.length})
                  </h3>
                  {active.map(pkg => (
                    <PackageRow
                      key={pkg.package_id}
                      pkg={pkg}
                      onCopy={handleCopyLink}
                      onRevoke={handleRevoke}
                    />
                  ))}
                </div>
              )}

              {/* Expired / revoked */}
              {expired.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Expired / Revoked ({expired.length})
                  </h3>
                  {expired.map(pkg => (
                    <PackageRow
                      key={pkg.package_id}
                      pkg={pkg}
                      onCopy={handleCopyLink}
                      onRevoke={handleRevoke}
                    />
                  ))}
                </div>
              )}

              {/* Empty */}
              {active.length === 0 && expired.length === 0 && (
                <Card>
                  <CardContent className="py-10 text-center text-muted-foreground text-sm space-y-2">
                    <Lock className="w-8 h-8 mx-auto opacity-30" />
                    <p>No packages yet.</p>
                    <p className="text-xs">
                      Switch to the <strong>Create New</strong> tab to issue your first secure access link.
                    </p>
                  </CardContent>
                </Card>
              )}
            </>
          )}

          {/* Stats */}
          {packages && (
            <div className="text-xs text-muted-foreground border rounded px-3 py-2 space-y-1">
              <div className="font-medium">Package statistics</div>
              <div>Total: {packages.total || 0} · Active: {packages.active_count || active.length} · Expired: {packages.expired_count || expired.length}</div>
              {packages.generated_at && <div>Last refreshed: {new Date(packages.generated_at).toLocaleString()}</div>}
            </div>
          )}
        </TabsContent>

        {/* Create form */}
        <TabsContent value="create" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Plus className="w-4 h-4" /> New Secure Package
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                Package creation is an immutable operation. Content is sourced verbatim from the canonical scan record.
              </p>
            </CardHeader>
            <CardContent>
              <CreatePackageForm onCreated={loadPackages} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Backend gap notice */}
      <Card className="border-amber-200 bg-amber-50/50">
        <CardContent className="py-3 px-4">
          <div className="flex items-start gap-2 text-xs text-amber-900">
            <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-600" />
            <div>
              <span className="font-medium">Backend dependency:</span> This page requires three backend functions to be deployed:
              {" "}<code className="font-mono bg-amber-100 px-1 rounded">dataRoomList</code>,
              {" "}<code className="font-mono bg-amber-100 px-1 rounded">dataRoomCreate</code>, and
              {" "}<code className="font-mono bg-amber-100 px-1 rounded">dataRoomRevoke</code> —
              wired to the Aurora API <code className="font-mono bg-amber-100 px-1 rounded">/api/v1/data-room/</code> router.
              The UI will show graceful error states until they are deployed.
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}