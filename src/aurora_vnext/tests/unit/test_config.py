"""
Phase E — Configuration Layer Tests
"""

import pytest

from app.config.constants import (
    APP_NAME,
    OBSERVABLE_VECTOR_DIM,
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    SCAN_TIER_BOOTSTRAP,
    SCAN_TIER_PREMIUM,
    SCAN_TIER_SMART,
    THRESHOLD_SOURCE_AOI_PERCENTILE,
    THRESHOLD_SOURCE_COMMODITY_DEFAULT,
    THRESHOLD_SOURCE_GROUND_TRUTH,
    THRESHOLD_SOURCE_REPROCESSED,
)
from app.config.feature_flags import FLAGS
from app.config.versions import VERSION_DEFAULTS, get_version_registry_dict


class TestConstants:
    def test_app_name_defined(self):
        assert APP_NAME and isinstance(APP_NAME, str)

    def test_observable_vector_dim(self):
        assert OBSERVABLE_VECTOR_DIM == 42, (
            "Observable vector dimension must be 42 per Phase A observable registry"
        )

    def test_roles_defined(self):
        assert ROLE_ADMIN == "admin"
        assert ROLE_OPERATOR == "operator"
        assert ROLE_VIEWER == "viewer"

    def test_scan_tiers_defined(self):
        """Three-tier planetary scan funnel (Patent Breakthrough 11)"""
        assert SCAN_TIER_BOOTSTRAP == "BOOTSTRAP"
        assert SCAN_TIER_SMART == "SMART"
        assert SCAN_TIER_PREMIUM == "PREMIUM"

    def test_threshold_sources_defined(self):
        """All four allowed threshold provenance values from Phase B §13.3"""
        assert THRESHOLD_SOURCE_AOI_PERCENTILE == "aoi_percentile"
        assert THRESHOLD_SOURCE_COMMODITY_DEFAULT == "commodity_frozen_default"
        assert THRESHOLD_SOURCE_GROUND_TRUTH == "ground_truth_calibrated"
        assert THRESHOLD_SOURCE_REPROCESSED == "reprocessed_vX"


class TestFeatureFlags:
    def test_all_flags_off_at_scaffold(self):
        """All feature flags must be False at Phase E — no implementation yet."""
        flag_values = {
            "storage_layer_enabled": FLAGS.storage_layer_enabled,
            "observable_extraction_enabled": FLAGS.observable_extraction_enabled,
            "scientific_core_enabled": FLAGS.scientific_core_enabled,
            "scoring_engine_enabled": FLAGS.scoring_engine_enabled,
            "gee_integration_enabled": FLAGS.gee_integration_enabled,
            "scan_pipeline_enabled": FLAGS.scan_pipeline_enabled,
            "twin_builder_enabled": FLAGS.twin_builder_enabled,
            "auth_enforced": FLAGS.auth_enforced,
        }
        for flag_name, flag_value in flag_values.items():
            assert flag_value is False, (
                f"Feature flag '{flag_name}' must be False at Phase E scaffold. "
                f"Flags are enabled as implementation phases complete."
            )


class TestVersionRegistry:
    def test_version_defaults_frozen(self):
        """VersionDefaults is a frozen dataclass — must not be mutable."""
        import dataclasses
        assert dataclasses.is_dataclass(VERSION_DEFAULTS)
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            VERSION_DEFAULTS.score_version = "9.9.9"  # type: ignore

    def test_version_registry_dict_contains_all_fields(self):
        registry = get_version_registry_dict()
        required = [
            "score_version", "tier_version", "causal_graph_version",
            "physics_model_version", "temporal_model_version",
            "province_prior_version", "commodity_library_version",
            "scan_pipeline_version",
        ]
        for field in required:
            assert field in registry, f"Missing version registry field: {field}"

    def test_version_registry_dict_overrides_work(self):
        registry = get_version_registry_dict(overrides={"score_version": "1.2.3"})
        assert registry["score_version"] == "1.2.3"
        # Other fields unchanged
        assert registry["tier_version"] == VERSION_DEFAULTS.tier_version