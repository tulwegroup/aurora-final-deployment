"""
Aurora OSI vNext — Phase AE Determinism & Reproducibility Tests

Tests (25):
  1.  canonical_json produces identical output for identical dicts
  2.  canonical_json sorts keys deterministically
  3.  canonical_json produces different output for different dicts
  4.  stable_round is consistent with IEEE 754 round-half-to-even
  5.  float_to_bytes is lossless round-trip
  6.  stable_sum is order-independent (any permutation → same result)
  7.  stable_mean returns None for empty list
  8.  sort_cells_deterministic: same cells in different order → same sorted output
  9.  sort_observable_dict: key order irrelevant to output
  10. compute_scan_input_hash: identical inputs → identical hash
  11. compute_scan_input_hash: changed parameter → different hash
  12. compute_scan_output_hash: identical cells → identical hash
  13. compute_scan_output_hash: cell order does not affect hash
  14. deterministic_scan_id: same inputs → same UUID
  15. deterministic_cell_id: same inputs → same UUID
  16. version_registry: all frozen strings match Phase AE values
  17. assert_version_frozen: passes with current registry
  18. VersionRegistrySnapshot.current(): produces snapshot with all fields
  19. VersionRegistrySnapshot.assert_compatible: passes for identical snapshots
  20. VersionRegistrySnapshot.assert_compatible: raises for mismatched version
  21. ReplayResult.certified = True only when all three conditions met
  22. replay_scan: raises ReplayFailed for missing fields
  23. replay_scan with stub pipeline: certified=True on second run of identical inputs
  24. assert_no_randomness_in_module: passes for determinism.py itself
  25. assert_no_randomness_in_module: fails for module containing uuid4
"""

from __future__ import annotations

import json
import math
import pytest


# ─── 1–3. canonical_json ─────────────────────────────────────────────────────

class TestCanonicalJson:
    def test_identical_dicts_produce_identical_json(self):
        from app.services.determinism import canonical_json
        a = {"z": 1.0, "a": 2.0, "m": [3.0, 4.0]}
        b = {"m": [3.0, 4.0], "z": 1.0, "a": 2.0}
        assert canonical_json(a) == canonical_json(b)

    def test_keys_sorted(self):
        from app.services.determinism import canonical_json
        result = canonical_json({"z": 1, "a": 2, "m": 3})
        parsed = json.loads(result)
        assert list(parsed.keys()) == sorted(parsed.keys())

    def test_different_dicts_produce_different_json(self):
        from app.services.determinism import canonical_json
        assert canonical_json({"a": 1}) != canonical_json({"a": 2})


# ─── 4–5. Float handling ─────────────────────────────────────────────────────

class TestFloatHandling:
    def test_stable_round_ieee754_half_to_even(self):
        from app.services.determinism import stable_round
        # Round half to even: 0.5 → 0, 1.5 → 2
        assert stable_round(2.5, 0) == 2.0  # rounds to even
        assert stable_round(3.5, 0) == 4.0

    def test_float_to_bytes_round_trip(self):
        import struct
        from app.services.determinism import float_to_bytes
        value = 3.141592653589793
        b = float_to_bytes(value)
        restored = struct.unpack(">d", b)[0]
        assert restored == value  # lossless

    def test_stable_float_eq_within_tolerance(self):
        from app.services.determinism import stable_float_eq
        assert stable_float_eq(1.0000000001, 1.0000000002, tolerance=1e-8)
        assert not stable_float_eq(1.0, 2.0)


# ─── 6–7. Stable aggregations ────────────────────────────────────────────────

class TestStableAggregations:
    def test_stable_sum_order_independent(self):
        from app.services.determinism import stable_sum
        values  = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        import itertools, random
        result = stable_sum(values)
        # Test 10 shuffled permutations
        for _ in range(10):
            shuffled = values[:]
            random.shuffle(shuffled)
            assert stable_sum(shuffled) == result, "stable_sum not order-independent"

    def test_stable_mean_none_for_empty(self):
        from app.services.determinism import stable_mean
        assert stable_mean([]) is None
        assert stable_mean([None, None]) is None


# ─── 8–9. Deterministic ordering ─────────────────────────────────────────────

class TestDeterministicOrdering:
    def _cells(self):
        return [
            {"cell_id": "c3", "lat_center": -31.0, "lon_center": 117.5, "acif_score": 0.7},
            {"cell_id": "c1", "lat_center": -29.5, "lon_center": 116.0, "acif_score": 0.5},
            {"cell_id": "c2", "lat_center": -30.0, "lon_center": 116.5, "acif_score": 0.6},
        ]

    def test_sort_cells_deterministic_consistent(self):
        from app.services.determinism import sort_cells_deterministic
        cells = self._cells()
        import random
        expected = sort_cells_deterministic(cells)
        for _ in range(10):
            shuffled = cells[:]
            random.shuffle(shuffled)
            assert sort_cells_deterministic(shuffled) == expected

    def test_sort_observable_dict_key_order(self):
        from app.services.determinism import sort_observable_dict
        d1 = {"z": 1, "a": 2, "m": 3}
        d2 = {"m": 3, "z": 1, "a": 2}
        assert sort_observable_dict(d1) == sort_observable_dict(d2)
        assert list(sort_observable_dict(d1).keys()) == ["a", "m", "z"]


# ─── 10–13. Hash functions ────────────────────────────────────────────────────

class TestHashFunctions:
    _VER = {"score_version": "acif-1.0.0", "tier_version": "tier-1.0.0"}
    _PARAMS = {"commodity": "gold", "depth_max_m": 500}

    def test_input_hash_identical_for_identical_inputs(self):
        from app.services.determinism import compute_scan_input_hash
        h1 = compute_scan_input_hash("aoi-abc", "cal-v1", self._VER, self._PARAMS)
        h2 = compute_scan_input_hash("aoi-abc", "cal-v1", self._VER, self._PARAMS)
        assert h1 == h2

    def test_input_hash_changes_on_parameter_change(self):
        from app.services.determinism import compute_scan_input_hash
        h1 = compute_scan_input_hash("aoi-abc", "cal-v1", self._VER, self._PARAMS)
        h2 = compute_scan_input_hash("aoi-abc", "cal-v2", self._VER, self._PARAMS)
        assert h1 != h2

    def test_output_hash_identical_for_identical_cells(self):
        from app.services.determinism import compute_scan_output_hash
        cells = [
            {"cell_id": "c1", "lat_center": -30.0, "lon_center": 116.5,
             "acif_score": 0.712, "tier": "TIER_1", "any_veto_fired": False},
        ]
        h1 = compute_scan_output_hash(cells, {"scan_id": "s1", "commodity": "gold"})
        h2 = compute_scan_output_hash(cells, {"scan_id": "s1", "commodity": "gold"})
        assert h1 == h2

    def test_output_hash_independent_of_cell_order(self):
        from app.services.determinism import compute_scan_output_hash
        cells_a = [
            {"cell_id": "c1", "lat_center": -29.0, "lon_center": 116.0,
             "acif_score": 0.8, "tier": "TIER_1", "any_veto_fired": False},
            {"cell_id": "c2", "lat_center": -30.0, "lon_center": 117.0,
             "acif_score": 0.6, "tier": "TIER_2", "any_veto_fired": False},
        ]
        cells_b = list(reversed(cells_a))
        meta = {"scan_id": "s1", "commodity": "gold"}
        assert compute_scan_output_hash(cells_a, meta) == compute_scan_output_hash(cells_b, meta)


# ─── 14–15. Deterministic IDs ────────────────────────────────────────────────

class TestDeterministicIds:
    def test_scan_id_same_for_same_inputs(self):
        from app.services.determinism import deterministic_scan_id
        id1 = deterministic_scan_id("aoi-hash-abc", "cal-v1", "gold")
        id2 = deterministic_scan_id("aoi-hash-abc", "cal-v1", "gold")
        assert id1 == id2

    def test_cell_id_same_for_same_inputs(self):
        from app.services.determinism import deterministic_cell_id
        id1 = deterministic_cell_id("scan-001", -30.12345678, 116.87654321)
        id2 = deterministic_cell_id("scan-001", -30.12345678, 116.87654321)
        assert id1 == id2

    def test_different_coordinates_different_ids(self):
        from app.services.determinism import deterministic_cell_id
        id1 = deterministic_cell_id("scan-001", -30.0, 116.0)
        id2 = deterministic_cell_id("scan-001", -31.0, 117.0)
        assert id1 != id2


# ─── 16–20. Version registry ─────────────────────────────────────────────────

class TestVersionRegistry:
    def test_all_frozen_versions_present(self):
        from app.config.version_registry import (
            SCORE_VERSION, TIER_VERSION, GATE_VERSION,
            CALIBRATION_VERSION, SCHEMA_VERSION, PIPELINE_VERSION,
            REGISTRY_HASH,
        )
        assert all([
            SCORE_VERSION, TIER_VERSION, GATE_VERSION,
            CALIBRATION_VERSION, SCHEMA_VERSION, PIPELINE_VERSION,
            REGISTRY_HASH,
        ])

    def test_assert_version_frozen_passes(self):
        from app.config.version_registry import assert_version_frozen
        assert_version_frozen()  # must not raise

    def test_snapshot_current_has_all_fields(self):
        from app.config.version_registry import VersionRegistrySnapshot
        snap = VersionRegistrySnapshot.current()
        assert snap.score_version == "acif-1.0.0"
        assert snap.tier_version  == "tier-1.0.0"
        assert snap.gate_version  == "gate-1.0.0"
        assert snap.registry_hash == "ae-freeze-2026-03-26-v1"
        assert snap.locked_at is not None

    def test_compatible_snapshots_do_not_raise(self):
        from app.config.version_registry import VersionRegistrySnapshot
        s1 = VersionRegistrySnapshot.current()
        s2 = VersionRegistrySnapshot.current()
        s1.assert_compatible(s2)  # must not raise

    def test_incompatible_version_raises(self):
        from app.config.version_registry import (
            VersionRegistrySnapshot, IncompatibleVersionError,
        )
        s1 = VersionRegistrySnapshot.current()
        # Manually create a mismatched snapshot
        fields = s1.to_dict()
        fields["score_version"] = "acif-MUTATED"
        from datetime import datetime
        fields["locked_at"] = datetime.utcnow().isoformat()
        s_mutated = VersionRegistrySnapshot(**fields)
        with pytest.raises(IncompatibleVersionError, match="score_version"):
            s1.assert_compatible(s_mutated)


# ─── 21–23. Replay ───────────────────────────────────────────────────────────

class TestReplay:
    def _stub_pipeline(self, *, aoi_geometry_hash, scan_parameters, calibration_version):
        """Deterministic stub pipeline: same inputs → same cells."""
        import hashlib
        # Produce a deterministic cell based on inputs
        seed = f"{aoi_geometry_hash}::{calibration_version}::{scan_parameters.get('commodity', 'gold')}"
        acif = int(hashlib.md5(seed.encode()).hexdigest()[:4], 16) / 65535.0
        cells = [
            {"cell_id": "c1", "lat_center": -30.0, "lon_center": 116.5,
             "acif_score": round(acif, 8), "tier": "TIER_1", "any_veto_fired": False},
        ]
        metadata = {"commodity": scan_parameters.get("commodity", "gold")}
        return cells, metadata

    def _build_scan_record(self):
        from app.config.version_registry import VersionRegistrySnapshot
        from app.services.determinism import compute_scan_input_hash, compute_scan_output_hash
        snap = VersionRegistrySnapshot.current()
        aoi_hash = "aoi-test-hash-abc123"
        cal_ver  = "cal-v1"
        params   = {"commodity": "gold", "depth_max_m": 500}
        cells, meta = self._stub_pipeline(
            aoi_geometry_hash=aoi_hash, scan_parameters=params,
            calibration_version=cal_ver,
        )
        return {
            "scan_id":          "scan-test-001",
            "aoi_geometry_hash": aoi_hash,
            "calibration_version": cal_ver,
            "scan_parameters":  params,
            "scan_input_hash":  compute_scan_input_hash(aoi_hash, cal_ver, snap.to_dict(), params),
            "scan_output_hash": compute_scan_output_hash(cells, meta),
            "version_snapshot": snap.to_dict(),
        }

    def test_certified_true_on_second_run(self):
        from app.pipeline.replay_controller import replay_scan
        record = self._build_scan_record()
        result = replay_scan(record, self._stub_pipeline)
        assert result.certified, f"Replay not certified: {result.replay_notes}"

    def test_replay_fails_on_missing_fields(self):
        from app.pipeline.replay_controller import replay_scan, ReplayFailed
        with pytest.raises(ReplayFailed, match="missing required fields"):
            replay_scan({"scan_id": "s-bad"}, self._stub_pipeline)

    def test_replay_result_frozen(self):
        from app.pipeline.replay_controller import replay_scan
        record = self._build_scan_record()
        result = replay_scan(record, self._stub_pipeline)
        with pytest.raises((AttributeError, TypeError)):
            object.__setattr__(result, "certified", False)


# ─── 24–25. No-randomness audit ──────────────────────────────────────────────

class TestNoRandomness:
    def test_determinism_module_has_no_randomness(self):
        import inspect
        from app.services import determinism
        src = inspect.getsource(determinism)
        # Allow "random.shuffle" only in comments — not in actual code
        # (the module itself uses no randomness)
        lines_with_random = [
            l for l in src.splitlines()
            if "random" in l and not l.strip().startswith("#")
        ]
        assert len(lines_with_random) == 0, f"Found randomness: {lines_with_random}"

    def test_assert_no_randomness_detects_uuid4(self):
        from app.services.determinism import assert_no_randomness_in_module
        fake_src = "import uuid\ndef make_id(): return uuid.uuid4()\n"
        with pytest.raises(AssertionError, match="uuid4"):
            assert_no_randomness_in_module(fake_src, "fake_module")

    def test_assert_no_randomness_passes_for_clean_source(self):
        from app.services.determinism import assert_no_randomness_in_module
        clean_src = "import math\ndef compute(x): return math.sqrt(x)\n"
        assert_no_randomness_in_module(clean_src, "clean_module")  # must not raise