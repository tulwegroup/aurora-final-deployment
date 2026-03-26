"""
Aurora OSI vNext — Calibration Mathematics Model
Phase AC §AC.1

Defines the immutable result types for all calibration update operations.

CONSTITUTIONAL RULES:
  Rule 1: Every result type is frozen. Calibration outputs are configuration
          parameters only — never ACIF values, tier memberships, or gate flags.
  Rule 2: The only fields that calibration may update are:
            λ₁, λ₂ (evidence/causal weighting)
            τ_grav, τ_phys, τ_temp (veto thresholds)
            province prior α₀, β₀ adjustments
            uncertainty recalibration factor k_u (per commodity)
            commodity family modifier set
  Rule 3: No CalibrationResult carries ACIF, tier, or gate values.
          Any such field would be a constitutional violation.
  Rule 4: All results carry provenance_weight_used (w_gt geometric mean)
          for full auditability of the weighting applied.
  Rule 5: No import from core/*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProvenanceWeight:
    """
    Ground-truth record provenance weighting.
    w_gt = (w_s · w_a · w_t · w_g)^(1/4)  — geometric mean.

    This is the auditable composite weight for one GT record.
    Geometric mean ensures one weak dimension cannot be hidden
    by arithmetic averaging.

    Fields:
      source_confidence           w_s ∈ [0, 1]
      spatial_accuracy            w_a ∈ [0, 1]
      temporal_relevance          w_t ∈ [0, 1]
      geological_context_strength w_g ∈ [0, 1]
      composite                   w_gt = (w_s·w_a·w_t·w_g)^(1/4)
      record_id                   the GT record this weight applies to
    """
    record_id:                   str
    source_confidence:           float
    spatial_accuracy:            float
    temporal_relevance:          float
    geological_context_strength: float
    composite:                   float    # geometric mean — computed, stored verbatim

    def __post_init__(self):
        for field, val in [
            ("source_confidence",           self.source_confidence),
            ("spatial_accuracy",            self.spatial_accuracy),
            ("temporal_relevance",          self.temporal_relevance),
            ("geological_context_strength", self.geological_context_strength),
        ]:
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"ProvenanceWeight.{field} must be in [0, 1], got {val}")


@dataclass(frozen=True)
class BayesianPriorUpdate:
    """
    Province prior update for one (commodity, province) pair.

    Formula (Bayesian Beta-Binomial update):
      Π_post(c,r) = (α₀ + Σw_gt⁺) / (α₀ + β₀ + Σw_gt)

    Where:
      α₀, β₀   — prior hyperparameters (from existing calibration version)
      Σw_gt⁺   — sum of composite weights for confirmed positive GT records
      Σw_gt     — sum of composite weights for all relevant GT records

    PROOF: result is a probability ∈ (0, 1) — not an ACIF value.
    It adjusts the province prior Π(c,r) used in core/priors.py ONLY.
    It does not compute or substitute ACIF.
    """
    commodity:            str
    province_id:          str
    alpha_0:              float    # prior positive pseudocount
    beta_0:               float    # prior negative pseudocount
    sum_wgt_positive:     float    # Σw_gt for confirmed positive records
    sum_wgt_total:        float    # Σw_gt for all relevant records
    posterior_prior:      float    # Π_post — updated province prior probability
    n_records_positive:   int      # count of confirmed positive GT records used
    n_records_total:      int      # total GT records used
    provenance_weights:   tuple[ProvenanceWeight, ...]

    def __post_init__(self):
        if not (0.0 < self.posterior_prior < 1.0):
            raise ValueError(
                f"BayesianPriorUpdate.posterior_prior must be in (0, 1), "
                f"got {self.posterior_prior}"
            )
        # Hard guard: prior update must never equal 0 or 1 (degenerate)
        if self.sum_wgt_total <= 0:
            raise ValueError("sum_wgt_total must be > 0")


@dataclass(frozen=True)
class ResidualQuantileThreshold:
    """
    Empirically grounded veto threshold from ground-truth residual distributions.

    Formula:
      τ(c) = Q_q( R | confirmed truth for commodity c )

    Where:
      R     — physical or gravity residual values for confirmed positive GT records
      q     — quantile (default 0.95 for veto thresholds)
      τ(c)  — the new veto threshold for commodity c

    PROOF: τ is a threshold for an existing veto check (τ_phys or τ_grav).
    It replaces the prior threshold in CalibrationParameters only.
    It does not compute ACIF; it updates the configuration that the
    veto gate reads at scan time.

    threshold_type: "physics" | "gravity" | "temporal"
    """
    commodity:           str
    threshold_type:      str          # "physics" | "gravity" | "temporal"
    quantile:            float        # q — default 0.95
    residual_values:     tuple[float, ...]   # verbatim residuals from confirmed positives
    computed_threshold:  float        # Q_q of residual_values
    n_records:           int          # number of confirmed positive records used
    provenance_weights:  tuple[ProvenanceWeight, ...]

    def __post_init__(self):
        if not (0.0 < self.quantile <= 1.0):
            raise ValueError(f"quantile must be in (0, 1], got {self.quantile}")
        if self.n_records < 3:
            raise ValueError(
                f"ResidualQuantileThreshold requires ≥ 3 confirmed records, "
                f"got {self.n_records}. Insufficient ground truth for threshold calibration."
            )


@dataclass(frozen=True)
class UncertaintyRecalibration:
    """
    Uncertainty recalibration factor k_u per commodity.

    Formula:
      U' = 1 - (1 - U)^k_u    with k_u > 1 only when evidence shows underestimation.

    k_u = 1.0 means no recalibration (identity).
    k_u > 1.0 inflates uncertainty (corrects systematic overconfidence).
    k_u < 1.0 is FORBIDDEN — this would deflate uncertainty without evidence.

    PROOF: U' is a modified uncertainty score — not an ACIF value.
    k_u is configuration stored in CalibrationParameters.uncertainty_ku_per_commodity.
    It is applied in core/uncertainty.py during scan processing only.
    This result does not trigger any rescore of existing canonical scans.
    """
    commodity:              str
    k_u:                    float    # recalibration factor — must be ≥ 1.0
    mean_overconfidence:    float    # measured gap: predicted_uncertainty - empirical_uncertainty
    n_records:              int      # calibration records used
    provenance_weights:     tuple[ProvenanceWeight, ...]
    evidence_summary:       str      # human-readable justification for k_u > 1

    def __post_init__(self):
        if self.k_u < 1.0:
            raise ValueError(
                f"UncertaintyRecalibration.k_u must be ≥ 1.0 (deflating uncertainty "
                f"is forbidden without explicit evidence). Got {self.k_u}."
            )


@dataclass(frozen=True)
class CalibrationRunResult:
    """
    Complete output of one calibration run.

    Contains:
      prior_updates:      BayesianPriorUpdate per (commodity, province)
      threshold_updates:  ResidualQuantileThreshold per (commodity, threshold_type)
      uncertainty_updates: UncertaintyRecalibration per commodity
      lambda_updates:     λ₁, λ₂ per commodity (direct parameter updates)
      new_version_id:     the CalibrationVersion created by this run
      parent_version_id:  the CalibrationVersion this run supersedes
      run_summary:        human-readable summary of what changed

    PROOF: No field in CalibrationRunResult carries:
      - An ACIF score
      - A tier classification
      - A gate pass/fail result
      - A scan-level output

    All fields are configuration parameters for the calibration system only.
    """
    new_version_id:      str
    parent_version_id:   Optional[str]
    commodity:           str
    prior_updates:       tuple[BayesianPriorUpdate, ...]
    threshold_updates:   tuple[ResidualQuantileThreshold, ...]
    uncertainty_updates: tuple[UncertaintyRecalibration, ...]
    lambda_updates:      dict[str, float]   # {"lambda_1": float, "lambda_2": float}
    n_gt_records_used:   int
    run_summary:         str
    executed_at:         str   # ISO 8601 UTC
    executed_by:         str

    def assert_no_acif_fields(self) -> None:
        """
        Hard guard: verify no ACIF, tier, or gate data in this result.
        Called by CalibrationExecutor before persisting the result.
        """
        forbidden_keys = {"acif", "tier", "gate", "score", "probability"}
        all_keys = set(self.__dataclass_fields__.keys())
        for key in all_keys:
            for f in forbidden_keys:
                if f in key.lower():
                    raise ValueError(
                        f"CONSTITUTIONAL VIOLATION: CalibrationRunResult has field "
                        f"'{key}' which contains forbidden term '{f}'. "
                        f"Calibration results must never carry ACIF, tier, or gate data."
                    )