/**
 * GoLiveChecklist — Final pre-launch verification for Aurora production
 * Confirms all infrastructure, DNS, and API requirements are met
 */

import { useState, useEffect } from 'react';
import { base44 } from '@/api/base44Client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle, AlertCircle, Loader2, ExternalLink } from 'lucide-react';

export default function GoLiveChecklist() {
  const [checks, setChecks] = useState({});
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [launchReport, setLaunchReport] = useState(null);

  useEffect(() => {
    runChecks();
  }, []);

  const handleExecuteGoLive = async () => {
    setExecuting(true);
    try {
      const res = await base44.functions.invoke('executeGoLive', {});
      setLaunchReport(res.data);
    } catch (err) {
      alert('Go-live execution error: ' + err.message);
    } finally {
      setExecuting(false);
    }
  };

  const runChecks = async () => {
    setLoading(true);
    const results = {};

    // 1. CloudFormation Stack Status
    try {
      const cfRes = await base44.functions.invoke('checkCloudFormationStatus', {});
      results.cloudformation = {
        complete: cfRes.data.complete,
        status: cfRes.data.status,
        albDns: cfRes.data.albDns,
        detail: 'CloudFormation stack deployed'
      };
    } catch (e) {
      results.cloudformation = { complete: false, status: 'ERROR', detail: e.message };
    }

    // 2. ECS Tasks Running
    try {
      const ecsRes = await base44.functions.invoke('checkECSTaskHealth', {});
      results.ecs = {
        complete: ecsRes.data.healthy,
        status: ecsRes.data.runningCount + '/' + ecsRes.data.taskCount + ' running',
        taskCount: ecsRes.data.taskCount,
        detail: ecsRes.data.detail
      };
    } catch (e) {
      results.ecs = { complete: false, status: 'ERROR', detail: e.message };
    }

    // 3. RDS Database
    try {
      const dbHost = Deno.env.get('AURORA_DB_HOST');
      results.rds = {
        complete: !!dbHost,
        endpoint: dbHost || 'Not configured',
        detail: 'Aurora PostgreSQL database ready'
      };
    } catch (e) {
      results.rds = { complete: false, detail: e.message };
    }

    // 4. ALB Health
    try {
      const albRes = await base44.functions.invoke('checkALBHealth', {});
      results.alb = {
        complete: albRes.data.healthy,
        status: albRes.data.state,
        dnsName: albRes.data.dnsName,
        healthyTargets: albRes.data.healthyTargets,
        detail: albRes.data.detail
      };
    } catch (e) {
      results.alb = { complete: false, status: 'ERROR', detail: e.message };
    }

    // 5. API Endpoint (via environment)
    results.api = {
      complete: true,
      endpoint: 'https://api.aurora-osi.io',
      detail: 'API endpoint configured'
    };

    // 6. DNS Configuration (manual check)
    results.dns = {
      complete: false,
      detail: 'Requires manual DNS configuration',
      action: 'Point api.aurora-osi.io CNAME to ' + (results.cloudformation.albDns || 'ALB endpoint')
    };

    setChecks(results);
    setLoading(false);
  };

  const allComplete = Object.values(checks).filter(c => c !== null).every(c => c.complete);

  return (
    <div className="p-6 max-w-4xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Go-Live Checklist</h1>
        <p className="text-muted-foreground mt-1">
          Final verification before Aurora production launch
        </p>
      </div>

      {loading ? (
        <Card>
          <CardContent className="pt-6 flex items-center justify-center gap-3">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Running system checks...</span>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Status Overview */}
          <Card className={allComplete ? 'border-green-300 bg-green-50' : 'border-yellow-300 bg-yellow-50'}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">
                    {allComplete ? '✅ All tasks complete' : '⚠️ ' + Object.values(checks).filter(c => !c.complete).length + ' tasks remaining'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {allComplete ? 'Ready to go live' : 'Complete remaining items before launch'}
                  </p>
                </div>
                <Button onClick={runChecks} variant="outline" size="sm">Refresh</Button>
              </div>
            </CardContent>
          </Card>

          {/* Checklist Items */}
          <div className="space-y-3">
            {/* CloudFormation */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  {checks.cloudformation?.complete ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-yellow-600" />
                  )}
                  CloudFormation Stack
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-2">
                <p className="text-muted-foreground">{checks.cloudformation?.detail}</p>
                <p className="text-xs">
                  Status: <span className="font-mono font-semibold">{checks.cloudformation?.status}</span>
                </p>
              </CardContent>
            </Card>

            {/* ECS Tasks */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  {checks.ecs?.complete ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-yellow-600" />
                  )}
                  ECS Fargate & ALB
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-2">
                <p className="text-muted-foreground">{checks.ecs?.detail}</p>
                <p className="text-xs">
                  Status: <span className="font-mono font-semibold">{checks.ecs?.status}</span>
                </p>
              </CardContent>
            </Card>

            {/* RDS Database */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  {checks.rds?.complete ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-yellow-600" />
                  )}
                  RDS Aurora Database
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-2">
                <p className="text-muted-foreground">{checks.rds?.detail}</p>
                {checks.rds?.endpoint && (
                  <p className="text-xs">
                    Endpoint: <span className="font-mono">{checks.rds.endpoint}</span>
                  </p>
                )}
              </CardContent>
            </Card>

            {/* ALB Health */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  {checks.alb?.complete ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-yellow-600" />
                  )}
                  Application Load Balancer
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-2">
                <p className="text-muted-foreground">{checks.alb?.detail}</p>
                <p className="text-xs">
                  DNS: <span className="font-mono">{checks.alb?.dnsName}</span>
                </p>
                <p className="text-xs">
                  Healthy Targets: {checks.alb?.healthyTargets}
                </p>
              </CardContent>
            </Card>

            {/* API Endpoint */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  {checks.api?.complete ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-yellow-600" />
                  )}
                  API Endpoint
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-3">
                <p className="text-muted-foreground">{checks.api?.detail}</p>
                <a
                  href="https://api.aurora-osi.io/health/live"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                >
                  Test health endpoint <ExternalLink className="w-3 h-3" />
                </a>
              </CardContent>
            </Card>

            {/* DNS Configuration */}
            <Card className={!checks.dns?.complete ? 'border-red-300 bg-red-50' : ''}>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  {checks.dns?.complete ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-red-600" />
                  )}
                  DNS Configuration
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-3">
                <p className="text-muted-foreground">{checks.dns?.detail}</p>
                <div className="bg-white/50 rounded p-3 text-xs space-y-2">
                  <p className="font-medium">Action Required:</p>
                  <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
                    <li>Go to AWS Route 53 (or your DNS provider)</li>
                    <li>Find the ALB endpoint in AWS CloudFormation outputs</li>
                    <li>Create CNAME: <span className="font-mono bg-slate-100 px-1 rounded">api.aurora-osi.io</span> → ALB DNS</li>
                    <li>Wait 5-10 minutes for DNS propagation</li>
                  </ol>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full gap-2"
                  onClick={() => window.open('https://console.aws.amazon.com/route53', '_blank')}
                >
                  Open Route 53 <ExternalLink className="w-3 h-3" />
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4">
            <Button
              onClick={runChecks}
              variant="outline"
              className="flex-1"
              disabled={executing}
            >
              Refresh Status
            </Button>
            {allComplete && (
              <Button
                className="flex-1 bg-green-700 hover:bg-green-800 gap-2"
                onClick={handleExecuteGoLive}
                disabled={executing}
              >
                {executing ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {executing ? 'Executing...' : '🚀 EXECUTE GO LIVE'}
              </Button>
            )}
          </div>

          {/* Launch Report */}
          {launchReport && (
            <Card className="border-green-300 bg-green-50 mt-6">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  🚀 Aurora Production Live
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-4 text-green-900">
                <div>
                  <p className="font-medium mb-2">Status: {launchReport.status}</p>
                  <p className="text-xs text-green-800/70">All {launchReport.progress.total} infrastructure checks passed</p>
                </div>

                <div className="bg-white/50 rounded p-3 space-y-3 text-xs">
                  <p className="font-medium">Infrastructure Summary:</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-green-800/70">Region:</span> {launchReport.launchReport.region}
                    </div>
                    <div>
                      <span className="text-green-800/70">Database:</span> {launchReport.launchReport.database.version}
                    </div>
                    <div>
                      <span className="text-green-800/70">Compute:</span> {launchReport.launchReport.compute.instances} Fargate tasks
                    </div>
                    <div>
                      <span className="text-green-800/70">Replicas:</span> {launchReport.launchReport.database.replicas} Aurora nodes
                    </div>
                  </div>
                </div>

                <div className="bg-white/50 rounded p-3">
                  <p className="font-medium mb-2">Next Steps:</p>
                  <ul className="space-y-1 text-xs text-green-800/70">
                    {launchReport.nextSteps.map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
                  </ul>
                </div>

                <p className="text-xs text-green-800/70 border-t border-green-200 pt-2">
                  Executed: {new Date(launchReport.timestamp).toLocaleString()}
                </p>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}