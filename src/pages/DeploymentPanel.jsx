/**
 * DeploymentPanel — Admin-only deployment control
 * Triggers AWS CloudFormation deployment via deployToAWS backend function
 */

import { useState } from 'react';
import { base44 } from '@/api/base44Client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Cloud, Loader2, CheckCircle, Copy } from 'lucide-react';

export default function DeploymentPanel() {
  const [step, setStep] = useState('form'); // form | generating | success | error
  const [script, setScript] = useState(null);
  const [error, setError] = useState(null);

  // Form state
  const [form, setForm] = useState({
    aws_region: 'us-east-1',
    environment: 'production',
    domain_name: 'api.aurora-osi.io',
    db_password: '',
    certificate_arn: '',
    gee_service_account_key: '',
  });

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleDeploy = async () => {
    setStep('generating');
    setScript(null);
    setError(null);

    try {
      const response = await base44.functions.invoke('deployToAWS', form);
      
      if (response.data.status === 'success') {
        setScript(response.data.script);
        setStep('success');
      } else {
        setError(response.data.error || 'Failed to generate script');
        setStep('error');
      }
    } catch (err) {
      setError(err.message);
      setStep('error');
    }
  };

  const copyToClipboard = () => {
    if (script) {
      navigator.clipboard.writeText(script);
      alert('Script copied to clipboard!');
    }
  };

  return (
    <div className="p-6 max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Cloud className="w-6 h-6" /> AWS Deployment Control
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Deploy Aurora OSI to AWS production environment
        </p>
      </div>

      {/* Warning */}
      <div className="flex items-start gap-2.5 p-4 border border-red-300 bg-red-50 rounded-lg">
        <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5 shrink-0" />
        <div className="text-sm text-red-900">
          <strong>Production Deployment:</strong> This will create/update AWS resources including ECS, RDS, ALB, and S3 buckets.
          Ensure all parameters are correct before proceeding.
        </div>
      </div>

      {/* Form */}
      {step === 'form' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Deployment Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* AWS Region */}
            <div>
              <label className="text-sm font-medium">AWS Region</label>
              <input
                type="text"
                name="aws_region"
                value={form.aws_region}
                onChange={handleInputChange}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm bg-background"
              />
              <p className="text-xs text-muted-foreground mt-1">e.g., us-east-1, eu-west-1</p>
            </div>

            {/* Environment */}
            <div>
              <label className="text-sm font-medium">Environment</label>
              <select
                name="environment"
                value={form.environment}
                onChange={handleInputChange}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm bg-background"
              >
                <option value="production">Production</option>
                <option value="staging">Staging</option>
                <option value="development">Development</option>
              </select>
            </div>

            {/* Domain Name */}
            <div>
              <label className="text-sm font-medium">Domain Name</label>
              <input
                type="text"
                name="domain_name"
                value={form.domain_name}
                onChange={handleInputChange}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm bg-background"
              />
              <p className="text-xs text-muted-foreground mt-1">e.g., api.aurora-osi.io</p>
            </div>

            {/* DB Password */}
            <div>
              <label className="text-sm font-medium">RDS Master Password</label>
              <input
                type="password"
                name="db_password"
                value={form.db_password}
                onChange={handleInputChange}
                placeholder="••••••••"
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm bg-background"
              />
              <p className="text-xs text-muted-foreground mt-1">Strong password required (min 8 chars, special chars recommended)</p>
            </div>

            {/* Certificate ARN */}
            <div>
              <label className="text-sm font-medium">ACM Certificate ARN</label>
              <input
                type="text"
                name="certificate_arn"
                value={form.certificate_arn}
                onChange={handleInputChange}
                placeholder="arn:aws:acm:..."
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm bg-background font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground mt-1">Get from AWS Certificate Manager console</p>
            </div>

            {/* GEE Service Account Key */}
            <div>
              <label className="text-sm font-medium">GEE Service Account Key (JSON)</label>
              <textarea
                name="gee_service_account_key"
                value={form.gee_service_account_key}
                onChange={handleInputChange}
                placeholder='{"type":"service_account",...}'
                rows={6}
                className="w-full mt-1 px-3 py-2 border rounded-md text-sm bg-background font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground mt-1">Full GEE service account JSON from console.cloud.google.com</p>
            </div>

            {/* Action */}
            <div className="flex gap-3 pt-4">
              <Button
                onClick={handleDeploy}
                disabled={!form.db_password || !form.certificate_arn || !form.gee_service_account_key}
                className="gap-2"
              >
                <Cloud className="w-4 h-4" />
                Deploy to AWS
              </Button>
              <p className="text-xs text-muted-foreground self-center">
                Estimated time: 15–25 minutes
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Generating */}
      {step === 'generating' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Generating Script
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm text-muted-foreground">Creating deployment shell script...</p>
          </CardContent>
        </Card>
      )}

      {/* Success */}
      {step === 'success' && (
        <Card className="border-emerald-300 bg-emerald-50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-emerald-900">
              <CheckCircle className="w-5 h-5" /> Script Generated
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-emerald-900">
            <div className="space-y-2">
              <p className="text-sm font-medium">Copy & run this script on your local machine:</p>
              <div className="bg-slate-900 text-slate-100 rounded-lg p-4 font-mono text-xs overflow-x-auto max-h-96 overflow-y-auto">
                {script?.split('\n').map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={copyToClipboard}
                className="gap-2 flex-1"
              >
                <Copy className="w-4 h-4" /> Copy Script
              </Button>
              <Button
                onClick={() => {
                  setStep('form');
                  setScript(null);
                }}
                variant="outline"
                className="flex-1"
              >
                Done
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {step === 'error' && (
        <Card className="border-red-300 bg-red-50">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-red-900">
              <AlertTriangle className="w-5 h-5" /> Error
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-red-900">
            <p className="text-sm font-medium">{error}</p>
            <div className="flex gap-2">
              <Button
                onClick={() => setStep('form')}
                variant="outline"
                className="flex-1"
              >
                Try Again
              </Button>
              <Button
                onClick={() => {
                  setStep('form');
                  setLogs([]);
                  setError(null);
                }}
                variant="outline"
                className="flex-1"
              >
                Reset
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">About This Deployment</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-xs text-muted-foreground">
          <p>✓ Builds Docker image locally</p>
          <p>✓ Pushes to AWS ECR (Elastic Container Registry)</p>
          <p>✓ Creates CloudFormation stack with all infrastructure</p>
          <p>✓ Provisions RDS Aurora, ECS Fargate, ALB, S3, auto-scaling</p>
          <p>✓ Configures HTTPS, monitoring, and security groups</p>
        </CardContent>
      </Card>
    </div>
  );
}