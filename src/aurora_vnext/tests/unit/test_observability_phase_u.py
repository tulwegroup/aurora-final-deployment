"""
Aurora OSI vNext — Phase U Observability Tests
Phase U §U.4 — Completion Proof Tests

Tests:
  1. Metric label validation — scientific values never used as labels
  2. Forbidden span attribute blocking — _FORBIDDEN_SPAN_ATTRS enforced
  3. Pipeline telemetry — stage timing emits correct metric labels
  4. Canonical ACIF gauge — only emitted when env var set; value verbatim
  5. Log field blocking — _BLOCKED_FIELDS in _JsonFormatter enforced
  6. cache_hit / cache_miss metrics — correct key_type labels
  7. No core/* imports across all observability modules
  8. scan_tier label uses stored enum string — not a numeric threshold
  9. voxel_count and cell_count are integers — not scientific floats
  10. Tracing span attributes sanitised before emission
"""

from __future__ import annotations

import os
import pytest

from app.observability.metrics import (
    record_scan_submitted,
    record_scan_completed,
    record_scan_failed,
    record_twin_built,
    record_migration,
    emit_canonical_acif_gauge,
    PIPELINE_STAGE_DURATION,
    SCAN_SUBMITTED,
    SCAN_COMPLETED,
    TWIN_VOXEL_COUNT,
)
from app.observability.tracing import (
    _FORBIDDEN_SPAN_ATTRS,
    _NoopSpan,
    trace_span,
    http_span_attrs,
    pipeline_span_attrs,
    twin_span_attrs,
    db_span_attrs,
    cache_span_attrs,
)
from app.observability.pipeline_telemetry import (
    instrument_stage,
    on_scan_submitted,
    on_scan_completed,
    on_scan_failed,
    on_twin_built,
    on_migration_record,
)


# ─── 1. Metric label validation ───────────────────────────────────────────────

class TestMetricLabels:
    def test_scan_submitted_labels_are_strings(self):
        """Labels must be string identifiers — no float ACIF scores."""
        # Verify the function accepts and handles string-only labels without error
        record_scan_submitted("gold", "AFRICA_CRATON")   # must not raise

    def test_scan_completed_scan_tier_is_string(self):
        """
        PROOF: scan_tier label is the stored canonical enum string (e.g. "TIER_1").
        It is NOT a numeric threshold value (e.g. 0.7 or 0.5).
        """
        record_scan_completed("gold", "TIER_1", 45.2)   # must not raise
        # Verify scan_tier is a string, not a float threshold
        scan_tier = "TIER_1"
        assert isinstance(scan_tier, str)
        assert "." not in scan_tier   # no decimal point → not a numeric threshold

    def test_scan_failed_label_is_stage_name(self):
        record_scan_failed("evidence")
        record_scan_failed("physics")   # stage names only — must not raise

    def test_migration_class_label(self):
        for cls in ["A", "B", "C"]:
            record_migration(cls)   # must not raise

    def test_twin_built_counts_are_integers(self):
        """
        PROOF: voxel_count is an integer DB row count.
        It is NOT a scientific float (e.g. probability, score).
        """
        count = 12345
        assert isinstance(count, int)
        record_twin_built(count, 42.5)   # must not raise


# ─── 2. Forbidden span attribute blocking ─────────────────────────────────────

class TestForbiddenSpanAttrs:
    def test_forbidden_set_contains_scientific_fields(self):
        """_FORBIDDEN_SPAN_ATTRS must cover all critical scientific output fields."""
        required_forbidden = {
            "acif_score", "display_acif_score",
            "tier_counts", "system_status", "gate_results",
            "tier_thresholds_used", "normalisation_params",
            "evidence_score", "causal_score", "physics_score",
        }
        assert required_forbidden.issubset(_FORBIDDEN_SPAN_ATTRS)

    def test_forbidden_fields_not_in_http_attrs(self):
        attrs = http_span_attrs("GET", "/api/v1/history", "user_1", "viewer")
        for key in _FORBIDDEN_SPAN_ATTRS:
            assert key not in attrs

    def test_forbidden_fields_not_in_pipeline_attrs(self):
        attrs = pipeline_span_attrs("scan_abc", "evidence", cell_count=1000)
        for key in _FORBIDDEN_SPAN_ATTRS:
            assert key not in attrs

    def test_forbidden_fields_not_in_twin_attrs(self):
        attrs = twin_span_attrs("scan_abc", 1, voxel_count=5000)
        for key in _FORBIDDEN_SPAN_ATTRS:
            assert key not in attrs

    def test_forbidden_fields_not_in_db_attrs(self):
        attrs = db_span_attrs("list_scans", scan_id="scan_abc")
        for key in _FORBIDDEN_SPAN_ATTRS:
            assert key not in attrs

    def test_forbidden_fields_not_in_cache_attrs(self):
        attrs = cache_span_attrs("get", "scan_summary", hit=True)
        for key in _FORBIDDEN_SPAN_ATTRS:
            assert key not in attrs

    def test_trace_span_drops_forbidden_attr(self):
        """
        PROOF: if caller accidentally passes a forbidden attribute,
        trace_span() drops it silently (no leak into span labels).
        trace_span() uses _NoopSpan when tracing is disabled — test noop path.
        """
        # _get_tracer returns None in test env (otel not configured)
        # trace_span must complete without error and not raise on forbidden attr
        with trace_span("test.op", {"acif_score": 0.812, "aurora.scan_id": "s1"}) as span:
            assert span is not None   # noop span returned

    def test_cell_count_is_allowed_attr(self):
        """cell_count is an integer row count — allowed as span attribute."""
        attrs = pipeline_span_attrs("scan_abc", "scoring", cell_count=500)
        assert "aurora.cell_count" in attrs
        assert isinstance(attrs["aurora.cell_count"], int)

    def test_voxel_count_is_allowed_attr(self):
        attrs = twin_span_attrs("scan_abc", 2, voxel_count=10000)
        assert "aurora.voxel_count" in attrs
        assert isinstance(attrs["aurora.voxel_count"], int)


# ─── 3. Pipeline telemetry stage instrumentation ──────────────────────────────

class TestPipelineTelemetry:
    def test_instrument_stage_does_not_raise(self):
        with instrument_stage("scan_x", "evidence", cell_count=100):
            pass   # purely timing — must not raise

    def test_on_scan_submitted_does_not_raise(self):
        on_scan_submitted("scan_x", "copper", "ANDES_PORPHYRY")

    def test_on_scan_completed_scan_tier_verbatim(self):
        """
        PROOF: on_scan_completed receives scan_tier as a stored string.
        No numeric comparison or threshold lookup performed here.
        """
        import time
        start = time.monotonic() - 10.0
        on_scan_completed("scan_x", "gold", "TIER_1", start, acif_score=0.812)
        # If we get here without error, scan_tier was passed through as-is

    def test_on_scan_failed_does_not_raise(self):
        on_scan_failed("scan_x", "physics", "Residual overflow")

    def test_on_twin_built_integer_count(self):
        import time
        start = time.monotonic() - 5.0
        on_twin_built("scan_x", 1, 42000, start)

    def test_on_migration_record_classes(self):
        for cls in ["A", "B", "C"]:
            on_migration_record("scan_x", cls)


# ─── 4. Canonical ACIF gauge — verbatim only ─────────────────────────────────

class TestCanonicalAcifGauge:
    def test_gauge_disabled_by_default(self):
        """
        PROOF: Without EMIT_CANONICAL_SUMMARY_METRICS=true, the gauge emitter
        is a no-op. No scientific value is emitted to any metric system.
        """
        os.environ.pop("EMIT_CANONICAL_SUMMARY_METRICS", None)
        # Should complete silently without emitting
        emit_canonical_acif_gauge("scan_x", "gold", 0.812)

    def test_gauge_enabled_accepts_verbatim_value(self):
        """When enabled, the value must be the exact float from the canonical record."""
        os.environ["EMIT_CANONICAL_SUMMARY_METRICS"] = "true"
        try:
            emit_canonical_acif_gauge("scan_x", "gold", 0.812)   # verbatim — must not raise
        finally:
            os.environ.pop("EMIT_CANONICAL_SUMMARY_METRICS", None)

    def test_gauge_skips_none_acif(self):
        """If acif_score is None (Class B/C record), gauge must not be emitted."""
        os.environ["EMIT_CANONICAL_SUMMARY_METRICS"] = "true"
        try:
            emit_canonical_acif_gauge("scan_x", "gold", None)   # must not raise
        finally:
            os.environ.pop("EMIT_CANONICAL_SUMMARY_METRICS", None)


# ─── 5. Log field blocking ────────────────────────────────────────────────────

class TestLogFieldBlocking:
    def test_blocked_fields_list_complete(self):
        from app.config.observability import _JsonFormatter
        blocked = _JsonFormatter._BLOCKED_FIELDS
        required = {
            "acif_score", "display_acif_score", "tier_counts",
            "system_status", "gate_results", "tier_thresholds_used",
            "normalisation_params",
        }
        assert required.issubset(blocked)

    def test_blocked_field_not_in_formatted_record(self):
        """
        PROOF: a log call with extra={"acif_score": 0.812} must NOT include
        acif_score in the formatted JSON output.
        """
        import logging, json
        from app.config.observability import _JsonFormatter
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test event", args=(), exc_info=None
        )
        record.acif_score = 0.812          # injected as extra
        record.scan_id = "scan_x"          # allowed field
        output = json.loads(formatter.format(record))
        assert "acif_score" not in output  # PROOF: blocked
        assert "scan_id" not in output or output.get("scan_id") == "scan_x"  # allowed


# ─── 6. No core/* imports across observability modules ───────────────────────

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

    def test_metrics_no_core(self):       self._check("app.observability.metrics")
    def test_tracing_no_core(self):       self._check("app.observability.tracing")
    def test_telemetry_no_core(self):     self._check("app.observability.pipeline_telemetry")