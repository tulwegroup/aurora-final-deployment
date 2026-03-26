# Phase N Completion Proof
## Aurora OSI vNext — Digital Twin Core

---

## 1. Twin Builder Module Inventory

| Module | File | Purpose |
|---|---|---|
| `twin_builder.py` | `services/twin_builder.py` | Main builder: depth kernel, projection, voxel write |
| `digital_twin_model.py` | `models/digital_twin_model.py` | DigitalTwinVoxel, DepthKernelConfig, VoxelLineage, TwinBuildManifest |
| `storage/twin.py` | `storage/twin.py` | Voxel persistence, version history, metadata (Phase G) |
| `api/twin.py` | `api/twin.py` | Read-only query endpoints (Phase M) |

### Builder Functions

| Function | Signature | Role |
|---|---|---|
| `compute_kernel_weight` | `(depth_m, z_expected_m, sigma_z_m) → float` | §15.2 Gaussian D^(c)(z) |
| `project_commodity_probability` | `(acif_score, kernel_weight, commodity) → dict` | p(z) = ACIF × D^(c)(z) |
| `compute_expected_density` | `(depth_m, bg_density, gradient) → float` | ρ(z) = ρ_bg + dρ/dz × z |
| `compute_density_uncertainty` | `(cell_uncertainty, sigma_z, depth) → float` | Propagated uncertainty |
| `depth_range_for_slice` | `(slices, idx) → tuple` | Depth bin bounds |
| `project_cell_to_voxels` | `(cell, commodity, kernel, version, built_at) → (voxels, lineages)` | Cell → voxel column |
| `get_depth_kernel_for_commodity` | `(commodity, family, overrides) → DepthKernelConfig` | Θ_c kernel lookup |
| `build_twin` | `async (scan_id, canonical_store, twin_store, ...) → TwinBuildManifest` | Main entry point |

---

## 2. Voxel Schema Proof

### DigitalTwinVoxel fields

| Field | Type | Source | Re-scored? |
|---|---|---|---|
| `voxel_id` | `str` | Generated (`scan_id_cell_id_vN_dZ`) | — |
| `scan_id` | `str` | `CanonicalScan.scan_id` | No |
| `twin_version` | `int` | Monotonic counter | — |
| `lat_center`, `lon_center` | `float` | `ScanCell.lat_center/.lon_center` | No |
| `depth_m` | `float` | `DepthKernelConfig.depth_slices_m[i]` | — |
| `depth_range_m` | `tuple[float, float]` | Midpoints between adjacent slices | — |
| `commodity_probs` | `dict[str, float]` | `ScanCell.acif_score × D^(c)(z)` | **No** — ACIF read from frozen cell |
| `expected_density` | `float` | `ρ_bg + dρ/dz × z` (from Θ_c) | No |
| `density_uncertainty` | `float` | `U_i × σ_z / z × 1000` (propagated) | **No** — U_i from frozen cell |
| `temporal_score` | `float` | `ScanCell.temporal_score` verbatim | **No — propagated** |
| `physics_residual` | `float` | `ScanCell.physics_residual` verbatim | **No — propagated** |
| `uncertainty` | `float` | `ScanCell.uncertainty` verbatim | **No — propagated** |
| `kernel_weight` | `float` | `D^(c)(z)` value stored for traceability | — |
| `source_cell_id` | `str` | `ScanCell.cell_id` | — |

**Result:** Every voxel field is either a pure mathematical projection of frozen ScanCell data
or a depth-space coordinate. No field requires calling any `core/*` function.

### VoxelLineage fields

Per-voxel audit record linking every field value to its canonical source:

- `scan_id`, `cell_id` → canonical source identity
- `twin_version` → which build produced this voxel
- `scan_pipeline_version`, `score_version`, `physics_model_version` → from `CanonicalScan.version_registry`
- `source_acif_score`, `source_uncertainty`, `source_temporal_score`, `source_physics_residual` → verbatim values read from the frozen ScanCell record
- `z_expected_m`, `sigma_z_m` → Θ_c depth kernel parameters used
- `depth_slice_m`, `kernel_weight` → the specific depth and kernel value at this voxel

### TwinBuildManifest

Scan-level audit artifact recording:
- Which CanonicalScan was read (`scan_id`, `canonical_completed_at`)
- How many cells were projected and voxels produced
- Full `version_registry` snapshot (`score_version`, `physics_model_version`, `scan_pipeline_version`, `tier_version`)
- Depth kernel configuration used
- `built_at` timestamp

---

## 3. Example Scan-to-Voxel Projection Trace

### Input — Frozen ScanCell (read-only)

```python
cell = {
    "cell_id":        "scan_n_001_c00003",
    "scan_id":        "scan_n_001",
    "lat_center":     -29.5,
    "lon_center":     121.5,
    "acif_score":     0.75,          # read from frozen record — NOT recomputed
    "uncertainty":    0.22,          # read from frozen record — NOT recomputed
    "temporal_score": 0.80,          # read from frozen record — NOT recomputed
    "physics_residual": 0.03,        # read from frozen record — NOT recomputed
    "tier":           "TIER_1",      # NOT used in twin builder
}
```

### Depth Kernel (from Θ_c — orogenic_gold family)

```python
kernel = DepthKernelConfig(
    commodity="gold",
    z_expected_m=200.0,           # from Θ_c (orogenic gold target depth)
    sigma_z_m=80.0,               # from Θ_c (depth uncertainty)
    depth_slices_m=[100.0, 200.0, 300.0, 500.0, 750.0],
    background_density_kg_m3=2670.0,
    density_gradient_kg_m3_per_m=0.3,
)
```

### Projection Trace — Depth Slice at z = 200 m (expected depth)

```
Step 1: D^(c)(200) = exp(−(200−200)² / (2×80²)) = exp(0) = 1.000

Step 2: p_gold(200) = ACIF × D^(c)(200) = 0.75 × 1.000 = 0.750

Step 3: ρ(200)     = 2670 + 0.3 × 200 = 2730.0 kg/m³

Step 4: unc_density = 0.22 × (80/200) × 1000 = 88.0 kg/m³

Step 5: Propagation (verbatim from ScanCell):
         temporal_score   = 0.80  (not recomputed)
         physics_residual = 0.03  (not recomputed)
         uncertainty      = 0.22  (not recomputed)
```

### Output — DigitalTwinVoxel at z = 200 m

```python
DigitalTwinVoxel(
    voxel_id          = "scan_n_001_scan_n_001_c00003_v1_d200",
    scan_id           = "scan_n_001",
    twin_version      = 1,
    lat_center        = -29.5,
    lon_center        = 121.5,
    depth_m           = 200.0,
    depth_range_m     = (150.0, 250.0),
    commodity_probs   = {"gold": 0.750},   # ACIF × D^(c)(z) — no re-scoring
    expected_density  = 2730.0,            # kg/m³ — crustal model from Θ_c
    density_uncertainty = 88.0,            # kg/m³ — propagated from U_i
    temporal_score    = 0.80,              # VERBATIM from ScanCell
    physics_residual  = 0.03,             # VERBATIM from ScanCell
    uncertainty       = 0.22,             # VERBATIM from ScanCell
    kernel_weight     = 1.000,            # D^(c)(200) — stored for audit
    source_cell_id    = "scan_n_001_c00003",
)
```

### Projection at z = 500 m (below expected depth)

```
D^(c)(500) = exp(−(500−200)² / (2×80²)) = exp(−5.625) ≈ 0.00360

p_gold(500) = 0.75 × 0.00360 = 0.00270   # correctly near zero at 2.5σ below

ρ(500)     = 2670 + 0.3 × 500 = 2820.0 kg/m³
```

The depth kernel correctly suppresses probability at depths far from the expected target,
without any scoring computation — purely from the Gaussian formula and the frozen ACIF.

---

## 4. Version-History Query Example

Twin records are append-only. Each build call increments the version counter.

### Example version history for one scan

```python
# Build 1 — initial twin (trigger = "initial")
manifest_v1 = await build_twin(
    scan_id="scan_001",
    canonical_store=...,
    twin_store=...,
    family="orogenic_gold",
    trigger_type="initial",
)
# → manifest_v1.twin_version = 1, voxels_produced = 4 cells × 5 slices = 20

# Build 2 — after reprocess with new δh (trigger = "reprocess")
manifest_v2 = await build_twin(
    scan_id="scan_001",
    canonical_store=...,      # reads NEW canonical scan (child of original)
    twin_store=...,
    family="orogenic_gold",
    trigger_type="reprocess",
    parent_version=1,
)
# → manifest_v2.twin_version = 2, parent_version = 1

# Query version 1 (historical)
query_v1 = TwinQuery(scan_id="scan_001", version=1, limit=500)
result = await twin_store.query_voxels(query_v1)
# → returns voxels from v1 only; v2 voxels are unaffected

# Query latest (no version specified)
query_latest = TwinQuery(scan_id="scan_001", limit=500)
result = await twin_store.query_voxels(query_latest)
# → returns voxels from v2 (latest)
```

Version history query:
```python
versions = await twin_store.get_twin_history("scan_001")
# → [
#     TwinVersion(version=1, voxel_count=20, trigger="initial", parent_version=None),
#     TwinVersion(version=2, voxel_count=20, trigger="reprocess", parent_version=1),
#   ]
```

---

## 5. Proof That Twin Generation Does Not Mutate CanonicalScan

### Structural proof — CanonicalReadAdapter protocol

The `CanonicalReadAdapter` protocol (injected into `build_twin()`) defines exactly two methods:

```python
class CanonicalReadAdapter(Protocol):
    async def get_canonical_scan(self, scan_id: str) -> dict: ...
    async def list_scan_cells(self, scan_id: str) -> list[dict]: ...
```

There is no `freeze_canonical_scan()`, `create_pending_scan()`, `write_cells()`,
`soft_delete_scan()`, or any other write method in this protocol.

**Therefore:** `build_twin()` cannot mutate canonical records — the adapter provides
no write path. This is enforced at the type level, not just convention.

### Code-level proof — what `build_twin()` calls on canonical_store

```python
# Step 1 — read only
canonical = await canonical_store.get_canonical_scan(scan_id)

# Step 2 — read only
cells = await canonical_store.list_scan_cells(scan_id)
```

No other calls to `canonical_store` exist in `build_twin()`. Two reads; zero writes.

### Storage-level proof

`build_twin()` writes exclusively to:
```python
await twin_store.write_voxels(...)
await twin_store.write_twin_manifest(...)
```

These write to the `digital_twin_voxels` and `digital_twin_versions` tables.
The `canonical_scans` and `scan_cells` tables are never touched after freeze.

---

## 6. Proof That Twin Modules Do Not Import Scoring/Tiering/Gates Authority

### `services/twin_builder.py` imports

```python
# Standard library
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol

# Internal — models and protocols only
from app.models.digital_twin_model import (
    DepthKernelConfig, DigitalTwinVoxel, TwinBuildManifest, VoxelLineage,
)
```

**Absent:** `core.scoring`, `core.tiering`, `core.gates`, `core.evidence`,
`core.causal`, `core.physics`, `core.temporal`, `core.priors`, `core.uncertainty`.

No call to: `compute_acif()`, `assign_tier()`, `evaluate_gates()`, `score_evidence()`,
`score_causal()`, `score_physics()`, `score_temporal()`, `score_province_prior()`,
`score_uncertainty()`.

### `models/digital_twin_model.py` imports

```python
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.models.observable_vector import NormalisedFloat
```

**Absent:** all `core.*`, `services.*`, `storage.*`, `api.*`.

### Verification

These invariants are verified programmatically in:
`tests/unit/test_twin_phase_n.py :: TestTwinImportIsolation`

All 5 parametrized test cases pass on source inspection. The depth kernel formula
`compute_kernel_weight()` uses only `math.exp` — no imports, no side effects,
no database access.