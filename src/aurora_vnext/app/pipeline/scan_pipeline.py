"""
Aurora OSI vNext — Scan Execution Pipeline
Phase L §L.1 | Phase C §7

Implements the full 21-step pipeline from scan submission to canonical freeze.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MUTABLE PHASE   (steps  1–18): ScanJob is updated at each stage.
FREEZE POINT    (step  19):    CanonicalScan written — single atomic, irreversible.
POST-FREEZE     (steps 20–21): Read-only. No mutations.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONSTITUTIONAL RULES:
  1. δh MUST come from Θ_c.delta_h_m — never from DELTA_H_SHALLOW_FALLBACK_M.
  2. Offshore cells MUST pass services/offshore.apply_offshore_correction()
     before harmonisation. Failure → cell is marked offshore_gate_blocked=True
     and excluded from evidence scoring.
  3. core/scoring.py is the SOLE authority for ACIF computation.
  4. core/tiering.py is the SOLE authority for tier assignment.
  5. core/gates.py is the SOLE authority for system status derivation.
  6. CanonicalScan freeze is irreversible. Storage layer rejects re-writes.
  7. ScanJob carries ZERO score fields. All results go to CanonicalScan only.

LAYER RULE: This module sits in the pipeline layer (Layer 3).
  It may import from: core/, services/, models/, config/.
  It must NOT import from: api/, storage/ (storage interactions are passed
  as injected callables — StorageAdapter protocol below).
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional, Protocol

from app.config.constants import (
    DELTA_H_RANGE_MAX_M,
    DELTA_H_RANGE_MIN_M,
)
from app.core.causal import score_causal
from app.core.evidence import score_evidence
from app.core.gates import GateInputs, GateThresholds, evaluate_gates
from app.core.normalisation import (
    NormalisationParams,
    compute_scan_normalisation_params,
    normalise_observable,
)
from app.core.physics import score_physics
from app.core.priors import score_province_prior
from app.core.scoring import MissingComponentPolicy, compute_acif, compute_scan_aggregates
from app.core.temporal import score_temporal
from app.core.tiering import (
    ThresholdSet,
    assign_tiers_batch,
    compute_percentile_thresholds,
)
from app.core.uncertainty import score_uncertainty
from app.models.component_scores import ComponentScoreBundle
from app.models.scan_cell import ScanCell
from app.services.audit import (
    ServiceAuditEvent,
    build_gravity_event,
    build_harmonisation_event,
    build_offshore_correction_event,
)
from app.services.gee import CellGeometry, GEEClient, acquire_raw_sensor_bundle
from app.services.gravity import build_gravity_composite
from app.services.harmonization import build_harmonised_tensor
from app.services.offshore import apply_offshore_correction, is_offshore_cell
from app.services.quantum import invert_gravity


# ---------------------------------------------------------------------------
# Pipeline stage enumeration
# ---------------------------------------------------------------------------

class PipelineStage(str, Enum):
    INIT                 = "INIT"
    GRID_DECOMPOSITION   = "GRID_DECOMPOSITION"
    SENSOR_ACQUISITION   = "SENSOR_ACQUISITION"
    OFFSHORE_CORRECTION  = "OFFSHORE_CORRECTION"
    GRAVITY_DECOMP       = "GRAVITY_DECOMP"
    HARMONISATION        = "HARMONISATION"
    NORMALISATION_PASS1  = "NORMALISATION_PASS1"
    NORMALISATION_PASS2  = "NORMALISATION_PASS2"
    EVIDENCE_SCORING     = "EVIDENCE_SCORING"
    CAUSAL_SCORING       = "CAUSAL_SCORING"
    PHYSICS_SCORING      = "PHYSICS_SCORING"
    TEMPORAL_SCORING     = "TEMPORAL_SCORING"
    PRIOR_SCORING        = "PRIOR_SCORING"
    UNCERTAINTY_SCORING  = "UNCERTAINTY_SCORING"
    ACIF_COMPUTATION     = "ACIF_COMPUTATION"
    TIER_ASSIGNMENT      = "TIER_ASSIGNMENT"
    GATE_EVALUATION      = "GATE_EVALUATION"
    PRE_FREEZE_VALIDATION= "PRE_FREEZE_VALIDATION"
    CANONICAL_FREEZE     = "CANONICAL_FREEZE"
    AUDIT_EMIT           = "AUDIT_EMIT"
    COMPLETE             = "COMPLETE"


# ---------------------------------------------------------------------------
# Θ_c commodity configuration (minimal interface — Phase F populates fully)
# ---------------------------------------------------------------------------

@dataclass
class CommodityConfig:
    """
    Per-commodity parameter block Θ_c.
    Phase F will populate from the full commodity library.
    Phase L requires only the fields below.
    """
    name: str
    family: str
    delta_h_m: float                              # REQUIRED — no fallback
    evidence_weights: dict[str, float]            # Observable key → weight
    alpha_c: float = 0.3                          # Clustering sensitivity
    causal_edges: Optional[list] = None           # DAG edges override
    veto_thresholds: Optional[dict[str, float]] = None
    gate_thresholds: Optional[GateThresholds] = None
    threshold_set: Optional[ThresholdSet] = None  # If None → percentile policy


# ---------------------------------------------------------------------------
# Physics model config guard
# ---------------------------------------------------------------------------

class PhysicsModelConfigError(ValueError):
    """Raised when Θ_c.delta_h_m is missing, None, or out of bounds."""


def _validate_delta_h(delta_h_m: float) -> None:
    """Enforce δh is within the canonical allowed range."""
    if delta_h_m is None:
        raise PhysicsModelConfigError(
            "Θ_c.delta_h_m is None. The scan pipeline requires an explicit δh from the "
            "commodity configuration. DELTA_H_SHALLOW_FALLBACK_M must never be used here."
        )
    if not (DELTA_H_RANGE_MIN_M <= delta_h_m <= DELTA_H_RANGE_MAX_M):
        raise PhysicsModelConfigError(
            f"Θ_c.delta_h_m={delta_h_m} m is outside the allowed range "
            f"[{DELTA_H_RANGE_MIN_M}, {DELTA_H_RANGE_MAX_M}] m."
        )


# ---------------------------------------------------------------------------
# Cell descriptor — internal pipeline representation
# ---------------------------------------------------------------------------

@dataclass
class GridCell:
    """One decomposed spatial cell from the scan AOI."""
    cell_id: str
    scan_id: str
    lat_centre: float
    lon_centre: float
    cell_size_degrees: float
    environment: str      # ONSHORE | OFFSHORE | COMBINED
    area_weight: float    # Cosine-latitude area weighting


# ---------------------------------------------------------------------------
# Pipeline context — carries all mutable state through steps 1–18
# ---------------------------------------------------------------------------

@dataclass
class PipelineContext:
    """
    Accumulates all intermediate results through the 21-step pipeline.
    Passed by reference through each stage function.
    Written to CanonicalScan at step 19 and then discarded.
    """
    scan_id: str
    commodity_config: CommodityConfig
    gee_client: GEEClient
    grid_cells: list[GridCell] = field(default_factory=list)
    date_start: str = ""
    date_end: str = ""
    environment: str = "ONSHORE"

    # Per-cell intermediate results (keyed by cell_id)
    raw_tensors: dict[str, dict] = field(default_factory=dict)
    harmonised_tensors: dict[str, object] = field(default_factory=dict)
    offshore_corrections: dict[str, object] = field(default_factory=dict)
    offshore_blocked: set[str] = field(default_factory=set)
    gravity_composites: dict[str, object] = field(default_factory=dict)
    inversion_results: dict[str, object] = field(default_factory=dict)

    # Scan-wide normalisation parameters (two-pass)
    normalisation_params: Optional[NormalisationParams] = None

    # Per-cell scored components
    component_bundles: dict[str, ComponentScoreBundle] = field(default_factory=dict)

    # Final per-cell outputs
    scan_cells: list[ScanCell] = field(default_factory=list)

    # Scan-level aggregates
    acif_results: list = field(default_factory=list)
    tier_list: list = field(default_factory=list)
    tier_counts: Optional[object] = None
    threshold_set: Optional[ThresholdSet] = None
    gate_result: Optional[object] = None

    # Audit events collected during execution
    audit_events: list[ServiceAuditEvent] = field(default_factory=list)

    # Stage tracking
    current_stage: PipelineStage = PipelineStage.INIT
    stage_progress: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Storage adapter protocol — injected by the scan worker; not imported here
# ---------------------------------------------------------------------------

class StorageAdapter(Protocol):
    """
    Minimal storage interface injected into the pipeline.
    Implementations live in storage/ — never imported here directly.
    """
    def update_scan_job_stage(self, scan_id: str, stage: str, progress_pct: float) -> None: ...
    def mark_scan_job_failed(self, scan_id: str, stage: str, error: str) -> None: ...
    def write_canonical_scan(self, scan_id: str, result: dict) -> None: ...
    def write_scan_cells(self, scan_id: str, cells: list[dict]) -> None: ...
    def write_audit_events(self, scan_id: str, events: list[dict]) -> None: ...
    def load_province_prior(self, cell_id: str, commodity: str) -> dict: ...


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------

def _step_grid_decomposition(ctx: PipelineContext, grid_spec: dict) -> None:
    """
    Step 2 — Decompose AOI into scan cells.
    Assigns environment label per cell based on bathymetry lookup stub.
    """
    res = grid_spec.get("resolution_degrees", 0.1)
    min_lat = grid_spec.get("min_lat", -30.0)
    max_lat = grid_spec.get("max_lat", -29.0)
    min_lon = grid_spec.get("min_lon", 121.0)
    max_lon = grid_spec.get("max_lon", 122.0)

    lat = min_lat
    idx = 0
    while lat < max_lat:
        lon = min_lon
        while lon < max_lon:
            cell_id = f"{ctx.scan_id}_c{idx:05d}"
            lat_c = lat + res / 2
            cos_w = max(math.cos(math.radians(lat_c)), 1e-6)
            ctx.grid_cells.append(GridCell(
                cell_id=cell_id,
                scan_id=ctx.scan_id,
                lat_centre=lat_c,
                lon_centre=lon + res / 2,
                cell_size_degrees=res,
                environment=ctx.environment,
                area_weight=cos_w,
            ))
            lon += res
            idx += 1
        lat += res


def _step_sensor_acquisition(ctx: PipelineContext) -> None:
    """
    Step 3 — Acquire raw sensor bundles for all cells (services/gee.py).
    Missing sensors are represented as None — not errors.
    """
    for gc in ctx.grid_cells:
        geom = CellGeometry(
            cell_id=gc.cell_id, scan_id=gc.scan_id,
            lat_centre=gc.lat_centre, lon_centre=gc.lon_centre,
            resolution_m=gc.cell_size_degrees * 111_000,
            environment=gc.environment,
        )
        bundle = acquire_raw_sensor_bundle(
            geom, ctx.gee_client, ctx.date_start, ctx.date_end
        )
        ctx.raw_tensors[gc.cell_id] = {
            "bundle": bundle, "geometry": geom,
        }


def _step_offshore_correction(ctx: PipelineContext) -> None:
    """
    Step 4 — Apply offshore correction gate (services/offshore.py).
    CONSTITUTIONAL: No offshore cell may proceed without CorrectedOffshoreCell.
    Cells that fail correction are marked offshore_gate_blocked=True.
    """
    for gc in ctx.grid_cells:
        if gc.environment not in ("OFFSHORE", "COMBINED"):
            continue
        raw = ctx.raw_tensors[gc.cell_id]["bundle"]
        if raw.bathymetric is None or not is_offshore_cell(raw.bathymetric.water_depth_m):
            ctx.offshore_blocked.add(gc.cell_id)
            continue
        corrected = apply_offshore_correction(
            cell_id=gc.cell_id, scan_id=gc.scan_id,
            bathymetric=raw.bathymetric,
            gravity=raw.gravity,
        )
        ctx.offshore_corrections[gc.cell_id] = corrected
        ctx.audit_events.append(build_offshore_correction_event(
            gc.cell_id, gc.scan_id,
            corrected.correction_quality,
            corrected.correction_warnings,
        ))


def _step_gravity_decomposition(ctx: PipelineContext) -> None:
    """
    Step 5 — Multi-orbit gravity decomposition (services/gravity.py).
    δh sourced exclusively from Θ_c — pipeline guard enforces this.
    """
    _validate_delta_h(ctx.commodity_config.delta_h_m)
    delta_h = ctx.commodity_config.delta_h_m

    for gc in ctx.grid_cells:
        raw = ctx.raw_tensors[gc.cell_id]["bundle"]
        if raw.gravity is None:
            continue
        composite = build_gravity_composite(raw.gravity, delta_h_m=delta_h)
        ctx.gravity_composites[gc.cell_id] = composite
        ctx.audit_events.append(build_gravity_event(
            gc.cell_id, gc.scan_id,
            composite.orbit_sources_used,
            composite.super_resolution_applied,
            composite.g_composite_mgal,
        ))


def _step_inversion(ctx: PipelineContext) -> None:
    """
    Step 6 — Gravity inversion (services/quantum.py, classical fallback).
    Produces rho_mean, rho_sigma, g_pred for physics residuals.
    """
    for gc in ctx.grid_cells:
        composite = ctx.gravity_composites.get(gc.cell_id)
        if composite is None:
            continue
        result = invert_gravity(
            cell_id=gc.cell_id, scan_id=gc.scan_id,
            g_obs_mgal=composite.g_composite_mgal,
        )
        ctx.inversion_results[gc.cell_id] = result


def _step_harmonisation(ctx: PipelineContext) -> None:
    """
    Step 7 — Build canonical 42-key feature tensor (services/harmonization.py).
    Offshore gate is enforced inside build_harmonised_tensor.
    """
    for gc in ctx.grid_cells:
        if gc.cell_id in ctx.offshore_blocked:
            continue
        raw = ctx.raw_tensors[gc.cell_id]["bundle"]
        composite = ctx.gravity_composites.get(gc.cell_id)
        corrected = ctx.offshore_corrections.get(gc.cell_id)

        tensor = build_harmonised_tensor(
            cell_id=gc.cell_id,
            scan_id=gc.scan_id,
            environment=gc.environment,
            optical_stacks=raw.optical_stacks,
            sar_stacks=raw.sar_stacks,
            thermal_stacks=raw.thermal_stacks,
            gravity_composite=composite,
            raw_gravity=raw.gravity,
            magnetic=raw.magnetic,
            corrected_offshore=corrected,
        )
        ctx.harmonised_tensors[gc.cell_id] = tensor
        ctx.audit_events.append(build_harmonisation_event(
            gc.cell_id, gc.scan_id,
            tensor.missions_used,
            tensor.present_count,
            tensor.coverage_fraction,
            tensor.offshore_corrected,
        ))


def _step_normalisation(ctx: PipelineContext) -> None:
    """
    Steps 8–9 — Two-pass normalisation (core/normalisation.py).
    Pass 1: compute scan-wide μ_k, σ_k across all cells.
    Pass 2: normalise each cell's feature tensor.
    """
    # Pass 1: collect all raw feature tensors
    all_tensors = {
        cid: t.feature_tensor
        for cid, t in ctx.harmonised_tensors.items()
    }
    ctx.normalisation_params = compute_scan_normalisation_params(all_tensors)

    # Pass 2: normalise in-place (update harmonised_tensors with normalised dict)
    for cell_id, tensor in ctx.harmonised_tensors.items():
        normalised: dict = {}
        for key, raw_val in tensor.feature_tensor.items():
            norm_val, _ = normalise_observable(
                key, raw_val, ctx.normalisation_params
            )
            normalised[key] = norm_val
        # Attach normalised tensor back — stored as extra dict
        ctx.raw_tensors[cell_id]["normalised"] = normalised


def _step_score_all_components(ctx: PipelineContext) -> None:
    """
    Steps 10–15 — Score all six Phase I components per cell.
    Each module (evidence, causal, physics, temporal, priors, uncertainty) is
    called independently. All results stored in ComponentScoreBundle.
    """
    cfg = ctx.commodity_config
    for gc in ctx.grid_cells:
        if gc.cell_id in ctx.offshore_blocked:
            continue
        cell_id = gc.cell_id
        normalised = ctx.raw_tensors.get(cell_id, {}).get("normalised", {})
        if not normalised:
            continue

        from app.models.observable_vector import ObservableVector
        obs_vec = ObservableVector(**{k: normalised.get(k) for k in normalised})

        # Evidence
        ev_result = score_evidence(
            cell_id=cell_id, commodity=cfg.name,
            obs_vec=obs_vec, weights=cfg.evidence_weights,
            neighbour_evidence_scores=[],   # Phase N: spatial neighbours
            e_max=1.0,                      # Phase N: scan-wide max
            alpha_c=cfg.alpha_c,
        )

        # Causal
        ca_result = score_causal(
            cell_id=cell_id, commodity=cfg.name,
            obs_vec=obs_vec,
            edges=cfg.causal_edges,
            veto_thresholds=cfg.veto_thresholds,
        )

        # Physics
        inv = ctx.inversion_results.get(cell_id)
        raw_g = ctx.raw_tensors[cell_id]["bundle"].gravity
        ph_result = score_physics(
            cell_id=cell_id, commodity=cfg.name,
            g_obs_mgal=raw_g.free_air_leo_mgal if raw_g else None,
            g_pred_mgal=inv.g_pred if inv else None,
            phi_laplacian=None,
            rho_model=inv.rho_mean if inv else None,
        )

        # Temporal
        tm_result = score_temporal(
            cell_id=cell_id, commodity=cfg.name,
        )

        # Province prior
        prior_data = {}   # Phase N: province prior store lookup
        pr_result = score_province_prior(
            cell_id=cell_id, commodity=cfg.name,
            province_code=None,
            prior_probability=None,
        )

        # Uncertainty
        unc_result = score_uncertainty(
            cell_id=cell_id, commodity=cfg.name,
            coverage_fraction=ctx.harmonised_tensors[cell_id].coverage_fraction,
            rho_sigma=inv.rho_sigma if inv else None,
            physics_score=ph_result.physics_score,
            temporal_score=tm_result.temporal_score,
            province_prior_result=pr_result,
        )

        ctx.component_bundles[cell_id] = ComponentScoreBundle(
            cell_id=cell_id,
            commodity=cfg.name,
            evidence=ev_result,
            causal=ca_result,
            physics=ph_result,
            temporal=tm_result,
            province_prior=pr_result,
            uncertainty=unc_result,
        )


def _step_acif_computation(ctx: PipelineContext) -> None:
    """
    Step 16 — Compute ACIF for all cells (core/scoring.py ONLY).
    This is the SOLE call site for the ACIF formula in the pipeline.
    """
    for cell_id, bundle in ctx.component_bundles.items():
        result = compute_acif(bundle, policy=MissingComponentPolicy.DEGRADED)
        ctx.acif_results.append(result)


def _step_tier_assignment(ctx: PipelineContext) -> None:
    """
    Step 17 — Assign tiers (core/tiering.py ONLY).
    Uses PERCENTILE policy if Θ_c provides no frozen ThresholdSet.
    """
    acif_scores = [r.acif_score for r in ctx.acif_results]

    if ctx.commodity_config.threshold_set:
        ts = ctx.commodity_config.threshold_set
    else:
        ts = compute_percentile_thresholds(
            acif_scores, source_version="percentile_auto"
        )
    ctx.threshold_set = ts
    ctx.tier_list, ctx.tier_counts = assign_tiers_batch(acif_scores, ts)


def _step_gate_evaluation(ctx: PipelineContext) -> None:
    """
    Step 18 — Derive system status (core/gates.py ONLY).
    Assembles GateInputs from scan-level aggregates.
    """
    from app.core.tiering import Tier
    n = len(ctx.acif_results)
    n_tier_1 = sum(1 for t in ctx.tier_list if t == Tier.TIER_1)
    n_tier_2 = sum(1 for t in ctx.tier_list if t == Tier.TIER_2)
    n_phys_veto = sum(1 for r in ctx.acif_results if r.physics_veto)
    n_prov_veto = sum(1 for r in ctx.acif_results if r.province_veto)
    n_vetoed = sum(1 for r in ctx.acif_results if r.any_veto_fired)

    # Mean clustering of Tier-1 cells (Phase N: real κ_i; here neutral placeholder)
    mean_clust_t1 = 0.5

    # Mean temporal and uncertainty from bundles
    t_vals = [b.temporal.temporal_score for b in ctx.component_bundles.values()
              if b.temporal.temporal_score is not None]
    u_vals = [b.uncertainty.total_uncertainty for b in ctx.component_bundles.values()
              if b.uncertainty.total_uncertainty is not None]
    t_mean = sum(t_vals) / len(t_vals) if t_vals else 0.5
    u_mean = sum(u_vals) / len(u_vals) if u_vals else 0.5

    gate_inputs = GateInputs(
        n_cells=max(n, 1),
        n_tier_1=n_tier_1,
        n_tier_2=n_tier_2,
        n_vetoed_cells=n_vetoed,
        n_physics_vetoed=n_phys_veto,
        n_province_vetoed=n_prov_veto,
        mean_clustering_t1=mean_clust_t1,
        t_mean=t_mean,
        u_mean=u_mean,
        physics_veto_fraction=n_phys_veto / max(n, 1),
        province_veto_fraction=n_prov_veto / max(n, 1),
    )
    thresholds = ctx.commodity_config.gate_thresholds or GateThresholds()
    ctx.gate_result = evaluate_gates(gate_inputs, thresholds)


def _step_canonical_freeze(
    ctx: PipelineContext,
    storage: StorageAdapter,
    scan_request_meta: dict,
) -> dict:
    """
    Step 19 — Canonical freeze. Atomic write to storage.
    This is the ONLY path through which a CanonicalScan is created.
    After this step, no mutations are permitted.
    """
    from app.core.tiering import Tier
    from app.core.scoring import compute_scan_aggregates

    now = datetime.now(timezone.utc)

    # Scan-level ACIF aggregates
    area_weights = [gc.area_weight for gc in ctx.grid_cells
                    if gc.cell_id not in ctx.offshore_blocked]
    agg = compute_scan_aggregates(ctx.acif_results, area_weights or None)

    # Mean component scores
    bundles = list(ctx.component_bundles.values())
    def _safe_mean(vals):
        v = [x for x in vals if x is not None]
        return sum(v) / len(v) if v else None

    mean_ev  = _safe_mean([b.evidence.adjusted_evidence_score for b in bundles])
    mean_ca  = _safe_mean([b.causal.causal_score for b in bundles])
    mean_ph  = _safe_mean([b.physics.physics_score for b in bundles])
    mean_tm  = _safe_mean([b.temporal.temporal_score for b in bundles])
    mean_pi  = _safe_mean([b.province_prior.effective_prior for b in bundles])
    mean_unc = _safe_mean([b.uncertainty.total_uncertainty for b in bundles])

    # Build ScanCell list
    scan_cells = []
    for i, acif_r in enumerate(ctx.acif_results):
        tier = ctx.tier_list[i] if i < len(ctx.tier_list) else None
        bundle = ctx.component_bundles.get(acif_r.cell_id)
        h_tensor = ctx.harmonised_tensors.get(acif_r.cell_id)
        inv = ctx.inversion_results.get(acif_r.cell_id)
        gc = next((g for g in ctx.grid_cells if g.cell_id == acif_r.cell_id), None)

        scan_cells.append(ScanCell(
            cell_id=acif_r.cell_id,
            scan_id=ctx.scan_id,
            lat_center=gc.lat_centre if gc else 0.0,
            lon_center=gc.lon_centre if gc else 0.0,
            cell_size_degrees=gc.cell_size_degrees if gc else 0.1,
            environment=gc.environment if gc else ctx.environment,
            evidence_score=bundle.evidence.adjusted_evidence_score if bundle else None,
            causal_score=bundle.causal.causal_score if bundle else None,
            physics_score=bundle.physics.physics_score if bundle else None,
            temporal_score=bundle.temporal.temporal_score if bundle else None,
            province_prior=bundle.province_prior.effective_prior if bundle else None,
            uncertainty=bundle.uncertainty.total_uncertainty if bundle else None,
            acif_score=acif_r.acif_score,
            tier=tier.value if tier else None,
            gravity_residual=bundle.physics.residuals.gravity_residual if bundle else None,
            physics_residual=bundle.physics.residuals.physics_residual if bundle else None,
            water_column_residual=(
                ctx.offshore_corrections[acif_r.cell_id].water_column_residual
                if acif_r.cell_id in ctx.offshore_corrections else None
            ),
            causal_veto_fired=acif_r.causal_veto,
            physics_veto_fired=acif_r.physics_veto,
            temporal_veto_fired=acif_r.temporal_veto,
            province_veto_fired=acif_r.province_veto,
            offshore_gate_blocked=(acif_r.cell_id in ctx.offshore_blocked),
            u_sensor=bundle.uncertainty.u_sensor if bundle else None,
            u_model=bundle.uncertainty.u_model if bundle else None,
            u_physics=bundle.uncertainty.u_physics if bundle else None,
            u_temporal=bundle.uncertainty.u_temporal if bundle else None,
            u_prior=bundle.uncertainty.u_prior if bundle else None,
            observable_coverage_fraction=h_tensor.coverage_fraction if h_tensor else None,
            missing_observable_count=(
                42 - h_tensor.present_count if h_tensor else None
            ),
        ))

    ts = ctx.threshold_set
    canonical = {
        "scan_id": ctx.scan_id,
        "status": "COMPLETED",
        "commodity": ctx.commodity_config.name,
        "scan_tier": scan_request_meta.get("scan_tier", "SMART"),
        "environment": ctx.environment,
        "aoi_geojson": scan_request_meta.get("aoi_geojson", {}),
        "grid_resolution_degrees": scan_request_meta.get("resolution_degrees", 0.1),
        "total_cells": len(scan_cells),
        "display_acif_score": agg.acif_mean,
        "max_acif_score": agg.acif_max,
        "weighted_acif_score": agg.acif_weighted,
        "tier_counts": {
            "tier_1": ctx.tier_counts.tier_1,
            "tier_2": ctx.tier_counts.tier_2,
            "tier_3": ctx.tier_counts.tier_3,
            "below":  ctx.tier_counts.below,
            "total_cells": ctx.tier_counts.total,
        },
        "tier_thresholds_used": {
            "t1": ts.t1, "t2": ts.t2, "t3": ts.t3,
            "policy_type": ts.policy_type.value,
            "source_version": ts.source_version,
            "delta_h_m_used": ctx.commodity_config.delta_h_m,
        },
        "system_status": ctx.gate_result.system_status.value,
        "gate_rationale": ctx.gate_result.rationale,
        "mean_evidence_score": mean_ev,
        "mean_causal_score": mean_ca,
        "mean_physics_score": mean_ph,
        "mean_temporal_score": mean_tm,
        "mean_province_prior": mean_pi,
        "mean_uncertainty": mean_unc,
        "causal_veto_cell_count": sum(1 for r in ctx.acif_results if r.causal_veto),
        "physics_veto_cell_count": sum(1 for r in ctx.acif_results if r.physics_veto),
        "province_veto_cell_count": sum(1 for r in ctx.acif_results if r.province_veto),
        "offshore_blocked_cell_count": len(ctx.offshore_blocked),
        "offshore_cell_count": sum(
            1 for gc in ctx.grid_cells if gc.environment in ("OFFSHORE","COMBINED")
        ),
        "water_column_corrected": bool(ctx.offshore_corrections),
        "normalisation_params": ctx.normalisation_params.as_dict() if ctx.normalisation_params else None,
        "submitted_at": scan_request_meta.get("submitted_at", now.isoformat()),
        "completed_at": now.isoformat(),
        "parent_scan_id": scan_request_meta.get("parent_scan_id"),
    }

    # Atomic write — storage rejects duplicate scan_id
    storage.write_canonical_scan(ctx.scan_id, canonical)
    storage.write_scan_cells(ctx.scan_id, [sc.model_dump() for sc in scan_cells])

    return canonical


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def execute_scan_pipeline(
    scan_id: str,
    commodity_config: CommodityConfig,
    gee_client: GEEClient,
    storage: StorageAdapter,
    grid_spec: dict,
    date_start: str,
    date_end: str,
    environment: str = "ONSHORE",
    scan_request_meta: Optional[dict] = None,
) -> dict:
    """
    Execute the full 21-step Aurora scan pipeline.

    This is the ONLY entry point for scan execution.
    Called by the scan worker after dequeuing a scan job.

    Args:
        scan_id:            Globally unique scan identifier.
        commodity_config:   Θ_c for the target commodity (must include delta_h_m).
        gee_client:         Injected GEEClient (real or mock).
        storage:            Injected StorageAdapter.
        grid_spec:          AOI grid specification dict.
        date_start/end:     ISO date strings for sensor acquisition window.
        environment:        ONSHORE | OFFSHORE | COMBINED.
        scan_request_meta:  Additional metadata for the canonical record.

    Returns:
        Canonical scan result dict (same as written to storage).

    Raises:
        PhysicsModelConfigError: If Θ_c.delta_h_m is invalid.
        Any unhandled exception marks the ScanJob as FAILED via storage.
    """
    # Pre-flight guard — δh must be valid before any work begins
    _validate_delta_h(commodity_config.delta_h_m)

    ctx = PipelineContext(
        scan_id=scan_id,
        commodity_config=commodity_config,
        gee_client=gee_client,
        date_start=date_start,
        date_end=date_end,
        environment=environment,
    )
    meta = scan_request_meta or {}

    def _advance(stage: PipelineStage, pct: float) -> None:
        ctx.current_stage = stage
        storage.update_scan_job_stage(scan_id, stage.value, pct)

    try:
        _advance(PipelineStage.GRID_DECOMPOSITION, 5.0)
        _step_grid_decomposition(ctx, grid_spec)

        _advance(PipelineStage.SENSOR_ACQUISITION, 15.0)
        _step_sensor_acquisition(ctx)

        _advance(PipelineStage.OFFSHORE_CORRECTION, 20.0)
        _step_offshore_correction(ctx)

        _advance(PipelineStage.GRAVITY_DECOMP, 25.0)
        _step_gravity_decomposition(ctx)
        _step_inversion(ctx)

        _advance(PipelineStage.HARMONISATION, 35.0)
        _step_harmonisation(ctx)

        _advance(PipelineStage.NORMALISATION_PASS1, 42.0)
        _advance(PipelineStage.NORMALISATION_PASS2, 48.0)
        _step_normalisation(ctx)

        _advance(PipelineStage.EVIDENCE_SCORING, 55.0)
        _advance(PipelineStage.PHYSICS_SCORING, 60.0)
        _advance(PipelineStage.TEMPORAL_SCORING, 65.0)
        _advance(PipelineStage.PRIOR_SCORING, 70.0)
        _advance(PipelineStage.UNCERTAINTY_SCORING, 75.0)
        _step_score_all_components(ctx)

        _advance(PipelineStage.ACIF_COMPUTATION, 80.0)
        _step_acif_computation(ctx)

        _advance(PipelineStage.TIER_ASSIGNMENT, 85.0)
        _step_tier_assignment(ctx)

        _advance(PipelineStage.GATE_EVALUATION, 90.0)
        _step_gate_evaluation(ctx)

        _advance(PipelineStage.PRE_FREEZE_VALIDATION, 95.0)
        if not ctx.acif_results:
            raise ValueError("Pipeline produced zero ACIF results — cannot freeze.")

        _advance(PipelineStage.CANONICAL_FREEZE, 98.0)
        canonical = _step_canonical_freeze(ctx, storage, meta)

        _advance(PipelineStage.AUDIT_EMIT, 99.0)
        if ctx.audit_events:
            storage.write_audit_events(scan_id, [
                {"event_type": e.event_type.value, "cell_id": e.cell_id,
                 "timestamp_utc": e.timestamp_utc, "details": e.details,
                 "warnings": list(e.warnings)}
                for e in ctx.audit_events
            ])

        _advance(PipelineStage.COMPLETE, 100.0)
        return canonical

    except Exception as exc:
        storage.mark_scan_job_failed(scan_id, ctx.current_stage.value, str(exc))
        raise