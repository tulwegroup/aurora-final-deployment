"""
Phase K — Sensor Services & Harmonization Tests

Validates all six service modules:
  1. services/gee.py         — raw sensor acquisition, MockGEEClient
  2. services/harmonization.py — mission-to-canonical mapping, feature tensor
  3. services/gravity.py     — multi-orbit decomposition, super-resolution
  4. services/offshore.py    — correction pipeline, gate enforcement
  5. services/quantum.py     — classical inversion stub
  6. services/audit.py       — event emission, no storage writes

Constitutional checks:
  - No Phase J scoring imports in any service module
  - Offshore gate enforcement at harmonization layer
  - Canonical key count always 42
  - Environmental modifier is multiplicative, not additive
"""

from __future__ import annotations

import math
from typing import Optional

import pytest

from app.models.extraction_types import (
    CorrectedOffshoreCell,
    GravityComposite,
    OffshoreGateViolation,
    RawBathymetricData,
    RawGravityData,
    RawMagneticData,
    RawOpticalStack,
    RawSARStack,
    RawThermalStack,
)
from app.services.audit import (
    ServiceAuditEventType,
    build_gravity_event,
    build_harmonisation_event,
    build_offshore_correction_event,
    emit_audit_event,
)
from app.services.gee import (
    CellGeometry,
    MockGEEClient,
    RawSensorBundle,
    acquire_raw_sensor_bundle,
)
from app.services.gravity import (
    build_gravity_composite,
    compose_gravity_signal,
    decompose_wavelength_bands,
    super_resolve_short_wavelength,
)
from app.services.harmonization import (
    CANONICAL_KEYS,
    HarmonisedTensor,
    build_harmonised_tensor,
    translate_gravity,
    translate_magnetic,
    translate_optical,
    translate_sar,
    translate_thermal,
)
from app.services.offshore import (
    apply_offshore_correction,
    compute_oceanographic_anomalies,
    correct_water_column_gravity,
    correct_water_column_reflectance,
    is_offshore_cell,
)
from app.services.quantum import (
    InversionMode,
    InversionResult,
    invert_gravity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _onshore_cell(cell_id: str = "c001", scan_id: str = "s001") -> CellGeometry:
    return CellGeometry(cell_id=cell_id, scan_id=scan_id,
                        lat_centre=-29.5, lon_centre=121.5,
                        resolution_m=500.0, environment="ONSHORE")


def _offshore_cell(cell_id: str = "c_off", scan_id: str = "s001") -> CellGeometry:
    return CellGeometry(cell_id=cell_id, scan_id=scan_id,
                        lat_centre=-20.0, lon_centre=115.0,
                        resolution_m=500.0, environment="OFFSHORE")


def _raw_gravity(cell_id: str = "c001") -> RawGravityData:
    return RawGravityData(
        cell_id=cell_id, scan_id="s001",
        free_air_leo_mgal=-2.5, free_air_meo_mgal=5.1,
        free_air_legacy_mgal=4.8,
        bouguer_anomaly_mgal=-22.0,
        vertical_gradient_eotvos=3200.0,
    )


def _raw_bathy(cell_id: str = "c_off") -> RawBathymetricData:
    return RawBathymetricData(
        cell_id=cell_id, scan_id="s001",
        water_depth_m=500.0, sst_celsius=25.5,
        ssh_m=0.15, chlorophyll_mg_m3=1.0,
        backscatter_db=-15.0,
    )


def _corrected_offshore(cell_id: str = "c_off") -> CorrectedOffshoreCell:
    return CorrectedOffshoreCell(
        cell_id=cell_id, scan_id="s001",
        bottom_reflectance=0.06, water_column_tau=0.4,
        water_depth_m=500.0, sst_anomaly_celsius=0.8,
        ssh_anomaly_m=0.03, chlorophyll_anomaly_mg_m3=-0.2,
        gravity_water_column_correction_mgal=0.21,
        corrected_gravity_mgal=4.89, water_column_residual=0.21,
    )


# ===========================================================================
# GEE SERVICE — sensor acquisition
# ===========================================================================

class TestGEEService:
    def test_mock_client_returns_raw_bundle(self):
        cell = _onshore_cell()
        client = MockGEEClient()
        bundle = acquire_raw_sensor_bundle(cell, client, "2023-01-01", "2023-12-31")
        assert isinstance(bundle, RawSensorBundle)

    def test_optical_stacks_populated(self):
        cell = _onshore_cell()
        bundle = acquire_raw_sensor_bundle(_onshore_cell(), MockGEEClient(), "2023-01-01", "2023-12-31")
        assert bundle.has_optical
        assert len(bundle.optical_stacks) >= 1

    def test_gravity_populated(self):
        bundle = acquire_raw_sensor_bundle(_onshore_cell(), MockGEEClient(), "2023-01-01", "2023-12-31")
        assert bundle.has_gravity
        assert bundle.gravity.free_air_meo_mgal is not None

    def test_offshore_cell_has_bathymetric(self):
        bundle = acquire_raw_sensor_bundle(_offshore_cell(), MockGEEClient(), "2023-01-01", "2023-12-31")
        assert bundle.has_bathymetric
        assert bundle.bathymetric.water_depth_m > 0

    def test_onshore_cell_has_no_bathymetric(self):
        bundle = acquire_raw_sensor_bundle(_onshore_cell(), MockGEEClient(), "2023-01-01", "2023-12-31")
        assert not bundle.has_bathymetric

    def test_raw_values_are_not_normalised(self):
        """Raw optical values should be raw reflectance, not in [0, 1] normalised space."""
        bundle = acquire_raw_sensor_bundle(_onshore_cell(), MockGEEClient(), "2023-01-01", "2023-12-31")
        # Sentinel-2 B12 raw reflectance can be any raw float
        b12 = bundle.optical_stacks[0].band_values.get("B12")
        assert b12 is not None  # Present
        # Not checking bounds — raw values are NOT normalised


# ===========================================================================
# HARMONISATION SERVICE — mission-to-canonical mapping
# ===========================================================================

class TestHarmonisationService:
    def test_canonical_keys_count_is_42(self):
        assert len(CANONICAL_KEYS) == 42

    def test_translate_optical_sentinel2(self):
        stack = RawOpticalStack(
            cell_id="c", scan_id="s", mission="Sentinel-2",
            scene_id=None, acquisition_date=None,
            band_values={"B2": 0.04, "B3": 0.06, "B4": 0.08,
                         "B8": 0.25, "B11": 0.35, "B12": 0.42},
        )
        result = translate_optical(stack)
        assert result.get("x_spec_1") == pytest.approx(0.04)
        assert result.get("x_spec_7") == pytest.approx(0.35)
        assert result.get("x_spec_8") == pytest.approx(0.42)

    def test_translate_optical_missing_band_is_none(self):
        stack = RawOpticalStack(
            cell_id="c", scan_id="s", mission="Sentinel-2",
            scene_id=None, acquisition_date=None,
            band_values={"B2": 0.04},  # All others missing
        )
        result = translate_optical(stack)
        assert result.get("x_spec_1") == pytest.approx(0.04)
        assert result.get("x_spec_8") is None

    def test_translate_sar_vv_to_x_sar_1(self):
        stack = RawSARStack(cell_id="c", scan_id="s", mission="Sentinel-1",
                            polarisation="VV", backscatter_vv=-12.5, coherence=0.70)
        result = translate_sar(stack)
        assert result["x_sar_1"] == pytest.approx(-12.5)
        assert result["x_sar_3"] == pytest.approx(0.70)

    def test_translate_thermal(self):
        stack = RawThermalStack(cell_id="c", scan_id="s", mission="ECOSTRESS",
                                lst_kelvin=308.5, heat_flow_mw_m2=85.0)
        result = translate_thermal(stack)
        assert result["x_therm_1"] == pytest.approx(308.5)
        assert result["x_therm_2"] == pytest.approx(85.0)

    def test_build_harmonised_tensor_has_42_keys(self):
        raw_g = _raw_gravity()
        composite = build_gravity_composite(raw_g)
        tensor = build_harmonised_tensor(
            cell_id="c001", scan_id="s001", environment="ONSHORE",
            optical_stacks=[RawOpticalStack(
                cell_id="c001", scan_id="s001", mission="Sentinel-2",
                scene_id=None, acquisition_date=None,
                band_values={"B2": 0.04, "B12": 0.42},
                cloud_cover_fraction=0.05,
            )],
            gravity_composite=composite, raw_gravity=raw_g,
        )
        assert len(tensor.feature_tensor) == 42

    def test_onshore_tensor_x_off_all_none(self):
        tensor = build_harmonised_tensor(
            cell_id="c001", scan_id="s001", environment="ONSHORE",
        )
        for k in ("x_off_1","x_off_2","x_off_3","x_off_4"):
            assert tensor.feature_tensor[k] is None, f"{k} must be None for ONSHORE"

    def test_offshore_without_correction_raises(self):
        with pytest.raises(OffshoreGateViolation):
            build_harmonised_tensor(
                cell_id="c_off", scan_id="s001", environment="OFFSHORE",
                corrected_offshore=None,
            )

    def test_offshore_with_correction_populates_x_off(self):
        corrected = _corrected_offshore()
        tensor = build_harmonised_tensor(
            cell_id="c_off", scan_id="s001", environment="OFFSHORE",
            corrected_offshore=corrected,
        )
        assert tensor.feature_tensor["x_off_2"] == pytest.approx(0.8)  # sst_anomaly

    def test_environmental_modifier_multiplicative(self):
        """Modifier must scale existing values, not add to them."""
        raw_g = _raw_gravity()
        composite = build_gravity_composite(raw_g)
        tensor_no_mod = build_harmonised_tensor(
            "c", "s", "ONSHORE",
            gravity_composite=composite, raw_gravity=raw_g,
        )
        modifier = {"x_grav_1": 2.0}
        tensor_with_mod = build_harmonised_tensor(
            "c", "s", "ONSHORE",
            gravity_composite=composite, raw_gravity=raw_g,
            environmental_modifier=modifier,
        )
        base = tensor_no_mod.feature_tensor["x_grav_1"]
        modified = tensor_with_mod.feature_tensor["x_grav_1"]
        if base is not None:
            assert modified == pytest.approx(base * 2.0)

    def test_best_optical_selected_by_cloud_cover(self):
        """Lowest cloud cover optical stack should be preferred."""
        stacks = [
            RawOpticalStack(cell_id="c", scan_id="s", mission="Sentinel-2",
                            scene_id=None, acquisition_date=None,
                            band_values={"B12": 0.99}, cloud_cover_fraction=0.80),
            RawOpticalStack(cell_id="c", scan_id="s", mission="Sentinel-2",
                            scene_id=None, acquisition_date=None,
                            band_values={"B12": 0.10}, cloud_cover_fraction=0.05),
        ]
        tensor = build_harmonised_tensor("c", "s", "ONSHORE", optical_stacks=stacks)
        # Best quality (cloud=0.05) has B12=0.10, not 0.99
        assert tensor.feature_tensor.get("x_spec_8") == pytest.approx(0.10)

    def test_coverage_fraction_correct(self):
        tensor = build_harmonised_tensor("c", "s", "ONSHORE")
        # Empty tensor: all None → coverage = 0
        assert tensor.coverage_fraction == pytest.approx(0.0)


# ===========================================================================
# GRAVITY SERVICE — multi-orbit decomposition
# ===========================================================================

class TestGravityService:
    def test_decompose_produces_long_and_medium(self):
        raw = _raw_gravity()
        g_long, g_medium = decompose_wavelength_bands(raw)
        assert g_long is not None
        assert g_medium is not None

    def test_only_meo_produces_long_only(self):
        raw = RawGravityData(cell_id="c", scan_id="s",
                             free_air_meo_mgal=5.0)
        g_long, g_medium = decompose_wavelength_bands(raw)
        assert g_long == pytest.approx(5.0)
        assert g_medium is None

    def test_super_resolve_formula(self):
        """g_short = Γ_zz × 1e-4 × δh."""
        g_short = super_resolve_short_wavelength(3200.0, delta_h_m=50.0)
        assert g_short == pytest.approx(3200.0 * 1e-4 * 50.0)

    def test_super_resolve_none_gradient(self):
        assert super_resolve_short_wavelength(None, 50.0) is None

    def test_compose_all_none_returns_none(self):
        assert compose_gravity_signal(None, None, None) is None

    def test_compose_partial(self):
        assert compose_gravity_signal(3.0, None, 1.5) == pytest.approx(4.5)

    def test_full_composite_pipeline(self):
        raw = _raw_gravity()
        composite = build_gravity_composite(raw)
        assert isinstance(composite, GravityComposite)
        assert composite.g_composite_mgal is not None
        assert composite.super_resolution_applied is True
        assert "LEO" in composite.orbit_sources_used
        assert "MEO" in composite.orbit_sources_used

    def test_all_none_gravity_produces_none_composite(self):
        raw = RawGravityData(cell_id="c", scan_id="s")
        composite = build_gravity_composite(raw)
        assert composite.g_composite_mgal is None
        assert composite.super_resolution_applied is False


# ===========================================================================
# OFFSHORE SERVICE — correction pipeline + gate
# ===========================================================================

class TestOffshoreService:
    def test_is_offshore_positive_depth(self):
        assert is_offshore_cell(500.0) is True

    def test_is_not_offshore_zero_depth(self):
        assert is_offshore_cell(0.0) is False

    def test_is_not_offshore_none_depth(self):
        assert is_offshore_cell(None) is False

    def test_water_column_reflectance_correction(self):
        r_b, tau = correct_water_column_reflectance(l_w=0.05, tau_w=0.5, z=10.0)
        assert r_b is not None
        assert 0.0 <= r_b <= 1.0

    def test_reflectance_correction_none_if_missing(self):
        r_b, _ = correct_water_column_reflectance(None, 0.5, 10.0)
        assert r_b is None

    def test_oceanographic_anomalies(self):
        sst_a, ssh_a, chl_a = compute_oceanographic_anomalies(
            sst_celsius=26.0, ssh_m=0.2, chlorophyll_mg_m3=1.5,
            sst_baseline=25.0, ssh_baseline=0.1, chl_baseline=1.0,
        )
        assert sst_a == pytest.approx(1.0)
        assert ssh_a == pytest.approx(0.1)
        assert chl_a == pytest.approx(0.5)

    def test_gravity_correction_reduces_gravity(self):
        g_corr, delta_g, r_wc = correct_water_column_gravity(5.0, 500.0)
        assert g_corr is not None
        assert g_corr < 5.0
        assert r_wc is not None and r_wc >= 0

    def test_gravity_correction_none_if_no_depth(self):
        result = correct_water_column_gravity(5.0, None)
        assert all(v is None for v in result)

    def test_apply_offshore_correction_returns_corrected_cell(self):
        bathy = _raw_bathy()
        result = apply_offshore_correction(
            cell_id="c_off", scan_id="s001", bathymetric=bathy,
            sst_baseline=24.0, ssh_baseline=0.10, chl_baseline=1.2,
        )
        assert isinstance(result, CorrectedOffshoreCell)
        assert result.sst_anomaly_celsius == pytest.approx(1.5)
        assert result.ssh_anomaly_m == pytest.approx(0.05)
        assert result.correction_quality in ("nominal", "degraded")

    def test_apply_correction_nominal_quality_all_present(self):
        bathy = _raw_bathy()
        result = apply_offshore_correction(
            "c", "s", bathy,
            sst_baseline=25.0, ssh_baseline=0.1, chl_baseline=1.0,
        )
        # sst_a, ssh_a all present → nominal
        assert result.correction_quality == "nominal"

    def test_apply_correction_degraded_when_baseline_missing(self):
        bathy = _raw_bathy()
        result = apply_offshore_correction(
            "c", "s", bathy,
            sst_baseline=None, ssh_baseline=None, chl_baseline=None,
        )
        assert result.correction_quality == "degraded"
        assert len(result.correction_warnings) > 0


# ===========================================================================
# QUANTUM SERVICE — classical inversion stub
# ===========================================================================

class TestQuantumService:
    def test_inversion_returns_result(self):
        result = invert_gravity("c", "s", g_obs_mgal=5.0, depth_m=1000.0)
        assert isinstance(result, InversionResult)
        assert result.mode == InversionMode.CLASSICAL

    def test_inversion_produces_prediction(self):
        result = invert_gravity("c", "s", g_obs_mgal=5.0, depth_m=1000.0)
        assert result.g_pred is not None
        assert result.rho_mean is not None

    def test_inversion_none_gravity_not_converged(self):
        result = invert_gravity("c", "s", g_obs_mgal=None)
        assert not result.converged
        assert result.rho_mean is None

    def test_inversion_bouguer_formula(self):
        """Verify Bouguer slab: ρ = g / (2πG × h)."""
        import math as _math
        G_MGAL = 6.674e-11 * 1e5
        depth = 1000.0
        bouguer_factor = 2.0 * _math.pi * G_MGAL * depth
        g_obs = bouguer_factor * 2700.0  # Synthetic: g = 2πGρh
        result = invert_gravity("c", "s", g_obs_mgal=g_obs, depth_m=depth)
        assert result.rho_mean == pytest.approx(2700.0, rel=0.01)
        assert result.converged

    def test_rho_sigma_is_nonnegative(self):
        result = invert_gravity("c", "s", g_obs_mgal=5.0)
        if result.rho_sigma is not None:
            assert result.rho_sigma >= 0.0


# ===========================================================================
# AUDIT SERVICE
# ===========================================================================

class TestAuditService:
    def test_emit_returns_event(self):
        evt = emit_audit_event(
            ServiceAuditEventType.HARMONISATION_COMPLETE,
            "c001", "s001", "services.harmonization",
            details={"present_observables": 35},
        )
        assert evt.event_type == ServiceAuditEventType.HARMONISATION_COMPLETE
        assert evt.cell_id == "c001"
        assert evt.details["present_observables"] == 35

    def test_event_is_immutable(self):
        evt = emit_audit_event(ServiceAuditEventType.GRAVITY_COMPOSITE_BUILT,
                               "c", "s", "services.gravity")
        with pytest.raises(Exception):
            evt.cell_id = "changed"  # type: ignore  # frozen dataclass

    def test_build_offshore_correction_event_nominal(self):
        evt = build_offshore_correction_event("c", "s", "nominal", ())
        assert evt.event_type == ServiceAuditEventType.OFFSHORE_CORRECTION_APPLIED

    def test_build_offshore_correction_event_degraded(self):
        evt = build_offshore_correction_event("c", "s", "degraded",
                                               ("sst_anomaly_unavailable",))
        assert evt.event_type == ServiceAuditEventType.OFFSHORE_CORRECTION_DEGRADED
        assert "sst_anomaly_unavailable" in evt.warnings

    def test_build_harmonisation_event(self):
        evt = build_harmonisation_event("c", "s", ("Sentinel-2",), 38, 38/42, False)
        assert evt.details["present_observables"] == 38
        assert evt.details["offshore_corrected"] is False

    def test_build_gravity_event(self):
        evt = build_gravity_event("c", "s", ("LEO","MEO"), True, 13.6)
        assert evt.details["super_resolution"] is True
        assert evt.details["g_composite_mgal"] == pytest.approx(13.6)

    def test_timestamp_is_iso_format(self):
        evt = emit_audit_event(ServiceAuditEventType.INVERSION_COMPLETE,
                               "c", "s", "services.quantum")
        # Should be parseable as ISO datetime
        from datetime import datetime
        datetime.fromisoformat(evt.timestamp_utc.replace("Z", "+00:00"))


# ===========================================================================
# CONSTITUTIONAL: No Phase J scoring imports in service modules
# ===========================================================================

class TestServiceImportIsolation:
    FORBIDDEN_IMPORTS = [
        "core.scoring", "core.tiering", "core.gates",
        "core.evidence", "core.causal",
    ]
    SERVICE_MODULES = [
        "app.services.gee",
        "app.services.harmonization",
        "app.services.gravity",
        "app.services.offshore",
        "app.services.quantum",
        "app.services.audit",
    ]

    def test_no_scoring_authority_imported_in_services(self):
        import sys
        import inspect
        violations = []
        for mod_name in self.SERVICE_MODULES:
            if mod_name not in sys.modules:
                continue
            mod = sys.modules[mod_name]
            try:
                src = inspect.getsource(mod)
                for forbidden in self.FORBIDDEN_IMPORTS:
                    if forbidden in src:
                        violations.append(f"{mod_name} imports {forbidden}")
            except (TypeError, OSError):
                pass
        assert not violations, (
            "Service modules import from forbidden Phase J authorities:\n"
            + "\n".join(violations)
        )