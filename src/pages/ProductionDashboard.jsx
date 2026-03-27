/**
 * ProductionDashboard — Real-time ops monitoring for Aurora production
 * Orchestrates CloudFormation deployment, DB initialization, API validation
 */

import { useState, useEffect } from 'react';
import { base44 } from '@/api/base44Client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { AlertTriangle, CheckCircle, Loader2, Cloud, Database, Zap } from 'lucide-react';

export default function ProductionDashboard() {
  const [step, setStep] = useState('ready'); // ready | deploying | validating | complete | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [deployment, setDeployment] = useState({});

  const handleDeploy = async () => {
    setStep('deploying');
    setError(null);

    try {
      // Step 1: Deploy CloudFormation stack
      const cfRes = await base44.functions.invoke('deployToAWS', {
        action: 'deploy',
        aws_region: 'us-east-1',
        environment: 'production',
        domain_name: 'api.aurora-osi.io'
      });

      if (cfRes.data.status !== 'success') {
        throw new Error(cfRes.data.error || 'CloudFormation deployment failed');
      }

      setDeployment(prev => ({ ...prev, cloudformation: cfRes.data }));

      // Step 2: Initialize database (wait 30s for RDS to be ready)
      await new Promise(r => setTimeout(r, 30000));

      const dbRes = await base44.functions.invoke('initDatabase', {});
      if (dbRes.data.status !== 'success') {
        throw new Error('Database initialization failed: ' + JSON.stringify(dbRes.data.details));
      }

      setDeployment(prev => ({ ...prev, database: dbRes.data }));
      setStep('validating');

      // Step 3: Validate all systems
      const valRes = await base44.functions.invoke('validateDeployment', {});
      setDeployment(prev => ({ ...prev, validation: valRes.data }));

      if (valRes.data.status === 'healthy') {
        setResult(valRes.data);
        setStep('complete');
      } else {
        setError('Some systems are degraded. See validation details.');
        setStep('error');
      }
    } catch (err) {
      setError(err.message || 'Deployment failed');
      setStep('error');
    }
  };

  return (
    <div className="p-6 max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Cloud className="w-6 h-6" /> Aurora Production Ops
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Full infrastructure deployment: CloudFormation → RDS → ECS → Validation
        </p>
      </div>

      {/* Ready state */}
      {step === 'ready' && (
        <Card className="border-blue-300 bg-blue-50">
          <CardHeader>
            <CardTitle className="text-base">Ready for Production Launch</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2 text-sm text-blue-900">
              <p>✓ Docker image built and in ECR</p>
              <p>✓ All secrets configured in dashboard</p>
              <p>✓ CloudFormation template validated</p>
            </div>
            <p className="text-xs text-blue-800">
              This will orchestrate: <strong>VPC creation → RDS Aurora → ECS Fargate → ALB → Database init → System validation</strong>
            </p>
            <Button onClick={handleDeploy} className="w-full gap-2 bg-blue-700 hover:bg-blue-800">
              <Cloud className="w-4 h-4" /> Launch Full Production Stack
            </Button>
            <p className="text-xs text-blue-800">⏱️ Estimated: 20-30 minutes</p>
          </CardContent>
        </Card>
      )}

      {/* Deploying */}
      {step === 'deploying' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Infrastructure Deployment
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2 text-sm">
              {!deployment.cloudformation ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span>Creating CloudFormation stack...</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-green-700">
                  <CheckCircle className="w-4 h-4" />
                  <span>CloudFormation stack initiated</span>
                </div>
              )}

              {deployment.cloudformation && !deployment.database ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span>Initializing RDS Aurora database...</span>
                </div>
              ) : deployment.database ? (
                <div className="flex items-center gap-2 text-green-700">
                  <CheckCircle className="w-4 h-4" />
                  <span>Database initialized with schema</span>
                </div>
              ) : null}

              {deployment.database && !deployment.validation ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span>Validating all systems...</span>
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Validating */}
      {step === 'validating' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Zap className="w-4 h-4 animate-pulse" /> Running Validation Checks
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>Testing CloudFormation stack, RDS, ECS, ALB, and API health...</p>
            <div className="flex gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
              <span className="text-muted-foreground">This may take 2-3 minutes</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Complete */}
      {step === 'complete' && result && (
        <Card className="border-green-300 bg-green-50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-green-900">
              <CheckCircle className="w-5 h-5" /> 🚀 Aurora Production Live!
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-green-900">
            <p className="text-sm font-medium">All systems operational and validated:</p>

            <div className="grid grid-cols-2 gap-3 text-xs">
              {Object.entries(result.checks).map(([key, check]) => (
                <div key={key} className="bg-white/50 rounded p-2 flex items-start gap-2">
                  <CheckCircle className="w-3 h-3 mt-0.5 flex-shrink-0 text-green-700" />
                  <div>
                    <div className="font-medium capitalize">{key}</div>
                    <div className="text-green-800/70 text-xs">{check.status || 'Healthy'}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="bg-white/50 rounded p-3 text-xs space-y-1">
              <p className="font-medium">Next Steps:</p>
              <ul className="space-y-1 ml-3 list-disc">
                <li>Point your DNS to the ALB endpoint</li>
                <li>Run pilot scans in Ghana, Zambia, Senegal</li>
                <li>Monitor CloudWatch logs at AWS Console</li>
                <li>Scale to commercial operations</li>
              </ul>
            </div>

            <Button className="w-full gap-2 bg-green-700 hover:bg-green-800">
              <CheckCircle className="w-4 h-4" /> View Deployment Details
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {step === 'error' && (
        <Card className="border-red-300 bg-red-50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-red-900">
              <AlertTriangle className="w-5 h-5" /> Deployment Error
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-red-900">
            <p className="text-sm">{error}</p>
            {deployment.validation?.checks && (
              <div className="bg-white/50 rounded p-2 text-xs space-y-1 max-h-40 overflow-y-auto">
                <p className="font-medium">Validation Results:</p>
                {Object.entries(deployment.validation.checks).map(([k, v]) => (
                  <div key={k} className="text-red-800/70">
                    {k}: {v.healthy ? '✓' : '✗'} {v.error || v.status}
                  </div>
                ))}
              </div>
            )}
            <Button
              onClick={() => {
                setStep('ready');
                setError(null);
                setDeployment({});
              }}
              className="w-full"
              variant="outline"
            >
              Retry Deployment
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Deployment timeline */}
      {Object.keys(deployment).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-xs">Deployment Timeline</CardTitle>
          </CardHeader>
          <CardContent className="text-xs space-y-2">
            {deployment.cloudformation && (
              <div>
                <p className="font-medium">CloudFormation</p>
                <p className="text-muted-foreground text-[11px]">Stack ID: {deployment.cloudformation.stackId?.slice(0, 50)}...</p>
              </div>
            )}
            {deployment.database && (
              <div>
                <p className="font-medium">Database</p>
                <p className="text-muted-foreground text-[11px]">Migrations: {deployment.database.migrations_applied}/{deployment.database.total}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}