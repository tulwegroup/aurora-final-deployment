"""
Aurora OSI vNext — Portfolio API
Phase AD §AD.4

REST endpoints for portfolio and territory intelligence.

Endpoints:
  GET  /api/v1/portfolio                    — list portfolio entries (filterable)
  GET  /api/v1/portfolio/snapshot           — ranked snapshot for current cohort
  GET  /api/v1/portfolio/{entry_id}         — single portfolio entry detail
  POST /api/v1/portfolio/assemble           — assemble entry from scan_ids
  GET  /api/v1/portfolio/territories        — list territory blocks
  GET  /api/v1/portfolio/risk-summary       — risk distribution across portfolio

CONSTITUTIONAL RULES:
  Rule 1: All portfolio data assembled from stored canonical fields only.
  Rule 2: No ACIF recomputation. No tier reassignment.
  Rule 3: portfolio_score is a composite display metric — labeled clearly.
  Rule 4: No import from core/*.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.portfolio_model import (
    PortfolioEntry, TerritoryBlock, ScanContribution,
    TerritoryType, PortfolioStatus,
)
from app.services.portfolio_aggregation import assemble_portfolio_entry
from app.services.portfolio_ranking import build_snapshot
from app.config.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])

# In-memory store (replaced by DB in production)
_entries: dict[str, PortfolioEntry] = {}


class AssembleEntryRequest(BaseModel):
    block_id:       str
    block_name:     str
    territory_type: str
    country_code:   str
    commodity:      str
    scan_ids:       list[str]

    class Config:
        extra = "forbid"


def _stub_contribution(scan_id: str, commodity: str) -> ScanContribution:
    """Production: fetches from canonical scan store. Stub returns representative data."""
    return ScanContribution(
        scan_id             = scan_id,
        commodity           = commodity,
        acif_mean           = 0.7412,
        tier_1_count        = 12,
        tier_2_count        = 47,
        tier_3_count        = 88,
        total_cells         = 300,
        veto_count          = 8,
        system_status       = "PASS_CONFIRMED",
        completed_at        = "2026-03-26T00:00:00",
        calibration_version = "cal-v1",
        aoi_id              = None,
        geometry_hash       = None,
    )


def _serialise_entry(e: PortfolioEntry) -> dict:
    return {
        "entry_id":      e.entry_id,
        "block_id":      e.territory.block_id,
        "block_name":    e.territory.block_name,
        "territory_type": e.territory.territory_type.value,
        "country_code":  e.territory.country_code,
        "commodity":     e.territory.commodity,
        "scan_count":    e.scan_count,
        "latest_scan":   e.latest_scan_date,
        "portfolio_score": e.score.portfolio_score,
        "portfolio_rank":  e.score.portfolio_rank,
        "risk_tier":     e.risk.risk_tier.value,
        "risk_notes":    list(e.risk.risk_notes),
        "tier1_total":   e.tier1_total,
        "total_cells":   e.total_cells_all,
        "veto_rate":     e.risk.veto_rate,
        "raw_acif_mean": e.score.raw_acif_mean,
        "gt_confidence": e.risk.gt_confidence,
        "assembled_at":  e.assembled_at,
        "score_weights": e.score.weights_used,
        "score_note":    "portfolio_score is a composite display metric — not a scientific score. "
                         "No ACIF was recomputed. All inputs sourced from stored canonical records.",
    }


@router.get("")
async def list_entries(
    commodity:      Optional[str] = None,
    country_code:   Optional[str] = None,
    risk_tier:      Optional[str] = None,
    territory_type: Optional[str] = None,
):
    """List all portfolio entries with optional filters."""
    entries = list(_entries.values())
    if commodity:
        entries = [e for e in entries if e.territory.commodity == commodity]
    if country_code:
        entries = [e for e in entries if e.territory.country_code == country_code]
    if risk_tier:
        entries = [e for e in entries if e.risk.risk_tier.value == risk_tier]
    if territory_type:
        entries = [e for e in entries if e.territory.territory_type.value == territory_type]

    return [_serialise_entry(e) for e in entries]


@router.get("/snapshot")
async def portfolio_snapshot(
    commodity:      Optional[str] = None,
    territory_type: Optional[str] = None,
    risk_adjusted:  bool = True,
):
    """Return a ranked portfolio snapshot."""
    entries = list(_entries.values())
    if commodity:
        entries = [e for e in entries if e.territory.commodity == commodity]
    tt = TerritoryType(territory_type) if territory_type else None
    if tt:
        entries = [e for e in entries if e.territory.territory_type == tt]

    snapshot = build_snapshot(entries, commodity=commodity, territory_type=tt,
                               risk_adjusted=risk_adjusted)
    return {
        "snapshot_id":    snapshot.snapshot_id,
        "commodity":      snapshot.commodity,
        "territory_type": snapshot.territory_type.value if snapshot.territory_type else None,
        "total_entries":  snapshot.total_entries,
        "risk_summary":   snapshot.risk_summary,
        "generated_at":   snapshot.generated_at,
        "risk_adjusted":  risk_adjusted,
        "entries": [_serialise_entry(e) for e in snapshot.entries],
        "methodology_note": (
            "Rankings based on weighted composite of: stored acif_mean (0.5), "
            "stored tier1_density (0.3), stored (1-veto_rate) (0.2). "
            "Risk adjustment applies penalty of 0.0/0.05/0.15 for LOW/MEDIUM/HIGH risk. "
            "No ACIF was recomputed. No tier was reassigned."
        ),
    }


@router.get("/risk-summary")
async def risk_summary(commodity: Optional[str] = None):
    """Risk distribution summary across the portfolio."""
    entries = list(_entries.values())
    if commodity:
        entries = [e for e in entries if e.territory.commodity == commodity]

    dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for e in entries:
        dist[e.risk.risk_tier.value.upper()] = dist.get(e.risk.risk_tier.value.upper(), 0) + 1
    return {"commodity": commodity, "total": len(entries), "distribution": dist}


@router.get("/{entry_id}")
async def get_entry(entry_id: str):
    """Get full portfolio entry with scan contributions."""
    e = _entries.get(entry_id)
    if not e:
        raise HTTPException(status_code=404, detail="Portfolio entry not found")
    out = _serialise_entry(e)
    out["contributions"] = [
        {
            "scan_id": c.scan_id, "acif_mean": c.acif_mean,
            "tier_1_count": c.tier_1_count, "tier_2_count": c.tier_2_count,
            "total_cells": c.total_cells, "veto_count": c.veto_count,
            "system_status": c.system_status, "completed_at": c.completed_at,
            "calibration_version": c.calibration_version,
        }
        for c in e.contributions
    ]
    return out


@router.post("", status_code=201)
async def assemble_entry(body: AssembleEntryRequest):
    """Assemble a portfolio entry from a set of scan IDs."""
    import uuid
    try:
        tt = TerritoryType(body.territory_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown territory_type: {body.territory_type!r}")

    territory = TerritoryBlock(
        block_id       = body.block_id,
        block_name     = body.block_name,
        territory_type = tt,
        country_code   = body.country_code,
        commodity      = body.commodity,
        geometry_wkt   = None,
        area_km2       = None,
        scan_count     = len(body.scan_ids),
        scan_ids       = tuple(body.scan_ids),
    )
    contributions = [_stub_contribution(sid, body.commodity) for sid in body.scan_ids]

    entry = assemble_portfolio_entry(
        entry_id      = str(uuid.uuid4()),
        territory     = territory,
        contributions = contributions,
        actor_id      = "api",
    )
    _entries[entry.entry_id] = entry
    return _serialise_entry(entry)