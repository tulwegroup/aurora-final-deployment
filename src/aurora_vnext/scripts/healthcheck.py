"""
Aurora OSI vNext — Container Healthcheck Script
Phase Q §Q.4 — Deployment Hardening

Used as HEALTHCHECK CMD in Dockerfile:
    HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
        CMD python scripts/healthcheck.py

Returns:
    Exit 0 — healthy
    Exit 1 — unhealthy

Checks:
    1. HTTP liveness probe (GET /health/live)
    2. HTTP readiness probe (GET /health/ready)

CONSTITUTIONAL RULE: This script performs no scientific computation.
It only checks HTTP status codes. No scan data is read or evaluated.
"""

import sys
import urllib.request
import urllib.error
import os
import json

BASE_URL = os.environ.get("AURORA_INTERNAL_URL", "http://localhost:8000/api/v1")


def check(path: str, label: str) -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=5) as resp:
            if resp.status == 200:
                print(f"[OK] {label}")
                return True
            print(f"[FAIL] {label}: HTTP {resp.status}")
            return False
    except urllib.error.URLError as e:
        print(f"[FAIL] {label}: {e}")
        return False


def main():
    ok = all([
        check("/health/live",  "liveness"),
        check("/health/ready", "readiness"),
    ])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()