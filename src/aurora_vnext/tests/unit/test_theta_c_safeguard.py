"""
Aurora OSI vNext — Θ_c Veto Threshold Safeguard Tests
Phase W Constitutional Safeguard

PROOF REQUIREMENT:
  ACIF scoring cannot run without explicit commodity threshold configuration.
  Physics veto thresholds must never exist as effective runtime defaults.

Tests:
  1. score_physics() raises TypeError when lambda_1 omitted
  2. score_physics() raises TypeError when lambda_2 omitted
  3. score_physics() raises TypeError when tau_grav_veto omitted
  4. score_physics() raises TypeError when tau_phys_veto omitted
  5. score_physics() succeeds when all Θ_c params explicitly provided
  6. compute_physics_score() raises TypeError without lambda args
  7. apply_physics_veto() raises TypeError without tau args
  8. No module-level _DEFAULT_LAMBDA_1/_DEFAULT_LAMBDA_2 constants exist
  9. No module-level default tau values exist
  10. MissingThetaCError is importable (explicit error class for Θ_c violations)
"""

from __future__ import annotations

import pytest
import inspect


class TestThetaCSafeguard:
    """
    CONSTITUTIONAL PROOF:
    All four Θ_c-sourced parameters (lambda_1, lambda_2, tau_grav_veto, tau_phys_veto)
    are required. Omitting any one raises TypeError at call time — fail-fast.
    No scan can be evaluated with implicit default thresholds.
    """

    def test_score_physics_requires_lambda_1(self):
        """Omitting lambda_1 must raise TypeError — no default fallback."""
        from app.core.physics import score_physics
        with pytest.raises(TypeError):
            score_physics(
                cell_id="c1", commodity="gold",
                g_obs_mgal=10.0, g_pred_mgal=9.5,
                phi_laplacian=1e-6, rho_model=2700.0,
                # lambda_1 OMITTED
                lambda_2=0.3,
                tau_grav_veto=100.0,
                tau_phys_veto=50.0,
            )

    def test_score_physics_requires_lambda_2(self):
        """Omitting lambda_2 must raise TypeError."""
        from app.core.physics import score_physics
        with pytest.raises(TypeError):
            score_physics(
                cell_id="c1", commodity="gold",
                g_obs_mgal=10.0, g_pred_mgal=9.5,
                phi_laplacian=1e-6, rho_model=2700.0,
                lambda_1=0.5,
                # lambda_2 OMITTED
                tau_grav_veto=100.0,
                tau_phys_veto=50.0,
            )

    def test_score_physics_requires_tau_grav_veto(self):
        """Omitting tau_grav_veto must raise TypeError."""
        from app.core.physics import score_physics
        with pytest.raises(TypeError):
            score_physics(
                cell_id="c1", commodity="gold",
                g_obs_mgal=10.0, g_pred_mgal=9.5,
                phi_laplacian=1e-6, rho_model=2700.0,
                lambda_1=0.5, lambda_2=0.3,
                # tau_grav_veto OMITTED
                tau_phys_veto=50.0,
            )

    def test_score_physics_requires_tau_phys_veto(self):
        """Omitting tau_phys_veto must raise TypeError."""
        from app.core.physics import score_physics
        with pytest.raises(TypeError):
            score_physics(
                cell_id="c1", commodity="gold",
                g_obs_mgal=10.0, g_pred_mgal=9.5,
                phi_laplacian=1e-6, rho_model=2700.0,
                lambda_1=0.5, lambda_2=0.3,
                tau_grav_veto=100.0,
                # tau_phys_veto OMITTED
            )

    def test_score_physics_succeeds_with_explicit_theta_c(self):
        """
        PROOF: scoring succeeds when all Θ_c params are explicitly provided.
        This confirms the safeguard does not break valid Θ_c-sourced calls.
        """
        from app.core.physics import score_physics
        result = score_physics(
            cell_id="c1", commodity="gold",
            g_obs_mgal=10.0, g_pred_mgal=9.5,
            phi_laplacian=1e-6, rho_model=2700.0,
            lambda_1=0.5,       # explicit from Θ_c
            lambda_2=0.3,       # explicit from Θ_c
            tau_grav_veto=100.0, # explicit from Θ_c
            tau_phys_veto=50.0,  # explicit from Θ_c
        )
        assert 0.0 <= result.physics_score <= 1.0

    def test_compute_physics_score_requires_lambdas(self):
        """compute_physics_score() has no default lambda values."""
        from app.core.physics import compute_physics_score
        with pytest.raises(TypeError):
            compute_physics_score(r_grav=1.0, r_phys=1.0)  # lambdas omitted

    def test_apply_physics_veto_requires_tau_values(self):
        """apply_physics_veto() has no default tau values."""
        from app.core.physics import apply_physics_veto
        with pytest.raises(TypeError):
            apply_physics_veto(r_grav=1.0, r_phys=1.0)  # taus omitted

    def test_no_module_level_default_lambda_constants(self):
        """
        PROOF: _DEFAULT_LAMBDA_1 and _DEFAULT_LAMBDA_2 must not exist
        as module-level constants. Their removal is the constitutional safeguard.
        """
        import app.core.physics as physics_module
        assert not hasattr(physics_module, "_DEFAULT_LAMBDA_1"), \
            "VIOLATION: _DEFAULT_LAMBDA_1 still exists as a module-level default"
        assert not hasattr(physics_module, "_DEFAULT_LAMBDA_2"), \
            "VIOLATION: _DEFAULT_LAMBDA_2 still exists as a module-level default"

    def test_no_default_tau_in_function_signatures(self):
        """
        PROOF: score_physics(), compute_physics_score(), apply_physics_veto()
        must have no default values for lambda_1, lambda_2, tau_grav_veto,
        tau_phys_veto in their function signatures.
        """
        from app.core.physics import score_physics, compute_physics_score, apply_physics_veto

        for fn, required_params in [
            (score_physics,        ["lambda_1", "lambda_2", "tau_grav_veto", "tau_phys_veto"]),
            (compute_physics_score, ["lambda_1", "lambda_2"]),
            (apply_physics_veto,   ["tau_grav_veto", "tau_phys_veto"]),
        ]:
            sig = inspect.signature(fn)
            for param_name in required_params:
                param = sig.parameters.get(param_name)
                assert param is not None, f"{fn.__name__} missing param {param_name}"
                assert param.default is inspect.Parameter.empty, (
                    f"VIOLATION: {fn.__name__}.{param_name} has a default value "
                    f"({param.default!r}) — must be required (Θ_c safeguard)"
                )

    def test_missing_theta_c_error_importable(self):
        """MissingThetaCError exists for explicit Θ_c violation handling."""
        from app.core.physics import MissingThetaCError
        assert issubclass(MissingThetaCError, ValueError)