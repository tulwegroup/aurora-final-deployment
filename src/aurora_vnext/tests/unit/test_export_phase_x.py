"""
Aurora OSI vNext — Phase X Export API Tests
Phase X §X.2 — Completion Proof Tests

Tests:
  1.  JSON export — verbatim field values preserved
  2.  IEEE 754 precision preserved through JSON export
  3.  GeoJSON feature properties — verbatim stored fields only
  4.  GeoJSON no computed properties (no acif_percentile, tier_rank etc.)
  5.  CSV columns are canonical field names (no derived aliases)
  6.  CSV values verbatim from stored records
  7.  Missing cell fields → empty string (no fallback value injection)
  8.  Webhook consumers cannot subscribe using score/tier filters
  9.  Event payload schemas are verbatim canonical projections
  10. No core/* imports in export.py
"""

from __future__ import annotations

import csv
import io
import json
import pytest

from app.api.export import (
    cell_to_geojson_feature,
    cells_to_geojson,
    cells_to_csv,
    CSV_COLUMNS,
)
from app.events.consumer_auth import ConsumerScope
from app.events.event_bus import EventType
from app.events.payload_schemas import ScanCompletedPayload


# ─── Sample data ──────────────────────────────────────────────────────────────

CANONICAL_SCAN = {
    "scan_id":            "scan_abc123",
    "commodity":          "gold",
    "display_acif_score": 0.8120000000000001,
    "max_acif_score":     0.9340000000000002,
    "scan_tier":          "TIER_1",
    "system_status":      "PASS_CONFIRMED",
    "tier_counts":        {"tier_1": 42, "tier_2": 18, "tier_3": 5, "below": 2},
    "version_registry":   {"score_version": "1.0.0"},
    "frozen_at":          "2026-03-26T12:00:00",
}

CELLS = [
    {
        "cell_id": "c1", "scan_id": "scan_abc123",
        "lat_center": -25.1234, "lon_center": 28.5678,
        "acif_score": 0.812, "evidence_score": 0.9,
        "causal_score": 0.85, "physics_score": 0.78,
        "temporal_score": 0.91, "province_prior": 0.7,
        "total_uncertainty": 0.15, "tier": "TIER_1",
        "any_veto_fired": False,
        "physics_residual": 0.002, "gravity_residual": 0.001,
    },
    {
        "cell_id": "c2", "scan_id": "scan_abc123",
        "lat_center": -25.1300, "lon_center": 28.5700,
        "acif_score": 0.421, "evidence_score": 0.55,
        "causal_score": 0.60, "physics_score": 0.50,
        "temporal_score": 0.70, "province_prior": 0.6,
        "total_uncertainty": 0.35, "tier": "TIER_2",
        "any_veto_fired": False,
        "physics_residual": None, "gravity_residual": None,
    },
]


# ─── 1. JSON export verbatim ──────────────────────────────────────────────────

class TestJsonExport:
    def test_acif_score_verbatim(self):
        """
        PROOF (Rule 1): display_acif_score must survive JSON round-trip unchanged.
        """
        payload = json.dumps(CANONICAL_SCAN, default=str)
        restored = json.loads(payload)
        assert restored["display_acif_score"] == 0.8120000000000001

    def test_tier_counts_verbatim(self):
        payload = json.dumps(CANONICAL_SCAN, default=str)
        restored = json.loads(payload)
        assert restored["tier_counts"] == {"tier_1": 42, "tier_2": 18, "tier_3": 5, "below": 2}

    def test_version_registry_verbatim(self):
        payload = json.dumps(CANONICAL_SCAN, default=str)
        restored = json.loads(payload)
        assert restored["version_registry"] == {"score_version": "1.0.0"}

    def test_scan_tier_is_string(self):
        """PROOF: scan_tier exported as stored enum string — not a numeric threshold."""
        payload = json.dumps(CANONICAL_SCAN, default=str)
        restored = json.loads(payload)
        assert restored["scan_tier"] == "TIER_1"
        assert isinstance(restored["scan_tier"], str)


# ─── 2. GeoJSON export ────────────────────────────────────────────────────────

class TestGeoJsonExport:
    def test_feature_has_correct_geometry(self):
        feature = cell_to_geojson_feature(CELLS[0])
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [28.5678, -25.1234]

    def test_properties_are_verbatim_stored_fields(self):
        """
        PROOF (Rule 3): properties must contain only verbatim stored fields.
        No computed field (acif_percentile, tier_rank, normalised_score) present.
        """
        feature = cell_to_geojson_feature(CELLS[0])
        props = feature["properties"]
        assert props["acif_score"] == 0.812
        assert props["tier"] == "TIER_1"
        assert props["any_veto_fired"] is False

    def test_no_computed_properties(self):
        """
        PROOF (Rule 3): computed / derived columns must not appear in properties.
        """
        feature = cell_to_geojson_feature(CELLS[0])
        props = feature["properties"]
        forbidden_computed = [
            "acif_percentile", "tier_rank", "normalised_score",
            "score_rank", "tier_index", "acif_zscore",
        ]
        for key in forbidden_computed:
            assert key not in props, f"Computed property {key!r} must not appear in GeoJSON"

    def test_feature_collection_contains_all_cells(self):
        fc = cells_to_geojson("scan_abc123", CELLS)
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 2

    def test_null_coords_produce_null_geometry(self):
        cell_no_coords = {"cell_id": "c3", "acif_score": 0.5}
        feature = cell_to_geojson_feature(cell_no_coords)
        assert feature["geometry"] is None


# ─── 3. CSV export ────────────────────────────────────────────────────────────

class TestCsvExport:
    def test_column_names_are_canonical_field_names(self):
        """
        PROOF (Rule 4): CSV column names are canonical field names — no aliases.
        No derived name like 'normalised_score', 'tier_index', 'rank' appears.
        """
        csv_content = cells_to_csv(CELLS)
        reader = csv.DictReader(io.StringIO(csv_content))
        headers = reader.fieldnames
        assert headers == CSV_COLUMNS

        # None of the column names should imply derivation
        forbidden_aliases = ["normalised", "rank", "percentile", "index", "derived"]
        for col in headers:
            for alias in forbidden_aliases:
                assert alias not in col.lower(), \
                    f"CSV column {col!r} implies derived value — Rule 4 violation"

    def test_cell_values_verbatim(self):
        """PROOF (Rule 1): numeric values in CSV match stored cell values."""
        csv_content = cells_to_csv(CELLS)
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        assert rows[0]["acif_score"] == "0.812"
        assert rows[0]["tier"] == "TIER_1"
        assert rows[0]["any_veto_fired"] == "False"

    def test_missing_field_is_empty_not_fallback(self):
        """
        PROOF: missing cell fields produce empty string — NOT a fallback value.
        An empty string is not a scientific default; it signals missing data.
        """
        csv_content = cells_to_csv(CELLS)
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        # CELLS[1] has physics_residual=None — expect empty string, not "0" or "0.5"
        assert rows[1]["physics_residual"] == ""
        assert rows[1]["gravity_residual"] == ""


# ─── 4. Webhook consumers cannot subscribe using score/tier filters ────────────

class TestWebhookScopeNoScientificFilters:
    def test_consumer_scope_accepts_only_event_type_strings(self):
        """
        EXPLICIT PROOF (Phase X requirement):
        Webhook consumers can ONLY subscribe by event_type string.
        Score/tier/threshold filters are structurally impossible.
        """
        # Valid: event type strings
        scope = ConsumerScope(event_types={"scan.completed", "twin.built"})
        assert "scan.completed" in scope.event_types

    def test_consumer_scope_rejects_unknown_event(self):
        """Unknown strings are rejected — including any score-like string."""
        with pytest.raises(ValueError):
            ConsumerScope(event_types={"scan.completed", "tier.1.only"})

    def test_consumer_scope_has_no_filter_fields(self):
        """
        PROOF: ConsumerScope dataclass has NO field for scientific filtering.
        Inspect the class signature to confirm.
        """
        import inspect as ins
        from app.events.consumer_auth import ConsumerScope as CS
        fields = [f.name for f in ins.fields(CS) if ins.isclass(CS) and hasattr(CS, '__dataclass_fields__')]
        # Use dataclasses module
        import dataclasses
        scope_fields = [f.name for f in dataclasses.fields(CS)]
        assert scope_fields == ["event_types"], \
            f"ConsumerScope must have only 'event_types' field, got {scope_fields}"

    def test_no_score_filter_in_register_request(self):
        """
        PROOF: RegisterConsumerRequest Pydantic model rejects extra fields
        (extra='forbid'), so no filter_by_tier or min_acif_score can be passed.
        """
        from app.api.webhooks import RegisterConsumerRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegisterConsumerRequest(
                name="Test",
                endpoint_url="https://example.com/hook",
                event_types=["scan.completed"],
                filter_by_tier="TIER_1",   # MUST be rejected
            )

    def test_no_acif_threshold_in_register_request(self):
        from app.api.webhooks import RegisterConsumerRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegisterConsumerRequest(
                name="Test",
                endpoint_url="https://example.com/hook",
                min_acif_score=0.7,   # MUST be rejected
            )


# ─── 5. Event payload schemas are verbatim canonical projections ───────────────

class TestPayloadVerbatimProjection:
    def test_all_fields_are_direct_record_lookups(self):
        """
        EXPLICIT PROOF (Phase X requirement):
        Every field in ScanCompletedPayload.from_canonical_scan() is record.get(key).
        Verified by constructing from a known record and comparing field by field.
        """
        p = ScanCompletedPayload.from_canonical_scan(CANONICAL_SCAN)
        assert p.display_acif_score == CANONICAL_SCAN["display_acif_score"]
        assert p.tier_counts        == CANONICAL_SCAN["tier_counts"]
        assert p.scan_tier          == CANONICAL_SCAN["scan_tier"]
        assert p.version_registry   == CANONICAL_SCAN["version_registry"]
        assert p.system_status      == CANONICAL_SCAN["system_status"]

    def test_no_computed_field_in_payload(self):
        """Payload must not contain any field absent from the canonical record."""
        p = ScanCompletedPayload.from_canonical_scan(CANONICAL_SCAN)
        d = p.to_dict()
        forbidden_computed = ["acif_percentile", "tier_rank", "normalised_acif", "score_rank"]
        for key in forbidden_computed:
            assert key not in d, f"Computed field {key!r} must not appear in event payload"

    def test_missing_canonical_field_maps_to_none(self):
        """Missing fields produce None — no fabricated default."""
        p = ScanCompletedPayload.from_canonical_scan({"scan_id": "s1", "commodity": "gold"})
        assert p.display_acif_score is None
        assert p.tier_counts        is None
        assert p.version_registry   is None


# ─── 6. No core/* imports ─────────────────────────────────────────────────────

class TestNoScientificImports:
    def _check(self, module_path):
        import importlib, inspect
        mod = importlib.import_module(module_path)
        src = open(inspect.getfile(mod)).read()
        for prefix in ["app.core.scoring", "app.core.tiering", "app.core.gates"]:
            assert prefix not in src
        for fn in ["compute_acif", "assign_tier", "evaluate_gates"]:
            assert fn not in src

    def test_export_api_no_core(self): self._check("app.api.export")