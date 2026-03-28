/**
 * AdminPanel — user management + audit log
 * Phase P §P.7 ROLE-AWARE ADMIN UI
 *
 * CONSTITUTIONAL RULES:
 *  - This page requires role=admin. Non-admin users are redirected to /.
 *  - Role sourced from useOutletContext user.role — from /auth/me API, not localStorage.
 *  - Audit log rendered verbatim from GET /admin/audit.
 *  - Audit records are append-only — no delete/edit UI exists on this page.
 *  - No scientific data rendered here.
 */
import { useEffect, useState } from "react";
import { useOutletContext, useNavigate } from "react-router-dom";
import { admin } from "../lib/auroraApi";
import MissingValue from "../components/MissingValue";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Shield, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { useState as useDialogState } from "react";
import APIOffline from "../components/APIOffline";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const ROLE_BADGE = {
  admin:    "bg-purple-100 text-purple-800",
  operator: "bg-blue-100 text-blue-800",
  viewer:   "bg-slate-100 text-slate-700",
};

const EVENT_LABELS = {
  login_success:             "Login ✓",
  login_failure:             "Login ✗",
  logout:                    "Logout",
  scan_submitted:            "Scan submitted",
  scan_deleted:              "Scan deleted",
  scan_reprocessed:          "Reprocessed",
  threshold_policy_changed:  "Policy changed",
  role_changed:              "Role changed",
  data_exported:             "Data exported",
  admin_bootstrapped:        "Bootstrap",
};

export default function AdminPanel() {
  const { user }              = useOutletContext() || {};
  const navigate              = useNavigate();
  const [users, setUsers]     = useState(null);
  const [auditData, setAudit] = useState(null);
  const [auditPage, setAuditPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  // Role guard — non-admin redirected
  useEffect(() => {
    if (user && user.role !== "admin") {
      navigate("/");
    }
  }, [user]);

  useEffect(() => {
    if (!user || user.role !== "admin") return;
    Promise.all([admin.listUsers(), admin.auditLog({ page: 1, page_size: 30 })])
      .then(([u, a]) => { setUsers(u); setAudit(a); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [user]);

  async function loadAudit(p) {
    const a = await admin.auditLog({ page: p, page_size: 30 });
    setAudit(a);
    setAuditPage(p);
  }

  const [roleDialog, setRoleDialog] = useState(null); // { userId, newRole }
  const [roleReason, setRoleReason] = useState("");

  function promptRoleChange(userId, newRole) {
    setRoleDialog({ userId, newRole });
    setRoleReason("");
  }

  async function confirmRoleChange() {
    if (!roleReason.trim() || !roleDialog) return;
    try {
      await admin.updateRole(roleDialog.userId, roleDialog.newRole, roleReason);
      const u = await admin.listUsers();
      setUsers(u);
    } catch (e) { alert(e.message); }
    setRoleDialog(null);
    setRoleReason("");
  }

  if (!user || user.role !== "admin") return null;

  if (loading) return <div className="p-6 flex items-center gap-2 text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>;
  if (error)   return <div className="p-6"><APIOffline error={error} endpoint="GET /api/v1/admin/users" /></div>;

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div className="flex items-center gap-2">
        <Shield className="w-5 h-5 text-purple-600" />
        <h1 className="text-2xl font-bold">Admin Panel</h1>
      </div>

      <Tabs defaultValue="users">
        <TabsList>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="audit">Audit Log</TabsTrigger>
        </TabsList>

        {/* Users tab — admin only */}
        <TabsContent value="users" className="space-y-3 mt-4">
          <div className="text-sm text-muted-foreground">{users?.total} registered users</div>
          {users?.users.map(u => (
            <Card key={u.user_id}>
              <CardContent className="py-3 px-4 flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">{u.full_name}</div>
                  <div className="text-xs text-muted-foreground">{u.email}</div>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${ROLE_BADGE[u.role] || "bg-slate-100 text-slate-700"}`}>
                  {u.role}
                </span>
                {/* Role change — admin only; requires reason (audited before write) */}
                <Select
                  defaultValue={u.role}
                  onValueChange={val => { if (val !== u.role) promptRoleChange(u.user_id, val); }}
                >
                  <SelectTrigger className="w-32 h-7 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">admin</SelectItem>
                    <SelectItem value="operator">operator</SelectItem>
                    <SelectItem value="viewer">viewer</SelectItem>
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        {/* Audit log tab — read-only, append-only */}
        <TabsContent value="audit" className="space-y-3 mt-4">
          <div className="text-xs text-muted-foreground border border-amber-300 bg-amber-50 rounded px-3 py-2">
            Audit log is <strong>append-only</strong>. Records cannot be edited or deleted.
          </div>
          {auditData && (
            <>
              <div className="text-sm text-muted-foreground">{auditData.total} events</div>
              <Card>
                <CardContent className="p-0">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b bg-muted/40">
                        {["Timestamp", "Event", "Actor", "Role", "Scan ID", "Details"].map(h => (
                          <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {auditData.events.map(ev => (
                        <tr key={ev.audit_id} className="border-b hover:bg-muted/20">
                          <td className="px-3 py-1.5 whitespace-nowrap text-muted-foreground">
                            {ev.timestamp ? new Date(ev.timestamp).toLocaleString() : <MissingValue inline />}
                          </td>
                          <td className="px-3 py-1.5 font-medium whitespace-nowrap">
                            {EVENT_LABELS[ev.event_type] || ev.event_type}
                          </td>
                          <td className="px-3 py-1.5 text-muted-foreground max-w-[140px] truncate">
                            {ev.actor_email || <MissingValue inline />}
                          </td>
                          <td className="px-3 py-1.5">
                            {ev.actor_role
                              ? <span className={`px-1.5 py-0.5 rounded ${ROLE_BADGE[ev.actor_role] || ""}`}>{ev.actor_role}</span>
                              : <MissingValue inline />}
                          </td>
                          <td className="px-3 py-1.5 font-mono text-muted-foreground max-w-[100px] truncate">
                            {ev.scan_id || "—"}
                          </td>
                          <td className="px-3 py-1.5 text-muted-foreground max-w-[180px] truncate">
                            {ev.details ? JSON.stringify(ev.details) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
              {auditData.total_pages > 1 && (
                <div className="flex items-center gap-2 justify-center">
                  <Button variant="outline" size="sm" disabled={auditPage <= 1} onClick={() => loadAudit(auditPage - 1)}>
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <span className="text-xs text-muted-foreground">Page {auditPage} of {auditData.total_pages}</span>
                  <Button variant="outline" size="sm" disabled={auditPage >= auditData.total_pages} onClick={() => loadAudit(auditPage + 1)}>
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              )}
            </>
          )}
        </TabsContent>
      </Tabs>

      {/* Role change confirmation dialog */}
      {roleDialog && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-background rounded-lg shadow-xl p-6 w-full max-w-md space-y-4">
            <h2 className="text-lg font-semibold">Confirm Role Change</h2>
            <p className="text-sm text-muted-foreground">
              Changing role to <strong>{roleDialog.newRole}</strong>. Provide a mandatory reason (this is audited).
            </p>
            <textarea
              className="w-full border rounded px-3 py-2 text-sm h-20 resize-none"
              placeholder="Enter reason for role change…"
              value={roleReason}
              onChange={e => setRoleReason(e.target.value)}
              autoFocus
            />
            <div className="flex gap-2 justify-end">
              <button
                className="px-4 py-2 text-sm border rounded hover:bg-muted"
                onClick={() => { setRoleDialog(null); setRoleReason(""); }}
              >
                Cancel
              </button>
              <button
                className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded disabled:opacity-50"
                disabled={!roleReason.trim()}
                onClick={confirmRoleChange}
              >
                Confirm Change
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}