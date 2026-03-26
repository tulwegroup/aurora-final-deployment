"""
Aurora OSI vNext — Phase AF Validation Harness Tests

Tests:
  1.  GroundTruthReference with is_synthetic=True raises on build_validation_case
  2.  GroundTruthReference with is_synthetic=False passes
  3.  build_validation_case: GT in Tier 1 → DETECTION_SUCCESS
  4.  build_validation_case: GT in Tier 2 → PARTIAL_DETECTION
  5.  build_validation_case: GT vetoed → DETECTION_MISS
  6.  build_validation_case: no GT cell → DETECTION_MISS on low ACIF
  7.  signal_strength computed correctly from stored values
  8.  ValidationReport.detection_rate correct
  9.  ValidationReport.false_positive_rate correct
  10. ValidationReport.summary_by_commodity groups correctly
  11. ValidationCase is frozen (immutable)
  12. No scoring logic present in validation_harness.py
  13. Synthetic data excluded from detection rate
  14. DatasetProvenance enum covers required real sources
  15. ValidationMetrics has no acif recomputation field
"""

from __future__ import annotations

import pytest
from datetime import datetime


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _real_gt(is_synthetic=False):
    from app.services.validation_harness import GroundTruthReference, DatasetProvenance
    return GroundTruthReference(
        reference_id="gt-test-001",
        name="Obuasi (test)",
        commodity="gold",
        country="Ghana",
        province="Ashanti",
        lat=6.2035,
        lon=-1.6669,
        deposit_type="orogenic_gold",
        provenance=DatasetProvenance.GGS_GHANA,
        source_url="https://ggsa.gov.gh",
        source_citation="GGSA Mineral Map 2019",
        known_grade="~2.1 g/t Au",
        known_tonnage=">80 Moz Au",
        is_synthetic=is_synthetic,
    )


def _aoi():
    from app.services.validation_harness import AOIDefinition
    return AOIDefinition(
        aoi_id="aoi-test-001", name="Obuasi AOI",
        country="Ghana", centre_lat=6.2035, centre_lon=-1.6669,
        radius_km=10.0, geometry_hash="aoi-hash-abc", resolution="standard",
    )


def _scan(acif_mean=0.78, acif_max=0.92, t1=34, t2=67, t3=100,
          total=201, veto=3, status="PASS_CONFIRMED"):
    return {
        "scan_id": "scan-test-001", "commodity": "gold",
        "acif_mean": acif_mean, "acif_max": acif_max,
        "tier_counts": {"TIER_1": t1, "TIER_2": t2, "TIER_3": t3},
        "total_cells": total, "veto_count": veto,
        "system_status": status,
    }


def _gt_cell(tier="TIER_1", acif_score=0.91, vetoed=False, uncertainty=0.18):
    return {
        "cell_id": "cell-001", "tier": tier,
        "acif_score": acif_score, "any_veto_fired": vetoed,
        "uncertainty": uncertainty,
    }


# ─── 1–2. Synthetic exclusion ────────────────────────────────────────────────

class TestSyntheticExclusion:
    def test_synthetic_gt_raises(self):
        from app.services.validation_harness import build_validation_case
        with pytest.raises(AssertionError, match="synthetic"):
            build_validation_case(
                "c-1", "gold", _aoi(), _real_gt(is_synthetic=True),
                _scan(), _gt_cell(),
            )

    def test_real_gt_passes(self):
        from app.services.validation_harness import build_validation_case
        case = build_validation_case(
            "c-1", "gold", _aoi(), _real_gt(is_synthetic=False),
            _scan(), _gt_cell(),
        )
        assert case.case_id == "c-1"


# ─── 3–6. Detection outcomes ──────────────────────────────────────────────────

class TestDetectionOutcomes:
    def test_tier1_cell_is_detection_success(self):
        from app.services.validation_harness import build_validation_case, ValidationOutcome
        case = build_validation_case("c-2", "gold", _aoi(), _real_gt(), _scan(), _gt_cell("TIER_1"))
        assert case.metrics.detection_outcome == ValidationOutcome.DETECTION_SUCCESS

    def test_tier2_cell_is_partial_detection(self):
        from app.services.validation_harness import build_validation_case, ValidationOutcome
        case = build_validation_case("c-3", "gold", _aoi(), _real_gt(), _scan(), _gt_cell("TIER_2"))
        assert case.metrics.detection_outcome == ValidationOutcome.PARTIAL_DETECTION

    def test_vetoed_gt_cell_is_detection_miss(self):
        from app.services.validation_harness import build_validation_case, ValidationOutcome
        case = build_validation_case("c-4", "gold", _aoi(), _real_gt(), _scan(),
                                      _gt_cell("TIER_1", vetoed=True))
        # veto fires → DETECTION_MISS overrides tier
        assert case.metrics.detection_outcome == ValidationOutcome.DETECTION_MISS

    def test_no_gt_cell_low_acif_is_miss(self):
        from app.services.validation_harness import build_validation_case, ValidationOutcome
        case = build_validation_case("c-5", "gold", _aoi(), _real_gt(),
                                      _scan(acif_mean=0.3, t1=0, t2=0), gt_cell=None)
        assert case.metrics.detection_outcome == ValidationOutcome.DETECTION_MISS


# ─── 7. Signal strength ───────────────────────────────────────────────────────

class TestSignalStrength:
    def test_signal_strength_formula(self):
        from app.services.validation_harness import build_validation_case
        acif_mean = 0.78
        gt_acif   = 0.91
        case = build_validation_case("c-6", "gold", _aoi(), _real_gt(),
                                      _scan(acif_mean=acif_mean),
                                      _gt_cell("TIER_1", acif_score=gt_acif))
        expected = gt_acif / acif_mean
        assert abs(case.metrics.signal_strength - expected) < 1e-6


# ─── 8–10. ValidationReport ───────────────────────────────────────────────────

class TestValidationReport:
    def _report(self):
        from app.services.validation_harness import ValidationReport, build_validation_case, ValidationOutcome
        from app.services.validation_harness import ValidationCase, ValidationMetrics, ValidationFinding
        c1 = build_validation_case("c1", "gold", _aoi(), _real_gt(), _scan(), _gt_cell("TIER_1"))
        c2 = build_validation_case("c2", "gold", _aoi(), _real_gt(), _scan(), _gt_cell("TIER_2"))
        return ValidationReport(
            report_id="rep-001",
            cases=(c1, c2),
            generated_at=datetime.utcnow().isoformat(),
            dataset_inventory=(),
            no_modification_statement="No scoring logic was changed during Phase AF validation.",
        )

    def test_detection_rate_correct(self):
        report = self._report()
        # c1 = success (1.0), c2 = partial (counts), both count as detected
        assert report.detection_rate == 1.0

    def test_false_positive_rate_zero(self):
        report = self._report()
        assert report.false_positive_rate == 0.0

    def test_summary_by_commodity(self):
        report = self._report()
        summary = report.summary_by_commodity
        assert "gold" in summary
        assert summary["gold"]["total"] == 2


# ─── 11. Immutability ────────────────────────────────────────────────────────

class TestImmutability:
    def test_validation_case_frozen(self):
        from app.services.validation_harness import build_validation_case
        case = build_validation_case("c-fr", "gold", _aoi(), _real_gt(), _scan(), _gt_cell())
        with pytest.raises((AttributeError, TypeError)):
            object.__setattr__(case, "case_id", "mutated")


# ─── 12. No scoring logic in harness ─────────────────────────────────────────

class TestNoScoringLogic:
    def test_no_core_imports_in_harness(self):
        import inspect
        from app.services import validation_harness
        src = inspect.getsource(validation_harness)
        forbidden = ["app.core.scoring", "app.core.tiering", "app.core.gates",
                     "acif_score =", "tier_assignment ="]
        for f in forbidden:
            assert f not in src, f"Forbidden pattern in validation_harness: {f!r}"


# ─── 13. Synthetic excluded from rate ────────────────────────────────────────

class TestSyntheticExcludedFromStats:
    def test_synthetic_check_prevents_case_creation(self):
        """
        Prove: synthetic GT references cannot enter the validation pipeline.
        The assert in build_validation_case is the enforcement barrier.
        """
        from app.services.validation_harness import build_validation_case
        synthetic_gt = _real_gt(is_synthetic=True)
        with pytest.raises(AssertionError):
            build_validation_case("c-syn", "gold", _aoi(), synthetic_gt, _scan(), _gt_cell())


# ─── 14. DatasetProvenance covers required sources ───────────────────────────

class TestDatasetProvenance:
    def test_required_sources_present(self):
        from app.services.validation_harness import DatasetProvenance
        required = ["usgs_mrds", "geus", "ggs_ghana", "gsz_zambia", "brgm_senegal", "gsa"]
        for r in required:
            assert r in [p.value for p in DatasetProvenance], f"Missing provenance: {r}"


# ─── 15. ValidationMetrics has no ACIF recomputation ─────────────────────────

class TestValidationMetricsIntegrity:
    def test_metrics_has_no_recomputed_acif(self):
        from app.services.validation_harness import build_validation_case
        case = build_validation_case("c-int", "gold", _aoi(), _real_gt(), _scan(), _gt_cell())
        metrics = case.metrics
        assert not hasattr(metrics, "acif_score_recomputed")
        assert not hasattr(metrics, "tier_reassigned")
        # acif_mean_stored is the stored value — not a recomputation
        assert hasattr(metrics, "acif_mean_stored")