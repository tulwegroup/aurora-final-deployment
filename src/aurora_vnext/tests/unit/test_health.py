"""
Phase E — Health and Version Endpoint Tests
These are the only tests active at Phase E exit.
All other test files are stubs added progressively per Phase D build order.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self):
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_app_name(self):
        response = client.get("/health")
        data = response.json()
        assert "Aurora" in data["app"]

    def test_health_returns_flags(self):
        response = client.get("/health")
        data = response.json()
        assert "flags" in data
        # All flags should be False at Phase E (no implementation yet)
        for flag_value in data["flags"].values():
            assert flag_value is False, (
                f"Feature flag should be False at Phase E scaffold stage. "
                f"A True flag indicates premature implementation."
            )


class TestVersionEndpoint:
    def test_version_returns_200(self):
        response = client.get("/version")
        assert response.status_code == 200

    def test_version_returns_registry_fields(self):
        response = client.get("/version")
        data = response.json()
        registry = data["registry"]
        required_fields = [
            "score_version",
            "tier_version",
            "causal_graph_version",
            "physics_model_version",
            "temporal_model_version",
            "province_prior_version",
            "commodity_library_version",
            "scan_pipeline_version",
        ]
        for field in required_fields:
            assert field in registry, f"Missing version registry field: {field}"

    def test_version_registry_values_are_strings(self):
        response = client.get("/version")
        registry = response.json()["registry"]
        for key, value in registry.items():
            assert isinstance(value, str), (
                f"Version registry field '{key}' must be a string, got {type(value)}"
            )


class TestNoScoringLogicInScaffold:
    """
    Phase E exit criterion: zero scoring logic anywhere in the codebase.
    These tests verify the scaffold is clean.
    """

    def test_scoring_module_is_stub(self):
        """core/scoring.py must contain no callable scoring functions at Phase E."""
        import app.core.scoring as scoring_module
        public_functions = [
            name for name in dir(scoring_module)
            if not name.startswith("_") and callable(getattr(scoring_module, name))
        ]
        assert len(public_functions) == 0, (
            f"core/scoring.py contains callable functions at Phase E scaffold: "
            f"{public_functions}. Scoring logic must not be implemented until Phase J."
        )

    def test_tiering_module_is_stub(self):
        """core/tiering.py must contain no callable tiering functions at Phase E."""
        import app.core.tiering as tiering_module
        public_functions = [
            name for name in dir(tiering_module)
            if not name.startswith("_") and callable(getattr(tiering_module, name))
        ]
        assert len(public_functions) == 0, (
            f"core/tiering.py contains callable functions at Phase E scaffold: "
            f"{public_functions}. Tiering logic must not be implemented until Phase J."
        )

    def test_gates_module_is_stub(self):
        """core/gates.py must contain no callable gate functions at Phase E."""
        import app.core.gates as gates_module
        public_functions = [
            name for name in dir(gates_module)
            if not name.startswith("_") and callable(getattr(gates_module, name))
        ]
        assert len(public_functions) == 0, (
            f"core/gates.py contains callable functions at Phase E scaffold: "
            f"{public_functions}. Gate logic must not be implemented until Phase J."
        )

    def test_commodity_library_is_stub(self):
        """commodity/library.py must contain no commodity definitions at Phase E."""
        import app.commodity.library as library_module
        public_names = [
            name for name in dir(library_module)
            if not name.startswith("_")
        ]
        assert len(public_names) == 0, (
            f"commodity/library.py contains definitions at Phase E scaffold: "
            f"{public_names}. Commodity library must not be populated until Phase F."
        )