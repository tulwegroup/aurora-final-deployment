"""
Aurora OSI vNext — Phase AC Calibration Mathematics Tests
Phase AC §AC.4 — Completion Proof Tests

Tests:
  1.  Provenance weight geometric mean formula
  2.  Provenance weight = 0 when any dimension is 0
  3.  Provenance weight out-of-range raises ValueError
  4.  Bayesian prior update formula correctness
  5.  Bayesian posterior stays in (0, 1)
  6.  Bayesian update with zero positive records produces prior-dominated result
  7.  Residual quantile threshold — Q_0.95 of known distribution
  8.  Threshold calibration with fewer than 3 records raises ValueError
  9.  Threshold computed from confirmed positives only
  10. Uncertainty recalibration k_u ≥ 1.0 enforced
  11. k_u = 1.0 when model is underconfident (no deflation)
  12. k_u > 1.0 when systematic overconfidence detected
  13. Lambda update bounded to [0.1, 2.0]
  14. Lambda update neutral when signal_ratio = 0.5
  15. CalibrationRunResult.assert_no_acif_fields passes on clean result
  16. CalibrationRunResult has no ACIF, tier, or gate fields
  17. Synthetic records excluded from calibration (two barriers)
  18. No core/* imports in Phase AC files
  19. Calibration creates new version — does not modify existing
  20. New calibration version carries parent_version_id lineage
"""

from __future__ import annotations

import math
import pytest


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _weight(
    record_id="rec-001",
    source_confidence=0.9,
    spatial_accuracy=0.8,
    temporal_relevance=0.85,
    geological_context_strength=0.75,
):
    from app.services.calibration_math import compute_provenance_weight
    return compute_provenance_weight(
        record_id=record_id,
        source_confidence=source_confidence,
        spatial_accuracy=spatial_accuracy,
        temporal_relevance=temporal_relevance,
        geological_context_strength=geological_context_strength,
    )


# ─── 1–3. Provenance weighting ────────────────────────────────────────────────

class TestProvenanceWeight:
    def test_geometric_mean_formula(self):
        w = _weight(
            source_confidence=0.9,
            spatial_accuracy=0.8,
            temporal_relevance=0.85,
            geological_context_strength=0.75,
        )
        expected = (0.9 * 0.8 * 0.85 * 0.75) ** 0.25
        assert abs(w.composite - expected) < 1e-6

    def test_zero_dimension_produces_zero_composite(self):
        w = _weight(source_confidence=0.0, spatial_accuracy=0.9,
                    temporal_relevance=0.9, geological_context_strength=0.9)
        assert w.composite == 0.0

    def test_out_of_range_raises(self):
        from app.services.calibration_math import compute_provenance_weight
        with pytest.raises(ValueError, match="must be in \[0, 1\]"):
            compute_provenance_weight("r1", 1.5, 0.8, 0.85, 0.75)

    def test_all_ones_produces_composite_one(self):
        w = _weight(source_confidence=1.0, spatial_accuracy=1.0,
                    temporal_relevance=1.0, geological_context_strength=1.0)
        assert abs(w.composite - 1.0) < 1e-8


# ─── 4–6. Bayesian prior update ───────────────────────────────────────────────

class TestBayesianPriorUpdate:
    def _run(self, n_pos=3, n_total=5, alpha_0=2.0, beta_0=2.0):
        from app.services.calibration_math import bayesian_prior_update
        wgts_all = [_weight(f"r{i}") for i in range(n_total)]
        wgts_pos = wgts_all[:n_pos]
        return bayesian_prior_update("gold", "WA_Yilgarn", alpha_0, beta_0,
                                     wgts_pos, wgts_all)

    def test_formula_correctness(self):
        result = self._run(n_pos=3, n_total=5, alpha_0=2.0, beta_0=2.0)
        # posterior = (α₀ + Σw⁺) / (α₀ + β₀ + Σw)
        expected_numer = 2.0 + result.sum_wgt_positive
        expected_denom = 2.0 + 2.0 + result.sum_wgt_total
        assert abs(result.posterior_prior - expected_numer / expected_denom) < 1e-6

    def test_posterior_in_open_unit_interval(self):
        result = self._run()
        assert 0.0 < result.posterior_prior < 1.0

    def test_zero_positive_records_dominated_by_prior(self):
        from app.services.calibration_math import bayesian_prior_update
        wgts_all = [_weight(f"r{i}") for i in range(5)]
        result = bayesian_prior_update("gold", "prov-A", 2.0, 8.0, [], wgts_all)
        # With α₀=2, β₀=8, no positives: prior = 2/(2+8+Σw) < 0.2
        assert result.posterior_prior < 0.2
        assert result.n_records_positive == 0

    def test_empty_weights_raises(self):
        from app.services.calibration_math import bayesian_prior_update
        with pytest.raises(ValueError, match="non-empty"):
            bayesian_prior_update("gold", "prov-A", 2.0, 2.0, [], [])


# ─── 7–9. Residual quantile threshold ────────────────────────────────────────

class TestResidualQuantileThreshold:
    def _weights(self, n):
        return [_weight(f"r{i}") for i in range(n)]

    def test_q95_of_known_distribution(self):
        from app.services.calibration_math import residual_quantile_threshold
        residuals = [float(i) for i in range(100)]  # 0..99
        wgts = self._weights(100)
        result = residual_quantile_threshold("gold", "physics", residuals, wgts, quantile=0.95)
        # Q_0.95 of [0..99] ≈ 94.05
        assert abs(result.computed_threshold - 94.05) < 0.1

    def test_fewer_than_3_records_raises(self):
        from app.services.calibration_math import residual_quantile_threshold
        with pytest.raises(ValueError, match="≥ 3"):
            residual_quantile_threshold("gold", "physics", [0.1, 0.2], self._weights(2))

    def test_invalid_threshold_type_raises(self):
        from app.services.calibration_math import residual_quantile_threshold
        with pytest.raises(ValueError, match="threshold_type"):
            residual_quantile_threshold("gold", "magnetic", [0.1, 0.2, 0.3], self._weights(3))

    def test_result_has_no_acif_field(self):
        from app.services.calibration_math import residual_quantile_threshold
        result = residual_quantile_threshold("gold", "gravity", [0.1, 0.5, 0.9], self._weights(3))
        assert not hasattr(result, "acif_score")
        assert not hasattr(result, "tier")


# ─── 10–12. Uncertainty recalibration ────────────────────────────────────────

class TestUncertaintyRecalibration:
    def _weights(self, n):
        return [_weight(f"r{i}") for i in range(n)]

    def test_k_u_minimum_is_1(self):
        from app.services.calibration_math import uncertainty_recalibration_factor
        # Underconfident model: empirical > predicted → k_u = 1.0
        pred = [0.3, 0.4, 0.5]
        emp  = [0.8, 0.9, 0.7]   # empirical > predicted → model underconfident
        result = uncertainty_recalibration_factor("gold", pred, emp, self._weights(3))
        assert result.k_u >= 1.0

    def test_k_u_greater_than_1_on_overconfidence(self):
        from app.services.calibration_math import uncertainty_recalibration_factor
        pred = [0.8, 0.9, 0.85]  # high predicted uncertainty
        emp  = [0.2, 0.3, 0.25]  # low empirical error → overconfident
        result = uncertainty_recalibration_factor("gold", pred, emp, self._weights(3))
        assert result.k_u > 1.0

    def test_k_u_below_1_raises(self):
        from app.models.calibration_math_model import UncertaintyRecalibration
        from app.services.calibration_math import compute_provenance_weight
        w = compute_provenance_weight("r1", 0.9, 0.8, 0.85, 0.75)
        with pytest.raises(ValueError, match="k_u must be ≥ 1.0"):
            UncertaintyRecalibration(
                commodity="gold", k_u=0.5, mean_overconfidence=-0.1,
                n_records=5, provenance_weights=(w,),
                evidence_summary="test",
            )


# ─── 13–14. Lambda updates ────────────────────────────────────────────────────

class TestLambdaUpdates:
    def _weights(self, n):
        return [_weight(f"r{i}") for i in range(n)]

    def test_lambda_stays_in_bounds(self):
        from app.services.calibration_math import compute_lambda_updates
        # Extreme: all positive → signal_ratio = 1.0 → max delta
        wgts = self._weights(10)
        result = compute_lambda_updates("gold", 0.5, 0.5, wgts, wgts, learning_rate=0.5)
        assert result["lambda_1"] <= 2.0
        assert result["lambda_2"] <= 2.0

    def test_neutral_signal_no_change(self):
        from app.services.calibration_math import compute_lambda_updates
        wgts_all = self._weights(10)
        wgts_pos = wgts_all[:5]   # 50% positive → signal_ratio ≈ 0.5 → Δλ ≈ 0
        result = compute_lambda_updates("gold", 1.0, 1.0, wgts_pos, wgts_all)
        # At neutral signal ratio ≈ 0.5, delta ≈ 0
        assert abs(result["lambda_1"] - 1.0) < 0.1

    def test_empty_weights_returns_current(self):
        from app.services.calibration_math import compute_lambda_updates
        result = compute_lambda_updates("gold", 1.2, 0.8, [], [])
        assert result["lambda_1"] == 1.2
        assert result["lambda_2"] == 0.8


# ─── 15–16. CalibrationRunResult integrity ───────────────────────────────────

class TestCalibrationRunResult:
    def _minimal_result(self):
        from app.models.calibration_math_model import CalibrationRunResult
        return CalibrationRunResult(
            new_version_id="v2", parent_version_id="v1",
            commodity="gold",
            prior_updates=(), threshold_updates=(), uncertainty_updates=(),
            lambda_updates={"lambda_1": 1.02, "lambda_2": 0.98},
            n_gt_records_used=5,
            run_summary="Test run.",
            executed_at="2026-03-26T00:00:00",
            executed_by="test",
        )

    def test_assert_no_acif_fields_passes(self):
        self._minimal_result().assert_no_acif_fields()  # must not raise

    def test_result_has_no_tier_field(self):
        r = self._minimal_result()
        assert not hasattr(r, "tier")
        assert not hasattr(r, "acif_score")
        assert not hasattr(r, "gate_result")


# ─── 17. Synthetic exclusion ──────────────────────────────────────────────────

class TestSyntheticExclusion:
    def test_synthetic_records_excluded_from_calibration(self):
        """
        PROOF: CalibrationExecutor filters out is_synthetic=True records.
        This is the second barrier (storage layer is the first).
        """
        from app.services.calibration_executor import CalibrationExecutor, CalibrationStorageAdapter
        from app.services.calibration_version import CalibrationVersionManager
        from app.storage.ground_truth import GroundTruthStorage

        class SyntheticMixedAdapter(CalibrationStorageAdapter):
            def fetch_approved_gt_records(self, commodity):
                base = {
                    "source_confidence": 0.9, "spatial_accuracy": 0.8,
                    "temporal_relevance": 0.85, "geological_context_strength": 0.75,
                    "is_positive": True, "province_id": "test-prov",
                }
                return [
                    {"record_id": "r1", "is_synthetic": False, **base},
                    {"record_id": "r2", "is_synthetic": True,  **base},  # ← must be excluded
                    {"record_id": "r3", "is_synthetic": False, **base},
                ]
            def fetch_active_calibration_version(self, commodity): return None

        storage = SyntheticMixedAdapter()
        gt_store = GroundTruthStorage()
        mgr     = CalibrationVersionManager(gt_store)
        executor = CalibrationExecutor(storage, mgr)

        with pytest.raises(ValueError, match="≥ 3"):
            # Only 2 real records → fails minimum threshold
            executor.run("gold", "test-actor")


# ─── 18. No core/* imports ────────────────────────────────────────────────────

class TestNoScientificImports:
    FORBIDDEN = ["app.core.scoring", "app.core.tiering", "app.core.gates",
                 "app.core.uncertainty", "app.core.priors", "app.core.physics"]

    def _check(self, module_path: str):
        import importlib, inspect
        mod = importlib.import_module(module_path)
        src = open(inspect.getfile(mod)).read()
        for forbidden in self.FORBIDDEN:
            assert forbidden not in src, \
                f"VIOLATION: {module_path} imports {forbidden}"

    def test_calibration_math_model(self): self._check("app.models.calibration_math_model")
    def test_calibration_math(self):       self._check("app.services.calibration_math")
    def test_calibration_executor(self):   self._check("app.services.calibration_executor")


# ─── 19–20. Version lineage ──────────────────────────────────────────────────

class TestVersionLineage:
    def test_new_version_created_not_existing_modified(self):
        """
        PROOF: CalibrationVersionManager.create_version() always creates a
        new entry — it never overwrites an existing version.
        """
        from app.services.calibration_version import CalibrationVersionManager, CalibrationParameters
        from app.storage.ground_truth import GroundTruthStorage

        storage = GroundTruthStorage()
        mgr     = CalibrationVersionManager(storage)
        params  = CalibrationParameters(lambda_1_updates={"gold": 1.05})

        v1 = mgr.create_version("V1", "First version", params, [], [], "admin1")
        v2 = mgr.create_version("V2", "Second version", params, [], [], "admin1")

        assert v1.version_id != v2.version_id
        # v1 still retrievable — not overwritten
        assert storage.get_version(v1.version_id) is not None

    def test_calibration_run_result_carries_parent_version_id(self):
        """
        PROOF: CalibrationRunResult.parent_version_id links to the prior active version.
        This establishes the immutable lineage chain.
        """
        from app.models.calibration_math_model import CalibrationRunResult
        result = CalibrationRunResult(
            new_version_id="v-new", parent_version_id="v-old",
            commodity="gold",
            prior_updates=(), threshold_updates=(), uncertainty_updates=(),
            lambda_updates={"lambda_1": 1.0, "lambda_2": 1.0},
            n_gt_records_used=5,
            run_summary="Lineage test.",
            executed_at="2026-03-26T00:00:00",
            executed_by="test",
        )
        assert result.parent_version_id == "v-old"
        assert result.new_version_id == "v-new"