"""
Aurora OSI vNext — End-to-End Validation Harness
Phase AF §AF.1

Provides the scaffolding to run Aurora pipeline against real ground-truth
reference cases and produce structured ValidationResult objects.

CONSTITUTIONAL RULES:
  Rule 1: Validation reads canonical stored outputs only — no scoring changes.
  Rule 2: Synthetic data is permitted ONLY in test harness stubs.
          It must never appear in validation conclusions or reports.
  Rule 3: All ground-truth references are sourced from authoritative public datasets.
          Source provenance is recorded in GroundTruthReference.
  Rule 4: Weaknesses are recorded as ValidationFinding objects — never silently tuned.
  Rule 5: No import from core/scoring, core/tiering, core/gates.
          Validation evaluates stored outputs, not recomputed outputs.

PROOF THAT NO SCORING LOGIC WAS CHANGED:
  This module contains no formulas from core/scoring.py, core/tiering.py,
  or core/gates.py. It reads stored canonical results and compares them
  against ground-truth references. No CalibrationRunResult is produced here.
  No CanonicalScan is written here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ValidationOutcome(str, Enum):
    DETECTION_SUCCESS  = "detection_success"   # system flagged the known deposit area
    DETECTION_MISS     = "detection_miss"       # system missed the known deposit area
    FALSE_POSITIVE     = "false_positive"       # system flagged area with no known deposit
    PARTIAL_DETECTION  = "partial_detection"    # deposit partially detected
    INCONCLUSIVE       = "inconclusive"         # insufficient data to evaluate


class DatasetProvenance(str, Enum):
    USGS_MRDS          = "usgs_mrds"            # USGS Mineral Resources Data System
    USGS_MAS_MILS      = "usgs_mas_mils"        # USGS MAS/MILS deposit database
    GEUS               = "geus"                 # Geological Survey of Denmark & Greenland
    GSA                = "gsa"                  # Geological Survey of Australia
    BGS                = "bgs"                  # British Geological Survey
    GGS_GHANA          = "ggs_ghana"            # Geological Survey Authority of Ghana
    GSZ_ZAMBIA         = "gsz_zambia"           # Geological Survey of Zambia
    BRGM_SENEGAL       = "brgm_senegal"         # BRGM / Senegal geological data
    IHS_MARKIT         = "ihs_markit"           # IHS Markit (petroleum basins)
    PUBLIC_CADASTRE    = "public_cadastre"      # Published mining cadastre data
    PEER_REVIEWED      = "peer_reviewed"        # Peer-reviewed geological literature


@dataclass(frozen=True)
class GroundTruthReference:
    """
    A real-world ground-truth reference point for validation.
    All provenance is recorded.

    SYNTHETIC DATA PROHIBITION: is_synthetic must always be False in
    validation conclusions. Synthetic stubs are allowed only in test harnesses
    and are clearly marked is_synthetic=True and excluded from conclusions.
    """
    reference_id:       str
    name:               str
    commodity:          str
    country:            str
    province:           Optional[str]
    lat:                float
    lon:                float
    deposit_type:       str         # e.g. "orogenic_gold", "porphyry_copper"
    provenance:         DatasetProvenance
    source_url:         str
    source_citation:    str
    known_grade:        Optional[str]    # e.g. "2.1 g/t Au" — descriptive only
    known_tonnage:      Optional[str]    # e.g. ">1 Moz Au" — descriptive only
    is_synthetic:       bool = False     # MUST be False for all real validation cases


@dataclass(frozen=True)
class AOIDefinition:
    """
    Area of Interest used in a validation case.
    geometry_wkt: WGS84 polygon in WKT format.
    """
    aoi_id:           str
    name:             str
    country:          str
    centre_lat:       float
    centre_lon:       float
    radius_km:        float        # approximate AOI radius for reporting
    geometry_hash:    str          # SHA-256 of WKT (real hash in production)
    resolution:       str          # "standard" | "high"


@dataclass(frozen=True)
class ValidationMetrics:
    """
    Quantitative metrics from one validation case.
    All values derived from stored canonical outputs — not recomputed.
    """
    tier1_cells:            int
    tier2_cells:            int
    tier3_cells:            int
    total_cells:            int
    veto_cells:             int
    acif_mean_stored:       Optional[float]
    acif_max_stored:        Optional[float]
    system_status:          str
    detection_outcome:      ValidationOutcome
    # GT reference cell overlap
    gt_cells_in_tier1:      int              # cells containing GT reference in Tier 1
    gt_cells_in_tier2:      int
    gt_cells_in_tier3:      int
    gt_cells_vetoed:        int              # GT cells that were vetoed
    # Signal strength
    signal_strength:        Optional[float]  # acif at GT location / acif_mean
    uncertainty_at_gt:      Optional[float]  # stored uncertainty at GT cell


@dataclass(frozen=True)
class ValidationFinding:
    """
    An explicit finding (positive, limitation, or weakness) from one validation case.
    Weaknesses are NOT silently tuned — they are recorded here for Phase AG/AH input.
    """
    finding_id:     str
    severity:       str      # "positive" | "minor" | "moderate" | "significant"
    category:       str      # "detection" | "false_positive" | "uncertainty" | "calibration" | "coverage"
    description:    str
    recommendation: Optional[str]
    affects_case:   str      # case_id


@dataclass(frozen=True)
class ValidationCase:
    """
    One complete validation case: AOI + GT reference + canonical results + findings.
    """
    case_id:          str
    commodity:        str
    aoi:              AOIDefinition
    gt_reference:     GroundTruthReference
    metrics:          ValidationMetrics
    findings:         tuple[ValidationFinding, ...]
    case_notes:       str
    validated_at:     str


@dataclass(frozen=True)
class ValidationReport:
    """
    Complete Phase AF validation report.
    Contains all cases, summary statistics, and the no-modification statement.
    """
    report_id:            str
    cases:                tuple[ValidationCase, ...]
    generated_at:         str
    dataset_inventory:    tuple[dict, ...]    # provenance records
    no_modification_statement: str           # required by Phase AF

    @property
    def detection_rate(self) -> float:
        """Detection success rate across all cases."""
        if not self.cases:
            return 0.0
        successes = sum(
            1 for c in self.cases
            if c.metrics.detection_outcome in (
                ValidationOutcome.DETECTION_SUCCESS,
                ValidationOutcome.PARTIAL_DETECTION,
            )
        )
        return successes / len(self.cases)

    @property
    def false_positive_rate(self) -> float:
        """Rate of cases with false positive findings."""
        if not self.cases:
            return 0.0
        fp = sum(
            1 for c in self.cases
            if c.metrics.detection_outcome == ValidationOutcome.FALSE_POSITIVE
        )
        return fp / len(self.cases)

    @property
    def summary_by_commodity(self) -> dict:
        out = {}
        for c in self.cases:
            if c.commodity not in out:
                out[c.commodity] = {"total": 0, "detected": 0, "missed": 0, "fp": 0}
            out[c.commodity]["total"] += 1
            if c.metrics.detection_outcome == ValidationOutcome.DETECTION_SUCCESS:
                out[c.commodity]["detected"] += 1
            elif c.metrics.detection_outcome == ValidationOutcome.DETECTION_MISS:
                out[c.commodity]["missed"] += 1
            elif c.metrics.detection_outcome == ValidationOutcome.FALSE_POSITIVE:
                out[c.commodity]["fp"] += 1
        return out


# ---------------------------------------------------------------------------
# Validation case builder
# ---------------------------------------------------------------------------

def build_validation_case(
    case_id:      str,
    commodity:    str,
    aoi:          AOIDefinition,
    gt_reference: GroundTruthReference,
    stored_scan:  dict,        # stored CanonicalScan dict from storage
    gt_cell:      Optional[dict] = None,  # stored ScanCell nearest the GT reference
    case_notes:   str = "",
) -> ValidationCase:
    """
    Build a ValidationCase from a stored scan record and GT reference.
    No scoring is recomputed — all values read from stored_scan.

    Args:
      stored_scan: CanonicalScan record dict with tier_counts, acif_mean, etc.
      gt_cell:     Optional ScanCell dict at or near the GT reference location.
    """
    from datetime import datetime

    assert not gt_reference.is_synthetic, (
        f"GT reference {gt_reference.reference_id} is marked synthetic. "
        "Synthetic data is prohibited in validation conclusions."
    )

    tier_counts = stored_scan.get("tier_counts", {})
    t1 = tier_counts.get("TIER_1", 0)
    t2 = tier_counts.get("TIER_2", 0)
    t3 = tier_counts.get("TIER_3", 0)
    total = stored_scan.get("total_cells", t1 + t2 + t3)
    veto  = stored_scan.get("veto_count", 0)
    acif_mean = stored_scan.get("acif_mean")
    acif_max  = stored_scan.get("acif_max")
    status    = stored_scan.get("system_status", "UNKNOWN")

    # GT cell overlap
    gt_t1 = gt_t2 = gt_t3 = gt_veto = 0
    signal = None
    unc_at_gt = None
    if gt_cell:
        tier = gt_cell.get("tier")
        if tier == "TIER_1":   gt_t1 = 1
        elif tier == "TIER_2": gt_t2 = 1
        elif tier == "TIER_3": gt_t3 = 1
        if gt_cell.get("any_veto_fired"): gt_veto = 1
        if acif_mean and gt_cell.get("acif_score"):
            signal = gt_cell["acif_score"] / acif_mean if acif_mean > 0 else None
        unc_at_gt = gt_cell.get("uncertainty")

    # Detection outcome
    if gt_t1 > 0:
        outcome = ValidationOutcome.DETECTION_SUCCESS
    elif gt_t2 > 0 or gt_t3 > 0:
        outcome = ValidationOutcome.PARTIAL_DETECTION
    elif gt_veto > 0:
        outcome = ValidationOutcome.DETECTION_MISS
    elif acif_mean is None:
        outcome = ValidationOutcome.INCONCLUSIVE
    else:
        outcome = ValidationOutcome.DETECTION_MISS

    metrics = ValidationMetrics(
        tier1_cells         = t1,
        tier2_cells         = t2,
        tier3_cells         = t3,
        total_cells         = total,
        veto_cells          = veto,
        acif_mean_stored    = acif_mean,
        acif_max_stored     = acif_max,
        system_status       = status,
        detection_outcome   = outcome,
        gt_cells_in_tier1   = gt_t1,
        gt_cells_in_tier2   = gt_t2,
        gt_cells_in_tier3   = gt_t3,
        gt_cells_vetoed     = gt_veto,
        signal_strength     = signal,
        uncertainty_at_gt   = unc_at_gt,
    )

    return ValidationCase(
        case_id      = case_id,
        commodity    = commodity,
        aoi          = aoi,
        gt_reference = gt_reference,
        metrics      = metrics,
        findings     = (),   # populated separately
        case_notes   = case_notes,
        validated_at = datetime.utcnow().isoformat(),
    )