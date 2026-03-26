"""
Aurora OSI vNext — Version Registry
Defines the system version registry defaults and validation.

CONSTITUTIONAL RULE: Every completed scan must persist all version fields
from this registry. Changes to any version field require a reprocess event
— never a silent overwrite of historical scan data.

No scientific logic. No scoring. No thresholds.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VersionDefaults:
    """
    Default version registry values for new scans.
    These are overridden by environment variable pins in Settings.
    Frozen dataclass: values cannot be mutated at runtime.
    """
    score_version: str = "0.1.0"
    tier_version: str = "0.1.0"
    causal_graph_version: str = "0.1.0"
    physics_model_version: str = "0.1.0"
    temporal_model_version: str = "0.1.0"
    province_prior_version: str = "0.1.0"
    commodity_library_version: str = "0.1.0"
    scan_pipeline_version: str = "0.1.0"


# Singleton defaults instance — used by health/version endpoint and version registry model
VERSION_DEFAULTS = VersionDefaults()


def get_version_registry_dict(overrides: dict | None = None) -> dict[str, str]:
    """
    Return the version registry as a plain dict, optionally overriding
    specific fields from environment-pinned values.

    Called by:
      - GET /version endpoint
      - core/canonical.py at scan freeze time (with env-pinned overrides)

    Must never be called from scoring, tiering, or gate modules.
    """
    base = {
        "score_version": VERSION_DEFAULTS.score_version,
        "tier_version": VERSION_DEFAULTS.tier_version,
        "causal_graph_version": VERSION_DEFAULTS.causal_graph_version,
        "physics_model_version": VERSION_DEFAULTS.physics_model_version,
        "temporal_model_version": VERSION_DEFAULTS.temporal_model_version,
        "province_prior_version": VERSION_DEFAULTS.province_prior_version,
        "commodity_library_version": VERSION_DEFAULTS.commodity_library_version,
        "scan_pipeline_version": VERSION_DEFAULTS.scan_pipeline_version,
    }
    if overrides:
        base.update(overrides)
    return base