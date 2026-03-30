FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" asyncpg psycopg2-binary \
    structlog pydantic-settings alembic sqlalchemy \
    python-jose passlib python-multipart httpx aiofiles \
    bcrypt PyJWT cryptography

COPY aurora_vnext/app /srv/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
