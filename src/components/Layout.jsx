/**
 * Layout — sidebar navigation with role-aware menu
 * Phase P §P.7
 *
 * CONSTITUTIONAL RULE: Admin menu items rendered only when role === "admin".
 * Role sourced from /auth/me API response — never from localStorage assumption.
 * No scientific data in the navigation layer.
 */
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { LayoutDashboard, History, Database, Box, Shield, LogOut, Loader2, ChevronRight, Map, Download, FileText, Globe, Workflow } from "lucide-react";
import { auth, clearAccessToken } from "../lib/auroraApi";

const NAV = [
  { path: "/",         label: "Dashboard",  icon: LayoutDashboard, roles: ["admin","operator","viewer"] },
  { path: "/history",  label: "Scan History", icon: History,       roles: ["admin","operator","viewer"] },
  { path: "/datasets", label: "Datasets",   icon: Database,        roles: ["admin","operator","viewer"] },
  { path: "/twin",     label: "Digital Twin", icon: Box,           roles: ["admin","operator","viewer"] },
  { path: "/map-builder",  label: "Map Builder",  icon: Map,      roles: ["admin","operator","viewer"] },
  { path: "/reports",    label: "Reports",    icon: FileText, roles: ["admin","operator","viewer"] },
  { path: "/workflow",   label: "New Scan",   icon: Workflow, roles: ["admin","operator","viewer"] },
  { path: "/portfolio",  label: "Portfolio",  icon: Globe,    roles: ["admin","operator","viewer"] },
  { path: "/map-export",  label: "Map Export",   icon: Download, roles: ["admin","operator","viewer"] },
  { path: "/ground-truth", label: "Ground Truth", icon: Shield,  roles: ["admin","operator"] },
  { path: "/admin",       label: "Admin",        icon: Shield,  roles: ["admin"] },
];

export default function Layout() {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);
  const location  = useLocation();
  const navigate  = useNavigate();

  useEffect(() => {
    auth.me()
      .then(setUser)
      .catch(() => navigate("/login"))
      .finally(() => setLoading(false));
  }, []);

  async function handleLogout() {
    try { await auth.logout(); } catch {}
    clearAccessToken();
    navigate("/login");
  }

  if (loading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const visibleNav = NAV.filter(n => !user || n.roles.includes(user.role));

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 border-r bg-muted/30 flex flex-col">
        <div className="px-4 py-5 border-b">
          <div className="text-base font-bold tracking-tight">Aurora OSI</div>
          <div className="text-xs text-muted-foreground mt-0.5">vNext</div>
        </div>

        <nav className="flex-1 py-3 px-2 space-y-0.5">
          {visibleNav.map(({ path, label, icon: Icon }) => {
            const active = location.pathname === path || (path !== "/" && location.pathname.startsWith(path));
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
                {label}
                {active && <ChevronRight className="w-3 h-3 ml-auto opacity-60" />}
              </Link>
            );
          })}
        </nav>

        <div className="border-t p-3">
          {user && (
            <div className="mb-2 px-2">
              <div className="text-xs font-medium truncate">{user.email}</div>
              <div className="text-xs text-muted-foreground capitalize">{user.role}</div>
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
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet context={{ user }} />
      </main>
    </div>
  );
}