"""
Aurora OSI vNext — Determinism & Floating-Point Stability Utilities
Phase AE §AE.2

Provides:
  1. Stable float rounding (IEEE 754 compliant, consistent across environments)
  2. Deterministic sorting for cell lists and observable dicts
  3. Canonical JSON serialisation (sorted keys, stable float formatting)
  4. Scan input hash — cryptographic fingerprint of all scan inputs
  5. Output hash — cryptographic fingerprint of canonical scan outputs

CONSTITUTIONAL RULES:
  Rule 1: All numeric operations use IEEE 754 double precision throughout.
          No mixed-precision accumulation.
  Rule 2: All sort operations use explicit, deterministic keys.
          No reliance on dict insertion order or set iteration.
  Rule 3: Aggregations are order-independent:
          sum() on sorted list == sum() on any permutation for IEEE 754 doubles
          with consistent accumulation order.
  Rule 4: No random.*, no uuid4() inside scoring or pipeline.
          UUIDs for record IDs use uuid5 (deterministic from namespace + name).
  Rule 5: Float formatting uses repr() for lossless round-trip, not str().
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import uuid
from typing import Any, Optional


# ---------------------------------------------------------------------------
# 1. Stable float handling
# ---------------------------------------------------------------------------

# Aurora OSI standard precision: 8 decimal places for all stored float values.
# This matches the precision used in calibration_math.py (round(..., 8)).
FLOAT_PRECISION = 8


def stable_round(value: float, precision: int = FLOAT_PRECISION) -> float:
    """
    Round a float to Aurora standard precision.
    Uses Python's built-in round() which follows IEEE 754 round-half-to-even.
    This is consistent across CPython versions and platforms.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), precision)


def float_to_bytes(value: float) -> bytes:
    """
    Encode a float to its IEEE 754 double-precision byte representation.
    Used for byte-level equality checks in determinism tests.
    """
    return struct.pack(">d", value)   # big-endian double


def stable_float_eq(a: float, b: float, tolerance: float = 1e-9) -> bool:
    """
    Compare two floats within a tolerance compatible with IEEE 754 double precision.
    tolerance=1e-9 is conservative (doubles have ~15 significant decimal digits).
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= tolerance


# ---------------------------------------------------------------------------
# 2. Deterministic ordering
# ---------------------------------------------------------------------------

def sort_cells_deterministic(cells: list[dict]) -> list[dict]:
    """
    Sort cell records in a stable, deterministic order.
    Primary: lat_center ascending. Secondary: lon_center ascending. Tertiary: cell_id.
    This ensures cell ordering is independent of database query order.
    """
    return sorted(
        cells,
        key=lambda c: (
            stable_round(c.get("lat_center", 0.0)),
            stable_round(c.get("lon_center", 0.0)),
            c.get("cell_id", ""),
        )
    )


def sort_observable_dict(observables: dict) -> dict:
    """
    Return a new dict with keys sorted alphabetically.
    Ensures observable vectors hash identically regardless of insertion order.
    """
    return dict(sorted(observables.items()))


def stable_sum(values: list[float]) -> float:
    """
    Compute a sum with stable accumulation order.
    Sorts values by magnitude (ascending) before summing to minimise
    floating-point cancellation. Consistent across environments.
    """
    if not values:
        return 0.0
    cleaned = [float(v) for v in values if v is not None and not math.isnan(v)]
    return sum(sorted(cleaned, key=abs))


def stable_mean(values: list[float]) -> Optional[float]:
    """Compute mean with stable_sum for consistent floating-point result."""
    cleaned = [float(v) for v in values if v is not None and not math.isnan(v)]
    if not cleaned:
        return None
    return stable_sum(cleaned) / len(cleaned)


# ---------------------------------------------------------------------------
# 3. Canonical JSON serialisation
# ---------------------------------------------------------------------------

class _DeterministicEncoder(json.JSONEncoder):
    """JSON encoder producing deterministic, lossless output."""

    def default(self, obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        return super().default(obj)

    def encode(self, obj):
        # Intercept top-level to enforce sorted dict keys
        return super().encode(obj)


def canonical_json(obj: Any) -> str:
    """
    Produce a deterministic, lossless JSON string.
    - Dict keys sorted alphabetically (all levels)
    - Floats represented with full double precision (17 sig digits via repr)
    - No trailing whitespace
    - Consistent across Python versions ≥ 3.8

    Used for hashing scan inputs and outputs.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        cls=_DeterministicEncoder,
        ensure_ascii=True,
    )


# ---------------------------------------------------------------------------
# 4. Scan input hash
# ---------------------------------------------------------------------------

def compute_scan_input_hash(
    aoi_geometry_hash:   str,
    calibration_version: str,
    version_registry:    dict,
    scan_parameters:     dict,
) -> str:
    """
    Compute a cryptographic fingerprint of all scan inputs.

    Hash input = SHA-256 of canonical JSON of:
      {
        "aoi_geometry_hash":   ...,
        "calibration_version": ...,
        "version_registry":    {...},
        "scan_parameters":     {...},
      }

    PROOF: if any input changes, the hash changes.
    If all inputs are identical, the hash is identical.
    This is the basis of reproducibility: scan_input_hash stored on CanonicalScan
    allows replay_scan() to verify identical conditions.
    """
    payload = {
        "aoi_geometry_hash":   aoi_geometry_hash,
        "calibration_version": calibration_version,
        "version_registry":    version_registry,
        "scan_parameters":     sort_observable_dict(scan_parameters),
    }
    serialised = canonical_json(payload).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


def compute_scan_output_hash(cells: list[dict], scan_metadata: dict) -> str:
    """
    Compute a cryptographic fingerprint of all canonical scan outputs.

    Hash input = SHA-256 of canonical JSON of:
      {
        "cells":         [sorted cells with key fields],
        "scan_metadata": {...},
      }

    Cells are sorted deterministically before hashing.
    Only canonical fields are included (not created_date, updated_date).
    """
    canonical_cells = [
        {
            "cell_id":        c.get("cell_id"),
            "lat_center":     stable_round(c.get("lat_center")),
            "lon_center":     stable_round(c.get("lon_center")),
            "acif_score":     stable_round(c.get("acif_score")),
            "tier":           c.get("tier"),
            "any_veto_fired": c.get("any_veto_fired"),
        }
        for c in sort_cells_deterministic(cells)
    ]
    payload = {
        "cells":         canonical_cells,
        "scan_metadata": sort_observable_dict(scan_metadata),
    }
    serialised = canonical_json(payload).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


# ---------------------------------------------------------------------------
# 5. Deterministic UUID generation (scan and cell IDs)
# ---------------------------------------------------------------------------

# Namespace for Aurora OSI scan IDs — fixed, never changed
_AURORA_SCAN_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def deterministic_scan_id(aoi_geometry_hash: str, calibration_version: str, commodity: str) -> str:
    """
    Generate a deterministic scan ID from its canonical inputs.
    Uses UUID v5 (SHA-1 of namespace + name) — same inputs → same ID.

    PROOF: uuid5 is a pure function of its inputs. No randomness.
    """
    name = f"{aoi_geometry_hash}::{calibration_version}::{commodity}"
    return str(uuid.uuid5(_AURORA_SCAN_NAMESPACE, name))


def deterministic_cell_id(scan_id: str, lat_center: float, lon_center: float) -> str:
    """
    Generate a deterministic cell ID from its scan and spatial coordinates.
    lat/lon rounded to FLOAT_PRECISION before hashing.
    """
    lat_r = stable_round(lat_center)
    lon_r = stable_round(lon_center)
    name = f"{scan_id}::{lat_r:.8f}::{lon_r:.8f}"
    return str(uuid.uuid5(_AURORA_SCAN_NAMESPACE, name))


# ---------------------------------------------------------------------------
# 6. Randomness audit
# ---------------------------------------------------------------------------

def assert_no_randomness_in_module(module_source: str, module_name: str) -> None:
    """
    Assert that a module's source code contains no randomness primitives.
    Called by determinism tests for all frozen modules.

    Checks for:
      import random, from random, random.*, numpy.random, os.urandom,
      uuid.uuid4, secrets.*, torch.manual_seed (model inference not used)
    """
    forbidden_patterns = [
        "import random",
        "from random",
        "random.seed",
        "random.random()",
        "random.choice",
        "numpy.random",
        "np.random",
        "os.urandom",
        "uuid.uuid4",
        "uuid4()",
        "secrets.token",
    ]
    violations = [p for p in forbidden_patterns if p in module_source]
    if violations:
        raise AssertionError(
            f"DETERMINISM VIOLATION in {module_name}: "
            f"found randomness primitives: {violations}"
        )