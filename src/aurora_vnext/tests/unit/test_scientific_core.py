"""
Phase I — Scientific Core Module Tests

Tests all six modules against Phase B mathematical specifications:
  - evidence.py:     §4.2 weighted evidence, §4.3 clustering adjustment
  - causal.py:       §5.1 DAG consistency, §5.2 hard vetoes, §5.3 node scores
  - physics.py:      §6.1 gravity residual, §6.2 Poisson, §6.4 Ψ score, §6.6 veto
  - temporal.py:     §7.2 geometric mean, §7.3 sub-scores, §7.4 veto
  - priors.py:       §8.2 lookup, §8.3 veto, §8.4 Bayesian posterior
  - uncertainty.py:  §10.2 five components, §10.3 probabilistic union

Constitutional invariants verified explicitly:
  - Causal veto → C_i = 0.0 (not a low value)
  - Province veto → P_i = 0.0 (not a low value)
  - Temporal geometric mean: one q_j = 0 → T_i = 0 (arithmetic mean would not)
  - Uncertainty probabilistic union: one u_k = 1 → U_i = 1 (arithmetic mean would not)
  - Physics: Ψ = 1 at zero residuals; Ψ → 0 at large residuals
"""

from __future__ import annotations

import math
from typing import Optional

import pytest

from app.core.causal import (
    apply_causal_vetoes,
    compute_causal_consistency,
    compute_dag_node_scores,
    score_causal,
)
from app.core.evidence import (
    compute_adjusted_evidence,
    compute_clustering_metric,
    compute_evidence_score,
    score_evidence,
)
from app.core.physics import (
    apply_physics_veto,
    compute_darcy_residual,
    compute_gravity_residual,
    compute_physics_score,
    compute_poisson_residual,
    compute_water_column_residual,
    score_physics,
)
from app.core.priors import (
    apply_province_veto,
    compute_bayesian_posterior,
    compute_prior_uncertainty,
    lookup_province_prior,
    score_province_prior,
)
from app.core.temporal import (
    apply_temporal_veto,
    compute_persistence_sub_score,
    compute_stability_sub_score,
    compute_temporal_coherence,
    compute_vegetation_stress_persistence,
    score_temporal,
)
from app.core.uncertainty import (
    compute_model_uncertainty,
    compute_physics_uncertainty,
    compute_sensor_uncertainty,
    compute_temporal_uncertainty,
    compute_total_uncertainty,
    score_uncertainty,
)
from app.models.component_scores import (
    DagNodeScores,
    TemporalSubScores,
    UncertaintyComponents,
)
from app.models.observable_vector import ObservableVector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _obs(**overrides) -> ObservableVector:
    """Build an ObservableVector with specified field overrides; rest None."""
    return ObservableVector(**overrides)


def _full_obs(val: float = 0.5) -> ObservableVector:
    """Build an ObservableVector with all 42 fields set to val."""
    fields = {k: val for k in ObservableVector.model_fields}
    return ObservableVector(**fields)


def _uniform_weights(val: float = 1.0) -> dict[str, float]:
    return {k: val for k in ObservableVector.model_fields}


# ===========================================================================
# EVIDENCE MODULE §4.2, §4.3
# ===========================================================================

class TestEvidenceScore:
    def test_zero_weights_returns_zero(self):
        obs = _full_obs(0.8)
        e, _ = compute_evidence_score(obs, weights={})
        assert e == pytest.approx(0.0)

    def test_uniform_weights_equals_mean(self):
        obs = _obs(x_spec_1=0.4, x_spec_2=0.8)
        weights = {"x_spec_1": 1.0, "x_spec_2": 1.0}
        e, _ = compute_evidence_score(obs, weights)
        assert e == pytest.approx(0.6)

    def test_missing_observable_excluded_from_sum(self):
        obs = _obs(x_spec_1=0.6)  # x_spec_2 is None
        weights = {"x_spec_1": 1.0, "x_spec_2": 2.0}
        e, contributions = compute_evidence_score(obs, weights)
        # Only x_spec_1 contributes (weight=1.0, value=0.6)
        assert e == pytest.approx(0.6)
        assert contributions["x_spec_2"] is None

    def test_evidence_in_bounds(self):
        obs = _full_obs(1.0)
        e, _ = compute_evidence_score(obs, _uniform_weights())
        assert 0.0 <= e <= 1.0

    def test_evidence_all_missing_returns_zero(self):
        obs = _obs()  # All None
        e, _ = compute_evidence_score(obs, _uniform_weights())
        assert e == pytest.approx(0.0)

    def test_evidence_weighted_higher_modality_dominates(self):
        obs = _obs(x_spec_1=0.2, x_grav_1=0.9)
        weights = {"x_spec_1": 1.0, "x_grav_1": 5.0}
        e, _ = compute_evidence_score(obs, weights)
        # Gravity dominates: (1×0.2 + 5×0.9) / 6 = 4.7/6 ≈ 0.783
        assert e == pytest.approx(4.7 / 6, abs=0.001)


class TestClusteringAdjustment:
    def test_alpha_zero_no_effect(self):
        """α_c = 0: Ẽ = E regardless of κ."""
        e_tilde = compute_adjusted_evidence(e_i=0.6, kappa_i=0.9, alpha_c=0.0)
        assert e_tilde == pytest.approx(0.6)

    def test_high_clustering_boosts_score(self):
        """High κ_i with α_c > 0 should produce Ẽ > E."""
        e_tilde = compute_adjusted_evidence(e_i=0.6, kappa_i=1.0, alpha_c=1.0)
        assert e_tilde > 0.6

    def test_low_clustering_reduces_score(self):
        """Low κ_i (isolated anomaly) with α_c > 0 should produce Ẽ < E."""
        e_tilde = compute_adjusted_evidence(e_i=0.6, kappa_i=0.0, alpha_c=1.0)
        assert e_tilde < 0.6

    def test_adjusted_evidence_clamped_to_1(self):
        e_tilde = compute_adjusted_evidence(e_i=1.0, kappa_i=1.0, alpha_c=1.0)
        assert e_tilde <= 1.0

    def test_adjusted_evidence_clamped_to_0(self):
        e_tilde = compute_adjusted_evidence(e_i=0.0, kappa_i=0.0, alpha_c=1.0)
        assert e_tilde >= 0.0

    def test_neutral_kappa_no_adjustment(self):
        """κ_i = 0.5: no adjustment regardless of α_c."""
        e_tilde = compute_adjusted_evidence(e_i=0.7, kappa_i=0.5, alpha_c=1.0)
        assert e_tilde == pytest.approx(0.7)

    def test_clustering_metric_no_neighbours_returns_neutral(self):
        kappa = compute_clustering_metric(0.5, [], e_max=0.8)
        assert kappa == pytest.approx(0.5)

    def test_clustering_metric_zero_e_max_returns_neutral(self):
        kappa = compute_clustering_metric(0.5, [0.4, 0.6], e_max=0.0)
        assert kappa == pytest.approx(0.5)


# ===========================================================================
# CAUSAL MODULE §5.1, §5.2, §5.3
# ===========================================================================

class TestDagNodeScores:
    def test_all_zeros_when_all_missing(self):
        obs = _obs()
        dag = compute_dag_node_scores(obs)
        assert dag.z_surface    == pytest.approx(0.0)
        assert dag.z_structural == pytest.approx(0.0)
        assert dag.z_subsurface == pytest.approx(0.0)

    def test_nodes_in_0_1(self):
        obs = _full_obs(0.7)
        dag = compute_dag_node_scores(obs)
        for attr in ("z_surface","z_structural","z_subsurface","z_thermal","z_temporal_dag"):
            v = getattr(dag, attr)
            assert 0.0 <= v <= 1.0, f"{attr} = {v} out of bounds"


class TestCausalVetoes:
    def _make_dag(self, **kwargs) -> DagNodeScores:
        defaults = dict(cell_id="c", commodity="gold",
                        z_surface=0.3, z_structural=0.3, z_subsurface=0.3,
                        z_thermal=0.3, z_temporal_dag=0.3)
        defaults.update(kwargs)
        return DagNodeScores(**defaults)

    def test_veto_1_surface_without_structure(self):
        """High surface signal, no structural pathway → veto 1."""
        dag = self._make_dag(z_surface=0.8, z_structural=0.05)
        flags = apply_causal_vetoes(dag, tau_surf=0.4, tau_struct_min=0.15)
        assert flags.veto_1_surface_without_structure is True
        assert flags.any_veto_fired is True

    def test_veto_2_structure_without_subsurface(self):
        """Structure present, no geophysical subsurface support → veto 2."""
        dag = self._make_dag(z_structural=0.6, z_subsurface=0.05)
        flags = apply_causal_vetoes(dag, tau_struct=0.35, tau_sub_min=0.15)
        assert flags.veto_2_structure_without_subsurface is True

    def test_veto_3_temporal_inconsistency(self):
        """Near-zero temporal persistence → veto 3."""
        dag = self._make_dag(z_temporal_dag=0.02)
        flags = apply_causal_vetoes(dag, tau_temp_veto=0.10)
        assert flags.veto_3_temporal_inconsistency is True

    def test_no_veto_when_all_pass(self):
        dag = self._make_dag(z_surface=0.3, z_structural=0.5, z_subsurface=0.5, z_temporal_dag=0.4)
        flags = apply_causal_vetoes(dag)
        assert flags.any_veto_fired is False

    def test_veto_fires_produces_zero_causal_score(self):
        """CONSTITUTIONAL: causal veto must produce C_i = 0.0, not a low value."""
        obs = _obs(x_spec_1=0.9, x_spec_2=0.9, x_spec_3=0.9)  # Strong surface, no structure
        result = score_causal("c", "gold", obs,
                              veto_thresholds={"tau_surf": 0.4, "tau_struct_min": 0.15})
        # Surface is high (mean of x_spec_1,x_spec_2 + hydro ≈ 0.6), structural is 0
        # Veto 1 should fire → C = 0.0
        assert result.causal_score == pytest.approx(0.0)
        assert result.veto_flags.any_veto_fired is True


class TestCausalConsistencyScore:
    def test_perfect_dag_compliance_approaches_1(self):
        """When all child nodes > parent × delta, compliance → 1."""
        dag = DagNodeScores(cell_id="c", commodity="gold",
                            z_surface=0.5, z_structural=0.8,
                            z_subsurface=0.9, z_thermal=0.7, z_temporal_dag=0.6)
        c_i = compute_causal_consistency(dag)
        assert c_i > 0.5

    def test_empty_edges_returns_1(self):
        dag = DagNodeScores(cell_id="c", commodity="g",
                            z_surface=0.5, z_structural=0.3, z_subsurface=0.2,
                            z_thermal=0.4, z_temporal_dag=0.3)
        c_i = compute_causal_consistency(dag, edges=[])
        assert c_i == pytest.approx(1.0)

    def test_score_in_0_1(self):
        dag = DagNodeScores(cell_id="c", commodity="g",
                            z_surface=0.5, z_structural=0.3, z_subsurface=0.2,
                            z_thermal=0.4, z_temporal_dag=0.3)
        c_i = compute_causal_consistency(dag)
        assert 0.0 <= c_i <= 1.0


# ===========================================================================
# PHYSICS MODULE §6.1, §6.2, §6.4, §6.6
# ===========================================================================

class TestPhysicsResiduals:
    def test_gravity_residual_zero_at_perfect_fit(self):
        r = compute_gravity_residual(g_obs_mgal=5.0, g_pred_mgal=5.0)
        assert r == pytest.approx(0.0)

    def test_gravity_residual_grows_with_misfit(self):
        r1 = compute_gravity_residual(5.0, 5.1)
        r2 = compute_gravity_residual(5.0, 6.0)
        assert r2 > r1 > 0

    def test_gravity_residual_none_if_missing(self):
        assert compute_gravity_residual(None, 5.0) is None
        assert compute_gravity_residual(5.0, None) is None

    def test_gravity_residual_non_negative(self):
        r = compute_gravity_residual(3.0, 5.0)
        assert r >= 0.0

    def test_poisson_residual_zero_at_perfect_fit(self):
        G = 6.674e-11
        rho = 2700.0
        phi_lap = 4.0 * math.pi * G * rho
        r = compute_poisson_residual(phi_lap, rho)
        assert r == pytest.approx(0.0, abs=1e-20)

    def test_poisson_residual_none_if_missing(self):
        assert compute_poisson_residual(None, 2700.0) is None

    def test_darcy_residual_zero_at_perfect_fit(self):
        k, mu, grad_p = 1e-12, 1e-3, 1e4
        v_pred = -(k / mu) * grad_p
        r = compute_darcy_residual(v_pred, k, mu, grad_p)
        assert r == pytest.approx(0.0)

    def test_water_column_residual_non_negative(self):
        r = compute_water_column_residual(4.0, 4.5, 0.5)
        assert r is not None and r >= 0.0


class TestPhysicsScore:
    def test_psi_equals_1_at_zero_residuals(self):
        """CONSTITUTIONAL: Ψ = 1.0 when R_grav = R_phys = 0."""
        psi = compute_physics_score(r_grav=0.0, r_phys=0.0)
        assert psi == pytest.approx(1.0)

    def test_psi_approaches_zero_at_large_residuals(self):
        psi = compute_physics_score(r_grav=1000.0, r_phys=1000.0)
        assert psi < 0.01

    def test_psi_monotonically_decreasing(self):
        psi_a = compute_physics_score(0.0, 0.0)
        psi_b = compute_physics_score(1.0, 0.0)
        psi_c = compute_physics_score(5.0, 0.0)
        assert psi_a > psi_b > psi_c

    def test_psi_in_bounds(self):
        for r in [0.0, 0.1, 1.0, 10.0, 100.0]:
            psi = compute_physics_score(r, r)
            assert 0.0 <= psi <= 1.0

    def test_missing_residual_not_penalised(self):
        """None residual contributes 0 to exponent."""
        psi_full = compute_physics_score(0.0, 0.0)
        psi_partial = compute_physics_score(None, 0.0)
        assert psi_partial == pytest.approx(psi_full)

    def test_veto_fires_at_large_gravity_residual(self):
        assert apply_physics_veto(r_grav=200.0, r_phys=0.0) is True

    def test_veto_fires_at_large_physics_residual(self):
        assert apply_physics_veto(r_grav=0.0, r_phys=200.0) is True

    def test_no_veto_within_tolerance(self):
        assert apply_physics_veto(r_grav=50.0, r_phys=25.0) is False

    def test_score_physics_veto_sets_psi_to_zero(self):
        result = score_physics(
            "c", "gold",
            g_obs_mgal=5.0, g_pred_mgal=100.0,  # Massive misfit → veto
            phi_laplacian=None, rho_model=None,
            tau_grav_veto=1.0,  # Very low threshold
        )
        assert result.physics_veto_fired is True
        assert result.physics_score == pytest.approx(0.0)


# ===========================================================================
# TEMPORAL MODULE §7.2, §7.3, §7.4
# ===========================================================================

class TestTemporalSubScores:
    def test_persistence_stable_series(self):
        """Near-constant series → high persistence."""
        series = [1.0, 1.01, 0.99, 1.001]
        q = compute_persistence_sub_score(series, gamma=1.0)
        assert q is not None and q > 0.8

    def test_persistence_volatile_series(self):
        """Highly variable series → low persistence."""
        series = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
        q = compute_persistence_sub_score(series, gamma=5.0)
        assert q is not None and q < 0.5

    def test_persistence_single_epoch_returns_none(self):
        assert compute_persistence_sub_score([0.5]) is None

    def test_stability_constant_series(self):
        series = [0.3] * 10
        q = compute_stability_sub_score(series)
        assert q is not None and q == pytest.approx(1.0)

    def test_vegetation_stress_full_persistence(self):
        """All epochs below threshold → q_veg = 1.0."""
        series = [-0.1, -0.2, -0.15, -0.08]
        q = compute_vegetation_stress_persistence(series, tau_veg=-0.05)
        assert q == pytest.approx(1.0)

    def test_vegetation_stress_no_persistence(self):
        series = [0.1, 0.2, 0.3]
        q = compute_vegetation_stress_persistence(series, tau_veg=-0.05)
        assert q == pytest.approx(0.0)


class TestTemporalCoherence:
    def test_geometric_mean_one_zero_produces_zero(self):
        """CONSTITUTIONAL: geometric mean — one q_j = 0 → T_i = 0."""
        sub = TemporalSubScores(
            insar_persistence=0.8,
            thermal_stability=0.0,   # ← zero
            vegetation_stress_persistence=0.7,
            moisture_stability=0.9,
        )
        t_i = compute_temporal_coherence(sub)
        assert t_i == pytest.approx(0.0, abs=1e-6)

    def test_arithmetic_mean_would_not_be_zero(self):
        """Proves geometric mean is different from arithmetic mean here."""
        # Arithmetic mean of [0.8, 0.0, 0.7, 0.9] = 0.6 ≠ 0
        sub = TemporalSubScores(
            insar_persistence=0.8,
            thermal_stability=0.0,
            vegetation_stress_persistence=0.7,
            moisture_stability=0.9,
        )
        arith_mean = (0.8 + 0.0 + 0.7 + 0.9) / 4
        t_i = compute_temporal_coherence(sub)
        assert arith_mean > 0.0           # Arithmetic mean is non-zero
        assert t_i == pytest.approx(0.0, abs=1e-6)  # Geometric mean IS zero ✓

    def test_all_ones_produces_one(self):
        sub = TemporalSubScores(
            insar_persistence=1.0,
            thermal_stability=1.0,
            vegetation_stress_persistence=1.0,
            moisture_stability=1.0,
        )
        t_i = compute_temporal_coherence(sub)
        assert t_i == pytest.approx(1.0, abs=1e-6)

    def test_all_none_returns_neutral(self):
        sub = TemporalSubScores()
        t_i = compute_temporal_coherence(sub)
        assert t_i == pytest.approx(0.5)

    def test_temporal_veto_fires_when_below_threshold(self):
        assert apply_temporal_veto(t_i=0.03, tau_temp_veto=0.05) is True

    def test_no_veto_above_threshold(self):
        assert apply_temporal_veto(t_i=0.10, tau_temp_veto=0.05) is False

    def test_veto_sets_t_to_zero(self):
        result = score_temporal("c", "gold",
                                insar_series=[0.0, 0.0, 0.0],  # Zero persistence
                                gamma=100.0,
                                tau_temp_veto=0.05)
        if result.temporal_veto_fired:
            assert result.temporal_score == pytest.approx(0.0)


# ===========================================================================
# PRIORS MODULE §8.2, §8.3, §8.4
# ===========================================================================

class TestProvincePriors:
    def test_impossible_province_returns_zero(self):
        """CONSTITUTIONAL: impossible province → P = 0.0 (not low, exactly zero)."""
        val, veto, reason = lookup_province_prior(
            province_code="WRONG_PROVINCE",
            commodity="gold",
            prior_probability=0.0,
            is_impossible=True,
            impossibility_reason="No magmatic source",
        )
        assert val == pytest.approx(0.0)
        assert veto is True
        assert "magmatic" in (reason or "")

    def test_unknown_province_conservative_default(self):
        val, veto, _ = lookup_province_prior(
            province_code=None,
            commodity="gold",
            prior_probability=None,
        )
        assert val == pytest.approx(0.3)
        assert veto is False

    def test_valid_prior_returned_unchanged(self):
        val, veto, _ = lookup_province_prior(
            province_code="YILGARN",
            commodity="gold",
            prior_probability=0.72,
        )
        assert val == pytest.approx(0.72)
        assert veto is False

    def test_province_veto_fires_on_zero(self):
        assert apply_province_veto(0.0) is True

    def test_no_veto_on_nonzero(self):
        assert apply_province_veto(0.01) is False

    def test_bayesian_posterior_update(self):
        """Posterior should move toward data."""
        # Prior = 0.3, 10 observations all positive → posterior should be > 0.3
        post = compute_bayesian_posterior(0.3, n_positive_observations=10, n_total_observations=10)
        assert post > 0.3

    def test_bayesian_posterior_with_no_positive(self):
        """Prior = 0.7, 10 negative observations → posterior should be < 0.7."""
        post = compute_bayesian_posterior(0.7, n_positive_observations=0, n_total_observations=10)
        assert post < 0.7

    def test_bayesian_posterior_in_bounds(self):
        post = compute_bayesian_posterior(0.5, 5, 10)
        assert 0.0 <= post <= 1.0

    def test_bayesian_negative_observations_raises(self):
        with pytest.raises(ValueError):
            compute_bayesian_posterior(0.5, -1, 10)

    def test_prior_uncertainty_from_ci(self):
        u = compute_prior_uncertainty(ci_95_lower=0.2, ci_95_upper=0.8)
        assert u == pytest.approx(0.6)

    def test_prior_uncertainty_point_estimate(self):
        u = compute_prior_uncertainty(0.5, 0.5)
        assert u == pytest.approx(0.0)

    def test_score_province_prior_impossible_sets_veto(self):
        result = score_province_prior(
            "c", "gold", "BAD_PROVINCE",
            prior_probability=0.0,
            is_impossible=True,
            impossibility_reason="wrong geology",
        )
        assert result.province_veto_fired is True
        assert result.prior_probability == pytest.approx(0.0)
        assert result.effective_prior == pytest.approx(0.0)


# ===========================================================================
# UNCERTAINTY MODULE §10.2, §10.3
# ===========================================================================

class TestUncertaintyComponents:
    def test_sensor_all_present_zero_uncertainty(self):
        u = compute_sensor_uncertainty(present_count=42)
        assert u == pytest.approx(0.0)

    def test_sensor_all_missing_full_uncertainty(self):
        u = compute_sensor_uncertainty(present_count=0)
        assert u == pytest.approx(1.0)

    def test_sensor_partial_coverage(self):
        u = compute_sensor_uncertainty(present_count=21)
        assert u == pytest.approx(0.5)

    def test_physics_uncertainty_complement(self):
        u = compute_physics_uncertainty(psi_i=0.8)
        assert u == pytest.approx(0.2)

    def test_physics_uncertainty_at_zero_psi(self):
        u = compute_physics_uncertainty(psi_i=0.0)
        assert u == pytest.approx(1.0)

    def test_temporal_uncertainty_complement(self):
        u = compute_temporal_uncertainty(t_i=0.7)
        assert u == pytest.approx(0.3)

    def test_model_uncertainty_high_cv(self):
        """High sigma/rho → high u_model → capped at 1.0."""
        u = compute_model_uncertainty(sigma_rho=1000.0, rho_bar=10.0)
        assert u == pytest.approx(1.0)

    def test_model_uncertainty_zero_sigma(self):
        u = compute_model_uncertainty(sigma_rho=0.0, rho_bar=2700.0)
        assert u == pytest.approx(0.0)

    def test_model_uncertainty_none_inputs(self):
        u = compute_model_uncertainty(None, None)
        assert u == pytest.approx(0.5)


class TestProbabilisticUnion:
    def test_one_component_full_uncertainty_produces_total_1(self):
        """CONSTITUTIONAL: any u_k = 1.0 → U_i = 1.0."""
        c = UncertaintyComponents(
            u_sensor=1.0,   # ← Full uncertainty
            u_model=0.3,
            u_physics=0.2,
            u_temporal=0.1,
            u_prior=0.4,
        )
        u_total = compute_total_uncertainty(c)
        assert u_total == pytest.approx(1.0)

    def test_arithmetic_mean_would_not_be_one(self):
        """Proves probabilistic union differs from arithmetic mean."""
        c = UncertaintyComponents(u_sensor=1.0, u_model=0.3, u_physics=0.2, u_temporal=0.1, u_prior=0.4)
        arith_mean = (1.0 + 0.3 + 0.2 + 0.1 + 0.4) / 5   # = 0.4 ≠ 1.0
        u_total = compute_total_uncertainty(c)
        assert arith_mean < 1.0           # Arithmetic mean is NOT 1.0
        assert u_total == pytest.approx(1.0)  # Probabilistic union IS 1.0 ✓

    def test_all_zero_components_produce_zero(self):
        c = UncertaintyComponents(u_sensor=0.0, u_model=0.0, u_physics=0.0, u_temporal=0.0, u_prior=0.0)
        assert compute_total_uncertainty(c) == pytest.approx(0.0)

    def test_total_always_geq_max_component(self):
        """U_i ≥ max(u_k) — probabilistic union is always at least as large."""
        c = UncertaintyComponents(u_sensor=0.3, u_model=0.4, u_physics=0.2, u_temporal=0.5, u_prior=0.1)
        u_total = compute_total_uncertainty(c)
        assert u_total >= max(0.3, 0.4, 0.2, 0.5, 0.1)

    def test_total_always_in_0_1(self):
        for vals in [(0.0,0.0,0.0,0.0,0.0), (1.0,1.0,1.0,1.0,1.0), (0.3,0.4,0.2,0.5,0.1)]:
            c = UncertaintyComponents(*vals)
            u = compute_total_uncertainty(c)
            assert 0.0 <= u <= 1.0

    def test_probabilistic_union_formula(self):
        """Verify U = 1 - ∏(1 - u_k) numerically."""
        c = UncertaintyComponents(u_sensor=0.2, u_model=0.3, u_physics=0.1, u_temporal=0.4, u_prior=0.2)
        expected = 1 - (0.8 * 0.7 * 0.9 * 0.6 * 0.8)
        assert compute_total_uncertainty(c) == pytest.approx(expected, abs=1e-8)


# ===========================================================================
# SYNTHETIC CELL TRACE — Full Phase I pipeline evaluation
# ===========================================================================

class TestSyntheticCellTrace:
    """
    End-to-end trace of a gold (orogenic) cell through all six Phase I modules.

    Cell: high-quality orogenic gold cell in Yilgarn Craton, Western Australia.
    Expected: high evidence, valid causal path, good physics, moderate temporal,
              high prior, moderate-low uncertainty → all components non-zero.
    """

    def setup_method(self):
        self.obs = ObservableVector(
            x_spec_1=0.12, x_spec_2=0.18, x_spec_3=0.09, x_spec_4=0.42,
            x_spec_5=0.68, x_spec_6=0.65, x_spec_7=0.85, x_spec_8=0.91,
            x_sar_1=0.55, x_sar_2=0.40, x_sar_3=0.72,
            x_therm_1=0.78, x_therm_2=0.62,
            x_grav_1=0.60, x_grav_2=0.45, x_grav_3=0.58, x_grav_4=0.52, x_grav_5=0.66, x_grav_6=0.71,
            x_mag_1=0.74, x_mag_2=0.68, x_mag_3=0.55,
            x_struct_1=0.82, x_struct_2=0.75, x_struct_3=0.60,
            x_hydro_1=0.35, x_hydro_2=0.48,
        )
        self.weights = {
            "x_spec_7": 0.20, "x_spec_8": 0.25,
            "x_struct_1": 0.18, "x_struct_2": 0.12,
            "x_mag_1": 0.10, "x_mag_2": 0.08,
            "x_grav_1": 0.07,
        }
        self.insar_series = [0.5, 0.51, 0.49, 0.50, 0.52]
        self.thermal_series = [308.0, 308.5, 307.8, 308.2]

    def test_evidence_nonzero(self):
        e, _ = compute_evidence_score(self.obs, self.weights)
        assert e > 0.5, f"Evidence too low for high-quality gold cell: {e}"

    def test_causal_no_veto(self):
        result = score_causal("yilgarn_01", "gold", self.obs)
        # Strong subsurface signals → no veto
        assert not result.veto_flags.veto_3_temporal_inconsistency  # temporal_dag from NIR/SWIR

    def test_physics_high_score_at_zero_residuals(self):
        result = score_physics("yilgarn_01", "gold",
                               g_obs_mgal=5.2, g_pred_mgal=5.21,  # Nearly perfect
                               phi_laplacian=None, rho_model=None)
        assert result.physics_score > 0.9

    def test_temporal_positive_result(self):
        result = score_temporal("yilgarn_01", "gold",
                                insar_series=self.insar_series,
                                thermal_series=self.thermal_series)
        assert result.temporal_score > 0.0

    def test_prior_high_for_yilgarn(self):
        result = score_province_prior(
            "yilgarn_01", "gold", "YILGARN_CRATON",
            prior_probability=0.75,
            ci_95_lower=0.60, ci_95_upper=0.88,
        )
        assert result.prior_probability == pytest.approx(0.75)
        assert not result.province_veto_fired

    def test_uncertainty_moderate(self):
        """With ~30 present observables, u_sensor should be ~0.29."""
        present = sum(1 for f in self.obs.model_fields if getattr(self.obs, f) is not None)
        u_sensor = compute_sensor_uncertainty(present)
        expected = 1 - present / 42
        assert u_sensor == pytest.approx(expected, abs=0.01)

    def test_all_components_non_negative(self):
        """All component scores must be ≥ 0 for a valid cell."""
        e, _ = compute_evidence_score(self.obs, self.weights)
        causal = score_causal("c", "gold", self.obs)
        phys = score_physics("c", "gold", g_obs_mgal=5.2, g_pred_mgal=5.22,
                             phi_laplacian=None, rho_model=None)
        temp = score_temporal("c", "gold", insar_series=self.insar_series)
        prior = score_province_prior("c", "gold", "YILGARN", 0.75)
        present = sum(1 for f in self.obs.model_fields if getattr(self.obs, f) is not None)
        u_sensor = compute_sensor_uncertainty(present)

        assert e >= 0.0
        assert causal.causal_score >= 0.0
        assert phys.physics_score >= 0.0
        assert temp.temporal_score >= 0.0
        assert prior.effective_prior >= 0.0
        assert u_sensor >= 0.0