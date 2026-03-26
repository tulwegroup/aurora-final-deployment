"""
Aurora OSI vNext — Phase AD Portfolio Intelligence Tests
Phase AD §AD.8 — Completion Proof Tests

Tests:
  1.  portfolio_score computed from stored values — formula correctness
  2.  portfolio_score bounded to [0, 1]
  3.  risk_tier LOW when veto_rate < 0.05 and coverage > 0.70 and scans >= 3
  4.  risk_tier HIGH when veto_rate > 0.30
  5.  risk_tier HIGH when scan_count < 2
  6.  risk-adjusted ranking applies penalty for HIGH risk entries
  7.  ranking assigns sequential integers starting at 1
  8.  rank is stable for identical inputs (deterministic)
  9.  PortfolioEntry is frozen (immutable)
  10. PortfolioScore has no ACIF-computation fields
  11. snapshot_id is a 16-char hex string
  12. empty entry set produces empty snapshot
  13. GT diversity: insufficient sources raises CalibrationDiversityError
  14. GT diversity: insufficient spatial dispersion raises CalibrationDiversityError
  15. GT diversity: insufficient geological type variation raises CalibrationDiversityError
  16. GT diversity: passes when all constraints met
  17. calibration_diversity: commodity-scoped (checks per commodity only)
  18. No core/* imports in portfolio files
  19. No core/* imports in calibration_diversity
  20. PortfolioScore weights sum to 1.0
"""

from __future__ import annotations

import pytest
import math


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _contribution(**kwargs):
    from app.models.portfolio_model import ScanContribution
    return ScanContribution(
        scan_id="scan-001", commodity=kwargs.get("commodity", "gold"),
        acif_mean=kwargs.get("acif_mean", 0.7412),
        tier_1_count=kwargs.get("tier_1_count", 12),
        tier_2_count=kwargs.get("tier_2_count", 47),
        tier_3_count=kwargs.get("tier_3_count", 88),
        total_cells=kwargs.get("total_cells", 300),
        veto_count=kwargs.get("veto_count", 8),
        system_status=kwargs.get("system_status", "PASS_CONFIRMED"),
        completed_at="2026-03-26T00:00:00",
        calibration_version="cal-v1",
        aoi_id=None, geometry_hash=None,
    )


def _territory(commodity="gold"):
    from app.models.portfolio_model import TerritoryBlock, TerritoryType
    return TerritoryBlock(
        block_id="blk-001", block_name="Yilgarn Craton Test",
        territory_type=TerritoryType.PROVINCE,
        country_code="AU", commodity=commodity,
        geometry_wkt=None, area_km2=50000.0,
        scan_count=1, scan_ids=("scan-001",),
    )


def _entry(n_scans=3, veto_frac=0.02, acif_mean=0.74, commodity="gold"):
    from app.services.portfolio_aggregation import assemble_portfolio_entry
    territory = _territory(commodity)
    contributions = [
        _contribution(
            acif_mean=acif_mean, total_cells=300,
            veto_count=int(300 * veto_frac), system_status="PASS_CONFIRMED",
        )
        for _ in range(n_scans)
    ]
    return assemble_portfolio_entry("e-001", territory, contributions)


# ─── 1–2. Portfolio score formula ─────────────────────────────────────────────

class TestPortfolioScore:
    def test_score_formula_correctness(self):
        from app.services.portfolio_aggregation import compute_portfolio_score
        result = compute_portfolio_score(
            acif_mean=0.8, tier1_count=30, total_cells=100, veto_count=5
        )
        # tier1_density = 0.30, veto_rate = 0.05
        # score = (0.5×0.8 + 0.3×0.30 + 0.2×0.95) / 1.0
        expected = (0.5 * 0.8 + 0.3 * 0.30 + 0.2 * 0.95)
        assert abs(result.portfolio_score - expected) < 1e-4

    def test_score_bounded_zero_to_one(self):
        from app.services.portfolio_aggregation import compute_portfolio_score
        # Extreme: perfect and worst case
        perfect = compute_portfolio_score(1.0, 100, 100, 0)
        worst   = compute_portfolio_score(0.0, 0, 100, 100)
        assert 0.0 <= perfect.portfolio_score <= 1.0
        assert 0.0 <= worst.portfolio_score <= 1.0

    def test_weights_sum_to_one(self):
        from app.services.portfolio_aggregation import _W_ACIF, _W_TIER1, _W_RISK
        assert abs(_W_ACIF + _W_TIER1 + _W_RISK - 1.0) < 1e-9


# ─── 3–5. Risk tier classification ────────────────────────────────────────────

class TestRiskTier:
    def test_low_risk_conditions(self):
        from app.services.portfolio_aggregation import classify_risk_tier
        from app.models.portfolio_model import RiskTier
        assert classify_risk_tier(0.02, 0.80, 4) == RiskTier.LOW

    def test_high_risk_high_veto(self):
        from app.services.portfolio_aggregation import classify_risk_tier
        from app.models.portfolio_model import RiskTier
        assert classify_risk_tier(0.35, 0.70, 3) == RiskTier.HIGH

    def test_high_risk_few_scans(self):
        from app.services.portfolio_aggregation import classify_risk_tier
        from app.models.portfolio_model import RiskTier
        assert classify_risk_tier(0.01, 0.90, 1) == RiskTier.HIGH

    def test_medium_risk_default(self):
        from app.services.portfolio_aggregation import classify_risk_tier
        from app.models.portfolio_model import RiskTier
        assert classify_risk_tier(0.10, 0.60, 2) == RiskTier.MEDIUM


# ─── 6–8. Ranking ─────────────────────────────────────────────────────────────

class TestRanking:
    def _two_entries(self):
        from app.services.portfolio_aggregation import assemble_portfolio_entry
        from app.models.portfolio_model import TerritoryBlock, TerritoryType
        def entry(entry_id, acif_mean, veto_frac, n_scans=3, risk_tier_veto=0.01):
            territory = TerritoryBlock(
                block_id=entry_id, block_name=f"Block {entry_id}",
                territory_type=TerritoryType.BLOCK,
                country_code="ZA", commodity="gold",
                geometry_wkt=None, area_km2=None,
                scan_count=n_scans, scan_ids=tuple(f"s{i}" for i in range(n_scans)),
            )
            contributions = [
                _contribution(acif_mean=acif_mean, total_cells=300,
                               veto_count=int(300 * risk_tier_veto))
                for _ in range(n_scans)
            ]
            e = assemble_portfolio_entry(entry_id, territory, contributions)
            # Override entry_id for test
            from app.models.portfolio_model import PortfolioEntry
            return PortfolioEntry(
                entry_id=entry_id, territory=e.territory,
                contributions=e.contributions, risk=e.risk,
                score=e.score, status=e.status,
                assembled_at=e.assembled_at, assembled_by=e.assembled_by,
            )
        high = entry("e-high", acif_mean=0.9, veto_frac=0.01)
        low  = entry("e-low",  acif_mean=0.3, veto_frac=0.01)
        return high, low

    def test_risk_adjusted_penalty_reorders_high_risk(self):
        from app.services.portfolio_ranking import rank_entries
        from app.models.portfolio_model import PortfolioEntry, PortfolioScore, RiskTier, PortfolioRiskProfile
        # Manually build entries with known scores and risk tiers
        from app.models.portfolio_model import TerritoryBlock, TerritoryType, PortfolioStatus

        def make(entry_id, score_val, risk_tier):
            territory = TerritoryBlock(
                block_id=entry_id, block_name=entry_id, territory_type=TerritoryType.BLOCK,
                country_code="AU", commodity="gold", geometry_wkt=None, area_km2=None,
                scan_count=1, scan_ids=(entry_id,),
            )
            score = PortfolioScore(
                raw_acif_mean=score_val, tier1_density=score_val,
                veto_rate=0.0, portfolio_score=score_val, portfolio_rank=None,
                weights_used={"w_acif": 0.5, "w_tier1": 0.3, "w_risk": 0.2},
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

        high_score_high_risk = make("A", 0.80, RiskTier.HIGH)
        lower_score_low_risk  = make("B", 0.75, RiskTier.LOW)

        ranked = rank_entries([high_score_high_risk, lower_score_low_risk], risk_adjusted=True)
        # A: 0.80 - 0.15 = 0.65, B: 0.75 - 0.0 = 0.75 → B should rank #1
        assert ranked[0].entry_id == "B"

    def test_ranking_sequential_from_one(self):
        high, low = self._two_entries()
        from app.services.portfolio_ranking import rank_entries
        ranked = rank_entries([high, low])
        ranks = [e.score.portfolio_rank for e in ranked]
        assert ranks == [1, 2]

    def test_ranking_deterministic(self):
        high, low = self._two_entries()
        from app.services.portfolio_ranking import rank_entries
        r1 = [e.entry_id for e in rank_entries([high, low])]
        r2 = [e.entry_id for e in rank_entries([low, high])]
        assert r1 == r2   # same order regardless of input order


# ─── 9–10. Immutability ───────────────────────────────────────────────────────

class TestPortfolioImmutability:
    def test_portfolio_entry_is_frozen(self):
        e = _entry()
        with pytest.raises((AttributeError, TypeError)):
            object.__setattr__(e, "entry_id", "mutated")

    def test_portfolio_score_has_no_acif_computation_field(self):
        e = _entry()
        score = e.score
        assert not hasattr(score, "acif_score_recomputed")
        assert not hasattr(score, "tier_assignment")
        assert not hasattr(score, "gate_result")


# ─── 11–12. Snapshot ─────────────────────────────────────────────────────────

class TestPortfolioSnapshot:
    def test_snapshot_id_is_hex_string(self):
        from app.services.portfolio_ranking import build_snapshot
        snapshot = build_snapshot([_entry()])
        assert len(snapshot.snapshot_id) == 16
        assert all(c in "0123456789abcdef" for c in snapshot.snapshot_id)

    def test_empty_entries_produces_empty_snapshot(self):
        from app.services.portfolio_ranking import build_snapshot
        snapshot = build_snapshot([])
        assert snapshot.total_entries == 0
        assert len(snapshot.entries) == 0


# ─── 13–17. GT diversity ─────────────────────────────────────────────────────

class TestGTDiversity:
    def _records(self, n_sources=2, n_types=2, spread_deg=1.0):
        base = {
            "source_confidence": 0.9, "spatial_accuracy": 0.8,
            "temporal_relevance": 0.85, "geological_context_strength": 0.75,
        }
        records = []
        for i in range(4):
            records.append({
                **base,
                "record_id": f"r{i}",
                "source_name": f"Source{i % n_sources}",
                "geological_data_type": f"type_{i % n_types}",
                "lat": -30.0 + i * spread_deg,
                "lon": 20.0 + i * spread_deg,
                "is_synthetic": False,
            })
        return records

    def test_insufficient_sources_raises(self):
        from app.services.calibration_diversity import assert_gt_diversity, CalibrationDiversityError
        records = self._records(n_sources=1, n_types=2, spread_deg=1.0)
        with pytest.raises(CalibrationDiversityError, match="source diversity"):
            assert_gt_diversity("gold", records)

    def test_insufficient_spatial_dispersion_raises(self):
        from app.services.calibration_diversity import assert_gt_diversity, CalibrationDiversityError
        records = self._records(n_sources=2, n_types=2, spread_deg=0.01)  # clustered
        with pytest.raises(CalibrationDiversityError, match="spatial dispersion"):
            assert_gt_diversity("gold", records)

    def test_insufficient_geological_types_raises(self):
        from app.services.calibration_diversity import assert_gt_diversity, CalibrationDiversityError
        records = self._records(n_sources=2, n_types=1, spread_deg=1.0)
        with pytest.raises(CalibrationDiversityError, match="geological context"):
            assert_gt_diversity("gold", records)

    def test_passes_when_all_constraints_met(self):
        from app.services.calibration_diversity import assert_gt_diversity
        records = self._records(n_sources=2, n_types=2, spread_deg=1.0)
        report = assert_gt_diversity("gold", records)
        assert report.passed

    def test_diversity_report_commodity_scoped(self):
        from app.services.calibration_diversity import validate_gt_diversity
        records = self._records(n_sources=2, n_types=2, spread_deg=1.0)
        report = validate_gt_diversity("copper", records)
        assert report.commodity == "copper"


# ─── 18–19. No core/* imports ────────────────────────────────────────────────

class TestNoScientificImports:
    FORBIDDEN = ["app.core.scoring", "app.core.tiering", "app.core.gates",
                 "app.core.uncertainty", "app.core.priors"]

    def _check(self, module_path: str):
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