/**
 * fixCodeBuildYAML — Fix buildspec with simple inline commands.
 * ADMIN ONLY.
 */
import { createClientFromRequest } from 'npm:@base44/sdk@0.8.23';
import { CodeBuildClient, UpdateProjectCommand, StartBuildCommand } from 'npm:@aws-sdk/client-codebuild@3';

const REGION = 'us-east-1';
const ACCOUNT_ID = '368331615566';
const PROJECT_NAME = 'aurora-api-build';
const ECR_REPO = 'aurora-api';

Deno.serve(async (req) => {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (user?.role !== 'admin') return Response.json({ error: 'Forbidden' }, { status: 403 });

    const awsKeyId = Deno.env.get('AWS_ACCESS_KEY_ID');
    const awsSecret = Deno.env.get('AWS_SECRET_ACCESS_KEY');
    if (!awsKeyId || !awsSecret) return Response.json({ error: 'AWS credentials not set' }, { status: 500 });

    const buildspec = `version: 0.2
phases:
  pre_build:
    commands:
      - echo "Logging in to ECR..."
      - aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
  build:
    commands:
      - mkdir -p /tmp/build
      - cd /tmp/build
      - cat > Dockerfile << 'EOF'
FROM python:3.11-slim
WORKDIR /srv
RUN pip install fastapi uvicorn bcrypt pyjwt pydantic
COPY app.py /srv/app.py
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
EOF
      - cat > app.py << 'EOF'
import os, time, uuid
import bcrypt, jwt
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

ADMIN_EMAIL = os.getenv("AURORA_ADMIN_USER", "admin@aurora-osi.com")
ADMIN_PASS = os.getenv("AURORA_ADMIN_PASS", "")
JWT_SECRET = os.getenv("AURORA_JWT_SECRET", "dev-key")
_admin_hash = bcrypt.hashpw(ADMIN_PASS.encode(), bcrypt.gensalt(rounds=12)).decode() if ADMIN_PASS else ""

class LoginRequest(BaseModel):
    email: str
    password: str

@app.get("/")
def root():
    return {"status": "alive"}

@app.get("/health")
@app.get("/health/live")
def health():
    return {"status": "alive", "app": "Aurora OSI API"}

@app.post("/api/v1/auth/login")
def login(body: LoginRequest):
    if not body.email or body.email.lower() != ADMIN_EMAIL.lower():
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not _admin_hash:
        raise HTTPException(status_code=503, detail="Auth not configured")
    try:
        ok = bcrypt.checkpw(body.password.encode(), _admin_hash.encode())
    except:
        ok = False
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    jti = str(uuid.uuid4())
    now = int(time.time())
    token = jwt.encode({"sub": "admin", "email": ADMIN_EMAIL, "role": "admin", "jti": jti, "iat": now, "exp": now + 900}, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "refresh_token": str(uuid.uuid4()), "expires_in": 900}

@app.get("/api/v1/auth/me")
def me(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        data = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"user_id": data["sub"], "email": data["email"], "role": data["role"]}

@app.post("/api/v1/auth/logout")
def logout(authorization: str = Header(None)):
    return {"logged_out": True}
EOF
      - docker build -t aurora-api:latest .
      - docker tag aurora-api:latest ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:latest
  post_build:
    commands:
      - docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:latest
`;

    const awsCreds = { region: REGION, credentials: { accessKeyId: awsKeyId, secretAccessKey: awsSecret } };
    const cbClient = new CodeBuildClient(awsCreds);

    console.log('[fixCodeBuildYAML] Updating buildspec...');
    await cbClient.send(new UpdateProjectCommand({
      name: PROJECT_NAME,
      source: { type: 'NO_SOURCE', buildspec },
      environment: {
        type: 'LINUX_CONTAINER',
        image: 'aws/codebuild/standard:7.0',
        computeType: 'BUILD_GENERAL1_MEDIUM',
        privilegedMode: true,
      },
    }));

    console.log('[fixCodeBuildYAML] Starting build...');
    const buildRes = await cbClient.send(new StartBuildCommand({ projectName: PROJECT_NAME }));

    return Response.json({
      status: 'buildspec_fixed',
      build_id: buildRes.build?.id,
      build_status: buildRes.build?.buildStatus,
      message: 'Buildspec YAML fixed with clean heredoc syntax',
      estimated_duration: '5-10 minutes',
    });

  } catch (e) {
    console.error('[fixCodeBuildYAML]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});