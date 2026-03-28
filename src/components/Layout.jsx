/**
 * Layout — sidebar navigation with role-aware menu + version footer
 * Phase P §P.7 (Refined)
 *
 * CONSTITUTIONAL RULE: Admin menu items rendered only when role === "admin".
 * Role sourced from /auth/me API response — never from localStorage assumption.
 * No scientific data in the navigation layer.
 */
import { Link, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  LayoutDashboard, History, Database, Box, Shield, LogOut, Loader2,
  ChevronRight, Map, Download, FileText, Globe, Workflow, FlaskConical,
  DollarSign, Cloud, Rocket, Terminal, Lock, BarChart3, ClipboardList
} from "lucide-react";
import { auth, clearAccessToken } from "../lib/auroraApi";

const NAV_SECTIONS = [
  {
    label: "Core",
    items: [
      { path: "/",         label: "Dashboard",    icon: LayoutDashboard, roles: ["admin","operator","viewer"] },
      { path: "/workflow", label: "New Scan",      icon: Workflow,        roles: ["admin","operator"] },
      { path: "/history",  label: "Scan History",  icon: History,         roles: ["admin","operator","viewer"] },
    ],
  },
  {
    label: "Analysis",
    items: [
      { path: "/portfolio",  label: "Portfolio",    icon: BarChart3,  roles: ["admin","operator","viewer"] },
      { path: "/reports",    label: "Reports",      icon: FileText,   roles: ["admin","operator","viewer"] },
      { path: "/data-room",  label: "Data Room",    icon: Lock,       roles: ["admin","operator","viewer"] },
      { path: "/map-builder",label: "Map Builder",  icon: Map,        roles: ["admin","operator","viewer"] },
      { path: "/map-export", label: "Map Export",   icon: Download,   roles: ["admin","operator","viewer"] },
    ],
  },
  {
    label: "Advanced",
    items: [
      { path: "/history",       label: "Digital Twin",    icon: Box,          roles: ["admin","operator","viewer"] },
      { path: "/ground-truth", label: "Ground Truth",    icon: Shield,       roles: ["admin","operator"] },
      { path: "/pilots",       label: "Pilots",          icon: FlaskConical, roles: ["admin","operator"] },
      { path: "/commercial",   label: "Commercial",      icon: DollarSign,   roles: ["admin"] },
    ],
  },
  {
    label: "Admin",
    items: [
      { path: "/admin",      label: "User Admin",    icon: Shield,  roles: ["admin"] },
      { path: "/deploy",     label: "AWS Deploy",    icon: Cloud,   roles: ["admin"] },
      { path: "/go-live",    label: "Go Live",       icon: Rocket,  roles: ["admin"] },
      { path: "/ops",        label: "Ops Monitor",   icon: Cloud,   roles: ["admin"] },
      { path: "/api-console",label: "API Console",   icon: Terminal,      roles: ["admin"] },
      { path: "/coverage",    label: "UI Coverage",   icon: ClipboardList,  roles: ["admin"] },
    ],
  },
];

export default function Layout() {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);
  const location  = useLocation();

  useEffect(() => {
    auth.me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function handleLogout() {
    try { await auth.logout(); } catch {}
    clearAccessToken();
    window.location.href = "/";
  }

  if (loading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  function isActive(path) {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  }

  const visibleSections = NAV_SECTIONS.map(section => ({
    ...section,
    items: section.items.filter(item => !user || item.roles.includes(user.role)),
  })).filter(s => s.items.length > 0);

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 border-r bg-muted/20 flex flex-col">
        {/* Brand */}
        <div className="px-4 py-4 border-b">
          <div className="text-base font-bold tracking-tight text-foreground">Aurora OSI</div>
          <div className="text-[11px] text-muted-foreground mt-0.5 font-mono">vNext · Production</div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
          {visibleSections.map(section => (
            <div key={section.label}>
              <div className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                {section.label}
              </div>
              <div className="space-y-0.5">
                {section.items.map(({ path, label, icon: Icon }) => {
                  const active = isActive(path);
                  return (
                    <Link
                      key={path}
                      to={path}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                        active
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      }`}
                    >
                      <Icon className="w-4 h-4 flex-shrink-0" />
                      <span className="truncate">{label}</span>
                      {active && <ChevronRight className="w-3 h-3 ml-auto opacity-60 shrink-0" />}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* User + logout */}
        <div className="border-t p-3 space-y-2">
          {user && (
            <div className="px-2 py-1">
              <div className="text-xs font-medium truncate">{user.full_name || user.email}</div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  user.role === "admin"    ? "bg-purple-100 text-purple-700" :
                  user.role === "operator" ? "bg-blue-100 text-blue-700" :
                  "bg-slate-100 text-slate-600"
                }`}>
                  {user.role}
                </span>
                <span className="text-[10px] text-muted-foreground truncate">{user.email}</span>
              </div>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Log out
          </button>
        </div>

        {/* Version footer */}
        <div className="border-t px-4 py-2">
          <div className="text-[10px] text-muted-foreground/50 font-mono">Aurora OSI vNext</div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto min-h-screen">
        <Outlet context={{ user }} />
      </main>
    </div>
  );
}