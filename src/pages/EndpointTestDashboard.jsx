/**
 * EndpointTestDashboard — Consolidated endpoint testing suite
 * Tests all critical Aurora API routes with live results
 */
import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, XCircle, Loader2, Play } from 'lucide-react';

const API_BASE = 'https://api.aurora-osi.com';

const CRITICAL_ENDPOINTS = [
  { group: 'Health', path: '/health', method: 'GET', label: 'Root health' },
  { group: 'Scan', path: '/api/v1/scan/active', method: 'GET', label: 'Active scans', requiresAuth: true },
  { group: 'History', path: '/api/v1/history', method: 'GET', label: 'Scan history', requiresAuth: true },
  { group: 'DataRoom', path: '/api/v1/data-room/packages', method: 'GET', label: 'Data room packages', requiresAuth: true },
  { group: 'GroundTruth', path: '/api/v1/gt/records', method: 'GET', label: 'GT records', requiresAuth: true },
  { group: 'Auth', path: '/api/v1/auth/me', method: 'GET', label: 'Current user', requiresAuth: true },
  { group: 'Admin', path: '/api/v1/admin/bootstrap-status', method: 'GET', label: 'Bootstrap', requiresAuth: true },
];

function StatusBadge({ status }) {
  if (status === null) return <Badge variant="outline">pending</Badge>;
  if (status === 0) return <Badge variant="destructive">network error</Badge>;
  if (status >= 200 && status < 300) return <Badge className="bg-green-600">200 OK</Badge>;
  if (status === 401) return <Badge className="bg-yellow-600">401 auth required</Badge>;
  if (status === 403) return <Badge className="bg-yellow-600">403 forbidden</Badge>;
  if (status === 404) return <Badge variant="destructive">404 not found</Badge>;
  return <Badge variant="destructive">{status}</Badge>;
}

export default function EndpointTestDashboard() {
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState('');

  const testEndpoint = async (ep) => {
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const start = Date.now();
      const res = await fetch(`${API_BASE}${ep.path}`, { method: ep.method, headers });
      const elapsed = Date.now() - start;

      let body = '';
      try {
        const text = await res.text();
        body = text.substring(0, 200);
      } catch (e) {
        body = '';
      }

      setResults(prev => ({
        ...prev,
        [ep.path]: { status: res.status, elapsed, body, ok: res.ok },
      }));
    } catch (e) {
      setResults(prev => ({
        ...prev,
        [ep.path]: { status: 0, elapsed: 0, error: e.message, ok: false },
      }));
    }
  };

  const testAll = async () => {
    setLoading(true);
    for (const ep of CRITICAL_ENDPOINTS) {
      await testEndpoint(ep);
    }
    setLoading(false);
  };

  const groups = [...new Set(CRITICAL_ENDPOINTS.map(e => e.group))];
  const passCount = Object.values(results).filter(r => r.ok).length;
  const failCount = Object.values(results).filter(r => !r.ok).length;

  return (
    <div className="p-6 max-w-5xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold">Endpoint Test Dashboard</h1>
        <p className="text-muted-foreground">
          Test all critical Aurora API endpoints against{' '}
          <span className="font-mono text-sm">{API_BASE}</span>
        </p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-4 text-center">
            <div className="text-2xl font-bold">{Object.keys(results).length}</div>
            <div className="text-xs text-muted-foreground">Tests Run</div>
          </CardContent>
        </Card>
        <Card className="border-green-200 bg-green-50">
          <CardContent className="pt-4 text-center">
            <div className="text-2xl font-bold text-green-700">{passCount}</div>
            <div className="text-xs text-green-600">Passed</div>
          </CardContent>
        </Card>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-4 text-center">
            <div className="text-2xl font-bold text-red-700">{failCount}</div>
            <div className="text-xs text-red-600">Failed</div>
          </CardContent>
        </Card>
      </div>

      {/* Bearer Token */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Authentication</CardTitle>
        </CardHeader>
        <CardContent>
          <label className="text-xs text-muted-foreground block mb-2">Bearer Token (optional)</label>
          <input
            className="w-full border rounded px-3 py-2 text-sm font-mono bg-muted/30"
            placeholder="Paste JWT token for authenticated endpoints..."
            value={token}
            onChange={e => setToken(e.target.value)}
          />
        </CardContent>
      </Card>

      {/* Test All Button */}
      <Button onClick={testAll} disabled={loading} className="gap-2 w-full" size="lg">
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
        {loading ? 'Testing...' : 'Run All Tests'}
      </Button>

      {/* Results by Group */}
      {groups.map(group => (
        <div key={group} className="space-y-2">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase">{group}</h2>
          <div className="space-y-2">
            {CRITICAL_ENDPOINTS.filter(e => e.group === group).map(ep => {
              const result = results[ep.path];
              return (
                <Card key={ep.path} className={result && result.ok ? 'border-green-200' : result ? 'border-red-200' : ''}>
                  <CardContent className="p-4 flex items-center justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="font-mono text-sm">{ep.method} {ep.path}</p>
                      <p className="text-xs text-muted-foreground mt-1">{ep.label}</p>
                      {ep.requiresAuth && (
                        <Badge variant="outline" className="text-[10px] mt-2">requires auth</Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      {result ? (
                        <>
                          <div className="text-right">
                            <StatusBadge status={result.status} />
                            <p className="text-xs text-muted-foreground mt-1">{result.elapsed}ms</p>
                          </div>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => testEndpoint(ep)}
                          >
                            <Play className="w-3 h-3" />
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => testEndpoint(ep)}
                        >
                          <Play className="w-3 h-3" />
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      ))}

      {/* Final State */}
      <Card className="bg-slate-950 text-slate-300 border-0">
        <CardContent className="pt-4 font-mono text-xs space-y-1">
          <p className="text-slate-500">// Aurora API Configuration</p>
          <p>BASE_URL = "<span className="text-green-400">{API_BASE}</span>"</p>
          <p>VERSION = "<span className="text-blue-400">v1</span>"</p>
          <p>PROTOCOL = "<span className="text-green-400">HTTPS</span>"</p>
          <p>ENDPOINTS_TESTED = {CRITICAL_ENDPOINTS.length}</p>
          <p className="text-slate-500 mt-2">// Navigate to /api-console for full endpoint inventory</p>
        </CardContent>
      </Card>
    </div>
  );
}