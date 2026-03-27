/**
 * deployToAWS — Deploy Aurora OSI to AWS CloudFormation (Live)
 * Provisions ECS Fargate, RDS Aurora, ALB, S3 via CloudFormation API.
 * Template is loaded from the project's infra/cloudformation directory.
 */

import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

// --- AWS Sig V4 signing using Web Crypto API (async) ---
async function hmacSHA256(key, data) {
  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    typeof key === 'string' ? new TextEncoder().encode(key) : key,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  return new Uint8Array(await crypto.subtle.sign('HMAC', cryptoKey, new TextEncoder().encode(data)));
}

async function sha256Hex(data) {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(data));
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}

function toHex(bytes) {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function signV4({ method, host, path, body, region, service, accessKeyId, secretAccessKey }) {
  const now = new Date();
  const amzDate = now.toISOString().replace(/[:\-]|\.\d{3}/g, '');
  const dateStamp = amzDate.slice(0, 8);

  const bodyHash = await sha256Hex(body);
  const headers = {
    'content-type': 'application/x-www-form-urlencoded',
    'host': host,
    'x-amz-date': amzDate,
  };
  const signedHeaders = Object.keys(headers).sort().join(';');
  const canonicalHeaders = Object.keys(headers).sort().map(k => `${k}:${headers[k]}`).join('\n') + '\n';
  const canonicalRequest = [method, path, '', canonicalHeaders, signedHeaders, bodyHash].join('\n');
  const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;
  const stringToSign = ['AWS4-HMAC-SHA256', amzDate, credentialScope, await sha256Hex(canonicalRequest)].join('\n');

  const kDate = await hmacSHA256(`AWS4${secretAccessKey}`, dateStamp);
  const kRegion = await hmacSHA256(kDate, region);
  const kService = await hmacSHA256(kRegion, service);
  const kSigning = await hmacSHA256(kService, 'aws4_request');
  const signature = toHex(await hmacSHA256(kSigning, stringToSign));

  return { ...headers, authorization: `AWS4-HMAC-SHA256 Credential=${accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}` };
}

// --- CloudFormation template (embedded) ---
const CF_TEMPLATE = `AWSTemplateFormatVersion: '2010-09-09'
Description: 'Aurora OSI Production Deployment - ECS Fargate + RDS + S3'

Parameters:
  Environment:
    Type: String
    Default: production
    AllowedValues: [development, staging, production]
  DBPassword:
    Type: String
    NoEcho: true
  DomainName:
    Type: String
    Default: api.aurora-osi.io
  CertificateArn:
    Type: String
  GEEServiceAccountKey:
    Type: String
    NoEcho: true

Conditions:
  IsProduction: !Equals [!Ref Environment, production]

Resources:
  AuroraVPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: 10.0.0.0/16
      EnableDnsHostnames: true
      EnableDnsSupport: true
      Tags:
        - Key: Name
          Value: aurora-vpc

  PublicSubnet1:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref AuroraVPC
      CidrBlock: 10.0.1.0/24
      AvailabilityZone: !Select [0, !GetAZs '']
      MapPublicIpOnLaunch: true

  PublicSubnet2:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref AuroraVPC
      CidrBlock: 10.0.2.0/24
      AvailabilityZone: !Select [1, !GetAZs '']
      MapPublicIpOnLaunch: true

  PrivateSubnet1:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref AuroraVPC
      CidrBlock: 10.0.10.0/24
      AvailabilityZone: !Select [0, !GetAZs '']

  PrivateSubnet2:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref AuroraVPC
      CidrBlock: 10.0.11.0/24
      AvailabilityZone: !Select [1, !GetAZs '']

  InternetGateway:
    Type: AWS::EC2::InternetGateway

  AttachGateway:
    Type: AWS::EC2::VPCGatewayAttachment
    Properties:
      VpcId: !Ref AuroraVPC
      InternetGatewayId: !Ref InternetGateway

  PublicRouteTable:
    Type: AWS::EC2::RouteTable
    Properties:
      VpcId: !Ref AuroraVPC

  PublicRoute:
    Type: AWS::EC2::Route
    DependsOn: AttachGateway
    Properties:
      RouteTableId: !Ref PublicRouteTable
      DestinationCidrBlock: 0.0.0.0/0
      GatewayId: !Ref InternetGateway

  SubnetRouteTableAssociation1:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      SubnetId: !Ref PublicSubnet1
      RouteTableId: !Ref PublicRouteTable

  SubnetRouteTableAssociation2:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      SubnetId: !Ref PublicSubnet2
      RouteTableId: !Ref PublicRouteTable

  ALBSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: ALB security group
      VpcId: !Ref AuroraVPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIp: 0.0.0.0/0
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0

  ECSSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: ECS task security group
      VpcId: !Ref AuroraVPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 8000
          ToPort: 8000
          SourceSecurityGroupId: !Ref ALBSecurityGroup

  RDSSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: RDS security group
      VpcId: !Ref AuroraVPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 5432
          ToPort: 5432
          SourceSecurityGroupId: !Ref ECSSecurityGroup

  DBSubnetGroup:
    Type: AWS::RDS::DBSubnetGroup
    Properties:
      DBSubnetGroupDescription: RDS subnet group
      SubnetIds:
        - !Ref PrivateSubnet1
        - !Ref PrivateSubnet2

  AuroraDBCluster:
    Type: AWS::RDS::DBCluster
    DeletionPolicy: Snapshot
    Properties:
      Engine: aurora-postgresql
      EngineVersion: '15.2'
      DatabaseName: aurora_db
      MasterUsername: aurora_admin
      MasterUserPassword: !Ref DBPassword
      DBSubnetGroupName: !Ref DBSubnetGroup
      VpcSecurityGroupIds:
        - !Ref RDSSecurityGroup
      BackupRetentionPeriod: 35
      StorageEncrypted: true

  AuroraDBInstance1:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceIdentifier: aurora-db-instance-1
      DBInstanceClass: db.t3.small
      Engine: aurora-postgresql
      DBClusterIdentifier: !Ref AuroraDBCluster
      PubliclyAccessible: false

  GEESecretKey:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: aurora-osi/gee/service-account
      SecretString: !Ref GEEServiceAccountKey

  ECSCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: aurora-cluster
      ClusterSettings:
        - Name: containerInsights
          Value: enabled

  CloudWatchLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: /ecs/aurora-api
      RetentionInDays: 30

  ALB:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      Name: aurora-alb
      Subnets:
        - !Ref PublicSubnet1
        - !Ref PublicSubnet2
      SecurityGroups:
        - !Ref ALBSecurityGroup

  TargetGroup:
    Type: AWS::ElasticLoadBalancingV2::TargetGroup
    Properties:
      Name: aurora-tg
      Port: 8000
      Protocol: HTTP
      VpcId: !Ref AuroraVPC
      TargetType: ip
      HealthCheckPath: /health

  HTTPListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties:
      LoadBalancerArn: !Ref ALB
      Port: 80
      Protocol: HTTP
      DefaultActions:
        - Type: redirect
          RedirectConfig:
            Protocol: HTTPS
            StatusCode: HTTP_301
            Port: '443'

  HTTPSListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties:
      LoadBalancerArn: !Ref ALB
      Port: 443
      Protocol: HTTPS
      Certificates:
        - CertificateArn: !Ref CertificateArn
      DefaultActions:
        - Type: forward
          TargetGroupArn: !Ref TargetGroup

  DataRoomBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub 'aurora-osi-data-room-\${AWS::AccountId}'
      VersioningConfiguration:
        Status: Enabled
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true

Outputs:
  APIEndpoint:
    Value: !Sub 'https://\${DomainName}/api/v1'
  ALBDNSName:
    Value: !GetAtt ALB.DNSName
  DatabaseEndpoint:
    Value: !GetAtt AuroraDBCluster.Endpoint.Address
  DataRoomBucketName:
    Value: !Ref DataRoomBucket`;

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();

    if (user?.role !== 'admin') {
      return Response.json({ error: 'Forbidden: Admin access required' }, { status: 403 });
    }

    const awsAccessKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const awsSecretAccessKey = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    const dbPassword = Deno.env.get('AURORA_DB_PASSWORD');
    const certificateArn = Deno.env.get('AURORA_CERTIFICATE_ARN');
    const geeServiceAccountKey = Deno.env.get('AURORA_GEE_SERVICE_ACCOUNT_KEY');

    if (!awsAccessKeyId || !awsSecretAccessKey) {
      return Response.json({ error: 'AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY required' }, { status: 400 });
    }
    if (!dbPassword || !certificateArn || !geeServiceAccountKey) {
      return Response.json({ error: 'Missing: AURORA_DB_PASSWORD, AURORA_CERTIFICATE_ARN, or AURORA_GEE_SERVICE_ACCOUNT_KEY' }, { status: 400 });
    }
    if (dbPassword.startsWith('arn:aws:secretsmanager')) {
      return Response.json({ error: 'AURORA_DB_PASSWORD contains a Secrets Manager ARN — store the actual password string instead.' }, { status: 400 });
    }

    const requestBody = await req.json();
    const {
      aws_region = 'us-east-1',
      environment = 'production',
      domain_name = 'api.aurora-osi.io',
    } = requestBody;

    const stackName = `aurora-osi-${environment}`;
    const geeKeyBase64 = btoa(geeServiceAccountKey);

    // Build CloudFormation request
    const params = new URLSearchParams();
    params.append('Action', 'CreateStack');
    params.append('Version', '2010-05-15');
    params.append('StackName', stackName);
    params.append('TemplateBody', CF_TEMPLATE);
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

    const host = `cloudformation.${aws_region}.amazonaws.com`;
    const bodyStr = params.toString();

    const signedHeaders = await signV4({
      method: 'POST',
      host,
      path: '/',
      body: bodyStr,
      region: aws_region,
      service: 'cloudformation',
      accessKeyId: awsAccessKeyId,
      secretAccessKey: awsSecretAccessKey,
    });

    const cfResponse = await fetch(`https://${host}/`, {
      method: 'POST',
      headers: signedHeaders,
      body: bodyStr,
    });

    const xmlResponse = await cfResponse.text();

    if (!cfResponse.ok) {
      // Extract friendly error from XML
      const msgMatch = xmlResponse.match(/<Message>([^<]+)<\/Message>/);
      const friendlyError = msgMatch ? msgMatch[1] : xmlResponse.slice(0, 500);
      return Response.json({ error: `CloudFormation: ${friendlyError}` }, { status: cfResponse.status });
    }

    const stackIdMatch = xmlResponse.match(/<StackId>([^<]+)<\/StackId>/);
    const stackId = stackIdMatch ? stackIdMatch[1] : null;

    return Response.json({
      status: 'success',
      message: 'Stack creation initiated!',
      stackId,
      stackName,
      region: aws_region,
      action: 'CREATE_IN_PROGRESS',
      estimatedTime: '15-25 minutes',
      consoleUrl: `https://console.aws.amazon.com/cloudformation/home?region=${aws_region}#/stacks`,
      nextSteps: [
        'Stack creation in progress',
        'Resources: VPC, RDS Aurora, ALB, ECS Cluster, S3 Data Room',
        `Monitor at: https://console.aws.amazon.com/cloudformation/home?region=${aws_region}`,
        'Point DNS to ALB once stack is complete',
      ],
    });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});