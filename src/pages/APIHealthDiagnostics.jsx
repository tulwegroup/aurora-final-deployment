/**
 * APIHealthDiagnostics — Real-time API health & connectivity troubleshooting
 */
import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AlertCircle, CheckCircle, Loader2, RefreshCw, Activity, Network, Database } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

export default function APIHealthDiagnostics() {
  const [liveness, setLiveness] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [dependencies, setDependencies] = useState(null);
  const [routes, setRoutes] = useState(null);
  const [endpointStatus, setEndpointStatus] = useState({});
  const [networkDiags, setNetworkDiags] = useState(null);
  const [loading, setLoading] = useState(false);

  const runFullDiagnostics = async () => {
    setLoading(true);
    try {
      // 1. Liveness
      const liveRes = await fetch(`${API_BASE}/api/v1/health/live`);
      setLiveness(liveRes.ok ? await liveRes.json() : { error: 'Failed to reach liveness' });

      // 2. Readiness
      const readyRes = await fetch(`${API_BASE}/api/v1/health/ready`);
      setReadiness(readyRes.ok ? await readyRes.json() : { error: 'Failed to reach readiness' });

      // 3. Dependencies
      const depsRes = await fetch(`${API_BASE}/api/v1/health/dependencies`);
      setDependencies(depsRes.ok ? await depsRes.json() : { error: 'Failed to reach dependencies' });

      // 4. Routes
      const routesRes = await fetch(`${API_BASE}/api/v1/discover/routes`);
      setRoutes(routesRes.ok ? await routesRes.json() : { error: 'Failed to fetch routes' });

      // 5. Network diagnostics
      const netRes = await fetch(`${API_BASE}/api/v1/discover/network-diagnostics`);
      setNetworkDiags(netRes.ok ? await netRes.json() : { error: 'Failed to fetch network diagnostics' });

      // 6. Test key endpoints
      const endpointsToTest = [
        '/api/v1/history',
        '/api/v1/discover/routes',
        '/api/v1/health/live',
      ];

      for (const ep of endpointsToTest) {
        try {
          const res = await fetch(`${API_BASE}${ep}`);
          setEndpointStatus(prev => ({
            ...prev,
            [ep]: { status: res.ok ? 'reachable' : 'unreachable', code: res.status },
          }));
        } catch (e) {
          setEndpointStatus(prev => ({
            ...prev,
            [ep]: { status: 'unreachable', error: e.message },
          }));
        }
      }
    } catch (error) {
      console.error('Diagnostics error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runFullDiagnostics();
    const interval = setInterval(runFullDiagnostics, 10000); // Rerun every 10s
    return () => clearInterval(interval);
  }, []);

  const StatusBadge = ({ status }) => {
    if (!status) return <Badge>Unknown</Badge>;
    if (status.error) return <Badge variant="destructive">Error</Badge>;
    if (status.status === 'healthy' || status.status === 'ok' || status.status === 'ready') {
      return <Badge className="bg-emerald-500">Healthy</Badge>;
    }
    if (status.status === 'reachable') return <Badge className="bg-emerald-500">Reachable</Badge>;
    return <Badge variant="outline">Unknown</Badge>;
  };

  return (
    <div className="p-6 max-w-6xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Activity className="w-7 h-7" /> API Health & Diagnostics
        </h1>
        <p className="text-sm text-muted-foreground">
          Real-time monitoring and troubleshooting for Aurora API connectivity
        </p>
      </div>

      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="py-4">
          <Button onClick={runFullDiagnostics} disabled={loading} className="gap-2">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Run Full Diagnostics
          </Button>
          <p className="text-xs text-muted-foreground mt-2">Last updated: {new Date().toLocaleTimeString()}</p>
        </CardContent>
      </Card>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="dependencies">Dependencies</TabsTrigger>
          <TabsTrigger value="routes">Routes</TabsTrigger>
          <TabsTrigger value="network">Network</TabsTrigger>
        </TabsList>

        {/* OVERVIEW */}
        <TabsContent value="overview" className="space-y-4 mt-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Liveness */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <CheckCircle className="w-4 h-4" /> Liveness
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-1">
                {liveness ? (
                  <>
                    <StatusBadge status={liveness} />
                    <div className="text-xs text-muted-foreground">
                      {liveness.status === 'alive' ? 'API process is running' : liveness.error}
                    </div>
                  </>
                ) : (
                  <Loader2 className="w-4 h-4 animate-spin" />
                )}
              </CardContent>
            </Card>

            {/* Readiness */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Network className="w-4 h-4" /> Readiness
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-1">
                {readiness ? (
                  <>
                    <StatusBadge status={readiness} />
                    <div className="text-xs text-muted-foreground">
                      {readiness.status === 'ready' ? 'API ready to serve' : readiness.reason || readiness.error}
                    </div>
                  </>
                ) : (
                  <Loader2 className="w-4 h-4 animate-spin" />
                )}
              </CardContent>
            </Card>

            {/* Dependencies */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Database className="w-4 h-4" /> Dependencies
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-1">
                {dependencies?.dependencies ? (
                  <>
                    {Object.entries(dependencies.dependencies).map(([name, dep]) => (
                      <div key={name} className="flex justify-between items-center text-xs">
                        <span className="capitalize">{name}</span>
                        <Badge
                          variant={dep.status === 'healthy' ? 'default' : 'outline'}
                          className="text-[10px]"
                        >
                          {dep.status}
                        </Badge>
                      </div>
                    ))}
                  </>
                ) : (
                  <Loader2 className="w-4 h-4 animate-spin" />
                )}
              </CardContent>
            </Card>
          </div>

          {/* Endpoint Status */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Endpoint Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {Object.entries(endpointStatus).map(([endpoint, status]) => (
                <div key={endpoint} className="flex items-center justify-between border-b pb-2 text-sm">
                  <span className="font-mono text-xs">{endpoint}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">{status.code || status.error}</span>
                    <Badge variant={status.status === 'reachable' ? 'default' : 'destructive'}>
                      {status.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* DEPENDENCIES */}
        <TabsContent value="dependencies" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Service Dependencies</CardTitle>
            </CardHeader>
            <CardContent>
              {dependencies?.dependencies ? (
                <div className="space-y-4">
                  {Object.entries(dependencies.dependencies).map(([name, dep]) => (
                    <div key={name} className="border rounded p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-medium capitalize">{name}</span>
                        <StatusBadge status={dep} />
                      </div>
                      {dep.host && (
                        <div className="text-xs text-muted-foreground">
                          Host: <span className="font-mono">{dep.host}</span>
                        </div>
                      )}
                      {dep.error && (
                        <div className="text-xs text-red-600 flex items-start gap-1">
                          <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
                          {dep.error}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <Loader2 className="w-4 h-4 animate-spin" />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ROUTES */}
        <TabsContent value="routes" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Available Routes ({routes?.count || 0})</CardTitle>
            </CardHeader>
            <CardContent>
              {routes?.grouped ? (
                <div className="space-y-4">
                  {Object.entries(routes.grouped).map(([group, routeList]) => (
                    <div key={group}>
                      <h4 className="font-medium text-sm capitalize mb-2">{group}</h4>
                      <div className="space-y-1">
                        {routeList.map(route => (
                          <div key={route.path} className="text-xs border rounded p-2 flex justify-between items-center">
                            <span className="font-mono">{route.method} {route.path}</span>
                            <Badge variant="outline">{route.group}</Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <Loader2 className="w-4 h-4 animate-spin" />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* NETWORK */}
        <TabsContent value="network" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Network Diagnostics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {networkDiags?.diagnostics ? (
                <>
                  <div className="flex items-center justify-between border-b pb-3">
                    <span className="font-medium">Overall Status</span>
                    <Badge
                      className={
                        networkDiags.overall_status === 'healthy'
                          ? 'bg-emerald-500'
                          : 'bg-amber-500'
                      }
                    >
                      {networkDiags.overall_status}
                    </Badge>
                  </div>
                  {Object.entries(networkDiags.diagnostics).map(([key, diag]) => (
                    <div key={key} className="border rounded p-3 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm capitalize">{key}</span>
                        <StatusBadge status={diag} />
                      </div>
                      {diag.hostname && <div className="text-xs text-muted-foreground">Hostname: {diag.hostname}</div>}
                      {diag.ip && <div className="text-xs text-muted-foreground">IP: {diag.ip}</div>}
                      {diag.host && <div className="text-xs text-muted-foreground">Host: {diag.host}</div>}
                      {diag.port && <div className="text-xs text-muted-foreground">Port: {diag.port}</div>}
                      {diag.error && (
                        <div className="text-xs text-red-600 flex items-start gap-1">
                          <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
                          {diag.error}
                        </div>
                      )}
                    </div>
                  ))}
                </>
              ) : (
                <Loader2 className="w-4 h-4 animate-spin" />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Troubleshooting guide */}
      <Card className="border-amber-200 bg-amber-50">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4" /> Troubleshooting
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-2">
          <div>
            <p className="font-medium">API Unreachable?</p>
            <ul className="list-disc list-inside text-xs text-muted-foreground mt-1 space-y-0.5">
              <li>Check if Aurora API container is running: <span className="font-mono">docker ps</span></li>
              <li>View logs: <span className="font-mono">docker logs aurora-api</span></li>
              <li>Verify DNS resolution: <span className="font-mono">nslookup aurora-db</span> or hostname</li>
              <li>Test port directly: <span className="font-mono">nc -zv aurora-db 8000</span></li>
            </ul>
          </div>
          <div>
            <p className="font-medium">Database Connection Failed?</p>
            <ul className="list-disc list-inside text-xs text-muted-foreground mt-1 space-y-0.5">
              <li>Verify PostgreSQL is running and port 5432 is open</li>
              <li>Check connection string matches environment: <span className="font-mono">{API_BASE}</span></li>
              <li>Ensure network policies allow inter-container communication</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}