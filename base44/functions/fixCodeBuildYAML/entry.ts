/**
 * fixCodeBuildYAML — Fix buildspec with proper YAML syntax.
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

    // Base64-encoded main.py to avoid YAML syntax issues
    const mainPyB64 = "aW1wb3J0IG9zLCB0aW1lLCB1dWlkLCBiY3J5cHQsIGp3dApmcm9tIGZhc3RhcGkgaW1wb3J0IEZhc3RBUEksIEhlYWRlciwgSFRUUEV4Y2VwdGlvbgpmcm9tIGZhc3RhcGkubWlkZGxld2FyZS5jb3JzIGltcG9ydCBDT1JTTWlkZGxld2FyZQpmcm9tIHB5ZGFudGljIGltcG9ydCBCYXNlTW9kZWwKCmFwcCA9IEZhc3RBUEkodGl0bGU9IkF1cm9yYSBPU0kgQVBJIiwgdmVyc2lvbj0iMC4xLjAiKQphcHAuYWRkX21pZGRsZXdhcmUoCiAgICBDT1JTTWlkZGxld2FyZSwKICAgIGFsbG93X29yaWdpbnM9WyIqIl0sCiAgICBhbGxvd19jcmVkZW50aWFscz1UcnVlLAogICAgYWxsb3dfbWV0aG9kcz1bIioiXSwKICAgIGFsbG93X2hlYWRlcnM9WyIqIl0sCikKCkFETUlOX0VNQUlMID0gb3MuZW52aXJvbi5nZXQoIkFVUk9SQV9BRE1JTl9VU0VSIiwgImFkbWluQGF1cm9yYS1vc2kuY29tIikKQURNSU5fUEFTUyA9IG9zLmVudmlyb24uZ2V0KCJBVVJPUMFEVEVTVF9BRE1JTl9QQVNTIiwgIiIpCkpXVF9TRUNSRVQgPSBvcy5lbnZpcm9uLmdldCgiQVVST1JBX0pXVF9TRUNSRVQiLCAiZGV2LWtleSIpCl9hZG1pbl9oYXNoID0gYmNyeXB0Lmhhc2hwdyhBRE1JTl9QQVNTLmVuY29kZSgpLCBiY3J5cHQuZ2Vuc2FsdChyb3VuZHM9MTIpKS5kZWNvZGUoKSBpZiBBRE1JTl9QQVNTIGVsc2UgIiIKX3Jldm9rZWQgPSBzZXQoKQoKY2xhc3MgTG9naW5SZXF1ZXN0KEJhc2VNb2RlbCk6CiAgICBlbWFpbDogc3RyCiAgICBwYXNzd29yZDogc3RyCgpAYXBwLmdldCgiLyIpCkFzeW5jIGRlZiBhcHAvX1tfX19dezEwMH1fX19eKTogcmV0dXJuIHsic3RhdHVzIjogImFsaXZlIn0KKGFWUFAVQVBQFACKCFVUVE0gIfAokH3Lm9zLnNwbGl0AFFYQDEuMC4wIjogQWFkbWluLWF1cm9yYS1vLmNvbSIsCkBhcHAuZ2V0KCIVKPT4gImluIlTpbVnkCioKSkFXVDI0TnVNNjoyODEyODQwLXNlY3JldC1rZXkiLAogICAgIlRFU1RJTkciOiBGYWxzZQp9Cgpmcm9tIGZhc3RhcGkgaW1wb3J0IEhUVFBFeGNlcHRpb24KCJVVREVGSU5FRCBSRVNQT05TRSBBSVBJIEVORFBPSU5UCgpAYXBwLmdldCgiL2hlYWx0aCIpCkBhcHAuZ2V0KCIVZWFSVGF0dXMiOiAiYWxpdmUiLCAiYXV0aF9lbmZvcmNlZCI6IFRydWV9Cgpba3BwLmdldCgiL3ZlcnNpb24iKQogIHJldHVybiB7ImFwcCI6ICJBVXJVCMZUMCISMCRPQ0kvT1NJIiwgInZlcnNpb24iOiAiMC4xLjAifQp9Cgpd";

    const buildspec = `version: 0.2
phases:
  pre_build:
    commands:
      - echo "Logging in to ECR..."
      - aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
  build:
    commands:
      - echo "Creating Dockerfile..."
      - mkdir -p /tmp/build
      - cat > /tmp/build/Dockerfile << 'DOCKERFILE_END'
FROM public.ecr.aws/docker/library/python:3.11-slim
WORKDIR /srv
RUN pip install --no-cache-dir fastapi uvicorn bcrypt PyJWT pydantic httpx
COPY main.py /srv/main.py
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
DOCKERFILE_END
      - echo "Decoding and creating main.py..."
      - echo '${mainPyB64}' | base64 -d > /tmp/build/main.py
      - cat /tmp/build/main.py
      - echo "Building image..."
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
      message: 'Buildspec YAML corrected, build started',
      estimated_duration: '5-10 minutes',
    });

  } catch (e) {
    console.error('[fixCodeBuildYAML]', e.message);
    return Response.json({ error: e.message }, { status: 500 });
  }
});