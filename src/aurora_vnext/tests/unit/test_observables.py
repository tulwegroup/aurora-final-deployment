"""
Phase H — Observable Extraction Layer Tests

Validates:
  1. Normalisation engine — §3.2 z-score + clamping
  2. Missing observable handling — §3.3 null value + u_sensor=1.0
  3. Offshore gate enforcement — OffshoreGateViolation raised without correction
  4. Offshore correction pipeline — §9.2, §9.3, §9.5
  5. Gravity decomposition — §6.3 multi-orbit + super-resolution
  6. Harmonisation — mission-to-canonical mapping + feature tensor assembly
  7. Sub-score extraction — §4.1 modality weighted means
  8. ObservableVector construction — gate enforcement + field count
  9. Phase H import isolation — no imports from scoring, tiering, gates
"""

from __future__ import annotations

import math
import sys
from typing import Optional

import pytest

from app.core.normalisation import (
    OBSERVABLE_KEYS,
    compute_coverage_stats,
    compute_scan_normalisation_params,
    handle_missing_observable,
    normalise_observable,
)
from app.core.observables import (
    build_observable_vector,
    extract_gravity_sub_score,
    extract_hydro_sub_score,
    extract_magnetic_sub_score,
    extract_offshore_sub_score,
    extract_sar_sub_score,
    extract_spectral_sub_score,
    extract_structural_sub_score,
    extract_thermal_sub_score,
)
from app.models.extraction_types import (
    CorrectedOffshoreCell,
    GravityComposite,
    MissingObservable,
    ObservableNormParams,
    OffshoreGateViolation,
    RawBathymetricData,
    RawGravityData,
    RawMagneticData,
    RawOpticalStack,
    RawSARStack,
    ScanNormalisationParams,
)
from app.services.gravity import (
    build_gravity_composite,
    compose_g_composite,
    decompose_gravity_multi_orbit,
    super_resolve_short_wavelength,
)
from app.services.harmonization import build_universal_feature_tensor
from app.services.offshore import (
    apply_offshore_correction,
    compute_oceanographic_anomalies,
    correct_water_column_gravity,
    correct_water_column_reflectance,
    is_offshore_cell,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_norm_params(mu: float = 0.5, sigma: float = 1.0) -> ObservableNormParams:
    return ObservableNormParams(
        observable_key="x_spec_1", mu=mu, sigma=sigma, n_samples=100
    )


def make_raw_gravity(
    leo: float = -2.5,
    meo: float = 5.0,
    legacy: float = 4.8,
    bouguer: float = -8.0,
    vgrad: float = 3000.0,
) -> RawGravityData:
    return RawGravityData(
        cell_id="c001", scan_id="s001",
        free_air_leo_mgal=leo,
        free_air_meo_mgal=meo,
        free_air_legacy_mgal=legacy,
        bouguer_anomaly_mgal=bouguer,
        vertical_gradient_eotvos=vgrad,
    )


def make_corrected_offshore(cell_id: str = "c001") -> CorrectedOffshoreCell:
    return CorrectedOffshoreCell(
        cell_id=cell_id, scan_id="s001",
        bottom_reflectance=0.08,
        water_column_tau=0.3,
        water_depth_m=120.0,
        sst_anomaly_celsius=0.5,
        ssh_anomaly_m=-0.02,
        chlorophyll_anomaly_mg_m3=0.15,
        gravity_water_column_correction_mgal=0.45,
        corrected_gravity_mgal=4.55,
        water_column_residual=0.45,
    )


def _all_none_normalised() -> dict[str, Optional[float]]:
    return {k: None for k in OBSERVABLE_KEYS}


# ---------------------------------------------------------------------------
# §3.2 — Normalisation engine
# ---------------------------------------------------------------------------

class TestNormalisationEngine:
    def test_at_mean_produces_0_5(self):
        """Value at μ should normalise to ~0.5 (midpoint)."""
        p = make_norm_params(mu=10.0, sigma=5.0)
        result, u_sensor = normalise_observable(raw_value=10.0, norm_params=p)
        assert result is not None
        assert result == pytest.approx(0.5, abs=0.01)
        assert u_sensor == pytest.approx(0.0)

    def test_above_mean_produces_above_0_5(self):
        p = make_norm_params(mu=10.0, sigma=5.0)
        result, _ = normalise_observable(raw_value=20.0, norm_params=p)
        assert result is not None and result > 0.5

    def test_below_mean_produces_below_0_5(self):
        p = make_norm_params(mu=10.0, sigma=5.0)
        result, _ = normalise_observable(raw_value=0.0, norm_params=p)
        assert result is not None and result < 0.5

    def test_extreme_value_clamped_to_1(self):
        """Values far above μ must be clamped to 1.0."""
        p = make_norm_params(mu=0.0, sigma=1.0)
        result, _ = normalise_observable(raw_value=1000.0, norm_params=p)
        assert result == pytest.approx(1.0)

    def test_extreme_low_value_clamped_to_0(self):
        """Values far below μ must be clamped to 0.0."""
        p = make_norm_params(mu=0.0, sigma=1.0)
        result, _ = normalise_observable(raw_value=-1000.0, norm_params=p)
        assert result == pytest.approx(0.0)

    def test_output_always_in_0_1(self):
        """Normalised output must always be in [0, 1]."""
        p = make_norm_params(mu=5.0, sigma=2.0)
        for raw in [-100.0, 0.0, 2.5, 5.0, 7.5, 100.0]:
            result, _ = normalise_observable(raw, p)
            assert result is not None
            assert 0.0 <= result <= 1.0, f"Out of bounds for raw={raw}: {result}"


# ---------------------------------------------------------------------------
# §3.3 — Missing observable handling
# ---------------------------------------------------------------------------

class TestMissingObservableHandling:
    def test_none_raw_returns_none_and_full_u_sensor(self):
        """§3.3: None raw value → normalised=None, u_sensor=1.0"""
        p = make_norm_params()
        result, u_sensor = normalise_observable(None, p)
        assert result is None
        assert u_sensor == pytest.approx(1.0)

    def test_missing_observable_default_0_5(self):
        """§3.3: MissingObservable normalised_value must be 0.5 (not 0)."""
        m = handle_missing_observable("x_spec_1", "cloud")
        assert m.normalised_value == pytest.approx(0.5)
        assert m.u_sensor_contribution == pytest.approx(1.0)
        assert m.key == "x_spec_1"

    def test_zero_is_not_missing(self):
        """0.0 raw value is a valid measured zero, not missing."""
        p = make_norm_params(mu=5.0, sigma=2.0)
        result, u_sensor = normalise_observable(0.0, p)
        assert result is not None
        assert u_sensor == pytest.approx(0.0)  # Present observable

    def test_coverage_stats_all_missing(self):
        values = {k: None for k in OBSERVABLE_KEYS}
        present, missing, fraction = compute_coverage_stats(values)
        assert present == 0
        assert missing == 42
        assert fraction == pytest.approx(0.0)

    def test_coverage_stats_partial(self):
        values = {k: None for k in OBSERVABLE_KEYS}
        values["x_spec_1"] = 0.5
        values["x_grav_1"] = 0.3
        values["x_mag_1"] = 0.7
        present, missing, fraction = compute_coverage_stats(values)
        assert present == 3
        assert missing == 39
        assert fraction == pytest.approx(3 / 42)


# ---------------------------------------------------------------------------
# Observable keys constant
# ---------------------------------------------------------------------------

class TestObservableKeys:
    def test_exactly_42_keys(self):
        assert len(OBSERVABLE_KEYS) == 42

    def test_all_groups_present(self):
        keys = set(OBSERVABLE_KEYS)
        for prefix in ("x_spec_", "x_sar_", "x_therm_", "x_grav_",
                       "x_mag_", "x_struct_", "x_hydro_", "x_off_"):
            matching = [k for k in keys if k.startswith(prefix)]
            assert len(matching) > 0, f"No keys found for prefix {prefix}"


# ---------------------------------------------------------------------------
# §9.2 — Water-column reflectance correction
# ---------------------------------------------------------------------------

class TestWaterColumnReflectanceCorrection:
    def test_correction_with_valid_inputs(self):
        r_b, tau = correct_water_column_reflectance(l_w=0.05, tau_w=0.5, z=10.0)
        assert r_b is not None
        assert 0.0 <= r_b <= 1.0
        assert tau == pytest.approx(0.5)

    def test_none_l_w_returns_none(self):
        r_b, tau = correct_water_column_reflectance(l_w=None, tau_w=0.5, z=10.0)
        assert r_b is None

    def test_zero_depth_returns_none(self):
        r_b, tau = correct_water_column_reflectance(l_w=0.05, tau_w=0.5, z=0.0)
        assert r_b is None

    def test_very_deep_water_returns_none(self):
        """Extreme optical depth makes bottom reflectance unrecoverable."""
        r_b, tau = correct_water_column_reflectance(l_w=0.01, tau_w=100.0, z=5000.0)
        assert r_b is None  # attenuation_factor < 1e-10


# ---------------------------------------------------------------------------
# §9.3 — Oceanographic anomalies
# ---------------------------------------------------------------------------

class TestOceanographicAnomalies:
    def test_positive_anomaly(self):
        sst_anom, _, _ = compute_oceanographic_anomalies(
            sst_celsius=26.5, ssh_m=None, chlorophyll_mg_m3=None,
            sst_baseline=25.0, ssh_baseline=None, chl_baseline=None,
        )
        assert sst_anom == pytest.approx(1.5)

    def test_negative_anomaly(self):
        _, ssh_anom, _ = compute_oceanographic_anomalies(
            sst_celsius=None, ssh_m=0.3, chlorophyll_mg_m3=None,
            sst_baseline=None, ssh_baseline=0.5, chl_baseline=None,
        )
        assert ssh_anom == pytest.approx(-0.2)

    def test_missing_baseline_returns_none(self):
        sst_anom, _, _ = compute_oceanographic_anomalies(
            sst_celsius=25.0, ssh_m=None, chlorophyll_mg_m3=None,
            sst_baseline=None, ssh_baseline=None, chl_baseline=None,
        )
        assert sst_anom is None


# ---------------------------------------------------------------------------
# §9.5 — Water-column gravity correction
# ---------------------------------------------------------------------------

class TestWaterColumnGravityCorrection:
    def test_correction_produces_valid_output(self):
        g_corr, delta_g, r_wc = correct_water_column_gravity(
            g_observed_mgal=5.0, lat_deg=-30.0, lon_deg=120.0, water_depth_m=200.0
        )
        assert g_corr is not None
        assert delta_g is not None and delta_g > 0
        assert r_wc is not None and r_wc >= 0
        # Corrected gravity should be less than observed (water column removed)
        assert g_corr < 5.0

    def test_zero_depth_returns_none(self):
        result = correct_water_column_gravity(5.0, 0.0, 0.0, water_depth_m=0.0)
        assert all(v is None for v in result)

    def test_none_observation_returns_none(self):
        result = correct_water_column_gravity(None, 0.0, 0.0, water_depth_m=200.0)
        assert all(v is None for v in result)

    def test_residual_is_non_negative(self):
        _, _, r_wc = correct_water_column_gravity(
            g_observed_mgal=-3.0, lat_deg=0.0, lon_deg=0.0, water_depth_m=500.0
        )
        assert r_wc is not None and r_wc >= 0


# ---------------------------------------------------------------------------
# Offshore gate enforcement
# ---------------------------------------------------------------------------

class TestOffshoreGateEnforcement:
    def test_is_offshore_with_positive_water_depth(self):
        assert is_offshore_cell(lat=-20.0, lon=100.0, water_depth_m=120.0) is True

    def test_is_not_offshore_with_zero_depth(self):
        assert is_offshore_cell(lat=51.5, lon=-0.1, water_depth_m=0.0) is False

    def test_is_not_offshore_with_none_depth(self):
        assert is_offshore_cell(lat=51.5, lon=-0.1, water_depth_m=None) is False

    def test_build_observable_vector_offshore_without_correction_raises(self):
        """§9: offshore cell without CorrectedOffshoreCell must raise OffshoreGateViolation."""
        values = {k: 0.5 for k in OBSERVABLE_KEYS}
        with pytest.raises(OffshoreGateViolation):
            build_observable_vector(values, corrected_offshore=None, environment="OFFSHORE")

    def test_extract_offshore_sub_score_without_correction_raises(self):
        """§9.4: offshore sub-score extraction without gate proof raises."""
        values = {k: 0.5 for k in OBSERVABLE_KEYS}
        with pytest.raises(OffshoreGateViolation):
            extract_offshore_sub_score(corrected_cell=None, normalised_values=values)

    def test_build_feature_tensor_offshore_without_correction_raises(self):
        """Harmonisation must raise for offshore cells without correction."""
        with pytest.raises(OffshoreGateViolation):
            build_universal_feature_tensor(
                cell_id="c001",
                environment="OFFSHORE",
                corrected_offshore=None,  # MISSING
            )

    def test_apply_offshore_correction_returns_corrected_cell(self):
        bathy = RawBathymetricData(
            cell_id="c001", scan_id="s001",
            water_depth_m=150.0,
            sst_celsius=28.5,
            ssh_m=0.15,
            chlorophyll_mg_m3=1.2,
        )
        result = apply_offshore_correction(
            cell_id="c001", scan_id="s001",
            bathymetric=bathy, gravity=None,
            sst_baseline=27.0, ssh_baseline=0.1, chl_baseline=1.0,
        )
        assert isinstance(result, CorrectedOffshoreCell)
        assert result.sst_anomaly_celsius == pytest.approx(1.5)
        assert result.ssh_anomaly_m == pytest.approx(0.05)
        assert result.correction_quality in ("nominal", "degraded")


# ---------------------------------------------------------------------------
# §6.3 — Gravity decomposition
# ---------------------------------------------------------------------------

class TestGravityDecomposition:
    def test_multi_orbit_produces_long_and_medium(self):
        raw = make_raw_gravity()
        g_long, g_medium, g_short = decompose_gravity_multi_orbit(raw)
        assert g_long is not None
        assert g_medium is not None
        assert g_short is None  # short-wavelength requires vertical gradient separately

    def test_super_resolution_with_valid_gradient(self):
        g_short = super_resolve_short_wavelength(gamma_zz_eotvos=3000.0, delta_h_m=50.0)
        assert g_short is not None
        assert g_short == pytest.approx(3000.0 * 1e-4 * 50.0)

    def test_super_resolution_with_none_gradient_returns_none(self):
        g_short = super_resolve_short_wavelength(gamma_zz_eotvos=None, delta_h_m=50.0)
        assert g_short is None

    def test_composite_all_none_returns_none(self):
        assert compose_g_composite(None, None, None) is None

    def test_composite_partial_none_sums_available(self):
        result = compose_g_composite(g_long=5.0, g_medium=None, g_short=1.0)
        assert result == pytest.approx(6.0)

    def test_build_gravity_composite_full_pipeline(self):
        raw = make_raw_gravity()
        composite = build_gravity_composite(raw)
        assert isinstance(composite, GravityComposite)
        assert composite.g_composite_mgal is not None
        assert composite.super_resolution_applied is True
        assert "LEO" in composite.orbit_sources_used
        assert "MEO" in composite.orbit_sources_used

    def test_build_composite_with_no_data(self):
        raw = RawGravityData(cell_id="c", scan_id="s")
        composite = build_gravity_composite(raw)
        assert composite.g_composite_mgal is None
        assert composite.super_resolution_applied is False


# ---------------------------------------------------------------------------
# §4.1 — Modality sub-score extraction
# ---------------------------------------------------------------------------

class TestModalitySubScores:
    def _vals(self, **overrides) -> dict[str, Optional[float]]:
        base = {k: None for k in OBSERVABLE_KEYS}
        base.update(overrides)
        return base

    def test_spectral_sub_score_mean_of_present(self):
        vals = self._vals(x_spec_1=0.6, x_spec_2=0.8)
        s = extract_spectral_sub_score(vals)
        assert s == pytest.approx(0.7)

    def test_spectral_all_missing_returns_none(self):
        vals = self._vals()
        assert extract_spectral_sub_score(vals) is None

    def test_gravity_sub_score_uniform(self):
        vals = self._vals(x_grav_1=0.4, x_grav_2=0.4, x_grav_3=0.4)
        g = extract_gravity_sub_score(vals)
        assert g == pytest.approx(0.4)

    def test_sar_sub_score_single_value(self):
        vals = self._vals(x_sar_1=0.75)
        r = extract_sar_sub_score(vals)
        assert r == pytest.approx(0.75)

    def test_thermal_sub_score_weighted(self):
        vals = self._vals(x_therm_1=0.9, x_therm_2=0.5)
        weights = {"x_therm_1": 2.0, "x_therm_2": 1.0}
        t = extract_thermal_sub_score(vals, weights=weights)
        # weighted: (2*0.9 + 1*0.5) / (2+1) = 2.3/3 ≈ 0.767
        assert t == pytest.approx(2.3 / 3.0, abs=0.001)

    def test_magnetic_all_none_returns_none(self):
        vals = self._vals()
        assert extract_magnetic_sub_score(vals) is None

    def test_structural_sub_score_in_bounds(self):
        vals = self._vals(x_struct_1=0.3, x_struct_2=0.7)
        result = extract_structural_sub_score(vals)
        assert result is not None
        assert 0.0 <= result <= 1.0

    def test_hydro_sub_score_in_bounds(self):
        vals = self._vals(x_hydro_1=0.2, x_hydro_4=0.6)
        result = extract_hydro_sub_score(vals)
        assert result is not None
        assert 0.0 <= result <= 1.0

    def test_offshore_sub_score_with_correction(self):
        vals = self._vals(x_off_1=0.4, x_off_2=0.6, x_off_3=0.5, x_off_4=0.7)
        corrected = make_corrected_offshore()
        result = extract_offshore_sub_score(corrected, vals)
        assert result == pytest.approx((0.4 + 0.6 + 0.5 + 0.7) / 4)

    def test_offshore_sub_score_all_none_returns_none(self):
        vals = self._vals()  # all x_off_* are None
        corrected = make_corrected_offshore()
        result = extract_offshore_sub_score(corrected, vals)
        assert result is None


# ---------------------------------------------------------------------------
# ObservableVector construction
# ---------------------------------------------------------------------------

class TestObservableVectorConstruction:
    def test_onshore_vector_has_none_offshore_fields(self):
        vals = {k: 0.5 for k in OBSERVABLE_KEYS}
        # Set x_off_* to non-None to test they are cleared for onshore
        vals["x_off_1"] = 0.9
        vec = build_observable_vector(vals, corrected_offshore=None, environment="ONSHORE")
        assert vec.x_off_1 is None
        assert vec.x_off_2 is None

    def test_offshore_vector_preserves_offshore_fields(self):
        vals = {k: 0.5 for k in OBSERVABLE_KEYS}
        vals["x_off_1"] = 0.3
        vals["x_off_2"] = 0.4
        corrected = make_corrected_offshore()
        vec = build_observable_vector(vals, corrected_offshore=corrected, environment="OFFSHORE")
        assert vec.x_off_1 == pytest.approx(0.3)
        assert vec.x_off_2 == pytest.approx(0.4)

    def test_all_values_in_bounds(self):
        vals = {k: 0.7 for k in OBSERVABLE_KEYS}
        vec = build_observable_vector(vals, environment="ONSHORE")
        for key in vec.model_fields:
            v = getattr(vec, key)
            if v is not None:
                assert 0.0 <= v <= 1.0

    def test_vector_has_42_fields(self):
        assert len(OBSERVABLE_KEYS) == 42


# ---------------------------------------------------------------------------
# Scan-level normalisation parameter computation
# ---------------------------------------------------------------------------

class TestScanNormalisationParams:
    def test_computes_params_for_all_42_keys(self):
        stacks = [
            {k: float(i) * 0.1 for k in OBSERVABLE_KEYS}
            for i in range(20)
        ]
        params = compute_scan_normalisation_params(stacks, scan_id="s001")
        assert len(params.params) == 42
        for key in OBSERVABLE_KEYS:
            assert key in params.params

    def test_mu_matches_population_mean(self):
        """μ_k must equal the arithmetic mean of non-null raw values."""
        stacks = [{"x_spec_1": float(v)} for v in [10.0, 20.0, 30.0]]
        params = compute_scan_normalisation_params(stacks, scan_id="s_mu_test")
        p = params.get("x_spec_1")
        assert p is not None
        assert p.mu == pytest.approx(20.0)

    def test_fallback_for_sparse_key(self):
        """Keys with < 5 samples use fallback μ=0.5, σ=1.0."""
        stacks = [{"x_spec_1": 1.0}] * 3  # Only 3 samples
        params = compute_scan_normalisation_params(stacks, scan_id="s_sparse")
        p = params.get("x_spec_1")
        assert p is not None
        assert p.mu == pytest.approx(0.5)
        assert p.sigma == pytest.approx(1.0)

    def test_params_are_per_scan_not_global(self):
        """Different AOIs must produce different normalisation parameters."""
        stacks_a = [{"x_spec_1": float(v)} for v in range(10, 20)]
        stacks_b = [{"x_spec_1": float(v)} for v in range(100, 110)]
        params_a = compute_scan_normalisation_params(stacks_a, scan_id="a")
        params_b = compute_scan_normalisation_params(stacks_b, scan_id="b")
        mu_a = params_a.get("x_spec_1").mu
        mu_b = params_b.get("x_spec_1").mu
        assert mu_a != pytest.approx(mu_b), "Different AOIs must produce different μ_k"

    def test_jsonb_serialisation(self):
        stacks = [{k: 0.5 for k in OBSERVABLE_KEYS}] * 10
        params = compute_scan_normalisation_params(stacks, scan_id="s001")
        jsonb = params.as_jsonb_dict()
        assert len(jsonb) == 42
        for v in jsonb.values():
            assert "mu" in v
            assert "sigma" in v
            assert "n_samples" in v


# ---------------------------------------------------------------------------
# Phase H import isolation
# ---------------------------------------------------------------------------

class TestPhaseHImportIsolation:
    """Verifies no Phase H module imports from scoring, tiering, or gates."""

    PHASE_H_MODULES = [
        "app.core.observables",
        "app.core.normalisation",
        "app.services.offshore",
        "app.services.gravity",
        "app.services.harmonization",
        "app.models.extraction_types",
    ]

    FORBIDDEN_IMPORTS = [
        "app.core.scoring",
        "app.core.tiering",
        "app.core.gates",
    ]

    def test_no_scoring_imports_in_phase_h(self):
        import inspect
        violations = []
        for module_name in self.PHASE_H_MODULES:
            if module_name not in sys.modules:
                continue
            module = sys.modules[module_name]
            try:
                source = inspect.getsource(module)
                for forbidden in self.FORBIDDEN_IMPORTS:
                    if forbidden in source:
                        violations.append(f"{module_name} imports {forbidden}")
            except (TypeError, OSError):
                pass
        assert not violations, (
            "Phase H modules import from forbidden scoring/tiering/gates layers:\n"
            + "\n".join(violations)
        )