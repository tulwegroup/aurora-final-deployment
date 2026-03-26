"""
Aurora OSI vNext — Reports API
Phase AB §AB.6

REST endpoints for geological report generation and retrieval.

Endpoints:
  POST /api/v1/reports/{scan_id}               — generate report for scan + audience
  GET  /api/v1/reports/{scan_id}               — list all reports for a scan
  GET  /api/v1/reports/{scan_id}/{report_id}   — get full report
  GET  /api/v1/reports/{scan_id}/{report_id}/audit — get audit trail only

CONSTITUTIONAL RULES:
  Rule 1: Generation endpoint is POST — explicitly signals side-effectful creation.
  Rule 2: No endpoint triggers canonical scan reprocessing.
  Rule 3: Audit trail always returned with every report.
  Rule 4: No ACIF computation in this layer.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.report_model import ReportAudience, GeologicalReport, SectionType
from app.config.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

# In-memory report store (replaced by storage adapter in production)
_reports: dict[str, list[GeologicalReport]] = {}   # scan_id → [reports]
_by_id:   dict[str, GeologicalReport] = {}         # report_id → report


class GenerateReportRequest(BaseModel):
    audience: str   # ReportAudience value

    class Config:
        extra = "forbid"


def _serialise_section(s) -> dict:
    return {
        "section_type":   s.section_type.value,
        "title":          s.title,
        "content":        s.content,
        "redaction_notes": s.redaction_notes,
        "citations": [
            {"field_path": c.field_path, "stored_value": c.stored_value, "relevance": c.relevance}
            for c in s.citations
        ],
    }


def _serialise_report(r: GeologicalReport, sections: bool = True) -> dict:
    out = {
        "report_id":  r.report_id,
        "scan_id":    r.scan_id,
        "commodity":  r.commodity,
        "audience":   r.audience.value,
        "status":     r.status.value,
        "summary":    r.summary,
        "has_redactions": r.has_redactions,
        "audit": {
            "report_version":               r.audit.report_version,
            "prompt_version":               r.audit.prompt_version,
            "grounding_snapshot_hash":      r.audit.grounding_snapshot_hash,
            "calibration_version_id":       r.audit.calibration_version_id,
            "mineral_system_logic_version": r.audit.mineral_system_logic_version,
            "generated_at":                 r.audit.generated_at,
            "generated_by":                 r.audit.generated_by,
            "llm_model_hint":               r.audit.llm_model_hint,
        },
    }
    if sections:
        out["sections"] = [_serialise_section(s) for s in r.sections]
    return out


@router.post("/{scan_id}", status_code=201)
async def generate_report(scan_id: str, body: GenerateReportRequest):
    """
    Generate a geological report for a completed canonical scan.
    The scan must be in COMPLETED status — no reprocessing triggered.
    """
    try:
        audience = ReportAudience(body.audience)
    except ValueError:
        valid = [a.value for a in ReportAudience]
        raise HTTPException(status_code=422, detail=f"Unknown audience. Valid: {valid}")

    # Production: inject ReportEngine with real storage + LLM caller
    # Here we use stub implementations for demo
    from app.services.report_engine import ReportEngine, ReportStorageAdapter, StubLLMCaller
    from app.services.report_grounding import assemble_grounding_bundle
    from app.services.mineral_system_logic import get_entry
    from app.models.report_model import (
        GeologicalReport, ReportSection, ReportAuditTrail, ReportStatus,
        SectionType, CitationRef, new_report_id
    )

    class InMemoryAdapter(ReportStorageAdapter):
        def fetch_canonical_scan(self, sid):
            # Returns a minimal stub scan for demo — production fetches from DB
            return {
                "scan_id": sid, "commodity": "gold",
                "display_acif_score": 0.7412,
                "tier_counts": {"TIER_1": 12, "TIER_2": 47, "TIER_3": 88, "BELOW": 153},
                "tier_thresholds": {"TIER_1": 0.75, "TIER_2": 0.55, "TIER_3": 0.35},
                "system_status": "PASS_CONFIRMED",
                "veto_explanations": [],
                "component_scores": {
                    "evidence": 0.7812, "causal": 0.6934,
                    "physics": 0.8201, "temporal": 0.7100,
                    "prior": 0.6500, "certainty": 0.8800,
                },
                "completed_at": "2026-03-26T00:00:00",
                "pipeline_version": "vnext-1.0.0",
                "total_cells": 300,
            }
        def fetch_calibration_trace(self, sid):
            return {"calibration_version_id": "cal-v1-stub"}
        def save_report(self, r):
            _reports.setdefault(r.scan_id, []).append(r)
            _by_id[r.report_id] = r

    engine = ReportEngine(InMemoryAdapter(), StubLLMCaller())
    import asyncio
    report = asyncio.get_event_loop().run_until_complete(
        engine.generate(scan_id, audience, actor_id="api")
    ) if False else None

    # Synchronous path for FastAPI (use background task in production for large reports)
    import asyncio as _asyncio
    loop = _asyncio.new_event_loop()
    try:
        report = loop.run_until_complete(engine.generate(scan_id, audience, actor_id="api"))
    finally:
        loop.close()

    return _serialise_report(report)


@router.get("/{scan_id}")
async def list_reports(scan_id: str):
    """List all reports generated for a scan."""
    rpts = _reports.get(scan_id, [])
    return [_serialise_report(r, sections=False) for r in rpts]


@router.get("/{scan_id}/{report_id}")
async def get_report(scan_id: str, report_id: str):
    """Get full report with sections and citations."""
    report = _by_id.get(report_id)
    if not report or report.scan_id != scan_id:
        raise HTTPException(status_code=404, detail="Report not found")
    return _serialise_report(report, sections=True)


@router.get("/{scan_id}/{report_id}/audit")
async def get_audit_trail(scan_id: str, report_id: str):
    """Return audit trail only — for compliance verification."""
    report = _by_id.get(report_id)
    if not report or report.scan_id != scan_id:
        raise HTTPException(status_code=404, detail="Report not found")
    r = report
    return {
        "report_id":  r.report_id,
        "scan_id":    r.scan_id,
        "grounding_snapshot_hash":      r.audit.grounding_snapshot_hash,
        "calibration_version_id":       r.audit.calibration_version_id,
        "mineral_system_logic_version": r.audit.mineral_system_logic_version,
        "prompt_version":               r.audit.prompt_version,
        "report_version":               r.audit.report_version,
        "generated_at":                 r.audit.generated_at,
        "has_redactions":               r.has_redactions,
        "total_citations":              len(r.all_citations),
    }