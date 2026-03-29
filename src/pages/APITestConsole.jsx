/**
 * APITestConsole — Live interactive testing console for the Aurora API
 * All requests route through the auroraProxy backend function (no CORS issues)
 */
import { useState } from 'react';
import { base44 } from '@/api/base44Client';

const ENDPOINTS = [
  { group: 'System', label: 'GET /health/live', method: 'GET', path: '/health/live', description: 'Primary health check' },
  { group: 'System', label: 'GET /health', method: 'GET', path: '/health', description: 'Health alias' },
  { group: 'System', label: 'GET /', method: 'GET', path: '/', description: 'Root endpoint' },
  { group: 'System', label: 'GET /version', method: 'GET', path: '/version', description: 'Version registry' },
  { group: 'Scan', label: 'GET /api/v1/scan/active', method: 'GET', path: '/api/v1/scan/active', description: 'List active scans', requiresAuth: true },
  { group: 'History', label: 'GET /api/v1/history', method: 'GET', path: '/api/v1/history', description: 'Scan history list', requiresAuth: true },
  { group: 'Admin', label: 'GET /api/v1/admin/bootstrap-status', method: 'GET', path: '/api/v1/admin/bootstrap-status', description: 'Bootstrap status', requiresAuth: true },
  { group: 'Docs', label: 'GET /docs', method: 'GET', path: '/docs', description: 'OpenAPI Swagger UI' },
];

function StatusBadge({ status }) {
  if (!status) return null;
  const ok = status >= 200 && status < 300;
  return (
    <Badge className={ok ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
      {ok ? <CheckCircle className="w-3 h-3 mr-1" /> : <XCircle className="w-3 h-3 mr-1" />}
      {status}
    </Badge>
  );
}

function EndpointRow({ endpoint, token }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const run = async () => {
    setLoading(true);
    setResult(null);
    const start = Date.now();
    try {
      const res = await base44.functions.invoke('auroraProxy', {
        method: endpoint.method,
        path: endpoint.path,
        token: token || null,
      });
      const elapsed = Date.now() - start;
      setResult({ status: res.data.status, body: res.data.data, elapsed });
    } catch (e) {
      setResult({ status: 0, body: { error: e.message }, elapsed: Date.now() - start });
    }
    setLoading(false);
    setExpanded(true);
  };

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="flex items-center gap-3 p-3 bg-muted/30 hover:bg-muted/50 cursor-pointer" onClick={() => result && setExpanded(e => !e)}>
        <Badge variant="outline" className="font-mono text-xs shrink-0">{endpoint.method}</Badge>
        <span className="font-mono text-sm flex-1">{endpoint.path}</span>
        <span className="text-xs text-muted-foreground hidden sm:block">{endpoint.description}</span>
        {result && <StatusBadge status={result.status} />}
        {result && <span className="text-xs text-muted-foreground">{result.elapsed}ms</span>}
        {result && (expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />)}
        <Button size="sm" onClick={(e) => { e.stopPropagation(); run(); }} disabled={loading} className="shrink-0">
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
        </Button>
      </div>
      {expanded && result && (
        <div className="p-3 bg-slate-950 text-green-400 font-mono text-xs overflow-auto max-h-64">
          <pre>{JSON.stringify(result.body, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default function APITestConsole() {
  const [token, setToken] = useState('');
  const [runningAll, setRunningAll] = useState(false);
  const [globalResults, setGlobalResults] = useState(null);

  const runAllSystem = async () => {
    setRunningAll(true);
    const results = [];
    for (const ep of ENDPOINTS.filter(e => e.group === 'System')) {
      const start = Date.now();
      try {
        const res = await base44.functions.invoke('auroraProxy', { method: ep.method, path: ep.path });
        const { data, status, ok } = res.data;
        results.push({ label: ep.label, status, ok, elapsed: Date.now() - start, body: data });
      } catch (e) {
        results.push({ label: ep.label, status: 0, ok: false, elapsed: Date.now() - start, body: { error: e.message } });
      }
    }
    setGlobalResults(results);
    setRunningAll(false);
  };

  const groups = [...new Set(ENDPOINTS.map(e => e.group))];

  return (
    <div className="p-6 max-w-4xl space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">API Test Console</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Live testing against{' '}
            <a href="https://api.aurora-osi.com" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline font-mono">
              api.aurora-osi.com
            </a>
          </p>
        </div>
        <Button onClick={runAllSystem} disabled={runningAll} variant="outline" className="gap-2 shrink-0">
          {runningAll ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Run System Checks
        </Button>
      </div>

      {/* Quick system check results */}
      {globalResults && (
        <Card>
          <CardHeader><CardTitle className="text-sm">System Check Results</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {globalResults.map(r => (
              <div key={r.label} className="flex items-center gap-3 text-sm">
                {r.ok ? <CheckCircle className="w-4 h-4 text-green-600" /> : <XCircle className="w-4 h-4 text-red-500" />}
                <span className="font-mono flex-1">{r.label}</span>
                <StatusBadge status={r.status} />
                <span className="text-xs text-muted-foreground">{r.elapsed}ms</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Bearer Token Input */}
      <Card>
        <CardContent className="pt-4">
          <label className="text-xs text-muted-foreground block mb-1">Bearer Token (for authenticated endpoints)</label>
          <input
            className="w-full border rounded px-3 py-2 text-sm font-mono bg-muted/30"
            placeholder="Paste JWT token here..."
            value={token}
            onChange={e => setToken(e.target.value)}
          />
        </CardContent>
      </Card>

      {/* Endpoint Groups */}
      {groups.map(group => (
        <div key={group} className="space-y-2">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">{group}</h2>
          {ENDPOINTS.filter(e => e.group === group).map(ep => (
            <EndpointRow key={ep.path} endpoint={ep} token={token} />
          ))}
        </div>
      ))}

      {/* API Info */}
      <Card className="bg-slate-950 text-slate-300">
        <CardContent className="pt-4 font-mono text-xs space-y-1">
          <p className="text-slate-500">// Aurora API — Production (via server-side proxy, no CORS)</p>
          <p>PROXY = base44.functions.invoke('auroraProxy', ...)</p>
          <p>AURORA_BASE = "https://api.aurora-osi.com"</p>
          <p>STATUS = <span className="text-green-400">LIVE ✓</span></p>
          <p>IMAGE = 368331615566.dkr.ecr.us-east-1.amazonaws.com/aurora-api:latest</p>
          <p>CLUSTER = aurora-cluster-osi</p>
          <p>SERVICE = aurora-osi-production</p>
        </CardContent>
      </Card>
    </div>
  );
}