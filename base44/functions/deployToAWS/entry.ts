/**
 * deployToAWS — Trigger Aurora OSI production deployment to AWS
 * 
 * Requirements:
 *   - AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY set
 *   - Docker installed locally
 *   - AWS CLI configured
 *   - User must be admin
 */

import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { exec } from 'node:child_process';
import { promisify } from 'node:util';

const execAsync = promisify(exec);

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    // Admin-only access
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

    // Validate required parameters
    if (!db_password || !certificate_arn || !gee_service_account_key) {
      return Response.json(
        {
          error: 'Missing required parameters: db_password, certificate_arn, gee_service_account_key',
        },
        { status: 400 }
      );
    }

    // Check AWS credentials
    const awsAccessKey = Deno.env.get('AWS_ACCESS_KEY_ID');
    const awsSecretKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');

    if (!awsAccessKey || !awsSecretKey) {
      return Response.json(
        {
          error: 'AWS credentials not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.',
        },
        { status: 400 }
      );
    }

    const logs = [];
    const log = (msg) => {
      logs.push(`[${new Date().toISOString()}] ${msg}`);
      console.log(msg);
    };

    log('Starting Aurora OSI AWS deployment...');
    log(`Region: ${aws_region}, Environment: ${environment}`);

    // Step 1: Check Docker
    log('Step 1/5: Checking Docker...');
    try {
      const { stdout } = await execAsync('docker --version');
      log(`✓ Docker found: ${stdout.trim()}`);
    } catch (e) {
      return Response.json(
        { error: 'Docker is not installed or not in PATH', logs },
        { status: 500 }
      );
    }

    // Step 2: Build Docker image
    log('Step 2/5: Building Docker image...');
    try {
      await execAsync('cd aurora_vnext && docker build -f infra/docker/Dockerfile.api -t aurora-api:latest .', {
        timeout: 900000, // 15 minutes
      });
      log('✓ Docker image built successfully');
    } catch (e) {
      log(`✗ Docker build failed: ${e.message}`);
      return Response.json({ error: 'Docker build failed', logs }, { status: 500 });
    }

    // Step 3: Create ECR repository (ignore if exists)
    log('Step 3/5: Setting up ECR repository...');
    try {
      const acctId = await execAsync(`aws sts get-caller-identity --query Account --output text --region ${aws_region}`);
      const ecrUri = `${acctId.stdout.trim()}.dkr.ecr.${aws_region}.amazonaws.com`;
      const repoName = 'aurora-api';

      // Try to create repo (ignore error if already exists)
      await execAsync(`aws ecr create-repository --repository-name ${repoName} --region ${aws_region}`, {
        timeout: 30000,
      }).catch(() => {
        log('ℹ ECR repository already exists');
      });

      // Login to ECR
      const loginCmd = `aws ecr get-login-password --region ${aws_region} | docker login --username AWS --password-stdin ${ecrUri}`;
      await execAsync(loginCmd, { timeout: 30000 });
      log(`✓ Logged in to ECR: ${ecrUri}`);

      // Tag image
      const imageUri = `${ecrUri}/${repoName}:latest`;
      await execAsync(`docker tag aurora-api:latest ${imageUri}`);
      log(`✓ Tagged image: ${imageUri}`);

      // Push to ECR
      log('Pushing image to ECR (this may take 2–5 minutes)...');
      await execAsync(`docker push ${imageUri}`, { timeout: 600000 }); // 10 minutes
      log(`✓ Image pushed to ECR`);

      // Store ECR URI for CloudFormation
      body.ecr_image_uri = imageUri;
    } catch (e) {
      log(`✗ ECR setup failed: ${e.message}`);
      return Response.json({ error: 'ECR setup failed', logs }, { status: 500 });
    }

    // Step 4: Prepare CloudFormation parameters
    log('Step 4/5: Preparing CloudFormation deployment...');
    const geeKeyBase64 = Buffer.from(gee_service_account_key).toString('base64');
    const cfParams = [
      `ParameterKey=Environment,ParameterValue=${environment}`,
      `ParameterKey=DockerImage,ParameterValue=${body.ecr_image_uri}`,
      `ParameterKey=DBPassword,ParameterValue=${db_password}`,
      `ParameterKey=DomainName,ParameterValue=${domain_name}`,
      `ParameterKey=CertificateArn,ParameterValue=${certificate_arn}`,
      `ParameterKey=GEEServiceAccountKey,ParameterValue=${geeKeyBase64}`,
    ];

    log(`✓ Parameters prepared (${cfParams.length} values)`);

    // Step 5: Deploy CloudFormation
    log('Step 5/5: Deploying CloudFormation stack...');
    const stackName = `aurora-osi-${environment}`;

    try {
      const cfCmd = `aws cloudformation create-stack \
        --stack-name ${stackName} \
        --template-body file://infra/cloudformation/aurora-production.yaml \
        --parameters ${cfParams.join(' ')} \
        --capabilities CAPABILITY_NAMED_IAM \
        --region ${aws_region}`;

      const { stdout } = await execAsync(cfCmd, { timeout: 60000 });
      log(`✓ CloudFormation stack created: ${stdout.trim()}`);

      log('');
      log('✅ Deployment initiated successfully!');
      log('');
      log('Next steps:');
      log(`  1. Monitor stack: aws cloudformation describe-stack-events --stack-name ${stackName} --region ${aws_region}`);
      log(`  2. Wait for completion: aws cloudformation wait stack-create-complete --stack-name ${stackName} --region ${aws_region}`);
      log(`  3. Get outputs: aws cloudformation describe-stacks --stack-name ${stackName} --query 'Stacks[0].Outputs' --region ${aws_region}`);
      log('');
      log('Estimated time: 15–25 minutes');

      return Response.json({
        status: 'success',
        message: 'Deployment initiated',
        stack_name: stackName,
        region: aws_region,
        logs,
      });
    } catch (e) {
      log(`✗ CloudFormation deployment failed: ${e.message}`);
      return Response.json(
        { error: 'CloudFormation deployment failed', logs },
        { status: 500 }
      );
    }
  } catch (error) {
    return Response.json(
      { error: error.message },
      { status: 500 }
    );
  }
});