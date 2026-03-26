/**
 * DeploymentSetupGuide — Step-by-step guide to get AWS parameters
 * and store them in dashboard secrets
 */

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ChevronDown, Copy, CheckCircle, AlertTriangle } from 'lucide-react';
import { useState } from 'react';

export default function DeploymentSetupGuide() {
  const [expanded, setExpanded] = useState(null);

  const steps = [
    {
      title: '1️⃣ Create RDS Database Password',
      subtitle: 'For your Aurora PostgreSQL database',
      instructions: [
        'Generate a strong password (min 8 chars, mixed case, numbers, special chars)',
        'Examples: MyAurora@2024! or Secure#Pass123$',
        'Store this value in Dashboard → Settings → Secrets as: AURORA_DB_PASSWORD',
      ],
      code: 'AURORA_DB_PASSWORD=MyAurora@2024!',
    },
    {
      title: '2️⃣ Create ACM Certificate (HTTPS)',
      subtitle: 'Get your SSL certificate ARN from AWS',
      instructions: [
        'Go to: https://console.aws.amazon.com/acm/home',
        'Click "Request a certificate"',
        'Enter your domain name (e.g., api.aurora-osi.io)',
        'Choose DNS validation',
        'Complete validation (add CNAME records to your domain registrar)',
        'Once issued, copy the Certificate ARN',
        'Paste it in Dashboard → Settings → Secrets as: AURORA_CERTIFICATE_ARN',
      ],
      code: 'AURORA_CERTIFICATE_ARN=arn:aws:acm:us-east-1:123456789:certificate/abc123...',
    },
    {
      title: '3️⃣ Create Google Earth Engine Service Account',
      subtitle: 'For geospatial data access',
      instructions: [
        'Go to: https://console.cloud.google.com/iam-admin/serviceaccounts',
        'Click "Create Service Account"',
        'Name: aurora-gee-service',
        'Description: GEE access for Aurora OSI',
        'Click "Create and continue"',
        'Grant roles: Viewer (for GEE access)',
        'Click "Continue" then "Done"',
        'Find the service account in the list',
        'Click on it → "Keys" tab',
        'Click "Add Key" → "Create new key" → "JSON"',
        'Download the JSON file',
        'Copy the entire JSON content',
        'Paste in Dashboard → Settings → Secrets as: AURORA_GEE_SERVICE_ACCOUNT_KEY',
      ],
      code: '{"type":"service_account","project_id":"your-project","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",...}',
    },
  ];

  return (
    <div className="p-6 max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">🚀 Deployment Setup Guide</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Follow these steps to gather all required parameters and store them securely in dashboard secrets.
        </p>
      </div>

      {/* Security Notice */}
      <div className="flex items-start gap-3 p-4 border border-green-300 bg-green-50 rounded-lg">
        <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 shrink-0" />
        <div className="text-sm text-green-800">
          <strong>✅ Secure Approach:</strong> All sensitive parameters will be stored in the dashboard's encrypted secrets section. They'll never be stored in code or transmitted unnecessarily.
        </div>
      </div>

      {/* Steps */}
      <div className="space-y-3">
        {steps.map((step, i) => (
          <Card key={i}>
            <button
              onClick={() => setExpanded(expanded === i ? null : i)}
              className="w-full text-left"
            >
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{step.title}</CardTitle>
                  <ChevronDown
                    className={`w-5 h-5 text-muted-foreground transition-transform ${
                      expanded === i ? 'rotate-180' : ''
                    }`}
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-1">{step.subtitle}</p>
              </CardHeader>
            </button>

            {expanded === i && (
              <CardContent className="space-y-4">
                <ol className="space-y-2">
                  {step.instructions.map((instruction, j) => (
                    <li key={j} className="text-sm flex gap-3">
                      <span className="font-medium text-muted-foreground shrink-0">{j + 1}.</span>
                      <span>{instruction}</span>
                    </li>
                  ))}
                </ol>

                {step.code && (
                  <div className="mt-4 space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">Format when storing:</p>
                    <div className="bg-slate-900 text-slate-100 rounded-lg p-3 font-mono text-xs overflow-x-auto flex items-center justify-between group">
                      <span className="overflow-x-auto">{step.code}</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          navigator.clipboard.writeText(step.code);
                          alert('Format copied!');
                        }}
                        className="shrink-0 ml-2"
                      >
                        <Copy className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            )}
          </Card>
        ))}
      </div>

      {/* Final Step */}
      <Card className="border-blue-300 bg-blue-50">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2 text-blue-900">
            <AlertTriangle className="w-5 h-5" /> Store Secrets in Dashboard
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-3 text-blue-900">
          <p>Once you've gathered all parameters:</p>
          <ol className="space-y-2 ml-4 list-decimal">
            <li>Go to your app → Dashboard → Settings → Environment Variables</li>
            <li>Add each secret with the key names shown above:
              <ul className="ml-4 mt-1 space-y-1 list-disc text-xs">
                <li><code className="bg-white px-2 py-0.5 rounded">AURORA_DB_PASSWORD</code></li>
                <li><code className="bg-white px-2 py-0.5 rounded">AURORA_CERTIFICATE_ARN</code></li>
                <li><code className="bg-white px-2 py-0.5 rounded">AURORA_GEE_SERVICE_ACCOUNT_KEY</code></li>
              </ul>
            </li>
            <li>Click Save</li>
            <li>Return to Deployment Panel and click "Deploy to AWS" 🚀</li>
          </ol>
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex gap-3">
        <Button variant="outline" onClick={() => window.location.href = '/deploy'}>
          Back to Deployment Panel
        </Button>
        <Button asChild>
          <a href="https://console.aws.amazon.com" target="_blank" rel="noopener noreferrer">
            Open AWS Console
          </a>
        </Button>
      </div>
    </div>
  );
}