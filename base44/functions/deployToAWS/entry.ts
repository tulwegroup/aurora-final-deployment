/**
 * deployToAWS — Deploy Aurora OSI to AWS CloudFormation (Live)
 * 
 * Provisions ECS Fargate, RDS Aurora, ALB, S3 via CloudFormation API.
 */

import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { createHmac } from 'node:crypto';

function signRequest(method, host, path, headers, body, accessKeyId, secretAccessKey) {
  const canonicalRequest = [
    method,
    path,
    '',
    Object.entries(headers)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}:${v}`)
      .join('\n'),
    '',
    Object.keys(headers)
      .sort()
      .join(';'),
    body ? createHmac('sha256', 'AWS4-HMAC-SHA256').update(body).digest('hex') : 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  ].join('\n');

  const scope = [
    new Date().toISOString().split('T')[0],
    host.split('.')[1],
    'cloudformation',
    'aws4_request',
  ].join('/');

  const stringToSign = [
    'AWS4-HMAC-SHA256',
    new Date().toISOString(),
    scope,
    createHmac('sha256', 'AWS4-HMAC-SHA256').update(canonicalRequest).digest('hex'),
  ].join('\n');

  const kDate = createHmac('sha256', `AWS4${secretAccessKey}`).update(new Date().toISOString().split('T')[0]).digest();
  const kRegion = createHmac('sha256', kDate).update(host.split('.')[1]).digest();
  const kService = createHmac('sha256', kRegion).update('cloudformation').digest();
  const kSigning = createHmac('sha256', kService).update('aws4_request').digest();
  const signature = createHmac('sha256', kSigning).update(stringToSign).digest('hex');

  return signature;
}

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (user?.role !== 'admin') {
      return Response.json(
        { error: 'Forbidden: Admin access required' },
        { status: 403 }
      );
    }

    const awsAccessKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const awsSecretAccessKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const dbPassword = Deno.env.get('AURORA_DB_PASSWORD');
    const certificateArn = Deno.env.get('AURORA_CERTIFICATE_ARN');
    const geeServiceAccountKey = Deno.env.get('AURORA_GEE_SERVICE_ACCOUNT_KEY');

    if (!awsAccessKeyId || !awsSecretAccessKey) {
      return Response.json(
        { error: 'AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY required in dashboard secrets' },
        { status: 400 }
      );
    }

    if (!dbPassword || !certificateArn || !geeServiceAccountKey) {
      return Response.json(
        { error: 'Missing deployment secrets: AURORA_DB_PASSWORD, AURORA_CERTIFICATE_ARN, AURORA_GEE_SERVICE_ACCOUNT_KEY' },
        { status: 400 }
      );
    }

    const body = await req.json();
    const {
      aws_region = 'us-east-1',
      environment = 'production',
      domain_name = 'api.aurora-osi.io',
    } = body;

    const stackName = `aurora-osi-${environment}`;
    const geeKeyBase64 = btoa(geeServiceAccountKey);

    // Fetch CloudFormation template
    const templateUrl = 'https://raw.githubusercontent.com/aurora-ai/aurora-vnext/main/infra/cloudformation/aurora-production.yaml';
    const templateResponse = await fetch(templateUrl);
    const template = await templateResponse.text();

    // Build CloudFormation request parameters
    const params = new URLSearchParams();
    params.append('Action', 'CreateStack');
    params.append('StackName', stackName);
    params.append('TemplateBody', template);
    params.append('Parameters.member.1.ParameterKey', 'Environment');
    params.append('Parameters.member.1.ParameterValue', environment);
    params.append('Parameters.member.2.ParameterKey', 'DBPassword');
    params.append('Parameters.member.2.ParameterValue', dbPassword);
    params.append('Parameters.member.3.ParameterKey', 'DomainName');
    params.append('Parameters.member.3.ParameterValue', domain_name);
    params.append('Parameters.member.4.ParameterKey', 'CertificateArn');
    params.append('Parameters.member.4.ParameterValue', certificateArn);
    params.append('Parameters.member.5.ParameterKey', 'GEEServiceAccountKey');
    params.append('Parameters.member.5.ParameterValue', geeKeyBase64);
    params.append('Capabilities.member.1', 'CAPABILITY_NAMED_IAM');
    params.append('Capabilities.member.2', 'CAPABILITY_AUTO_EXPAND');
    params.append('Version', '2010-05-08');

    const host = `cloudformation.${aws_region}.amazonaws.com`;
    const path = '/';

    // Make request to AWS CloudFormation
    const cfResponse = await fetch(`https://${host}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Host': host,
      },
      body: params.toString(),
    });

    if (!cfResponse.ok) {
      const error = await cfResponse.text();
      return Response.json(
        { error: `CloudFormation error: ${error}` },
        { status: cfResponse.status }
      );
    }

    const xmlResponse = await cfResponse.text();
    const stackIdMatch = xmlResponse.match(/<StackId>([^<]+)<\/StackId>/);
    const stackId = stackIdMatch ? stackIdMatch[1] : null;

    return Response.json({
      status: 'success',
      message: 'Stack creation initiated - going live!',
      stackId,
      stackName,
      region: aws_region,
      estimatedTime: '15–25 minutes',
      consoleUrl: `https://console.aws.amazon.com/cloudformation/home?region=${aws_region}#/stacks`,
      nextSteps: [
        '✅ Stack creation in progress',
        'Resources being provisioned: ECS Fargate, RDS Aurora, ALB, S3, monitoring',
        `Monitor at: https://console.aws.amazon.com/cloudformation`,
        'Aurora API will be live at your domain once complete',
      ],
    });
  } catch (error) {
    return Response.json(
      { error: error.message },
      { status: 500 }
    );
  }
});