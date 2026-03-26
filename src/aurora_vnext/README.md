# Aurora OSI vNext

**Planetary-scale physics-causal sovereign subsurface intelligence platform.**

Clean-room rebuild governed by:
- Aurora Patent Specification
- Aurora Locked Physics & Mathematics Constitution (Phase B)
- Aurora Master Phased Build Prompt

---

## Phase Status

| Phase | Name | Status |
|---|---|---|
| 0 | Program Constitution v1.1 | ✅ APPROVED |
| A | Mineral Library & Commodity Systems | ✅ APPROVED |
| B | Locked Physics & Mathematics Constitution | ✅ APPROVED |
| C | Clean System Architecture Blueprint | ✅ APPROVED |
| D | Rebuild Implementation Master Plan | ✅ APPROVED |
| **E** | **Repository Scaffold & Clean App Bootstrap** | **🔄 IN REVIEW** |
| F | Core Data Models | ⏳ Pending Phase E approval |
| G | Storage Layer | ⏳ |
| ... | ... | ⏳ |

---

## Startup Instructions

### Prerequisites
- Docker and Docker Compose
- Python 3.11+

### Local Development

```bash
# 1. Clone and enter project
cd aurora_vnext

# 2. Copy environment template
cp .env.example .env
# Edit .env — set AURORA_SECRET_KEY to a random 32+ char string

# 3. Start all services
docker compose up --build

# 4. Verify health
curl http://localhost:8000/health

# 5. Verify version registry
curl http://localhost:8000/version
```

### Expected Health Response (Phase E)
```json
{
  "status": "ok",
  "app": "Aurora OSI vNext",
  "env": "development",
  "flags": {
    "storage": false,
    "scientific_core": false,
    "scoring_engine": false,
    "scan_pipeline": false,
    "auth_enforced": false
  }
}
```

All feature flags are `false` at Phase E. This is correct and expected.
Flags are enabled as implementation phases complete and pass exit criteria.

### Expected Version Response (Phase E)
```json
{
  "app": "Aurora OSI vNext",
  "version": "0.1.0",
  "registry": {
    "score_version": "0.1.0",
    "tier_version": "0.1.0",
    "causal_graph_version": "0.1.0",
    "physics_model_version": "0.1.0",
    "temporal_model_version": "0.1.0",
    "province_prior_version": "0.1.0",
    "commodity_library_version": "0.1.0",
    "scan_pipeline_version": "0.1.0"
  }
}
```

### Run Tests (Phase E)
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run Phase E tests
pytest tests/unit/test_health.py tests/unit/test_config.py -v

# Confirm zero scoring logic (constitutional check)
pytest tests/unit/test_health.py::TestNoScoringLogicInScaffold -v
```

---

## Architecture

See Phase C Architecture Blueprint for full documentation.

Six-layer topology:
```
Layer 6: Presentation (render-only web UI)
Layer 5: API (read-only result consumers)
Layer 4: Orchestration (scan pipeline)
Layer 3: Scientific Core (one Phase B equation per module)
Layer 2: Services (external integrations)
Layer 1: Storage & Security (immutable persistence)
```

**Constitutional rules:**
- `core/scoring.py` is the ONLY location for ACIF computation
- `core/tiering.py` is the ONLY location for tier assignment
- `core/gates.py` is the ONLY location for system status derivation
- `storage/scans.py` enforces write-once on COMPLETED canonical scans
- Frontend (Layer 6) has zero scientific logic

---

## No Scoring Logic Guarantee

Phase E contains zero scoring formulas, zero threshold values,
zero commodity definitions, and zero ACIF logic.

Verified by: `pytest tests/unit/test_health.py::TestNoScoringLogicInScaffold -v