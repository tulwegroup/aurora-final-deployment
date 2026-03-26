/**
 * deployToAWS — Generate deployment instructions for Aurora OSI
 * 
 * Since this runs in Deno (Base44 cloud), we can't execute Docker/AWS CLI.
 * Instead, we generate shell commands the user can copy & run locally.
 */

import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

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

    const body = await req.json();
    const {
      aws_region = 'us-east-1',
      environment = 'production',
      db_password,
      certificate_arn,
      domain_name = 'api.aurora-osi.io',
      gee_service_account_key,
    } = body;

    // Validate
    if (!db_password || !certificate_arn || !gee_service_account_key) {
      return Response.json(
        { error: 'Missing required: db_password, certificate_arn, gee_service_account_key' },
        { status: 400 }
      );
    }

    // Encode GEE key
    const geeKeyBase64 = btoa(gee_service_account_key);

    // Generate shell script commands
    const commands = [
      '#!/bin/bash',
      'set -e',
      '',
      '# Aurora OSI Deployment Script',
      `# Generated: ${new Date().toISOString()}`,
      '',
      'echo "Building Docker image..."',
      'cd aurora_vnext',
      'docker build -f infra/docker/Dockerfile.api -t aurora-api:latest .',
      '',
      'echo "Pushing to ECR..."',
      `AWS_REGION=${aws_region}`,
      `ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region $AWS_REGION)`,
      `ECR_URI=$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com`,
      `aws ecr create-repository --repository-name aurora-api --region $AWS_REGION 2>/dev/null || true`,
      `aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI`,
      `docker tag aurora-api:latest $ECR_URI/aurora-api:latest`,
      `docker push $ECR_URI/aurora-api:latest`,
      '',
      'echo "Deploying CloudFormation stack..."',
      `aws cloudformation create-stack \\`,
      `  --stack-name aurora-osi-${environment} \\`,
      `  --template-body file://infra/cloudformation/aurora-production.yaml \\`,
      `  --parameters \\`,
      `    ParameterKey=Environment,ParameterValue=${environment} \\`,
      `    ParameterKey=DockerImage,ParameterValue=\$ECR_URI/aurora-api:latest \\`,
      `    ParameterKey=DBPassword,ParameterValue='${db_password}' \\`,
      `    ParameterKey=DomainName,ParameterValue=${domain_name} \\`,
      `    ParameterKey=CertificateArn,ParameterValue='${certificate_arn}' \\`,
      `    ParameterKey=GEEServiceAccountKey,ParameterValue='${geeKeyBase64}' \\`,
      `  --capabilities CAPABILITY_NAMED_IAM \\`,
      `  --region $AWS_REGION`,
      '',
      'echo "✅ Stack creation initiated!"',
      `echo "Monitor: aws cloudformation describe-stack-events --stack-name aurora-osi-${environment} --region $AWS_REGION"`,
    ];

    return Response.json({
      status: 'success',
      message: 'Deployment script generated',
      script: commands.join('\n'),
      instructions: [
        '1. Copy the script below',
        '2. Save to: deploy.sh',
        '3. Run: chmod +x deploy.sh && ./deploy.sh',
        '4. Script will: build Docker image, push to ECR, deploy CloudFormation',
        '5. Estimated time: 15–25 minutes',
      ],
    });
  } catch (error) {
    return Response.json(
      { error: error.message },
      { status: 500 }
    );
  }
});