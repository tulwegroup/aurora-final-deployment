# Phase O Completion Proof
## Aurora OSI vNext — Security, JWT, RBAC, and Audit

---

## 1. Auth Module Inventory

| Module | File | Purpose |
|---|---|---|
| `security/auth.py` | JWT issue/decode, bcrypt, JTI revocation, FastAPI dependency guards |
| `security/rbac.py` | RBAC matrix, re-exports guards, `ROLE_PERMISSIONS` registry |
| `security/audit.py` | Typed audit event emitter for all 10 Phase O events |
| `security/bootstrap.py` | Admin bootstrap from env vars, rotation enforcement |
| `api/auth.py` | Login, logout, me, refresh endpoints |
| `api/admin.py` | User management, audit log query, bootstrap status |

### Key functions

| Function | Module | Purpose |
|---|---|---|
| `issue_access_token(user)` | `security/auth.py` | RS256 JWT, returns (token, jti) |
| `decode_access_token(token)` | `security/auth.py` | Verify RS256 signature + expiry |
| `revoke_token_jti(jti)` | `security/auth.py` | Add JTI to revocation set |
| `is_jti_revoked(jti)` | `security/auth.py` | Check revocation set |
| `hash_password(plain)` | `security/auth.py` | bcrypt 12 rounds |
| `verify_password(plain, hash)` | `security/auth.py` | bcrypt verify |
| `get_current_user` | `security/auth.py` | FastAPI dep: decode + revocation check |
| `require_authenticated_user` | `security/auth.py` | FastAPI dep: any role |
| `require_admin_user` | `security/auth.py` | FastAPI dep: admin only → 403 otherwise |
| `require_operator_or_above` | `security/auth.py` | FastAPI dep: admin/operator → 403 for viewer |
| `run_bootstrap` | `security/bootstrap.py` | Idempotent admin creation from env |
| `build_bootstrap_user` | `security/bootstrap.py` | Credential validation + hash |

---

## 2. RBAC Matrix by Route

| Endpoint | admin | operator | viewer | Guard |
|---|:---:|:---:|:---:|---|
| `POST /scan/grid` | ✓ | ✓ | ✗ | `require_operator_or_above` |
| `POST /scan/polygon` | ✓ | ✓ | ✗ | `require_operator_or_above` |
| `GET /scan/active` | ✓ | ✓ | ✓ | `require_authenticated_user` |
| `GET /scan/status/{id}` | ✓ | ✓ | ✓ | `require_authenticated_user` |
| `POST /scan/{id}/cancel` | ✓ | ✗ | ✗ | `require_admin_user` |
| `GET /history` | ✓ | ✓ | ✓ | `require_authenticated_user` |
| `GET /history/{id}` | ✓ | ✓ | ✓ | `require_authenticated_user` |
| `GET /history/{id}/cells` | ✓ | ✓ | ✓ | `require_authenticated_user` |
| `DELETE /history/{id}` | ✓ | ✗ | ✗ | `require_admin_user` |
| `POST /history/{id}/reprocess` | ✓ | ✗ | ✗ | `require_admin_user` |
| `GET /datasets/summary/{id}` | ✓ | ✓ | ✓ | `require_authenticated_user` |
| `GET /datasets/geojson/{id}` | ✓ | ✓ | ✓ | `require_authenticated_user` |
| `GET /datasets/package/{id}` | ✓ | ✓ | ✓ | `require_authenticated_user` |
| `GET /datasets/raster-spec/{id}` | ✓ | ✓ | ✓ | `require_authenticated_user` |
| `GET /datasets/export/{id}` | ✓ | ✗ | ✗ | `require_admin_user` |
| `GET /twin/*` | ✓ | ✓ | ✓ | `require_authenticated_user` |
| `POST /twin/{id}/query` | ✓ | ✓ | ✓ | `require_authenticated_user` |
| `GET /admin/users` | ✓ | ✗ | ✗ | `require_admin_user` |
| `POST /admin/users` | ✓ | ✗ | ✗ | `require_admin_user` |
| `PATCH /admin/users/{id}/role` | ✓ | ✗ | ✗ | `require_admin_user` |
| `GET /admin/audit` | ✓ | ✗ | ✗ | `require_admin_user` |

All guards are FastAPI `Depends()` injected — not configuration claims.
Verified programmatically in `tests/unit/test_security_phase_o.py :: TestRBACMatrix`.

---

## 3. Bootstrap Flow Proof

### Flow

```
1. Read AURORA_ADMIN_USER, AURORA_ADMIN_PASS from environment
2. validate_bootstrap_credentials() — raises BootstrapError if invalid
   - email must contain '@'
   - password >= 12 characters
   - password != email
3. user_store.admin_exists() → if True: return None (idempotent no-op)
4. audit_store.append_audit_event(ADMIN_BOOTSTRAPPED)  ← PRE-FLIGHT AUDIT
5. build_bootstrap_user() → hash password with bcrypt(12 rounds)
6. user_store.create_user(user_dict)  ← must_rotate_password=True
7. Return new user_id
```

### Rotation enforcement

Bootstrap admin is created with `must_rotate_password=True`.
On first login, the token payload includes this flag.
All non-auth endpoints return HTTP 428 Precondition Required until rotation completes.
HTTP 428 distinguishes "must rotate" from 403 "permission denied" for client handling.

### Idempotency

`user_store.admin_exists()` is checked before any write.
If True, `run_bootstrap()` returns `None` immediately — zero audit events, zero writes.
Safe to call on every application startup.

### Credentials

`AURORA_ADMIN_PASS` is read from environment and immediately passed to `bcrypt.hashpw()`.
The plaintext is NEVER stored, logged, or included in any audit event detail.
The audit event records only `{"must_rotate": True, "source": "environment_variable"}`.

---

## 4. Audit Event Inventory

All 10 Phase O required audit events:

| # | Event | Trigger | Pre-flight? |
|---|---|---|---|
| 1 | `LOGIN_SUCCESS` | Successful credential verification | — |
| 2 | `LOGIN_FAILURE` | Failed password / unknown user | — |
| 3 | `SCAN_SUBMITTED` | POST /scan/grid or /polygon | — |
| 4 | `SCAN_DELETED` | DELETE /history/{id} | **Yes** — written before soft delete |
| 5 | `SCAN_REPROCESSED` | POST /history/{id}/reprocess | **Yes** — written before pipeline |
| 6 | `THRESHOLD_POLICY_CHANGED` | Admin config/policy change | **Yes** |
| 7 | `ROLE_CHANGED` | PATCH /admin/users/{id}/role | **Yes** — written before role write |
| 8 | `DATA_EXPORTED` | GET /datasets/export/{id} | **Yes** — written before data returned |
| 9 | `ADMIN_BOOTSTRAPPED` | First-deployment bootstrap | **Yes** — written before user created |
| 10 | `LOGOUT` | POST /auth/logout | — (token revoked then event written) |

### Login failure sanitisation

`audit_login_failure()` accepts a `reason` argument but sanitises it:
```python
safe_reason = reason if reason in (
    "wrong_password", "unknown_user", "account_inactive"
) else "unknown"
```
The supplied password is NEVER included in the audit record.

---

## 5. Append-Only Audit Proof

### Four independent enforcement layers

**Layer 1 — AuditLogStore Python methods:**
```python
async def update_audit_event(self, *args, **kwargs):
    raise StorageAuditViolationError(
        "AURORA_AUDIT_VIOLATION: Audit log records are immutable and append-only."
    )

async def delete_audit_event(self, *args, **kwargs):
    raise StorageAuditViolationError(
        "AURORA_AUDIT_VIOLATION: Audit log records are immutable and append-only."
    )
```

**Layer 2 — No DELETE/UPDATE SQL in storage/audit.py:**
The only SQL in `storage/audit.py` is:
- `INSERT INTO audit_log ...` (in `append_audit_event()`)
- `SELECT * FROM audit_log ...` (in `query_audit_log()`)
No `UPDATE` or `DELETE` statement exists anywhere in the file.

**Layer 3 — PostgreSQL RLS:**
`infra/db/migrations/001_initial_schema.sql` installs RLS on `audit_log`:
```sql
CREATE POLICY audit_insert_only ON audit_log
  FOR INSERT WITH CHECK (true);

CREATE POLICY audit_no_update ON audit_log
  FOR UPDATE USING (false);   -- blocks all roles

CREATE POLICY audit_no_delete ON audit_log
  FOR DELETE USING (false);   -- blocks all roles
```
Even if application code is bypassed (direct DB connection), the trigger rejects mutations.

**Layer 4 — No admin API endpoint for audit mutation:**
`api/admin.py` exposes only `GET /admin/audit` and `GET /admin/audit/{id}`.
There is no `DELETE /admin/audit`, `PATCH /admin/audit`, or `PUT /admin/audit` endpoint.

**AuditRecord immutability:**
`AuditRecord` has `model_config = {"frozen": True}` — the Pydantic model is immutable
after construction. Two reads of the same row always return the same value.

---

## 6. 403/401 Test Evidence

All tests in `tests/unit/test_security_phase_o.py :: TestAuthorizationEnforcement`:

| Test | Scenario | Expected |
|---|---|---|
| `test_expired_token_raises_401` | Token with past `exp` | HTTP 401 |
| `test_invalid_token_raises_401` | Malformed JWT string | HTTP 401 |
| `test_revoked_jti_raises_401` | JTI in revocation set | HTTP 401 |
| `test_operator_calling_admin_guard_gets_403` | Operator on admin route | HTTP 403 |
| `test_viewer_calling_operator_guard_gets_403` | Viewer on operator route | HTTP 403 |
| `test_valid_admin_token_not_rejected` | Valid admin token | Passes all guards |

Plus RBAC matrix tests:
| Test | Scenario | Expected |
|---|---|---|
| `test_admin_passes_require_admin` | Admin token | Pass |
| `test_operator_fails_require_admin` | Operator token | HTTP 403 |
| `test_viewer_fails_require_admin` | Viewer token | HTTP 403 |
| `test_admin_passes_require_operator_or_above` | Admin token | Pass |
| `test_operator_passes_require_operator_or_above` | Operator token | Pass |
| `test_viewer_fails_require_operator_or_above` | Viewer token | HTTP 403 |
| `test_any_role_passes_require_authenticated` | Any role token | Pass |

All guards are verified by calling the actual FastAPI dependency function with a
crafted `TokenPayload` — not by reading configuration or trusting docstrings.

---

## 7. Security Modules Do Not Import Scoring/Tiering/Gates

### Import audit (source-level inspection)

| Module | Forbidden imports | Status |
|---|---|---|
| `security/auth.py` | `core.scoring`, `core.tiering`, `core.gates`, `compute_acif`, etc. | ✅ Absent |
| `security/rbac.py` | Same | ✅ Absent |
| `security/audit.py` | Same + no `acif_score`, `tier_counts`, `system_status` field refs | ✅ Absent |
| `security/bootstrap.py` | Same + no pipeline imports | ✅ Absent |
| `api/auth.py` | Same | ✅ Absent |
| `api/admin.py` | Same | ✅ Absent |

Security audit events carry **identity and action metadata only**:
- `actor_user_id`, `actor_email`, `actor_role` — who
- `event_type` — what
- `scan_id` — which scan (reference only, not score data)
- `details` — structured metadata (reason labels, changed role values)
- `ip_address`, `timestamp` — when/where

No security event detail ever includes: `acif_score`, `tier_counts`, `system_status`,
`display_acif_score`, `evidence_score`, or any other scientific field.

Verified programmatically in:
`tests/unit/test_security_phase_o.py :: TestSecurityImportIsolation`
All 6 modules pass the parametrized source inspection test.

### Confirmation that security does not alter canonical scientific outputs

`security/auth.py`, `security/rbac.py`, `security/audit.py`, and `security/bootstrap.py`
have **no write path to** `canonical_scans`, `scan_cells`, or any scientific storage table.
The only storage write in the security layer is `AuditLogStore.append_audit_event()`
which writes to `audit_log` only.
Scan lineage, canonical outputs, and version registry are never touched by the security layer.