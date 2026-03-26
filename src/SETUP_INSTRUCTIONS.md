# Aurora OSI — Local Setup & Production Deployment Guide

## Phase Status
Your backend is at **Phase E (scaffold only)** — all API routers are commented out. This is why you see 405 errors.

---

## LOCAL SETUP (Development)

### 1. Start Aurora Backend

```bash
cd aurora_vnext
cp .env.example .env
# Edit .env if needed (set AURORA_SECRET_KEY to a random 32+ char string)
docker compose up --build
```

Wait for:
```
aurora-api    | INFO:     Application startup complete
```

### 2. Verify Backend Health

```bash
# Should return 200 with status: "ok"
curl http://localhost:8000/health

# Should return version registry
curl http://localhost:8000/version
```

### 3. Check Frontend Configuration

Your frontend is correctly configured:
- `lib/auroraApi.js` line 11: `BASE = "http://localhost:8000/api/v1"` (via `VITE_AURORA_API_URL` env var or default)

### 4. Current Limitation

**All API routes are commented out in `aurora_vnext/app/main.py` (lines 138–151).**

The following endpoints do NOT exist yet:
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/scan/active`
- All `/history`, `/datasets`, `/twin`, `/admin` routes

**Status:** These will be implemented in phases F → AN. 

**For now:** Only `/health` and `/version` are available.

---

## PRODUCTION DEPLOYMENT (AWS)

### Architecture (Recommended)

```
┌─────────────────────────────────────────────────────────┐
│                   Aurora OSI Production                 │
├─────────────────────────────────────────────────────────┤
│  Domain: api.aurora-osi.io (Route53 + ACM SSL)         │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │   Application Load Balancer (ALB)               │   │
│  │   - HTTPS (port 443)                            │   │
│  │   - HTTP → HTTPS redirect                       │   │
│  └─────────────────────────────────────────────────┘   │
│                        ↓                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │  ECS Fargate Cluster                            │   │
│  │  - Task: aurora-api                             │   │
│  │  - CPU: 2048 (2 vCPU), Memory: 4096 (4GB)      │   │
│  │  - Desired count: 2 (auto-scaling 2-4)          │   │
│  │  - Health check: /health                        │   │
│  └─────────────────────────────────────────────────┘   │
│                        ↓                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │  RDS Aurora PostgreSQL                          │   │
│  │  - Multi-AZ (HA)                                │   │
│  │  - db.t3.small (development) → db.r6g (prod)   │   │
│  │  - Automated backups (35 days)                  │   │
│  └─────────────────────────────────────────────────┘   │
│                        ↓                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │  S3 + CloudFront (Data Room)                    │   │
│  │  - Versioning enabled                           │   │
│  │  - Encryption (KMS)                             │   │
│  │  - Lifecycle: Archive after 90 days             │   │
│  └─────────────────────────────────────────────────┘   │
│                        ↓                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │  CloudWatch + CloudTrail                        │   │
│  │  - Aurora logs → CloudWatch Logs                │   │
│  │  - Audit trail immutable (S3 MFA delete)        │   │
│  │  - PagerDuty integration                        │   │
│  └─────────────────────────────────────────────────┘   │
│                        ↓                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Secrets Manager                                │   │
│  │  - GEE credentials (encrypted)                  │   │
│  │  - Aurora database password                     │   │
│  │  - JWT signing keys                             │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Prerequisites

- AWS CLI v2 configured with credentials
- Docker (for building ECR image)
- `aws` CLI configured: `aws configure`

### Deployment Steps

#### Step 1: Build & Push Docker Image to ECR

```bash
# Create ECR repository
aws ecr create-repository --repository-name aurora-api --region us-east-1

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com

# Build Aurora backend image
cd aurora_vnext
docker build -f infra/docker/Dockerfile.api -t aurora-api:latest .

# Tag and push
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
docker tag aurora-api:latest $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/aurora-api:latest
docker push $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/aurora-api:latest
```

#### Step 2: Create RDS Aurora Database

```bash
aws rds create-db-cluster \
  --db-cluster-identifier aurora-osi-cluster \
  --engine aurora-postgresql \
  --engine-version 15.2 \
  --master-username aurora_admin \
  --master-user-password $(openssl rand -base64 32) \
  --database-name aurora_db \
  --db-subnet-group-name aurora-subnet-group \
  --vpc-security-group-ids sg-xxx \
  --backup-retention-period 35 \
  --multi-az \
  --storage-encrypted \
  --kms-key-id arn:aws:kms:us-east-1:XXX:key/XXX \
  --region us-east-1

# Store password in Secrets Manager
aws secretsmanager create-secret \
  --name aurora-osi/db/password \
  --secret-string $(openssl rand -base64 32) \
  --region us-east-1
```

#### Step 3: Deploy via CloudFormation (IaC)

See: `infra/cloudformation/aurora-production.yaml` (attached)

```bash
aws cloudformation create-stack \
  --stack-name aurora-osi-prod \
  --template-body file://infra/cloudformation/aurora-production.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=production \
    ParameterKey=DockerImage,ParameterValue=$ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/aurora-api:latest \
    ParameterKey=DBPassword,ParameterValue=$(aws secretsmanager get-secret-value --secret-id aurora-osi/db/password --query SecretString --output text) \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Monitor stack creation
aws cloudformation wait stack-create-complete --stack-name aurora-osi-prod --region us-east-1
```

---

## FRONTEND PRODUCTION CONFIG

### 1. Environment Variables

**Create `.env.production` in frontend root:**

```env
VITE_AURORA_API_URL=https://api.aurora-osi.io/api/v1
VITE_APP_NAME=Aurora OSI
VITE_LOG_LEVEL=warn
```

### 2. Build & Deploy

```bash
# Build
npm run build

# Deploy to CloudFront + S3
aws s3 sync dist/ s3://aurora-osi-frontend-prod/ --delete --cache-control "max-age=31536000"
aws cloudfront create-invalidation --distribution-id E123ABCD456 --paths "/*"
```

---

## CORS Configuration (Production)

**Backend (`aurora_vnext/app/main.py` line 50–56):**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aurora-osi.io",
        "https://www.aurora-osi.io",
        # NO localhost in production
    ] if settings.is_production else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,
)
```

---

## GEE Credentials (Secure Handling)

### Development (Local)

```bash
# .env in aurora_vnext/
GEE_SERVICE_ACCOUNT_KEY_JSON=$(cat ~/path/to/gee-key.json | base64 -w0)
```

### Production (AWS Secrets Manager)

```bash
# Store GEE key in Secrets Manager
aws secretsmanager create-secret \
  --name aurora-osi/gee/service-account \
  --secret-string file://gee-key.json \
  --region us-east-1

# ECS task will fetch at runtime:
# export GEE_SERVICE_ACCOUNT_KEY_JSON=$(aws secretsmanager get-secret-value --secret-id aurora-osi/gee/service-account --query SecretString --output text)
```

---

## Monitoring & Alerting

### CloudWatch

```bash
# Create dashboard
aws cloudwatch put-dashboard \
  --dashboard-name Aurora-OSI \
  --dashboard-body file://infra/cloudwatch/dashboard.json
```

### PagerDuty Integration

```bash
# Create SNS topic
aws sns create-topic --name aurora-osi-alerts --region us-east-1

# Subscribe PagerDuty
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:XXX:aurora-osi-alerts \
  --protocol https \
  --notification-endpoint https://events.pagerduty.com/integration/XXX/enqueue
```

---

## End-to-End Test (Once Routes are Implemented)

```bash
# 1. Backend health (always works)
curl https://api.aurora-osi.io/health

# 2. Auth test (Phase O)
curl -X POST https://api.aurora-osi.io/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@aurora-osi.io","password":"XXX"}'

# 3. Submit scan (Phase M)
curl -X POST https://api.aurora-osi.io/api/v1/scan/polygon \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{...}'

# 4. Retrieve results (Phase N/O)
curl https://api.aurora-osi.io/api/v1/history \
  -H "Authorization: Bearer $TOKEN"
```

---

## Summary

| Aspect | Local | Production |
|--------|-------|-----------|
| Backend | `docker compose up` in `aurora_vnext/` | ECS Fargate on ALB |
| Database | `postgres:15` container | RDS Aurora PostgreSQL (multi-AZ) |
| Frontend API URL | `http://localhost:8000/api/v1` | `https://api.aurora-osi.io/api/v1` |
| HTTPS | No (localhost) | Yes (ACM certificate) |
| Secrets | `.env` file | AWS Secrets Manager |
| Logging | Docker logs | CloudWatch Logs + CloudTrail |
| Backups | None | Automated (35 days) |
| Scaling | Fixed | Auto-scaling ECS (2–4 tasks) |

---

## Next Steps

1. ✅ **Complete Phase E–F:** Uncomment API routers as phases complete
2. ✅ **Test locally:** `curl http://localhost:8000/health`
3. ✅ **Prepare AWS:** Set up IAM roles, VPC, subnets
4. ✅ **Deploy CloudFormation:** Create production stack
5. ✅ **Test production:** Verify HTTPS + API connectivity
6. ✅ **Enable monitoring:** CloudWatch dashboards + PagerDuty alerts

---

**Questions?** See `aurora_vnext/README.md` and phase completion proofs in `aurora_vnext/docs/`.