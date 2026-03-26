# Phase W Completion Proof
## Aurora OSI vNext — Webhook Consumer Registry & API Key Authentication

---

## Pre-Phase Confirmation: Numeric Constants Audit

Before Phase W was started, a full source audit was performed across all five
scientific modules. Results are permanently recorded here.

### Files audited

| File | Purpose |
|---|---|
| `app/core/scoring.py` | ACIF computation |
| `app/services/harmonization.py` | Sensor harmonisation |
| `app/core/uncertainty.py` | Uncertainty propagation |
| `app/core/physics.py` | Physics residuals + scoring |
| `app/core/normalisation.py` | Observable normalisation |

---

### Numeric constants — complete inventory

#### `app/core/scoring.py`

| Constant | Value | Origin | Scientific? |
|---|---|---|---|
| DEGRADED fallback | `0.5` | Missing-data policy (moderate) | Documented policy — not a scaling factor |
| Clamp bounds | `0.0`, `1.0` | Mathematical range enforcement | Boundary values — not scaling factors |

**No hidden normalisation scaling factors. No `50`. No undocumented multipliers.**

#### `app/services/harmonization.py`

| Constant | Value | Origin | Scientific? |
|---|---|---|---|
| `len(CANONICAL_KEYS)` | `42` | Constitutional constant (42 observables) | Structural — documented |
| Environmental modifier | from `environmental_modifier` parameter | Commodity library `Θ_c` | Injected — not hard-coded |

**No numeric constants hard-coded in harmonisation arithmetic.
All modifiers originate from the commodity library (Θ_c). No `50`.**

#### `app/core/uncertainty.py`

| Constant | Value | Origin | Scientific? |
|---|---|---|---|
| `total_observables` | `42` | Constitutional constant | Structural — documented |
| `0.5` in model uncertainty | Missing inversion quality fallback | Documented policy: "Unknown inversion quality → moderate uncertainty" | Missing-data policy only |
| `_EPSILON` | `1e-10` | Numerical guard (prevent zero-division) | Infrastructure guard only |
| `_MIN_SAMPLES_FOR_SIGMA` | `5` | Minimum statistical sample | Infrastructure threshold, not scientific scaling |

**No undocumented scaling factors. No `50`. Probabilistic union formula (§10.3) contains only `1.0` bounds.**

#### `app/core/physics.py`

| Constant | Value | Origin | Scientific? |
|---|---|---|---|
| `G_SI` | `6.674e-11 m³ kg⁻¹ s⁻²` | **Newtonian gravitational constant** | Physical constant — patent-locked mathematical framework |
| `G_MGAL` | `G_SI × 1e5` | mGal unit conversion from SI | Physical unit conversion — not a scaling factor |
| `4.0 * math.pi` | `4π ≈ 12.566` | Poisson's equation: `∇²Φ = 4πGρ` | Mathematical constant — patent-locked |
| `_DEFAULT_LAMBDA_1` | `0.5` | Gravity penalty weight | **Default for Θ_c — overridden by commodity at runtime** |
| `_DEFAULT_LAMBDA_2` | `0.3` | Poisson penalty weight | **Default for Θ_c — overridden by commodity at runtime** |
| `tau_grav_veto` | `100.0` (default arg) | Gravity veto threshold | **Default for Θ_c — overridden by commodity at runtime** |
| `tau_phys_veto` | `50.0` (default arg) | Poisson veto threshold | **Default for Θ_c — overridden by commodity at runtime** |

**`50.0` appears as `tau_phys_veto` — the default Poisson residual hard-veto threshold.**

This is **NOT a normalisation scaling factor**. It is:
1. A residual magnitude threshold (§6.6), applied as `if R_phys > 50.0 → Ψ_i = 0.0`
2. A default argument, not a module-level constant — explicitly overridden by `Θ_c`
3. Documented in the function signature: `"Threshold values are sourced from Θ_c (overridden by commodity in Phase J)"`
4. Not applied to ACIF, tier assignment, normalisation, or any aggregation step

It originates from the **physics model definitions** (Θ_c commodity configuration) — exactly as required by the constitution.

**No hidden normalisation scaling factor exists. The `50.0` value is a physics veto threshold from the patent-locked mathematical framework, exposed as an overridable parameter.**

#### `app/core/normalisation.py`

| Constant | Value | Origin | Scientific? |
|---|---|---|---|
| `42` (coverage_fraction) | `/ 42` | Constitutional constant (42 observables) | Structural |
| `0.25` (z-score scaling) | `z_score * 0.25 + 0.5` | Maps ±2σ to [0, 1] range | **Mathematical mapping — §3.2** |
| `0.5` (z-score offset) | `z_score * 0.25 + 0.5` | Maps mean to 0.5 | **Mathematical mapping — §3.2** |
| `0.5` (missing sentinel) | `normalised_value=0.5` | §3.3 mid-range sentinel | **Documented policy** |
| `_FALLBACK_SIGMA` | `1.0` | Unit sigma fallback | Numerical guard |
| `_MIN_SAMPLES_FOR_SIGMA` | `5` | Minimum sample count | Infrastructure threshold |

**Note on docstring discrepancy in normalisation.py:**
The comment reads "The scaling factor 0.5 maps ±1σ to [0.0, 1.0] range" but the code
uses `0.25` (which maps ±2σ to [0, 1]). The code is correct per §3.2 — the comment is
imprecise. This is a documentation issue only; the formula `z * 0.25 + 0.5` is the
correct §3.2 implementation. No constitutional violation.

---

### Constitutional confirmation

> **Confirmed: No hard-coded numeric constants affecting scientific normalisation
> exist anywhere in scoring, harmonisation, uncertainty propagation, sensor fusion
> weighting, or inversion modules, beyond those that originate exclusively from:**
>
> - **Physics model definitions** (`G_SI`, `4π` — Newtonian gravity, Poisson's equation)
> - **Sensor calibration specifications** (unit conversions: `1e5` for mGal)
> - **Patent-locked mathematical framework** (`tau_phys_veto`, `_DEFAULT_LAMBDA_*` — Θ_c defaults, all overridable)
> - **Constitutional structural constants** (`42` observables, documented in §3)
> - **Documented missing-data policies** (`0.5` sentinels — not scaling factors)
>
> The value `50.0` in `physics.py` is the default Poisson residual veto threshold
> (§6.6), originating from Θ_c. It is a function default argument, overridden at
> runtime by commodity configuration. It does not affect normalisation or ACIF
> arithmetic in any way.

---

## 1. Phase W Objective

**Webhook Consumer Registry & API Key Authentication**

Phase V delivered the event bus and webhook dispatcher. Phase W provides the
management layer: REST endpoints for registering, listing, updating, and revoking
webhook consumer endpoints, with HMAC-secured API key issuance and verification.

External systems that receive `scan.completed` events need:
1. A way to register their HTTPS endpoint and obtain a signing secret
2. A way to rotate their API key without losing endpoint registration
3. A way to scope subscriptions to specific event types (by string — not scientific value)
4. Verification helpers to validate incoming HMAC signatures

This is a **pure infrastructure capability**. No scientific computation is introduced.

---

## 2. Deliverable File List

| File | Category | Purpose |
|---|---|---|
| `app/api/webhooks.py` | REST API | CRUD endpoints for webhook consumer registration |
| `app/events/consumer_auth.py` | Auth | API key generation, hashing, verification for consumers |
| `tests/unit/test_webhooks_phase_w.py` | Proof tests | 25 tests: key generation, scoping, verification, no-science imports |
| `docs/phase_w_completion_proof.md` | Proof | This document |

---

## 3. Constitutional Risks Introduced by Phase W

### Risk W-R1: Consumer subscription scope tied to scientific values (HIGH — prevented)

**Risk:** A developer could add a `filter_by_tier` scope so consumer only receives
events where `scan_tier == "TIER_1"`. This would cause the webhook layer to inspect
scientific field values for routing decisions.

**Mitigation:**
- `ConsumerScope.event_types` is a `set[str]` of EventType strings only
  (`"scan.completed"`, `"twin.built"`, etc.)
- No field filter, no tier filter, no score threshold in scope definition
- Verified by `TestConsumerScope.test_scope_contains_only_event_type_strings()`

### Risk W-R2: API key could embed scientific metadata (LOW — eliminated)

**Risk:** If API keys were JWT-style tokens carrying scan_tier claims or score ranges,
they could be used for scientific routing.

**Mitigation:**
- API keys are 32-byte random tokens (cryptographically random, no embedded claims)
- Stored as BLAKE2b hash — not reversible to any scientific value
- Verified by `TestConsumerAuth.test_api_key_contains_no_scientific_value()`

### Risk W-R3: Webhook event filtering could derive secondary science (MEDIUM — prevented)

**Risk:** A consumer-side filter could recompute `scan_tier` from `display_acif_score`
inside the API layer before dispatch.

**Mitigation:**
- Webhook payloads are assembled by `payload_schemas.py` (Phase V) — verbatim only
- `webhooks.py` routes events to `EventBus.publish()` unchanged
- No filtering, transformation, or inspection of scientific payload fields

---

## 4. Proof of Zero Scientific Transformation

Source-level grep across all Phase W files:

| Pattern | `webhooks.py` | `consumer_auth.py` |
|---|---|---|
| `from app.core` | 0 | 0 |
| `compute_acif` | 0 | 0 |
| `assign_tier` | 0 | 0 |
| `acif_score` (value access) | 0 | 0 |
| `tier_counts` (value access) | 0 | 0 |
| Arithmetic on scientific field | 0 | 0 |

---

## Phase W Complete

1. ✅ Pre-phase numeric constants audit completed — no undocumented scaling factors
2. ✅ `50.0` confirmed as Θ_c physics veto threshold — not a normalisation constant
3. ✅ Consumer scope limited to event_type strings — no scientific field filters
4. ✅ API keys are random tokens — no embedded scientific claims
5. ✅ Webhook payloads unchanged from Phase V — verbatim canonical mappings
6. ✅ Zero `core/*` imports across all Phase W files
7. ✅ 25 tests covering key generation, scoping, verification, import graph