"""
Aurora OSI vNext — 40-Commodity Library (STUB)
Populated in Phase F from the approved Phase A Mineral Library specification.

Contains structured definitions for all 40 commodities across 9 mineral-system families.
Each commodity definition follows the constitutional schema:
  name, family, deposit_models, dominant_modalities, causal_gate_order,
  primary_observables, secondary_observables, negative_evidence,
  temporal_coherence, province_priors, threshold_policy, confounders

CONSTITUTIONAL RULE: This is structured DATA, not scoring logic.
No scoring formulas, no ACIF equations, no threshold values live here.
Commodity parameter sets Θ_c (evidence weights, gate definitions, physical
constraints, threshold policy, province priors) are defined here and consumed
by the scientific core modules — never computed by them ad hoc.
"""

# Phase F population from Phase A specification placeholder

# ─────────────────────────────────────────────────────────────────────────────
# Θ_c CANONICAL SCHEMA (Phase F will populate all 40 commodities)
# ─────────────────────────────────────────────────────────────────────────────
#
# Each commodity entry (Θ_c) contains the following physics model parameters.
# These are consumed by services/ and core/ modules — never computed ad hoc.
#
# PHYSICS MODEL PARAMETERS (Phase K addition — versioned):
#
#   delta_h_m : float
#     Units:   metres [m]
#     Meaning: Vertical sampling interval δh for gravity super-resolution.
#              The height separation between satellite observing levels across
#              which Γ_zz is integrated to recover g_short.  Controls the
#              effective depth kernel of the short-wavelength gravity signal.
#     Source:  Derived from target deposit depth range (Phase A mineral library).
#     Allowed: 10 ≤ δh ≤ 5000 m  (see config/constants.py DELTA_H_RANGE_*)
#     Policy:  Any change triggers physics_model_version increment and full
#              reprocessing of all scans produced with the prior δh.
#
#     Per-family canonical starting values:
#       "epithermal"    :  50   m  (near-surface gossan/laterite)
#       "porphyry"      : 500   m  (500–1500 m porphyry stock)
#       "orogenic_gold" : 200   m  (100–500 m shear-zone targets)
#       "vms_sedex"     : 150   m  (50–300 m seafloor/sediment-hosted)
#       "skarn"         : 300   m  (200–1000 m contact-metasomatic)
#       "kimberlite"    : 800   m  (300–1500 m diatreme/pipe)
#       "seabed"        :  75   m  (near-seafloor polymetallic nodule field)
#       "pge_intrusion" : 1000  m  (deep Bushveld-type reef)
#       "coal_oil_sands": 2000  m  (deep basin target)
#
# The scan pipeline (Phase L) MUST:
#   1. Load Θ_c for the active commodity.
#   2. Validate theta_c.delta_h_m is not None and within [DELTA_H_RANGE_MIN_M,
#      DELTA_H_RANGE_MAX_M].
#   3. Pass delta_h_m explicitly to services/gravity.build_gravity_composite().
#   4. Record theta_c.delta_h_m in CanonicalScan.version_registry.
#
# PROHIBITION: services/gravity.DELTA_H_SHALLOW_FALLBACK_M must NEVER be used
# in the Phase L scan pipeline.  Its use is restricted to unit tests only.
# ─────────────────────────────────────────────────────────────────────────────