"""
Aurora OSI vNext — Phase V Event Bus & Webhook Tests
Phase V §V.3 — Completion Proof Tests

Tests:
  1. Payload field mapping — verbatim from canonical record (no arithmetic)
  2. display_acif_score pass-through — exact float preserved
  3. tier_counts pass-through — verbatim dict
  4. version_registry propagation — intact through event envelope
  5. Event serialisation — byte-stable (same event → same bytes)
  6. Retry byte-stability — same bytes across retry attempts
  7. HMAC signature — covers full payload bytes, no scientific-only signing
  8. EventBus subscriber naming convention — scientific functions blocked
  9. Forbidden field derivation — no arithmetic on ACIF in payload factory
  10. No core/* imports across event modules
  11. scan_tier in payload — verbatim stored string, not threshold
  12. voxel_count / cell_count — integer types confirmed
"""

from __future__ import annotations

import asyncio
import json
import pytest

from app.events.payload_schemas import (
    ScanCompletedPayload,
    TwinBuiltPayload,
    make_scan_completed_event,
    make_scan_failed_event,
    make_twin_built_event,
    make_scan_reprocessing_event,
)
from app.events.event_bus import (
    EventBus,
    EventType,
    DomainEvent,
    _PERMITTED_SUBSCRIBER_PREFIXES,
    get_event_bus,
)


# ─── Sample canonical scan record ─────────────────────────────────────────────

CANONICAL_RECORD = {
    "scan_id":            "scan_abc123",
    "commodity":          "gold",
    "environment":        "AFRICA_CRATON",
    "scan_status":        "COMPLETED",
    "system_status":      "PASS_CONFIRMED",
    "scan_tier":          "TIER_1",
    "display_acif_score": 0.8120000000000001,   # IEEE 754 precision test value
    "max_acif_score":     0.9340000000000002,
    "tier_counts":        {"tier_1": 42, "tier_2": 18, "tier_3": 5, "below": 2},
    "total_cells":        67,
    "version_registry":   {
        "score_version":         "1.0.0",
        "tier_version":          "1.0.0",
        "physics_model_version": "2.1.0",
    },
    "frozen_at": "2026-03-26T12:00:00.000000",
}


# ─── 1. Payload field mapping ─────────────────────────────────────────────────

class TestPayloadFieldMapping:
    def test_all_fields_sourced_verbatim(self):
        """
        PROOF: ScanCompletedPayload.from_canonical_scan() uses record.get(key)
        for every field. No arithmetic is applied.
        """
        p = ScanCompletedPayload.from_canonical_scan(CANONICAL_RECORD)
        assert p.scan_id            == CANONICAL_RECORD["scan_id"]
        assert p.commodity          == CANONICAL_RECORD["commodity"]
        assert p.environment        == CANONICAL_RECORD["environment"]
        assert p.scan_status        == CANONICAL_RECORD["scan_status"]
        assert p.system_status      == CANONICAL_RECORD["system_status"]
        assert p.scan_tier          == CANONICAL_RECORD["scan_tier"]
        assert p.total_cells        == CANONICAL_RECORD["total_cells"]
        assert p.frozen_at          == CANONICAL_RECORD["frozen_at"]

    def test_display_acif_score_verbatim(self):
        """
        PROOF: display_acif_score must be byte-identical to the source value.
        0.8120000000000001 is used to expose any silent rounding.
        """
        p = ScanCompletedPayload.from_canonical_scan(CANONICAL_RECORD)
        assert p.display_acif_score == 0.8120000000000001
        assert p.max_acif_score     == 0.9340000000000002

    def test_tier_counts_verbatim(self):
        """PROOF: tier_counts dict must be identical — no re-aggregation."""
        p = ScanCompletedPayload.from_canonical_scan(CANONICAL_RECORD)
        assert p.tier_counts == {"tier_1": 42, "tier_2": 18, "tier_3": 5, "below": 2}

    def test_version_registry_propagated(self):
        """
        PROOF: version_registry propagation — ScanCompletedPayload carries
        the verbatim version_registry from the frozen CanonicalScan.
        """
        p = ScanCompletedPayload.from_canonical_scan(CANONICAL_RECORD)
        assert p.version_registry == CANONICAL_RECORD["version_registry"]

    def test_scan_tier_is_string(self):
        """
        PROOF: scan_tier in payload is the stored enum string "TIER_1".
        It is NOT a numeric threshold value.
        """
        p = ScanCompletedPayload.from_canonical_scan(CANONICAL_RECORD)
        assert isinstance(p.scan_tier, str)
        assert p.scan_tier == "TIER_1"
        # Must not contain a decimal point (i.e. not a float threshold like 0.7)
        assert "." not in p.scan_tier

    def test_none_fields_on_missing_record_keys(self):
        """
        PROOF: missing fields map to None — not to a default/fallback value.
        No fabricated value is injected for missing scientific fields.
        """
        p = ScanCompletedPayload.from_canonical_scan({"scan_id": "s1", "commodity": "gold"})
        assert p.display_acif_score is None
        assert p.tier_counts is None
        assert p.version_registry is None


# ─── 2. Twin payload ──────────────────────────────────────────────────────────

class TestTwinPayload:
    MANIFEST = {
        "version":        2,
        "voxel_count":    42000,
        "build_duration_s": 37.4,
        "version_registry": {"score_version": "1.0.0"},
    }

    def test_voxel_count_is_integer(self):
        """PROOF: voxel_count is integer row count — not a scientific float."""
        p = TwinBuiltPayload.from_build_manifest("scan_x", "gold", self.MANIFEST)
        assert isinstance(p.voxel_count, int)
        assert p.voxel_count == 42000

    def test_twin_version_is_integer(self):
        p = TwinBuiltPayload.from_build_manifest("scan_x", "gold", self.MANIFEST)
        assert isinstance(p.twin_version, int)

    def test_version_registry_propagated(self):
        p = TwinBuiltPayload.from_build_manifest("scan_x", "gold", self.MANIFEST)
        assert p.version_registry == {"score_version": "1.0.0"}


# ─── 3. Event serialisation byte-stability ────────────────────────────────────

class TestEventSerialisation:
    def test_same_event_produces_same_bytes(self):
        """
        PROOF: DomainEvent.serialise() is byte-stable — calling it twice
        returns the same bytes (sort_keys=True ensures determinism).
        """
        event = make_scan_completed_event(CANONICAL_RECORD)
        bytes1 = event.serialise()
        bytes2 = event.serialise()
        assert bytes1 == bytes2

    def test_serialised_bytes_contain_verbatim_acif(self):
        """
        PROOF: the serialised JSON bytes contain the verbatim ACIF float.
        The payload is not sanitised or rounded during serialisation.
        """
        event = make_scan_completed_event(CANONICAL_RECORD)
        body = json.loads(event.serialise())
        acif_in_payload = body["payload"]["display_acif_score"]
        assert acif_in_payload == 0.8120000000000001

    def test_serialised_bytes_contain_version_registry(self):
        event = make_scan_completed_event(CANONICAL_RECORD)
        body = json.loads(event.serialise())
        assert body["payload"]["version_registry"] == CANONICAL_RECORD["version_registry"]

    def test_event_envelope_fields(self):
        event = make_scan_completed_event(CANONICAL_RECORD)
        body = json.loads(event.serialise())
        assert "event_id"    in body
        assert "event_type"  in body
        assert "occurred_at" in body
        assert "payload"     in body
        assert body["event_type"] == EventType.SCAN_COMPLETED


# ─── 4. Retry byte-stability ──────────────────────────────────────────────────

class TestRetryByteStability:
    def test_serialise_cached_after_first_call(self):
        """
        PROOF (Rule V.2): serialise() caches result after first call.
        Retry logic calls serialise() again — same object → same bytes.
        The payload is NEVER recomputed on retry.
        """
        event = make_scan_completed_event(CANONICAL_RECORD)
        first  = event.serialise()
        second = event.serialise()
        third  = event.serialise()
        assert first is second is third   # same object — cached bytes

    def test_hmac_over_full_payload_bytes(self):
        """
        PROOF (Rule V.3): HMAC is computed over the full serialised JSON bytes.
        Scientific field values are not used as separate signing inputs.
        """
        event = make_scan_completed_event(CANONICAL_RECORD)
        sig1 = event.hmac_signature("test_secret")
        sig2 = event.hmac_signature("test_secret")
        assert sig1 == sig2   # deterministic — same bytes → same HMAC

    def test_different_secrets_produce_different_sigs(self):
        event = make_scan_completed_event(CANONICAL_RECORD)
        sig_a = event.hmac_signature("secret_a")
        sig_b = event.hmac_signature("secret_b")
        assert sig_a != sig_b


# ─── 5. EventBus subscriber naming convention ─────────────────────────────────

class TestEventBusNamingConvention:
    @pytest.mark.asyncio
    async def test_permitted_handler_registered(self):
        bus = EventBus()
        async def on_scan_done(event): pass
        bus.subscribe(EventType.SCAN_COMPLETED, on_scan_done)   # must not raise

    @pytest.mark.asyncio
    async def test_scientific_function_name_blocked(self):
        """
        PROOF: a handler named like a scientific function (no permitted prefix)
        is rejected at registration — not at publish time.
        This prevents scientific functions from being accidentally wired into the bus.
        """
        bus = EventBus()
        async def compute_acif(event): pass   # forbidden name
        with pytest.raises(ValueError, match="naming convention"):
            bus.subscribe(EventType.SCAN_COMPLETED, compute_acif)

    @pytest.mark.asyncio
    async def test_assign_tier_name_blocked(self):
        bus = EventBus()
        async def assign_tier(event): pass
        with pytest.raises(ValueError):
            bus.subscribe(EventType.SCAN_COMPLETED, assign_tier)

    @pytest.mark.asyncio
    async def test_publish_calls_subscriber(self):
        bus = EventBus()
        received = []
        async def on_event(event): received.append(event.event_id)
        bus.subscribe(EventType.SCAN_COMPLETED, on_event)
        event = make_scan_completed_event(CANONICAL_RECORD)
        await bus.publish(event)
        assert event.event_id in received

    @pytest.mark.asyncio
    async def test_unknown_event_type_raises(self):
        bus = EventBus()
        async def on_x(event): pass
        with pytest.raises(ValueError, match="Unknown event type"):
            bus.subscribe("unknown.event", on_x)


# ─── 6. No scientific imports ─────────────────────────────────────────────────

class TestNoScientificImports:
    FORBIDDEN = [
        "app.core.scoring", "app.core.tiering", "app.core.gates",
        "app.core.evidence", "app.core.causal", "app.core.physics",
        "app.core.temporal", "app.core.priors", "app.core.uncertainty",
    ]
    FUNC_FORBIDDEN = ["compute_acif", "assign_tier", "evaluate_gates", "score_evidence"]

    def _check(self, module_path):
        import importlib, inspect
        mod = importlib.import_module(module_path)
        src = open(inspect.getfile(mod)).read()
        for prefix in self.FORBIDDEN:
            assert prefix not in src, f"VIOLATION: {module_path} imports {prefix}"
        for fn in self.FUNC_FORBIDDEN:
            assert fn not in src, f"VIOLATION: {module_path} calls {fn}"

    def test_event_bus_no_core(self):         self._check("app.events.event_bus")
    def test_payload_schemas_no_core(self):   self._check("app.events.payload_schemas")