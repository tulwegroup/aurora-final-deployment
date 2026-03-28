/**
 * GroundTruthAdmin — Ground Truth Management Interface
 * Phase Z §Z.4
 *
 * Admin/operator interface for:
 *   - Reviewing pending ground-truth submissions
 *   - Approving / rejecting with mandatory reason
 *   - Viewing provenance and confidence details
 *   - Browsing calibration version lineage
 *   - Full audit log (admin only)
 *
 * CONSTITUTIONAL RULE: This UI never displays or computes ACIF scores,
 * tier assignments, or any scientific output. It operates on ground-truth
 * records and calibration versions only.
 */
import { useState, useEffect, useCallback } from "react";
import { useOutletContext } from "react-router-dom";
import { base44 } from "@/api/base44Client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle, XCircle, Clock, GitBranch, FileText } from "lucide-react";
import GroundTruthTable from "../components/GroundTruthTable";
import ProvenancePanel from "../components/ProvenancePanel";
import APIOffline from "../components/APIOffline";

const STATUS_STYLES = {
  pending:   "bg-yellow-100 text-yellow-800 border-yellow-300",
  approved:  "bg-emerald-100 text-emerald-800 border-emerald-300",
  rejected:  "bg-red-100 text-red-800 border-red-300",
  superseded:"bg-slate-100 text-slate-600 border-slate-300",
};

export default function GroundTruthAdmin() {
  const [records, setRecords]           = useState([]);
  const [selected, setSelected]         = useState(null);
  const [versions, setVersions]         = useState([]);
  const [auditLog, setAuditLog]         = useState([]);
  const [loading, setLoading]           = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [error, setError]               = useState(null);

  const { user } = useOutletContext() || {};
  const actorRole = user?.role || "operator";
  const actorId   = user?.email || "unknown";

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      // Ground-truth backend functions (gtListRecords, gtListVersions, gtAuditLog)
      // will be wired once the Aurora API Phase Z routers are mounted.
      // For now, return empty arrays so the page renders without error.
      setRecords([]);
      setVersions([]);
      setAuditLog([]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  async function handleApprove(record_id) {
    // Blocked: Aurora API Phase Z ground-truth router not yet mounted
    // Action will be wired once POST /api/v1/ground-truth/approve is available
  }

  async function handleReject(record_id) {
    // Blocked: Aurora API Phase Z ground-truth router not yet mounted
    // Action will be wired once POST /api/v1/ground-truth/reject is available
  }

  const pending   = records.filter(r => r.status === "pending");
  const approved  = records.filter(r => r.status === "approved");
  const rejected  = records.filter(r => r.status === "rejected");

  if (loading) return (
    <div className="flex items-center justify-center h-64 gap-2 text-muted-foreground">
      <Loader2 className="w-5 h-5 animate-spin" /> Loading ground-truth records…
    </div>
  );

  if (error) return <div className="p-6 text-destructive text-sm">{error}</div>;

  return (
    <div className="p-6 max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Ground Truth Management</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Review, approve, and govern ground-truth calibration records.
        </p>
      </div>
      <APIOffline
        endpoint="GET /api/v1/ground-truth/records"
        hint="Aurora API Phase Z ground-truth routers are not yet mounted in main.py. Records will appear here once the router is uncommented and the API is redeployed."
      />

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Pending Review", count: pending.length,  IconComp: Clock,        color: "text-yellow-600" },
          { label: "Approved",       count: approved.length, IconComp: CheckCircle,  color: "text-emerald-600" },
          { label: "Rejected",       count: rejected.length, IconComp: XCircle,      color: "text-red-500" },
        ].map(({ label, count, IconComp, color }) => (
          <Card key={label}>
            <CardContent className="py-4 px-5 flex items-center gap-3">
              <IconComp className={`w-5 h-5 ${color}`} />
              <div>
                <div className="text-xs text-muted-foreground">{label}</div>
                <div className="text-2xl font-bold tabular-nums">{count}</div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: record list */}
        <div className="lg:col-span-2 space-y-4">
          <Tabs defaultValue="pending">
            <TabsList>
              <TabsTrigger value="pending">Pending ({pending.length})</TabsTrigger>
              <TabsTrigger value="approved">Approved ({approved.length})</TabsTrigger>
              <TabsTrigger value="rejected">Rejected ({rejected.length})</TabsTrigger>
              <TabsTrigger value="versions">
                <GitBranch className="w-3 h-3 mr-1" />Calibration Versions
              </TabsTrigger>
              <TabsTrigger value="audit">
                <FileText className="w-3 h-3 mr-1" />Audit Log
              </TabsTrigger>
            </TabsList>

            {["pending","approved","rejected"].map(tab => (
              <TabsContent key={tab} value={tab} className="mt-4">
                <GroundTruthTable
                  records={tab === "pending" ? pending : tab === "approved" ? approved : rejected}
                  selectedId={selected?.record_id}
                  onSelect={setSelected}
                />
              </TabsContent>
            ))}

            <TabsContent value="versions" className="mt-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Calibration Version Lineage</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="divide-y">
                    {versions.length === 0 && (
                      <div className="p-4 text-sm text-muted-foreground">No calibration versions yet.</div>
                    )}
                    {versions.map(v => (
                      <div key={v.version_id} className="px-4 py-3 flex items-start gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-xs text-muted-foreground">{v.version_id.slice(0,8)}…</span>
                            <Badge className={`text-xs ${STATUS_STYLES[v.status] || "bg-slate-100"}`}>
                              {v.status}
                            </Badge>
                            {v.parent_version_id && (
                              <span className="text-xs text-muted-foreground">
                                ← {v.parent_version_id.slice(0,8)}…
                              </span>
                            )}
                          </div>
                          <div className="text-sm mt-0.5">{v.description}</div>
                          <div className="text-xs text-muted-foreground mt-0.5">{v.rationale}</div>
                          {v.calibration_effect_flags?.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1">
                              {v.calibration_effect_flags.map(f => (
                                <span key={f} className="text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">
                                  {f}
                                </span>
                              ))}
                            </div>
                          )}
                          {v.applies_to_scans_after && (
                            <div className="text-[10px] text-muted-foreground mt-1">
                              Applies to scans after: {v.applies_to_scans_after.slice(0,19)}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="audit" className="mt-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Audit Log</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b bg-muted/40">
                          {["Time","Actor","Role","Action","Record","From","To","Reason"].map(h => (
                            <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {auditLog.map(e => (
                          <tr key={e.entry_id} className="border-b hover:bg-muted/20">
                            <td className="px-3 py-1.5 tabular-nums">{e.occurred_at?.slice(0,19)}</td>
                            <td className="px-3 py-1.5">{e.actor_id}</td>
                            <td className="px-3 py-1.5">{e.actor_role}</td>
                            <td className="px-3 py-1.5 font-medium">{e.action}</td>
                            <td className="px-3 py-1.5 font-mono text-muted-foreground">{e.record_id?.slice(0,8)}…</td>
                            <td className="px-3 py-1.5">{e.from_status || "—"}</td>
                            <td className="px-3 py-1.5">{e.to_status}</td>
                            <td className="px-3 py-1.5 max-w-[120px] truncate">{e.reason || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {auditLog.length === 0 && (
                      <div className="p-4 text-sm text-muted-foreground">No audit entries yet.</div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* Right: detail panel */}
        <div className="space-y-4">
          {selected ? (
            <>
              <ProvenancePanel record={selected} />
              {selected.status === "pending" && actorRole === "admin" && (
                <Card className="border-red-200 bg-red-50">
                  <CardHeader className="pb-2"><CardTitle className="text-sm text-red-800">Actions Unavailable</CardTitle></CardHeader>
                  <CardContent className="text-xs text-red-700 space-y-1">
                    <p>Approve / Reject actions are blocked.</p>
                    <p className="font-medium">Required: Mount Aurora API Phase Z ground-truth router in <code className="font-mono bg-red-100 px-1 rounded">main.py</code> and redeploy.</p>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <div className="text-sm text-muted-foreground p-4 border rounded-lg text-center">
              Select a record to view provenance details.
            </div>
          )}
        </div>
      </div>

      {/* Reject modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-background rounded-lg shadow-xl p-6 w-full max-w-md space-y-4">
            <h2 className="text-lg font-semibold">Reject Record</h2>
            <p className="text-sm text-muted-foreground">
              Provide a mandatory rejection reason. The record will be archived — not deleted.
            </p>
            <textarea
              className="w-full border rounded px-3 py-2 text-sm h-24 resize-none"
              placeholder="Enter rejection reason…"
              value={rejectReason}
              onChange={e => setRejectReason(e.target.value)}
            />
            <div className="flex gap-2 justify-end">
              <Button variant="outline" onClick={() => { setShowRejectModal(false); setRejectReason(""); }}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={!rejectReason.trim() || actionLoading}
                onClick={() => handleReject(selected?.record_id)}
              >
                Reject
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}