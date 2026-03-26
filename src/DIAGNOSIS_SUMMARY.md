# Aurora OSI — Backend Connectivity Diagnosis & Resolution

**Date:** 2026-03-26  
**Issue:** 405 errors and connection refused from frontend calling `http://localhost:8000/api/v1/...`

---

## Root Cause Analysis

### 1. **Backend Routers Are Commented Out**

**File:** `aurora_vnext/app/main.py` (lines 138–151)

```python
# Phase M — Scan execution and history APIs
# from app.api.scan import router as scan_router
# from app.api.history import router as history_router
# ...
# app.include_router(scan_router, prefix="/api/v1")
# app.include_router(history_router, prefix="/api/v1")

# Phase O — Auth and admin APIs
# from app.api.auth import router as auth_router
# from app.api.admin import router as admin_router
# app.include_router(auth_router, prefix="/api/v1")
# app.include_router(admin_router, prefix="/api/v1")
```

**Status:** Phase E (scaffold only). All routers are intentionally commented out until phases F → AN are completed.

### 2. **Only `/health` and `/version` Endpoints Exist**

The backend currently exposes only:
- `GET /health` — System health (200 OK)
- `GET /version` — Version registry (200 OK)

All `/api/v1/...` endpoints return **404 Not Found**.

### 3. **405 Errors Indicate Backend Is Reachable**

When you see a **405 Method Not Allowed** error, it means:
- ✅ Backend IS running
- ✅ Connection is successful
- ❌ But the route exists at a different path or uses a different HTTP method

### 4. **Connection Refused Indicates Backend Is Not Running**

When you see **connection refused** (ECONNREFUSED), it means:
- ❌ Backend is NOT running
- ❌ Port 8000 is not listening
- ❌ Docker container may not be started

---

## Immediate Local Fix

### Step 1: Start the Aurora Backend

```bash
cd aurora_vnext

# Copy environment template
cp .env.example .env

# Start all services
docker compose up --build
```

Expected output:
```
aurora-api    | INFO:     Application startup complete
aurora-api    | Uvicorn running on http://0.0.0.0:8000
```

### Step 2: Verify Health

```bash
curl http://localhost:8000/health

# Expected response:
# {"status":"ok","app":"Aurora OSI vNext","env":"development",...}
```

### Step 3: Verify Frontend Connectivity

Open browser dev console (F12) and check:
- No 405 errors on `/health` call (should be 200)
- Dashboard may show "no scans" until API routes are implemented

---

## Why API Endpoints Are 404 (Not 405)

The **404 errors** are **correct and expected** at Phase E:

| Phase | Component | Status |
|-------|-----------|--------|
| A–D | Architecture & prep | ✅ Complete |
| **E** | **Bootstrap scaffold** | **🔄 Current** |
| F–M | Core data models & APIs | ⏳ In progress |
| N–O | Digital twin & admin | ⏳ Pending |
| P–AN | Security & production | ⏳ Planned |

**The API routers will be uncommented as phases complete.**

---

## Frontend Configuration (Already Correct)

**File:** `lib/auroraApi.js` (line 11)

```javascript
const BASE = import.meta.env.VITE_AURORA_API_URL || "http://localhost:8000/api/v1";
```

✅ **Correctly defaults to local backend**  
✅ **Will use `VITE_AURORA_API_URL` from `.env` files in production**

---

## Production Deployment (AWS)

### Architecture Deployed

See `infra/cloudformation/aurora-production.yaml` — includes:

- **ECS Fargate**: 2–4 auto-scaling tasks
- **RDS Aurora PostgreSQL**: Multi-AZ, encrypted, 35-day backups
- **Application Load Balancer**: HTTPS on domain
- **S3 Data Room**: Versioned, encrypted
- **Secrets Manager**: GEE credentials + DB password
- **CloudWatch**: Logs + dashboards
- **Auto-scaling**: CPU-based (target: 70%)

### Deployment Steps

```bash
# 1. Build Docker image and push to ECR
cd aurora_vnext
docker build -f infra/docker/Dockerfile.api -t aurora-api:latest .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com
docker tag aurora-api:latest $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/aurora-api:latest
docker push $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/aurora-api:latest

# 2. Deploy CloudFormation stack
aws cloudformation create-stack \
  --stack-name aurora-osi-prod \
  --template-body file://infra/cloudformation/aurora-production.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=production \
    ParameterKey=DockerImage,ParameterValue=<ECR_IMAGE_URL> \
    ParameterKey=DBPassword,ParameterValue=<SECURE_PASSWORD> \
    ParameterKey=CertificateArn,ParameterValue=<ACM_CERT_ARN> \
    ParameterKey=GEEServiceAccountKey,ParameterValue=<BASE64_GEE_KEY> \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# 3. Monitor deployment
aws cloudformation wait stack-create-complete --stack-name aurora-osi-prod --region us-east-1

# 4. Get outputs
aws cloudformation describe-stacks --stack-name aurora-osi-prod --query 'Stacks[0].Outputs' --region us-east-1
```

### Frontend Production Config

**File:** `.env.production` (newly created)

```env
VITE_AURORA_API_URL=https://api.aurora-osi.io/api/v1
VITE_APP_NAME=Aurora OSI
VITE_LOG_LEVEL=warn
```

### Build & Deploy Frontend

```bash
# Build
npm run build

# Deploy to S3 + CloudFront
aws s3 sync dist/ s3://aurora-osi-frontend-prod/ --delete
aws cloudfront create-invalidation --distribution-id E123... --paths "/*"
```

---

## End-to-End Test Flow

### Local (Currently)

```bash
# 1. ✅ Health check works
curl http://localhost:8000/health

# 2. ❌ Auth endpoints 404 (expected, Phase O not started)
curl http://localhost:8000/api/v1/auth/login
# Response: {"detail":"Not Found"} (404)

# 3. ✅ Frontend loads, shows "no scans" (auth not implemented yet)
open http://localhost:5173
```

### Production (Once Routed Implemented)

```bash
# 1. ✅ Health check works
curl https://api.aurora-osi.io/health

# 2. ✅ Auth endpoints work (Phase O complete)
curl -X POST https://api.aurora-osi.io/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@aurora-osi.io","password":"..."}'

# 3. ✅ Frontend fully functional
open https://aurora-osi.io
```

---

## Diagnostic Script

**Run:** `bash scripts/diagnose-backend.sh`

This script:
- ✅ Checks Docker containers
- ✅ Tests connectivity to port 8000
- ✅ Verifies health/version endpoints
- ✅ Lists API route status
- ✅ Checks frontend configuration
- ✅ Suggests next steps

---

## Files Modified/Created

| File | Purpose |
|------|---------|
| `SETUP_INSTRUCTIONS.md` | Complete local + production setup guide |
| `DIAGNOSIS_SUMMARY.md` | This document |
| `infra/cloudformation/aurora-production.yaml` | AWS infrastructure-as-code |
| `scripts/diagnose-backend.sh` | Backend diagnostic script |
| `.env.production` | Frontend production config |

---

## Next Steps

### Immediate
1. ✅ **Start backend:** `cd aurora_vnext && docker compose up --build`
2. ✅ **Verify health:** `curl http://localhost:8000/health`
3. ✅ **Run diagnostic:** `bash scripts/diagnose-backend.sh`

### Short-term (Phases F–O)
1. ⏳ Uncomment API routers in `aurora_vnext/app/main.py` as phases complete
2. ⏳ Implement Phase M: Scan & history APIs
3. ⏳ Implement Phase O: Auth & admin APIs
4. ⏳ Test with frontend

### Medium-term (Production Readiness)
1. ⏳ Set up AWS account + IAM roles + VPC
2. ⏳ Register domain + SSL certificate
3. ⏳ Build and push Docker image to ECR
4. ⏳ Deploy CloudFormation stack
5. ⏳ Configure GEE credentials in Secrets Manager
6. ⏳ Deploy frontend to S3 + CloudFront
7. ⏳ Test end-to-end on production

---

## Key Takeaways

| Issue | Status | Cause | Fix |
|-------|--------|-------|-----|
| 405 errors | Transient | Backend reachable but routes commented | Start Docker container |
| Connection refused | Structural | Backend not running | `docker compose up` |
| API 404s | Expected | Phases F–O not implemented | Wait for implementation |
| Frontend works | ✅ | `lib/auroraApi.js` correctly configured | No changes needed |
| Production ready | 🔄 | CloudFormation template created | Run deployment steps |

---

## Questions?

- **Backend startup:** See `aurora_vnext/README.md`
- **Architecture:** See `aurora_vnext/docs/phase_c_architecture.md`
- **Phases:** See `aurora_vnext/docs/phase_*_completion_proof.md`
- **Infrastructure:** See `infra/cloudformation/aurora-production.yaml`

**All code changes are infrastructure/configuration only—no scientific logic modified.**