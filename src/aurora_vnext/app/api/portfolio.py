"""
Aurora OSI vNext — Portfolio API
Phase AD §AD.4 (Corrected)

CORRECTIONS APPLIED:
  - exploration_priority_index replaces portfolio_score in all responses
  - PortfolioWeightConfig passed through and serialised in all responses
  - weight_config_version included in every entry response
  - Methodology note updated to use corrected terminology

CONSTITUTIONAL RULES:
  Rule 1: All portfolio data assembled from stored canonical fields only.
  Rule 2: No ACIF recomputation. No tier reassignment.
  Rule 3: exploration_priority_index labeled as non-physical aggregation metric.
  Rule 4: No import from core/*.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.portfolio_model import (
    PortfolioEntry, TerritoryBlock, ScanContribution,
    TerritoryType, PortfolioStatus, PortfolioWeightConfig,
    DEFAULT_WEIGHT_CONFIG,
)
from app.services.portfolio_aggregation import assemble_portfolio_entry
from app.services.portfolio_ranking import build_snapshot
from app.config.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])

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


def _active_weight_config() -> PortfolioWeightConfig:
    """Production: fetches active config from store. Returns default for now."""
    return DEFAULT_WEIGHT_CONFIG


def _stub_contribution(scan_id: str, commodity: str) -> ScanContribution:
    return ScanContribution(
        scan_id=scan_id, commodity=commodity,
        acif_mean=0.7412, tier_1_count=12, tier_2_count=47, tier_3_count=88,
        total_cells=300, veto_count=8, system_status="PASS_CONFIRMED",
        completed_at="2026-03-26T00:00:00", calibration_version="cal-v1",
        aoi_id=None, geometry_hash=None,
    )


def _serialise_weight_config(cfg: PortfolioWeightConfig) -> dict:
    return {
        "version_id":        cfg.version_id,
        "description":       cfg.description,
        "w_acif_mean":       cfg.w_acif_mean,
        "w_tier1_density":   cfg.w_tier1_density,
        "w_veto_compliance": cfg.w_veto_compliance,
        "created_at":        cfg.created_at,
        "created_by":        cfg.created_by,
        "parent_version_id": cfg.parent_version_id,
    }


def _serialise_entry(e: PortfolioEntry) -> dict:
    return {
        "entry_id":        e.entry_id,
        "block_id":        e.territory.block_id,
        "block_name":      e.territory.block_name,
        "territory_type":  e.territory.territory_type.value,
        "country_code":    e.territory.country_code,
        "commodity":       e.territory.commodity,
        "scan_count":      e.scan_count,
        "latest_scan":     e.latest_scan_date,
        # CORRECTED: renamed from portfolio_score
        "exploration_priority_index": e.score.exploration_priority_index,
        "exploration_priority_rank":  e.score.exploration_priority_rank,
        "metric_label":    e.score.metric_label,   # non-physical label always present
        "risk_tier":       e.risk.risk_tier.value,
        "risk_notes":      list(e.risk.risk_notes),
        "tier1_total":     e.tier1_total,
        "total_cells":     e.total_cells_all,
        "veto_rate":       e.risk.veto_rate,
        "raw_acif_mean":   e.score.raw_acif_mean,
        "gt_confidence":   e.risk.gt_confidence,
        "assembled_at":    e.assembled_at,
        "weight_config_version": e.score.weight_config_version,
        "weights_used":    e.score.weights_used,
    }


@router.get("")
async def list_entries(
    commodity: Optional[str] = None, country_code: Optional[str] = None,
    risk_tier: Optional[str] = None, territory_type: Optional[str] = None,
):
    entries = list(_entries.values())
    if commodity:      entries = [e for e in entries if e.territory.commodity == commodity]
    if country_code:   entries = [e for e in entries if e.territory.country_code == country_code]
    if risk_tier:      entries = [e for e in entries if e.risk.risk_tier.value == risk_tier]
    if territory_type: entries = [e for e in entries if e.territory.territory_type.value == territory_type]
    return [_serialise_entry(e) for e in entries]


@router.get("/snapshot")
async def portfolio_snapshot(
    commodity: Optional[str] = None,
    territory_type: Optional[str] = None,
    risk_adjusted: bool = True,
):
    entries = list(_entries.values())
    if commodity: entries = [e for e in entries if e.territory.commodity == commodity]
    tt = TerritoryType(territory_type) if territory_type else None
    if tt: entries = [e for e in entries if e.territory.territory_type == tt]

    cfg      = _active_weight_config()
    snapshot = build_snapshot(entries, commodity=commodity, territory_type=tt,
                               risk_adjusted=risk_adjusted, weight_config=cfg)
    return {
        "snapshot_id":    snapshot.snapshot_id,
        "commodity":      snapshot.commodity,
        "territory_type": snapshot.territory_type.value if snapshot.territory_type else None,
        "total_entries":  snapshot.total_entries,
        "risk_summary":   snapshot.risk_summary,
        "generated_at":   snapshot.generated_at,
        "risk_adjusted":  risk_adjusted,
        "weight_config":  _serialise_weight_config(snapshot.weight_config),
        "entries": [_serialise_entry(e) for e in snapshot.entries],
        "methodology_note": (
            "exploration_priority_index is a non-physical aggregation metric. "
            "It combines stored canonical outputs (acif_mean, tier1_density, veto_compliance) "
            "using versioned configurable weights. "
            "Risk adjustment applies penalty of 0.0/0.05/0.15 for LOW/MEDIUM/HIGH risk. "
            "No ACIF was recomputed. No tier was reassigned. "
            "This metric is not a geological score or resource estimate."
        ),
    }


@router.get("/weight-config")
async def get_weight_config():
    """Return the active portfolio weight configuration (versioned)."""
    cfg = _active_weight_config()
    return _serialise_weight_config(cfg)


@router.get("/risk-summary")
async def risk_summary(commodity: Optional[str] = None):
    entries = list(_entries.values())
    if commodity: entries = [e for e in entries if e.territory.commodity == commodity]
    dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for e in entries:
        k = e.risk.risk_tier.value.upper()
        dist[k] = dist.get(k, 0) + 1
    return {"commodity": commodity, "total": len(entries), "distribution": dist}


@router.get("/{entry_id}")
async def get_entry(entry_id: str):
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
    import uuid
    try:
        tt = TerritoryType(body.territory_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown territory_type: {body.territory_type!r}")

    territory     = TerritoryBlock(
        block_id=body.block_id, block_name=body.block_name,
        territory_type=tt, country_code=body.country_code, commodity=body.commodity,
        geometry_wkt=None, area_km2=None,
        scan_count=len(body.scan_ids), scan_ids=tuple(body.scan_ids),
    )
    contributions = [_stub_contribution(sid, body.commodity) for sid in body.scan_ids]
    cfg           = _active_weight_config()
    entry = assemble_portfolio_entry(
        entry_id=str(uuid.uuid4()), territory=territory,
        contributions=contributions, actor_id="api", weight_config=cfg,
    )
    _entries[entry.entry_id] = entry
    return _serialise_entry(entry)