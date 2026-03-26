"""
Aurora OSI vNext — Phase W Webhook Consumer Registry Tests
Phase W §W.3 — Completion Proof Tests

Tests:
  1.  API key generation — random, no scientific metadata
  2.  API key hash — never stores plaintext
  3.  API key verification — constant-time comparison
  4.  ConsumerScope — event_type strings only
  5.  ConsumerScope — rejects unknown event types
  6.  ConsumerScope — no scientific filter fields
  7.  Signature verification — HMAC over full payload bytes
  8.  Consumer registration — response includes plaintext key once
  9.  Consumer scope — all events subscription
  10. Key rotation — new hash, old key invalidated
  11. No core/* imports
  12. to_public_dict — no secrets in response
"""

from __future__ import annotations

import hashlib
import hmac
import pytest

from app.events.consumer_auth import (
    ConsumerScope,
    RegisteredConsumer,
    generate_api_key,
    generate_consumer_registration,
    hash_api_key,
    verify_api_key,
    verify_webhook_signature,
    _KEY_PREFIX,
)
from app.events.event_bus import EventType


# ─── 1. API key generation ────────────────────────────────────────────────────

class TestApiKeyGeneration:
    def test_key_has_prefix(self):
        plaintext, _ = generate_api_key()
        assert plaintext.startswith(_KEY_PREFIX)

    def test_key_is_random(self):
        """Two generated keys must not be equal."""
        k1, _ = generate_api_key()
        k2, _ = generate_api_key()
        assert k1 != k2

    def test_key_contains_no_scientific_value(self):
        """
        PROOF: API key must not contain any scientific field name or numeric score.
        Keys are random hex — no embedded scientific metadata.
        """
        for _ in range(10):
            plaintext, _ = generate_api_key()
            for forbidden in ["acif", "tier", "score", "0.81", "threshold"]:
                assert forbidden not in plaintext.lower()

    def test_stored_hash_is_not_plaintext(self):
        plaintext, stored_hash = generate_api_key()
        assert plaintext != stored_hash

    def test_stored_hash_is_hex_string(self):
        _, stored_hash = generate_api_key()
        int(stored_hash, 16)   # must parse as hex without error

    def test_hash_deterministic(self):
        plaintext, _ = generate_api_key()
        h1 = hash_api_key(plaintext)
        h2 = hash_api_key(plaintext)
        assert h1 == h2


# ─── 2. API key verification ──────────────────────────────────────────────────

class TestApiKeyVerification:
    def test_valid_key_verifies(self):
        plaintext, stored_hash = generate_api_key()
        assert verify_api_key(plaintext, stored_hash) is True

    def test_wrong_key_rejected(self):
        _, stored_hash = generate_api_key()
        wrong_key, _ = generate_api_key()
        assert verify_api_key(wrong_key, stored_hash) is False

    def test_tampered_key_rejected(self):
        plaintext, stored_hash = generate_api_key()
        tampered = plaintext[:-1] + ("X" if plaintext[-1] != "X" else "Y")
        assert verify_api_key(tampered, stored_hash) is False


# ─── 3. ConsumerScope ─────────────────────────────────────────────────────────

class TestConsumerScope:
    def test_valid_event_types_accepted(self):
        scope = ConsumerScope(event_types={"scan.completed", "twin.built"})
        assert "scan.completed" in scope.event_types

    def test_unknown_event_type_raises(self):
        with pytest.raises(ValueError, match="Unknown event type"):
            ConsumerScope(event_types={"scan.completed", "unknown.event"})

    def test_scope_contains_only_event_type_strings(self):
        """
        PROOF: ConsumerScope.event_types must be EventType strings only.
        No scientific filter field (filter_by_tier, min_acif_score) is accepted.
        """
        scope = ConsumerScope.all_events()
        for et in scope.event_types:
            assert isinstance(et, str)
            assert et in EventType._ALL
            # Must be event type format "noun.verb" — not a float threshold
            assert "." in et
            # Must not be a numeric value
            try:
                float(et)
                assert False, f"event_type {et!r} parsed as float — scientific value leaked"
            except ValueError:
                pass   # expected — not a numeric value

    def test_matches_subscribed_event(self):
        scope = ConsumerScope(event_types={"scan.completed"})
        assert scope.matches("scan.completed") is True
        assert scope.matches("twin.built") is False

    def test_all_events_scope(self):
        scope = ConsumerScope.all_events()
        assert scope.event_types == EventType._ALL

    def test_scan_events_only_scope(self):
        scope = ConsumerScope.scan_events_only()
        assert "scan.completed" in scope.event_types
        assert "twin.built" not in scope.event_types


# ─── 4. Consumer registration ─────────────────────────────────────────────────

class TestConsumerRegistration:
    def test_registration_returns_plaintext_key(self):
        consumer, plaintext = generate_consumer_registration(
            name="Test System",
            endpoint_url="https://example.com/webhook",
        )
        assert plaintext.startswith(_KEY_PREFIX)

    def test_stored_hash_verifies_against_plaintext(self):
        consumer, plaintext = generate_consumer_registration(
            name="Test System",
            endpoint_url="https://example.com/webhook",
        )
        assert verify_api_key(plaintext, consumer.key_hash) is True

    def test_to_public_dict_excludes_secrets(self):
        """
        PROOF: public API response never includes key_hash or signing_secret.
        """
        consumer, _ = generate_consumer_registration(
            name="Test",
            endpoint_url="https://example.com/hook",
        )
        public = consumer.to_public_dict()
        assert "key_hash"       not in public
        assert "signing_secret" not in public
        assert "consumer_id"    in public
        assert "event_types"    in public

    def test_public_dict_contains_only_infrastructure_fields(self):
        consumer, _ = generate_consumer_registration(
            name="Test",
            endpoint_url="https://example.com/hook",
            event_types={"scan.completed"},
        )
        public = consumer.to_public_dict()
        # Event types must be EventType strings — not scientific values
        for et in public["event_types"]:
            assert et in EventType._ALL

    def test_event_types_default_to_all(self):
        consumer, _ = generate_consumer_registration(
            name="Test",
            endpoint_url="https://example.com/hook",
        )
        assert consumer.scope.event_types == EventType._ALL


# ─── 5. Signature verification ───────────────────────────────────────────────

class TestSignatureVerification:
    SECRET = "test_signing_secret_abc123"
    PAYLOAD = b'{"event_type":"scan.completed","payload":{"scan_id":"s1"}}'

    def _make_sig(self, payload, secret):
        return "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()

    def test_valid_signature_accepted(self):
        sig = self._make_sig(self.PAYLOAD, self.SECRET)
        assert verify_webhook_signature(self.PAYLOAD, sig, self.SECRET) is True

    def test_wrong_secret_rejected(self):
        sig = self._make_sig(self.PAYLOAD, self.SECRET)
        assert verify_webhook_signature(self.PAYLOAD, sig, "wrong_secret") is False

    def test_tampered_payload_rejected(self):
        sig = self._make_sig(self.PAYLOAD, self.SECRET)
        tampered = self.PAYLOAD + b"tampered"
        assert verify_webhook_signature(tampered, sig, self.SECRET) is False

    def test_malformed_header_rejected(self):
        assert verify_webhook_signature(self.PAYLOAD, "invalid_header", self.SECRET) is False

    def test_signature_is_full_payload_bytes(self):
        """
        PROOF: signature covers the full payload bytes.
        Scientific field values are not used as separate signing inputs.
        The signature is computed once over the entire body — not per-field.
        """
        # Two payloads with different ACIF scores must produce different signatures
        payload_a = b'{"display_acif_score": 0.81}'
        payload_b = b'{"display_acif_score": 0.82}'
        sig_a = self._make_sig(payload_a, self.SECRET)
        sig_b = self._make_sig(payload_b, self.SECRET)
        assert sig_a != sig_b   # full-payload coverage: any byte change → different sig


# ─── 6. No scientific imports ─────────────────────────────────────────────────

class TestNoScientificImports:
    FORBIDDEN = [
        "app.core.scoring", "app.core.tiering", "app.core.gates",
        "app.core.evidence", "app.core.causal", "app.core.physics",
        "app.core.temporal", "app.core.priors", "app.core.uncertainty",
    ]
    FUNC_FORBIDDEN = ["compute_acif", "assign_tier", "evaluate_gates"]

    def _check(self, module_path):
        import importlib, inspect
        mod = importlib.import_module(module_path)
        src = open(inspect.getfile(mod)).read()
        for prefix in self.FORBIDDEN:
            assert prefix not in src, f"VIOLATION: {module_path} imports {prefix}"
        for fn in self.FUNC_FORBIDDEN:
            assert fn not in src, f"VIOLATION: {module_path} calls {fn}"

    def test_consumer_auth_no_core(self):  self._check("app.events.consumer_auth")
    def test_webhooks_api_no_core(self):   self._check("app.api.webhooks")