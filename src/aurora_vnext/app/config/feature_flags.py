"""
Aurora OSI vNext — Feature Flags
Phase-gate and feature toggle management.

All flags default to OFF (False). Flags are enabled as implementation
phases complete and pass their exit criteria.

No scientific logic. No scoring. No thresholds.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureFlags:
    """
    Phase-gated feature flags. All OFF until the corresponding
    implementation phase is complete and approved.

    These flags guard endpoints and pipeline stages that depend on
    modules not yet implemented. They prevent partial-state exposure.
    """

    # Phase G — Storage layer operational
    storage_layer_enabled: bool = False

    # Phase H — Observable extraction operational
    observable_extraction_enabled: bool = False

    # Phase I — Scientific core modules operational
    scientific_core_enabled: bool = False

    # Phase J — ACIF scoring engine operational
    scoring_engine_enabled: bool = False

    # Phase K — Sensor services (GEE) operational
    gee_integration_enabled: bool = False

    # Phase L — Full scan pipeline operational
    scan_pipeline_enabled: bool = False

    # Phase N — Digital twin construction operational
    twin_builder_enabled: bool = False

    # Phase O — JWT authentication enforced
    auth_enforced: bool = False

    # Phase P — Web frontend deployed
    web_ui_enabled: bool = False

    # Phase V1 — Quantum inversion interface (post-MVP)
    quantum_interface_enabled: bool = False

    # Phase V4 — GeoGAN scenario generation (post-MVP)
    scenario_generation_enabled: bool = False


# Singleton flags instance — imported by app/main.py and API routers
FLAGS = FeatureFlags()