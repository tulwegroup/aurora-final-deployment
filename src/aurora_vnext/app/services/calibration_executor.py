"""
Aurora OSI vNext — Calibration Executor
Phase AC §AC.3

Executes a calibration run against a set of approved ground-truth records
and produces a new CalibrationVersion.

PIPELINE:
  1. Fetch approved GT records for the target commodity
  2. Compute ProvenanceWeights for each record
  3. Bayesian prior update per province
  4. Residual quantile threshold update (physics, gravity)
  5. Uncertainty recalibration factor k_u
  6. Lambda parameter update
  7. Assemble CalibrationRunResult
  8. assert_no_acif_fields() — hard guard
  9. Create new CalibrationVersion via CalibrationVersionManager
  10. Emit CALIBRATION_VERSION domain event

CONSTITUTIONAL RULES:
  Rule 1: Only approved GT records (status = "approved", is_synthetic = False)
          are used. Synthetic records are excluded by name.
  Rule 2: Existing CalibrationVersions are never modified. A new version is
          always created with parent_version_id pointing to the prior active.
  Rule 3: Historical canonical scans are never rescored. No scan is touched.
  Rule 4: All update formulas delegate to calibration_math.py — no inline math.
  Rule 5: No import from core/*.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.calibration_math_model import (
    CalibrationRunResult, ProvenanceWeight,
)
from app.services.calibration_math import (
    compute_provenance_weight,
    bayesian_prior_update,
    residual_quantile_threshold,
    uncertainty_recalibration_factor,
    compute_lambda_updates,
)
from app.services.calibration_version import (
    CalibrationVersionManager, CalibrationParameters,
)
from app.config.observability import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Storage protocol
# ---------------------------------------------------------------------------

class CalibrationStorageAdapter:
    """Protocol for reading approved GT records. Production: injected from storage."""

    def fetch_approved_gt_records(self, commodity: str) -> list[dict]:
        """
        Return list of approved, non-synthetic GT records for the commodity.
        Each dict must have:
          record_id, source_confidence, spatial_accuracy, temporal_relevance,
          geological_context_strength, is_positive, physics_residual (optional),
          gravity_residual (optional), predicted_uncertainty (optional),
          empirical_uncertainty (optional), province_id
        """
        raise NotImplementedError

    def fetch_active_calibration_version(self, commodity: str) -> Optional[dict]:
        """Return the currently active CalibrationVersion dict."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class CalibrationExecutor:
    """
    Executes a provenance-weighted calibration run for one commodity.

    Usage:
        executor = CalibrationExecutor(storage, version_manager)
        result = executor.run(commodity="gold", actor_id="admin1")
    """

    def __init__(
        self,
        storage:         CalibrationStorageAdapter,
        version_manager: CalibrationVersionManager,
    ):
        self._storage = storage
        self._mgr     = version_manager

    def run(
        self,
        commodity:     str,
        actor_id:      str,
        description:   str = "",
        rationale:     str = "",
        alpha_0:       float = 2.0,
        beta_0:        float = 2.0,
        physics_quantile: float = 0.95,
        gravity_quantile: float = 0.95,
    ) -> CalibrationRunResult:
        """
        Execute a full calibration run for the given commodity.

        Returns CalibrationRunResult (frozen).
        Raises ValueError if:
          - Fewer than 3 approved GT records exist
          - Any synthetic records slip through (second guard)
          - assert_no_acif_fields() fails (hard constitutional guard)

        PROOF: This method reads from storage, runs calibration_math functions,
        creates a new CalibrationVersion, and returns the result.
        It does NOT call core/scoring, core/tiering, core/gates, or any ACIF function.
        It does NOT modify any CanonicalScan record.
        """
        import uuid

        # ── 1. Fetch approved GT records ──
        records = self._storage.fetch_approved_gt_records(commodity)
        if not records:
            raise ValueError(f"No approved GT records found for commodity {commodity!r}")

        # Second barrier: exclude synthetic (constitutional requirement)
        records = [r for r in records if not r.get("is_synthetic", True)]
        if len(records) < 3:
            raise ValueError(
                f"Calibration requires ≥ 3 approved, non-synthetic GT records for "
                f"{commodity!r}. Found {len(records)} after synthetic exclusion."
            )

        logger.info("calibration_run_started", extra={
            "commodity": commodity, "n_records": len(records), "actor_id": actor_id,
        })

        # ── 2. Compute provenance weights ──
        weights: list[ProvenanceWeight] = []
        for r in records:
            w = compute_provenance_weight(
                record_id                   = r["record_id"],
                source_confidence           = r["source_confidence"],
                spatial_accuracy            = r["spatial_accuracy"],
                temporal_relevance          = r["temporal_relevance"],
                geological_context_strength = r["geological_context_strength"],
            )
            weights.append(w)

        positive_weights = [w for w, r in zip(weights, records) if r.get("is_positive", False)]
        all_weights      = weights

        # ── 3. Bayesian prior update (per province) ──
        provinces = list({r.get("province_id", "default") for r in records})
        prior_updates = []
        for province_id in provinces:
            prov_records  = [r for r in records if r.get("province_id", "default") == province_id]
            prov_weights  = [w for w, r in zip(weights, records)
                              if r.get("province_id", "default") == province_id]
            prov_pos_wgts = [w for w, r in zip(weights, records)
                              if r.get("province_id", "default") == province_id
                              and r.get("is_positive", False)]
            if prov_weights:
                update = bayesian_prior_update(
                    commodity         = commodity,
                    province_id       = province_id,
                    alpha_0           = alpha_0,
                    beta_0            = beta_0,
                    positive_weights  = prov_pos_wgts,
                    all_weights       = prov_weights,
                )
                prior_updates.append(update)

        # ── 4. Residual quantile thresholds ──
        threshold_updates = []
        for ttype in ("physics", "gravity"):
            key = f"{ttype}_residual"
            residuals_with_weights = [
                (r[key], w) for r, w in zip(records, weights)
                if key in r and r[key] is not None and r.get("is_positive", False)
            ]
            if len(residuals_with_weights) >= 3:
                res_vals, res_wgts = zip(*residuals_with_weights)
                thresh = residual_quantile_threshold(
                    commodity       = commodity,
                    threshold_type  = ttype,
                    residual_values = list(res_vals),
                    weights         = list(res_wgts),
                    quantile        = physics_quantile if ttype == "physics" else gravity_quantile,
                )
                threshold_updates.append(thresh)

        # ── 5. Uncertainty recalibration ──
        uncertainty_updates = []
        unc_records = [
            (r, w) for r, w in zip(records, weights)
            if "predicted_uncertainty" in r and "empirical_uncertainty" in r
        ]
        if len(unc_records) >= 3:
            pred_u = [r["predicted_uncertainty"] for r, _ in unc_records]
            emp_u  = [r["empirical_uncertainty"]  for r, _ in unc_records]
            unc_wgts = [w for _, w in unc_records]
            unc_result = uncertainty_recalibration_factor(
                commodity                = commodity,
                predicted_uncertainties  = pred_u,
                empirical_uncertainties  = emp_u,
                weights                  = unc_wgts,
            )
            uncertainty_updates.append(unc_result)

        # ── 6. Lambda updates ──
        active_version = self._storage.fetch_active_calibration_version(commodity)
        current_lambda_1 = (active_version or {}).get("lambda_1", 1.0)
        current_lambda_2 = (active_version or {}).get("lambda_2", 1.0)
        lambda_updates = compute_lambda_updates(
            commodity        = commodity,
            current_lambda_1 = current_lambda_1,
            current_lambda_2 = current_lambda_2,
            positive_weights = positive_weights,
            all_weights      = all_weights,
        )

        # ── 7. Build CalibrationParameters ──
        params = CalibrationParameters(
            lambda_1_updates = {commodity: lambda_updates["lambda_1"]},
            lambda_2_updates = {commodity: lambda_updates["lambda_2"]},
            tau_physics_updates = {
                t.commodity: t.computed_threshold for t in threshold_updates
                if t.threshold_type == "physics"
            },
            tau_gravity_updates = {
                t.commodity: t.computed_threshold for t in threshold_updates
                if t.threshold_type == "gravity"
            },
            uncertainty_ku_per_commodity = {
                u.commodity: u.k_u for u in uncertainty_updates
            },
            province_prior_updates = {
                f"{p.commodity}::{p.province_id}": p.posterior_prior
                for p in prior_updates
            },
        )

        # ── 8. Create new CalibrationVersion ──
        parent_id = (active_version or {}).get("version_id")
        gt_record_ids = [r["record_id"] for r in records]
        effect_flags  = []
        if prior_updates:      effect_flags.append("province_priors")
        if threshold_updates:  effect_flags.append("veto_thresholds")
        if uncertainty_updates: effect_flags.append("uncertainty_ku")
        if lambda_updates:     effect_flags.append("lambda_weights")

        new_version = self._mgr.create_version(
            description            = description or f"AC calibration run for {commodity}",
            rationale              = rationale or (
                f"Provenance-weighted calibration from {len(records)} approved GT records. "
                f"Effects: {', '.join(effect_flags)}."
            ),
            parameters             = params,
            ground_truth_record_ids = gt_record_ids,
            calibration_effect_flags = effect_flags,
            created_by             = actor_id,
        )

        # ── 9. Assemble CalibrationRunResult ──
        new_version_id = new_version.version_id
        executed_at    = datetime.utcnow().isoformat()

        run_result = CalibrationRunResult(
            new_version_id      = new_version_id,
            parent_version_id   = parent_id,
            commodity           = commodity,
            prior_updates       = tuple(prior_updates),
            threshold_updates   = tuple(threshold_updates),
            uncertainty_updates = tuple(uncertainty_updates),
            lambda_updates      = lambda_updates,
            n_gt_records_used   = len(records),
            run_summary         = (
                f"Calibration run for {commodity}: "
                f"{len(prior_updates)} province prior(s) updated, "
                f"{len(threshold_updates)} threshold(s) calibrated, "
                f"{len(uncertainty_updates)} uncertainty factor(s) set. "
                f"New version: {new_version_id}."
            ),
            executed_at  = executed_at,
            executed_by  = actor_id,
        )

        # ── 10. Hard constitutional guard ──
        run_result.assert_no_acif_fields()

        logger.info("calibration_run_complete", extra={
            "commodity": commodity, "new_version_id": new_version_id,
            "n_records": len(records), "effects": effect_flags,
        })

        return run_result