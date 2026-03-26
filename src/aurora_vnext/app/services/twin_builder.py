"""
Aurora OSI vNext — Digital Twin Builder Service
Phase N §N.1 | Phase B §15

Responsibility: project frozen 2D ScanCell outputs into 3D voxel columns via
the depth kernel D^(c)(z), write versioned DigitalTwinVoxel records to
storage/twin.py, and produce a TwinBuildManifest for full audit traceability.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONSTITUTIONAL RULES (Phase N):

  Rule 1 (Read-Only Source):    Twin builder reads CanonicalScan and ScanCell
                                records ONLY. It never reads from ScanJob,
                                pipeline context, or in-progress state.
                                Proof: only storage reads in build_twin().

  Rule 2 (No Re-scoring):       No call to compute_acif(), score_evidence(),
                                or any core/* scoring function. All score
                                values (acif_score, uncertainty, temporal_score,
                                physics_residual) are READ from frozen ScanCell
                                records and PROPAGATED verbatim.

  Rule 3 (No Re-tiering):       No call to assign_tier() or ThresholdSet.
                                Tier data is NOT used inside the twin builder.
                                (It is already in the frozen ScanCell record;
                                the twin represents depth, not tier assignment.)

  Rule 4 (No Re-gating):        No call to evaluate_gates() or GateInputs.

  Rule 5 (Deterministic Projection): D^(c)(z) is a pure mathematical function
                                of the depth kernel parameters from Θ_c and
                                the cell's ACIF score from the frozen record.
                                Given the same inputs it always produces the
                                same outputs.

  Rule 6 (Versioned Lineage):   Every voxel carries scan_id, source_cell_id,
                                twin_version, and kernel_weight.
                                TwinBuildManifest carries the full
                                version_registry snapshot from CanonicalScan.

  Rule 7 (CanonicalScan Immutability): This module NEVER writes to
                                canonical_scans or scan_cells tables.
                                It reads them once (post-freeze) and only
                                writes to digital_twin_voxels.

LAYER RULE: This is a Layer-2 Service.
  May import from: models/, config/.
  Must NOT import from: core/scoring, core/tiering, core/gates, core/evidence,
                        core/causal, core/physics, core/temporal, core/priors,
                        core/uncertainty, api/, pipeline/.

DEPTH KERNEL FORMULA (§15.2):
  D^(c)(z) = exp(−(z − z_expected)² / (2 × σ_z²))

  p_commodity(z) = clamp(ACIF_i × D^(c)(z), 0, 1)

  expected_density(z) = ρ_background + dρ/dz × z
  density_uncertainty(z) ∝ ScanCell.uncertainty × σ_z / max(depth_z, 1)

CONSTITUTIONAL IMPORT GUARD: must never import from
  core/scoring, core/tiering, core/gates, core/evidence,
  core/causal, core/physics, core/temporal, core/priors, core/uncertainty.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol

from app.models.digital_twin_model import (
    DepthKernelConfig,
    DigitalTwinVoxel,
    TwinBuildManifest,
    VoxelLineage,
)


# ---------------------------------------------------------------------------
# Storage protocol — injected; never imported from storage/ directly
# ---------------------------------------------------------------------------

class TwinStorageAdapter(Protocol):
    """
    Minimal storage interface injected into the twin builder.
    Real implementation: storage/twin.py DigitalTwinStore.
    Allows testing without a database.
    """
    async def write_voxels(
        self,
        scan_id: str,
        voxels: list[DigitalTwinVoxel],
        twin_version: int,
        trigger_type: str,
        parent_version: Optional[int],
    ) -> None: ...

    async def get_next_twin_version(self, scan_id: str) -> int: ...

    async def write_twin_manifest(
        self, scan_id: str, manifest: TwinBuildManifest
    ) -> None: ...


class CanonicalReadAdapter(Protocol):
    """
    Read-only adapter for accessing frozen CanonicalScan and ScanCell records.
    Injected by the caller — never imported from storage/ here.
    """
    async def get_canonical_scan(self, scan_id: str) -> dict: ...
    async def list_scan_cells(self, scan_id: str) -> list[dict]: ...


# ---------------------------------------------------------------------------
# Depth kernel — pure mathematics, no imports from core/
# ---------------------------------------------------------------------------

def compute_kernel_weight(
    depth_m: float,
    z_expected_m: float,
    sigma_z_m: float,
) -> float:
    """
    §15.2 — Gaussian depth kernel D^(c)(z).

    D^(c)(z) = exp(−(z − z_expected)² / (2 × σ_z²))

    Returns weight ∈ (0, 1]. Value is 1.0 at z = z_expected and
    decays symmetrically with distance from the expected depth.

    Args:
        depth_m:      Depth of the voxel slice (metres).
        z_expected_m: Expected target depth from Θ_c (metres).
        sigma_z_m:    Kernel width — depth uncertainty (metres).

    Returns:
        Kernel weight D^(c)(z) ∈ (0, 1].
    """
    exponent = -((depth_m - z_expected_m) ** 2) / (2.0 * sigma_z_m ** 2)
    return math.exp(exponent)


def project_commodity_probability(
    acif_score: Optional[float],
    kernel_weight: float,
    commodity: str,
) -> dict[str, float]:
    """
    §15.2 — Project ACIF score through depth kernel to commodity probability.

    p_commodity(z) = clamp(ACIF_i × D^(c)(z), 0, 1)

    This is the ONLY source of commodity_probs in every DigitalTwinVoxel.
    ACIF_i is read from the frozen ScanCell — never recomputed here.

    Returns:
        {commodity: probability} dict ready for DigitalTwinVoxel.commodity_probs.
    """
    if acif_score is None:
        return {commodity: 0.0}
    prob = max(0.0, min(1.0, acif_score * kernel_weight))
    return {commodity: prob}


def compute_expected_density(
    depth_m: float,
    background_density_kg_m3: float,
    density_gradient_kg_m3_per_m: float,
) -> float:
    """
    §15.3 — Compute expected bulk density at a given depth.

    ρ(z) = ρ_background + (dρ/dz) × z

    All parameters sourced from DepthKernelConfig (Θ_c).
    This is NOT a re-inversion — it is a linear crustal model.

    Args:
        depth_m:                      Voxel depth (metres).
        background_density_kg_m3:     ρ_background from Θ_c (kg/m³).
        density_gradient_kg_m3_per_m: dρ/dz from Θ_c (kg/m³/m).

    Returns:
        Expected bulk density (kg/m³).
    """
    return background_density_kg_m3 + density_gradient_kg_m3_per_m * depth_m


def compute_density_uncertainty(
    cell_uncertainty: Optional[float],
    sigma_z_m: float,
    depth_m: float,
) -> Optional[float]:
    """
    §15.3 — Propagate cell uncertainty to depth-adjusted density uncertainty.

    density_unc(z) = U_i × (σ_z / max(z, 1)) × 1000  [kg/m³]

    U_i is read verbatim from the frozen ScanCell — not recomputed.
    σ_z is from DepthKernelConfig. The factor 1000 converts the dimensionless
    uncertainty into a rough density spread.

    Returns:
        Density uncertainty in kg/m³, or None if cell uncertainty unavailable.
    """
    if cell_uncertainty is None:
        return None
    return cell_uncertainty * (sigma_z_m / max(depth_m, 1.0)) * 1000.0


def depth_range_for_slice(
    depth_slices: list[float],
    idx: int,
) -> tuple[float, float]:
    """
    Compute (depth_min, depth_max) bounds for depth slice at index idx.
    Uses midpoints between adjacent slices; first/last use half-spacing.
    """
    z = depth_slices[idx]
    if len(depth_slices) == 1:
        half = z / 2.0 if z > 0 else 50.0
        return (max(0.0, z - half), z + half)
    prev_z = depth_slices[idx - 1] if idx > 0 else z - (depth_slices[1] - z)
    next_z = depth_slices[idx + 1] if idx < len(depth_slices) - 1 else z + (z - prev_z)
    return (max(0.0, (prev_z + z) / 2.0), (z + next_z) / 2.0)


# ---------------------------------------------------------------------------
# Cell-to-voxel projection
# ---------------------------------------------------------------------------

def project_cell_to_voxels(
    cell: dict,
    commodity: str,
    kernel_config: DepthKernelConfig,
    twin_version: int,
    built_at: str,
) -> tuple[list[DigitalTwinVoxel], list[VoxelLineage]]:
    """
    Project one frozen ScanCell record into a column of DigitalTwinVoxels.

    One voxel is produced per depth slice in kernel_config.depth_slices_m.

    PROOF OF NO RE-SCORING:
      - acif_score: cell["acif_score"] — read from frozen record
      - uncertainty: cell["uncertainty"] — read from frozen record
      - temporal_score: cell["temporal_score"] — read from frozen record
      - physics_residual: cell["physics_residual"] — read from frozen record
      None of these values are recomputed. They are propagated verbatim.

    Args:
        cell:          Frozen ScanCell dict (from canonical storage).
        commodity:     Commodity name (from CanonicalScan.commodity).
        kernel_config: Depth kernel parameters from Θ_c.
        twin_version:  Monotonic twin version index.
        built_at:      ISO timestamp of build.

    Returns:
        (voxels, lineage_records) — one entry per depth slice.
    """
    scan_id = cell["scan_id"]
    cell_id = cell["cell_id"]
    lat = cell.get("lat_center", 0.0)
    lon = cell.get("lon_center", 0.0)

    # Read verbatim from frozen ScanCell — no recomputation
    acif_score: Optional[float] = cell.get("acif_score")
    uncertainty: Optional[float] = cell.get("uncertainty")
    temporal_score: Optional[float] = cell.get("temporal_score")
    physics_residual: Optional[float] = cell.get("physics_residual")

    slices = kernel_config.depth_slices_m
    voxels: list[DigitalTwinVoxel] = []
    lineages: list[VoxelLineage] = []

    for idx, depth_m in enumerate(slices):
        voxel_id = f"{scan_id}_{cell_id}_v{twin_version}_d{int(depth_m)}"
        depth_range = depth_range_for_slice(slices, idx)

        # §15.2 Depth kernel weight
        kernel_weight = compute_kernel_weight(
            depth_m=depth_m,
            z_expected_m=kernel_config.z_expected_m,
            sigma_z_m=kernel_config.sigma_z_m,
        )

        # §15.2 Commodity probability — ACIF × kernel (no re-scoring)
        commodity_probs = project_commodity_probability(acif_score, kernel_weight, commodity)

        # §15.3 Expected density (crustal gradient model from Θ_c)
        expected_density = compute_expected_density(
            depth_m=depth_m,
            background_density_kg_m3=kernel_config.background_density_kg_m3,
            density_gradient_kg_m3_per_m=kernel_config.density_gradient_kg_m3_per_m,
        )

        # §15.3 Density uncertainty propagated from cell uncertainty
        density_uncertainty = compute_density_uncertainty(
            cell_uncertainty=uncertainty,
            sigma_z_m=kernel_config.sigma_z_m,
            depth_m=depth_m,
        )

        voxel = DigitalTwinVoxel(
            voxel_id=voxel_id,
            scan_id=scan_id,
            twin_version=twin_version,
            lat_center=lat,
            lon_center=lon,
            depth_m=depth_m,
            depth_range_m=depth_range,
            commodity_probs=commodity_probs,
            expected_density=expected_density,
            density_uncertainty=density_uncertainty,
            # Propagated verbatim from frozen ScanCell — no recomputation
            temporal_score=temporal_score,
            physics_residual=physics_residual,
            uncertainty=uncertainty,
            kernel_weight=kernel_weight,
            source_cell_id=cell_id,
            created_at=datetime.fromisoformat(built_at) if "T" in built_at else datetime.now(timezone.utc),
        )
        voxels.append(voxel)

        lineage = VoxelLineage(
            voxel_id=voxel_id,
            scan_id=scan_id,
            cell_id=cell_id,
            twin_version=twin_version,
            scan_pipeline_version="",   # filled by build_twin()
            score_version="",            # filled by build_twin()
            physics_model_version="",    # filled by build_twin()
            source_acif_score=acif_score,
            source_uncertainty=uncertainty,
            source_temporal_score=temporal_score,
            source_physics_residual=physics_residual,
            z_expected_m=kernel_config.z_expected_m,
            sigma_z_m=kernel_config.sigma_z_m,
            depth_slice_m=depth_m,
            kernel_weight=kernel_weight,
            built_at=built_at,
        )
        lineages.append(lineage)

    return voxels, lineages


# ---------------------------------------------------------------------------
# Default depth kernel configs per mineral family
# ---------------------------------------------------------------------------

DEFAULT_DEPTH_KERNELS: dict[str, DepthKernelConfig] = {
    "epithermal": DepthKernelConfig(
        commodity="generic", z_expected_m=50.0, sigma_z_m=25.0,
        depth_slices_m=[25.0, 50.0, 100.0, 150.0, 200.0],
    ),
    "orogenic_gold": DepthKernelConfig(
        commodity="generic", z_expected_m=200.0, sigma_z_m=80.0,
        depth_slices_m=[100.0, 200.0, 300.0, 500.0, 750.0],
    ),
    "porphyry": DepthKernelConfig(
        commodity="generic", z_expected_m=500.0, sigma_z_m=200.0,
        depth_slices_m=[200.0, 400.0, 600.0, 800.0, 1000.0, 1500.0],
    ),
    "vms_sedex": DepthKernelConfig(
        commodity="generic", z_expected_m=150.0, sigma_z_m=60.0,
        depth_slices_m=[50.0, 100.0, 150.0, 200.0, 300.0],
    ),
    "skarn": DepthKernelConfig(
        commodity="generic", z_expected_m=300.0, sigma_z_m=100.0,
        depth_slices_m=[100.0, 200.0, 300.0, 500.0, 700.0, 1000.0],
    ),
    "kimberlite": DepthKernelConfig(
        commodity="generic", z_expected_m=800.0, sigma_z_m=300.0,
        depth_slices_m=[200.0, 400.0, 600.0, 800.0, 1000.0, 1500.0],
    ),
    "seabed": DepthKernelConfig(
        commodity="generic", z_expected_m=75.0, sigma_z_m=30.0,
        depth_slices_m=[25.0, 50.0, 75.0, 100.0, 150.0],
    ),
    "pge_intrusion": DepthKernelConfig(
        commodity="generic", z_expected_m=1000.0, sigma_z_m=400.0,
        depth_slices_m=[400.0, 600.0, 800.0, 1000.0, 1500.0, 2000.0],
    ),
    "coal_oil_sands": DepthKernelConfig(
        commodity="generic", z_expected_m=2000.0, sigma_z_m=600.0,
        depth_slices_m=[500.0, 1000.0, 1500.0, 2000.0, 2500.0, 3000.0],
    ),
}


def get_depth_kernel_for_commodity(
    commodity: str,
    family: Optional[str] = None,
    override_z_expected_m: Optional[float] = None,
    override_sigma_z_m: Optional[float] = None,
) -> DepthKernelConfig:
    """
    Retrieve and optionally override depth kernel config for a commodity.

    Lookup order:
      1. family-specific defaults (DEFAULT_DEPTH_KERNELS)
      2. Θ_c overrides if provided

    The returned config always has commodity name injected.
    """
    base = DEFAULT_DEPTH_KERNELS.get(family or "", DEFAULT_DEPTH_KERNELS["orogenic_gold"])
    z = override_z_expected_m or base.z_expected_m
    s = override_sigma_z_m or base.sigma_z_m
    return DepthKernelConfig(
        commodity=commodity,
        z_expected_m=z,
        sigma_z_m=s,
        depth_slices_m=base.depth_slices_m,
        density_gradient_kg_m3_per_m=base.density_gradient_kg_m3_per_m,
        background_density_kg_m3=base.background_density_kg_m3,
    )


# ---------------------------------------------------------------------------
# Main twin builder entry point
# ---------------------------------------------------------------------------

async def build_twin(
    scan_id: str,
    canonical_store: CanonicalReadAdapter,
    twin_store: TwinStorageAdapter,
    family: Optional[str] = None,
    override_kernel: Optional[DepthKernelConfig] = None,
    trigger_type: str = "initial",
    parent_version: Optional[int] = None,
) -> TwinBuildManifest:
    """
    Build a versioned digital twin from a frozen CanonicalScan.

    PHASE N CONSTITUTIONAL PROOF:
      1. Reads CanonicalScan via canonical_store.get_canonical_scan() → read-only.
      2. Reads ScanCells via canonical_store.list_scan_cells() → read-only.
      3. Writes ONLY to digital_twin_voxels via twin_store.write_voxels().
      4. Never calls compute_acif(), score_*, assign_tier(), evaluate_gates().
      5. All score values propagated verbatim from frozen ScanCell dicts.
      6. Returns TwinBuildManifest with full version_registry snapshot.
      7. CanonicalScan record is never mutated — the store adapter has no write method.

    Args:
        scan_id:          Target CanonicalScan.scan_id (must be COMPLETED).
        canonical_store:  Read-only canonical storage adapter.
        twin_store:       Twin write adapter.
        family:           Commodity family for depth kernel lookup.
        override_kernel:  Optional full DepthKernelConfig override from Θ_c.
        trigger_type:     'initial' | 'reprocess'.
        parent_version:   Previous twin version (for reprocess lineage).

    Returns:
        TwinBuildManifest — full audit record for this build.

    Raises:
        ValueError: If scan is not COMPLETED, or no cells found.
    """
    built_at = datetime.now(timezone.utc).isoformat()

    # Step 1: Load frozen CanonicalScan (read-only)
    canonical = await canonical_store.get_canonical_scan(scan_id)
    if canonical.get("status") != "COMPLETED":
        raise ValueError(
            f"Twin builder requires a COMPLETED CanonicalScan. "
            f"scan_id={scan_id} has status={canonical.get('status')}."
        )

    commodity = canonical.get("commodity", "unknown")
    version_registry = canonical.get("version_registry") or {}

    # Step 2: Load frozen ScanCell records (read-only)
    cells = await canonical_store.list_scan_cells(scan_id)
    if not cells:
        raise ValueError(
            f"Twin builder found zero ScanCell records for scan_id={scan_id}. "
            f"Ensure canonical freeze wrote scan cells before twin build is triggered."
        )

    # Step 3: Resolve depth kernel from Θ_c or defaults
    kernel = override_kernel or get_depth_kernel_for_commodity(
        commodity=commodity,
        family=family,
    )
    # Inject commodity name if using a default kernel
    kernel = DepthKernelConfig(
        commodity=commodity,
        z_expected_m=kernel.z_expected_m,
        sigma_z_m=kernel.sigma_z_m,
        depth_slices_m=kernel.depth_slices_m,
        density_gradient_kg_m3_per_m=kernel.density_gradient_kg_m3_per_m,
        background_density_kg_m3=kernel.background_density_kg_m3,
    )

    # Step 4: Determine twin version
    twin_version = await twin_store.get_next_twin_version(scan_id)

    # Step 5: Project all cells to voxels (pure mathematics — no re-scoring)
    all_voxels: list[DigitalTwinVoxel] = []
    all_lineages: list[VoxelLineage] = []
    scan_pip_ver = version_registry.get("scan_pipeline_version", "")
    score_ver = version_registry.get("score_version", "")
    physics_ver = version_registry.get("physics_model_version", "")

    for cell in cells:
        # Skip offshore-blocked cells — they have no valid ACIF
        if cell.get("offshore_gate_blocked"):
            continue
        if cell.get("acif_score") is None:
            continue

        voxels, lineages = project_cell_to_voxels(
            cell=cell,
            commodity=commodity,
            kernel_config=kernel,
            twin_version=twin_version,
            built_at=built_at,
        )
        # Inject version registry into lineage records
        for i, lin in enumerate(lineages):
            lineages[i] = VoxelLineage(
                **{**lin.__dict__,
                   "scan_pipeline_version": scan_pip_ver,
                   "score_version": score_ver,
                   "physics_model_version": physics_ver}
            )
        all_voxels.extend(voxels)
        all_lineages.extend(lineages)

    if not all_voxels:
        raise ValueError(
            f"Twin builder produced zero voxels for scan_id={scan_id}. "
            f"All cells may be offshore-blocked or have null ACIF scores."
        )

    # Step 6: Write voxels (ONLY write path — canonical_scans never touched)
    await twin_store.write_voxels(
        scan_id=scan_id,
        voxels=all_voxels,
        twin_version=twin_version,
        trigger_type=trigger_type,
        parent_version=parent_version,
    )

    # Step 7: Build and write manifest
    manifest = TwinBuildManifest(
        scan_id=scan_id,
        twin_version=twin_version,
        cells_projected=len(cells),
        voxels_produced=len(all_voxels),
        commodity=commodity,
        depth_kernel=kernel,
        score_version=score_ver,
        tier_version=version_registry.get("tier_version", ""),
        physics_model_version=physics_ver,
        scan_pipeline_version=scan_pip_ver,
        canonical_completed_at=canonical.get("completed_at"),
        built_at=built_at,
    )
    await twin_store.write_twin_manifest(scan_id, manifest)

    return manifest