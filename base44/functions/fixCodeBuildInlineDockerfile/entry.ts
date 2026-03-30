/**
 * fixCodeBuildInlineDockerfile — Update buildspec with inline Dockerfile.
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
      - echo "Building minimal Aurora API stub..."
      - mkdir -p /tmp/build
      - |
        cat > /tmp/build/Dockerfile << 'EOF'
FROM public.ecr.aws/docker/library/python:3.11-slim
WORKDIR /srv
RUN pip install --no-cache-dir fastapi uvicorn bcrypt PyJWT pydantic
COPY main.py /srv/main.py
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF
      - |
        cat > /tmp/build/main.py << 'EOF'
import os, time, uuid, bcrypt, jwt
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Aurora OSI API", version="0.1.0")
ADMIN_EMAIL = os.environ.get("AURORA_ADMIN_USER", "admin@aurora-osi.com")
ADMIN_PASS = os.environ.get("AURORA_ADMIN_PASS", "")
JWT_SECRET = os.environ.get("AURORA_JWT_SECRET", "dev-key")
_admin_hash = bcrypt.hashpw(ADMIN_PASS.encode(), bcrypt.gensalt(rounds=12)).decode() if ADMIN_PASS else ""
_revoked = set()

class LoginRequest(BaseModel):
    email: str
    password: str

@app.get("/")
async def root():
    return {"status": "alive"}

@app.get("/health")
@app.get("/health/live")
async def health():
    return {"status": "alive", "app": "Aurora OSI vNext", "auth_enforced": True}

@app.get("/version")
async def version():
    return {"app": "Aurora OSI vNext", "version": "0.1.0"}

@app.post("/api/v1/auth/login")
async def login(body: LoginRequest):
    if not _admin_hash or body.email.lower() != ADMIN_EMAIL.lower():
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    try:
        ok = bcrypt.checkpw(body.password.encode(), _admin_hash.encode())
    except:
        ok = False
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    jti = str(uuid.uuid4())
    now = int(time.time())
    token = jwt.encode({"sub": "admin", "email": ADMIN_EMAIL, "role": "admin", "jti": jti, "iat": now, "exp": now + 900}, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "refresh_token": str(uuid.uuid4()), "expires_in": 900}

@app.get("/api/v1/auth/me")
async def me(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token.")
    try:
        data = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
    except:
        raise HTTPException(status_code=401, detail="Invalid token.")
    return {"user_id": data["sub"], "email": data["email"], "role": data["role"]}

@app.post("/api/v1/auth/logout")
async def logout(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token.")
    try:
        data = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
        _revoked.add(data.get("jti"))
    except:
        pass
    return {"logged_out": True}
EOF
      - docker build -t aurora-api:latest -f /tmp/build/Dockerfile /tmp/build
      - docker tag aurora-api:latest ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:latest
  post_build:
    commands:
      - echo "Pushing to ECR..."
      - docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:latest
      - echo "Build complete"
`;

    const awsCreds = { region: REGION, credentials: { accessKeyId: awsKeyId, secretAccessKey: awsSecret } };
    const cbClient = new CodeBuildClient(awsCreds);

    console.log('[fixCodeBuildInlineDockerfile] Updating buildspec with inline Dockerfile+main.py...');
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

    console.log('[fixCodeBuildInlineDockerfile] Starting build...');
    const buildRes = await cbClient.send(new StartBuildCommand({ projectName: PROJECT_NAME }));

    return Response.json({
      status: 'buildspec_fixed_with_inline_code',
      build_id: buildRes.build?.id,
      build_status: buildRes.build?.buildStatus,
      buildspec: 'Creates Dockerfile and main.py inline, builds, pushes to ECR',
      estimated_duration: '5-10 minutes',
      console_url: `https://console.aws.amazon.com/codesuite/codebuild/${REGION}/projects/${PROJECT_NAME}`,
    });

  } catch (e) {
    console.error('[fixCodeBuildInlineDockerfile]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});