/**
 * deployToAWS — Deploy Aurora OSI to AWS CloudFormation
 * Provisions ECS Fargate, RDS Aurora, ALB, S3
 */

import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';

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

const CF_TEMPLATE = `AWSTemplateFormatVersion: '2010-09-09'
Description: 'Aurora OSI Production Deployment - ECS Fargate + RDS + S3'
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
      DBInstanceClass: db.t3.medium
      Engine: aurora-postgresql
      DBClusterIdentifier: !Ref AuroraDBCluster
      PubliclyAccessible: false

  AuroraDBInstance2:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceIdentifier: aurora-db-instance-2
      DBInstanceClass: db.t3.medium
      Engine: aurora-postgresql
      DBClusterIdentifier: !Ref AuroraDBCluster
      PubliclyAccessible: false

  ECSCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: !Join
        - '-'
        - - 'aurora-cluster'
          - !Select [1, !Split ['-', !Ref 'AWS::StackName']]
      ClusterSettings:
        - Name: containerInsights
          Value: enabled

  CloudWatchLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: /ecs/aurora-api
      RetentionInDays: 30

  GEESecretsManagerSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: aurora-gee-key
      SecretString: !Ref GEEServiceAccountKey

  ECSTaskExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: ecs-tasks.amazonaws.com
            Action: 'sts:AssumeRole'
      ManagedPolicyArns:
        - 'arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy'
      Policies:
        - PolicyName: SecretsAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: 'secretsmanager:GetSecretValue'
                Resource: 'arn:aws:secretsmanager:*:*:secret:aurora-gee-key*'

  ECSTaskRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: ecs-tasks.amazonaws.com
            Action: 'sts:AssumeRole'
      ManagedPolicyArns:
        - 'arn:aws:iam::aws:policy/AmazonS3FullAccess'
        - 'arn:aws:iam::aws:policy/CloudWatchLogsFullAccess'

  TaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: aurora-api
      NetworkMode: awsvpc
      RequiresCompatibilities:
        - FARGATE
      Cpu: '1024'
      Memory: '2048'
      ExecutionRoleArn: !GetAtt ECSTaskExecutionRole.Arn
      TaskRoleArn: !GetAtt ECSTaskRole.Arn
      ContainerDefinitions:
        - Name: aurora-api
          Image: 368331615566.dkr.ecr.us-east-1.amazonaws.com/aurora-api:latest
          PortMappings:
            - ContainerPort: 8000
              Protocol: tcp
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Ref CloudWatchLogGroup
              awslogs-region: !Ref 'AWS::Region'
              awslogs-stream-prefix: ecs
          Environment:
            - Name: AURORA_DB_HOST
              Value: !GetAtt AuroraDBCluster.Endpoint.Address
            - Name: AURORA_DB_USER
              Value: aurora_admin
            - Name: AURORA_DB_NAME
              Value: aurora_db
            - Name: AURORA_DB_PASSWORD
              Value: !Ref DBPassword
            - Name: AURORA_SECRET_KEY
              Value: aurora-secret-key-prod
            - Name: AURORA_ADMIN_PASS
              Value: aurora-admin-pass
            - Name: AURORA_ENV
              Value: !Ref Environment
          Secrets:
            - Name: AURORA_GEE_SERVICE_ACCOUNT_KEY
              ValueFrom: !Join
                - ''
                - - 'arn:aws:secretsmanager:'
                  - !Ref 'AWS::Region'
                  - ':'
                  - !Ref 'AWS::AccountId'
                  - ':secret:aurora-gee-key'
          HealthCheck:
            Command:
              - CMD-SHELL
              - curl -f http://localhost:8000/health/live || exit 1
            Interval: 30
            Timeout: 10
            Retries: 5
            StartPeriod: 300

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
      HealthCheckPath: /health/live
      HealthCheckProtocol: HTTP
      HealthCheckIntervalSeconds: 30
      HealthCheckTimeoutSeconds: 5

  HTTPListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties:
      LoadBalancerArn: !GetAtt ALB.LoadBalancerArn
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
      LoadBalancerArn: !GetAtt ALB.LoadBalancerArn
      Port: 443
      Protocol: HTTPS
      Certificates:
        - CertificateArn: !Ref CertificateArn
      DefaultActions:
        - Type: forward
          TargetGroupArn: !GetAtt TargetGroup.TargetGroupArn

  ECSService:
    Type: AWS::ECS::Service
    DependsOn:
      - HTTPSListener
      - AuroraDBCluster
    Properties:
      ServiceName: aurora-osi-production
      Cluster: !Ref ECSCluster
      TaskDefinition: !Ref TaskDefinition
      DesiredCount: 1
      LaunchType: FARGATE
      NetworkConfiguration:
        AwsvpcConfiguration:
          Subnets:
            - !Ref PrivateSubnet1
            - !Ref PrivateSubnet2
          SecurityGroups:
            - !Ref ECSSecurityGroup
          AssignPublicIp: DISABLED
      LoadBalancers:
        - ContainerName: aurora-api
          ContainerPort: 8000
          TargetGroupArn: !GetAtt TargetGroup.TargetGroupArn
      DeploymentConfiguration:
        MaximumPercent: 200
        MinimumHealthyPercent: 100
      HealthCheckGracePeriodSeconds: 60

  DataRoomBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub 'aurora-osi-data-room-\${AWS::AccountId}'
      VersioningConfiguration:
        Status: Enabled
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true

Outputs:
  APIEndpoint:
    Value: !Sub 'https://\${DomainName}'
  ALBDNSName:
    Value: !GetAtt ALB.DNSName
  DatabaseEndpoint:
    Value: !GetAtt AuroraDBCluster.Endpoint.Address
  DataRoomBucketName:
    Value: !Ref DataRoomBucket`;

async function cfRequest({ action, params, region, accessKeyId, secretAccessKey }) {
  const host = `cloudformation.${region}.amazonaws.com`;
  const urlParams = new URLSearchParams({ Action: action, Version: '2010-05-15', ...params });
  const bodyStr = urlParams.toString();
  const signedHeaders = await signV4({ method: 'POST', host, path: '/', body: bodyStr, region, service: 'cloudformation', accessKeyId, secretAccessKey });
  const res = await fetch(`https://${host}/`, { method: 'POST', headers: signedHeaders, body: bodyStr });
  const xml = await res.text();
  return { ok: res.ok, xml, status: res.status };
}

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
      return Response.json({ error: 'AWS credentials missing' }, { status: 400 });
    }

    const requestBody = await req.json();
    const {
      action = 'deploy',
      aws_region = 'us-east-1',
      environment = 'production',
      domain_name = 'api.aurora-osi.io',
      deployment_id = Date.now().toString().slice(-6),
    } = requestBody;

    const stackName = `aurora-osi-${environment}`;
    const creds = { region: aws_region, accessKeyId: awsAccessKeyId, secretAccessKey: awsSecretAccessKey };

    // Always use a single stable stack name — let CloudFormation handle DELETE/CREATE
    const cfParams = {
      StackName: stackName,
      TemplateBody: CF_TEMPLATE,
      'Parameters.member.1.ParameterKey': 'Environment',
      'Parameters.member.1.ParameterValue': environment,
      'Parameters.member.2.ParameterKey': 'DBPassword',
      'Parameters.member.2.ParameterValue': dbPassword,
      'Parameters.member.3.ParameterKey': 'DomainName',
      'Parameters.member.3.ParameterValue': domain_name,
      'Parameters.member.4.ParameterKey': 'CertificateArn',
      'Parameters.member.4.ParameterValue': certificateArn,
      'Parameters.member.5.ParameterKey': 'GEEServiceAccountKey',
      'Parameters.member.5.ParameterValue': geeServiceAccountKey,
      'Capabilities.member.1': 'CAPABILITY_NAMED_IAM',
    };

    let cfRes = await cfRequest({ action: 'CreateStack', params: cfParams, ...creds });
    let cfAction = 'CREATE_IN_PROGRESS';

    if (!cfRes.ok && cfRes.xml.includes('AlreadyExistsException')) {
      cfRes = await cfRequest({ action: 'UpdateStack', params: cfParams, ...creds });
      cfAction = 'UPDATE_IN_PROGRESS';
    } else if (!cfRes.ok && cfRes.xml.includes('DELETE_IN_PROGRESS')) {
      return Response.json({
        status: 'pending',
        message: `Stack ${stackName} is still being deleted. Please retry in 2 minutes.`,
        stackName,
        region: aws_region,
        estimatedTime: '2 minutes'
      });
    }

    if (!cfRes.ok) {
      const msgMatch = cfRes.xml.match(/<Message>([^<]+)<\/Message>/);
      return Response.json({ error: `CloudFormation: ${msgMatch ? msgMatch[1] : cfRes.xml.slice(0, 300)}` }, { status: cfRes.status });
    }

    const stackIdMatch = cfRes.xml.match(/<StackId>([^<]+)<\/StackId>/);
    return Response.json({
      status: 'success',
      message: 'Stack deployment initiated',
      stackId: stackIdMatch ? stackIdMatch[1] : null,
      stackName: finalStackName,
      region: aws_region,
      action: cfAction,
      estimatedTime: '15-25 minutes',
      consoleUrl: `https://console.aws.amazon.com/cloudformation/home?region=${aws_region}#/stacks`,
    });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
});