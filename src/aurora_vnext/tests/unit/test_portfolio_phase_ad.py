"""
Aurora OSI vNext — Phase AD Portfolio Intelligence Tests (Corrected)
Phase AD §AD.8

CORRECTIONS:
  - portfolio_score → exploration_priority_index throughout
  - Added PortfolioWeightConfig tests (versioned weights, weight sum constraint)
  - Hard-coded constant tests removed (no more _W_ACIF etc.)

Tests:
  1.  exploration_priority_index formula correctness (versioned weights)
  2.  exploration_priority_index bounded to [0, 1]
  3.  PortfolioWeightConfig weights must sum to 1.0
  4.  PortfolioWeightConfig weight out of (0,1) raises ValueError
  5.  risk_tier LOW when veto_rate < 0.05, coverage > 0.70, scans >= 3
  6.  risk_tier HIGH when veto_rate > 0.30
  7.  risk_tier HIGH when scan_count < 2
  8.  risk-adjusted ranking penalises HIGH risk entries correctly
  9.  ranking assigns sequential integers from 1
  10. ranking is deterministic (input order independent)
  11. PortfolioEntry is frozen (immutable)
  12. PortfolioScore has no ACIF-computation fields
  13. snapshot_id is 16-char hex string
  14. empty entry set produces empty snapshot
  15. GT diversity: insufficient sources raises CalibrationDiversityError
  16. GT diversity: insufficient spatial dispersion raises CalibrationDiversityError
  17. GT diversity: insufficient geological type variation raises CalibrationDiversityError
  18. GT diversity passes when all constraints met
  19. No core/* imports in portfolio files
  20. PortfolioScore carries weight_config_version (auditable)
"""

from __future__ import annotations

import pytest
import math


# ─── Weight config fixtures ───────────────────────────────────────────────────

def _default_cfg():
    from app.models.portfolio_model import DEFAULT_WEIGHT_CONFIG
    return DEFAULT_WEIGHT_CONFIG


def _custom_cfg(w_a=0.6, w_t=0.3, w_v=0.1):
    from app.models.portfolio_model import PortfolioWeightConfig
    from datetime import datetime
    return PortfolioWeightConfig(
        version_id="pwc-custom-test", description="Custom test weights",
        w_acif_mean=w_a, w_tier1_density=w_t, w_veto_compliance=w_v,
        created_at=datetime.utcnow().isoformat(), created_by="test",
        parent_version_id="pwc-default-v1",
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _contribution(**kwargs):
    from app.models.portfolio_model import ScanContribution
    return ScanContribution(
        scan_id="scan-001", commodity=kwargs.get("commodity", "gold"),
        acif_mean=kwargs.get("acif_mean", 0.7412),
        tier_1_count=kwargs.get("tier_1_count", 12),
        tier_2_count=47, tier_3_count=88,
        total_cells=kwargs.get("total_cells", 300),
        veto_count=kwargs.get("veto_count", 8),
        system_status=kwargs.get("system_status", "PASS_CONFIRMED"),
        completed_at="2026-03-26T00:00:00", calibration_version="cal-v1",
        aoi_id=None, geometry_hash=None,
    )


def _territory(commodity="gold"):
    from app.models.portfolio_model import TerritoryBlock, TerritoryType
    return TerritoryBlock(
        block_id="blk-001", block_name="Yilgarn Test",
        territory_type=TerritoryType.PROVINCE,
        country_code="AU", commodity=commodity,
        geometry_wkt=None, area_km2=50000.0,
        scan_count=1, scan_ids=("scan-001",),
    )


def _entry(n_scans=3, veto_frac=0.02, acif_mean=0.74, weight_config=None):
    from app.services.portfolio_aggregation import assemble_portfolio_entry
    cfg = weight_config or _default_cfg()
    contributions = [
        _contribution(acif_mean=acif_mean, total_cells=300,
                       veto_count=int(300 * veto_frac), system_status="PASS_CONFIRMED")
        for _ in range(n_scans)
    ]
    return assemble_portfolio_entry("e-001", _territory(), contributions, weight_config=cfg)


# ─── 1–4. exploration_priority_index + PortfolioWeightConfig ─────────────────

class TestExplorationPriorityIndex:
    def test_formula_with_versioned_weights(self):
        from app.services.portfolio_aggregation import compute_exploration_priority
        cfg = _custom_cfg(w_a=0.6, w_t=0.3, w_v=0.1)
        result = compute_exploration_priority(
            acif_mean=0.8, tier1_count=30, total_cells=100, veto_count=5,
            weight_config=cfg,
        )
        # EPI = 0.6×0.8 + 0.3×0.30 + 0.1×0.95 = 0.48+0.09+0.095 = 0.665
        expected = 0.6 * 0.8 + 0.3 * 0.30 + 0.1 * 0.95
        assert abs(result.exploration_priority_index - expected) < 1e-4

    def test_index_bounded_zero_to_one(self):
        from app.services.portfolio_aggregation import compute_exploration_priority
        cfg = _default_cfg()
        perfect = compute_exploration_priority(1.0, 100, 100, 0, cfg)
        worst   = compute_exploration_priority(0.0, 0, 100, 100, cfg)
        assert 0.0 <= perfect.exploration_priority_index <= 1.0
        assert 0.0 <= worst.exploration_priority_index <= 1.0

    def test_weight_config_version_in_result(self):
        from app.services.portfolio_aggregation import compute_exploration_priority
        cfg = _custom_cfg()
        result = compute_exploration_priority(0.7, 30, 100, 5, cfg)
        assert result.weight_config_version == "pwc-custom-test"

    def test_weights_must_sum_to_one(self):
        from app.models.portfolio_model import PortfolioWeightConfig
        from datetime import datetime
        with pytest.raises(ValueError, match="sum to 1.0"):
            PortfolioWeightConfig(
                version_id="bad", description="bad",
                w_acif_mean=0.6, w_tier1_density=0.3, w_veto_compliance=0.5,  # sums to 1.4
                created_at=datetime.utcnow().isoformat(), created_by="test",
            )

    def test_weight_out_of_bounds_raises(self):
        from app.models.portfolio_model import PortfolioWeightConfig
        from datetime import datetime
        with pytest.raises(ValueError, match="must be in"):
            PortfolioWeightConfig(
                version_id="bad2", description="bad2",
                w_acif_mean=0.0, w_tier1_density=0.5, w_veto_compliance=0.5,
                created_at=datetime.utcnow().isoformat(), created_by="test",
            )


# ─── 5–7. Risk tier ───────────────────────────────────────────────────────────

class TestRiskTier:
    def test_low_risk(self):
        from app.services.portfolio_aggregation import classify_risk_tier
        from app.models.portfolio_model import RiskTier
        assert classify_risk_tier(0.02, 0.80, 4) == RiskTier.LOW

    def test_high_risk_veto(self):
        from app.services.portfolio_aggregation import classify_risk_tier
        from app.models.portfolio_model import RiskTier
        assert classify_risk_tier(0.35, 0.70, 3) == RiskTier.HIGH

    def test_high_risk_few_scans(self):
        from app.services.portfolio_aggregation import classify_risk_tier
        from app.models.portfolio_model import RiskTier
        assert classify_risk_tier(0.01, 0.90, 1) == RiskTier.HIGH


# ─── 8–10. Ranking ────────────────────────────────────────────────────────────

class TestRanking:
    def _make_entry(self, entry_id, idx_val, risk_tier):
        from app.models.portfolio_model import (
            PortfolioEntry, PortfolioScore, PortfolioRiskProfile,
            TerritoryBlock, TerritoryType, PortfolioStatus, RiskTier,
        )
        territory = TerritoryBlock(
            block_id=entry_id, block_name=entry_id, territory_type=TerritoryType.BLOCK,
            country_code="AU", commodity="gold", geometry_wkt=None, area_km2=None,
            scan_count=1, scan_ids=(entry_id,),
        )
        score = PortfolioScore(
            raw_acif_mean=idx_val, tier1_density=idx_val,
            veto_rate=0.0, exploration_priority_index=idx_val,
            exploration_priority_rank=None, weight_config_version="pwc-default-v1",
            weights_used={"w_acif_mean": 0.5, "w_tier1_density": 0.3, "w_veto_compliance": 0.2},
        )
        risk = PortfolioRiskProfile(
            veto_rate=0.0, coverage_score=0.8, gt_confidence=None,
            scan_diversity=3, risk_tier=risk_tier, risk_notes=(),
        )
        return PortfolioEntry(
            entry_id=entry_id, territory=territory, contributions=(),
            risk=risk, score=score, status=PortfolioStatus.ACTIVE,
            assembled_at="2026-03-26", assembled_by="test",
        )

    def test_risk_adjusted_penalty_reorders(self):
        from app.services.portfolio_ranking import rank_entries
        from app.models.portfolio_model import RiskTier
        A = self._make_entry("A", 0.80, RiskTier.HIGH)   # 0.80 - 0.15 = 0.65
        B = self._make_entry("B", 0.75, RiskTier.LOW)    # 0.75 - 0.00 = 0.75
        ranked = rank_entries([A, B], risk_adjusted=True)
        assert ranked[0].entry_id == "B"

    def test_sequential_ranks_from_one(self):
        from app.services.portfolio_ranking import rank_entries
        from app.models.portfolio_model import RiskTier
        entries = [self._make_entry(f"e{i}", 0.8 - i * 0.1, RiskTier.LOW) for i in range(3)]
        ranked = rank_entries(entries)
        assert [e.score.exploration_priority_rank for e in ranked] == [1, 2, 3]

    def test_ranking_deterministic(self):
        from app.services.portfolio_ranking import rank_entries
        from app.models.portfolio_model import RiskTier
        A = self._make_entry("A", 0.9, RiskTier.LOW)
        B = self._make_entry("B", 0.7, RiskTier.LOW)
        r1 = [e.entry_id for e in rank_entries([A, B])]
        r2 = [e.entry_id for e in rank_entries([B, A])]
        assert r1 == r2


# ─── 11–12. Immutability ─────────────────────────────────────────────────────

class TestImmutability:
    def test_entry_frozen(self):
        e = _entry()
        with pytest.raises((AttributeError, TypeError)):
            object.__setattr__(e, "entry_id", "mutated")

    def test_score_has_no_acif_recompute_field(self):
        e = _entry()
        assert not hasattr(e.score, "acif_score_recomputed")
        assert not hasattr(e.score, "tier_assignment")


# ─── 13–14. Snapshot ─────────────────────────────────────────────────────────

class TestSnapshot:
    def test_snapshot_id_is_hex(self):
        from app.services.portfolio_ranking import build_snapshot
        snap = build_snapshot([_entry()])
        assert len(snap.snapshot_id) == 16
        assert all(c in "0123456789abcdef" for c in snap.snapshot_id)

    def test_empty_snapshot(self):
        from app.services.portfolio_ranking import build_snapshot
        snap = build_snapshot([])
        assert snap.total_entries == 0


# ─── 15–18. GT diversity ─────────────────────────────────────────────────────

class TestDiversity:
    def _records(self, n_sources=2, n_types=2, spread=1.0):
        base = {"source_confidence": 0.9, "spatial_accuracy": 0.8,
                "temporal_relevance": 0.85, "geological_context_strength": 0.75}
        return [
            {**base, "record_id": f"r{i}", "source_name": f"S{i % n_sources}",
             "geological_data_type": f"t{i % n_types}",
             "lat": -30.0 + i * spread, "lon": 20.0 + i * spread,
             "is_synthetic": False}
            for i in range(4)
        ]

    def test_insufficient_sources(self):
        from app.services.calibration_diversity import assert_gt_diversity, CalibrationDiversityError
        with pytest.raises(CalibrationDiversityError, match="source diversity"):
            assert_gt_diversity("gold", self._records(n_sources=1))

    def test_insufficient_dispersion(self):
        from app.services.calibration_diversity import assert_gt_diversity, CalibrationDiversityError
        with pytest.raises(CalibrationDiversityError, match="spatial dispersion"):
            assert_gt_diversity("gold", self._records(spread=0.01))

    def test_insufficient_geo_types(self):
        from app.services.calibration_diversity import assert_gt_diversity, CalibrationDiversityError
        with pytest.raises(CalibrationDiversityError, match="geological context"):
            assert_gt_diversity("gold", self._records(n_types=1))

    def test_passes_all_constraints(self):
        from app.services.calibration_diversity import assert_gt_diversity
        report = assert_gt_diversity("gold", self._records())
        assert report.passed


# ─── 19. No core/* imports ───────────────────────────────────────────────────

class TestNoScientificImports:
    FORBIDDEN = ["app.core.scoring", "app.core.tiering", "app.core.gates",
                 "app.core.uncertainty", "app.core.priors"]

    def _check(self, module_path):
        import importlib, inspect
        mod = importlib.import_module(module_path)
        src = open(inspect.getfile(mod)).read()
        for f in self.FORBIDDEN:
            assert f not in src, f"VIOLATION: {module_path} imports {f}"

    def test_portfolio_model(self):        self._check("app.models.portfolio_model")
    def test_portfolio_aggregation(self):  self._check("app.services.portfolio_aggregation")
    def test_portfolio_ranking(self):      self._check("app.services.portfolio_ranking")
    def test_portfolio_api(self):          self._check("app.api.portfolio")
    def test_calibration_diversity(self):  self._check("app.services.calibration_diversity")


# ─── 20. Weight config auditability ──────────────────────────────────────────

class TestWeightConfigAuditability:
    def test_default_config_has_version_id(self):
        from app.models.portfolio_model import DEFAULT_WEIGHT_CONFIG
        assert DEFAULT_WEIGHT_CONFIG.version_id == "pwc-default-v1"
        assert DEFAULT_WEIGHT_CONFIG.parent_version_id is None   # genesis

    def test_custom_config_carries_parent(self):
        cfg = _custom_cfg()
        assert cfg.parent_version_id == "pwc-default-v1"

    def test_score_carries_weight_config_version(self):
        cfg = _custom_cfg()
        e = _entry(weight_config=cfg)
        assert e.score.weight_config_version == "pwc-custom-test"