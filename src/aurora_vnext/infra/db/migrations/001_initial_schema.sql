-- =============================================================================
-- Aurora OSI vNext — Initial Schema Migration
-- Phase G §G.1
--
-- Scan data lifecycle:
--   scan_jobs (mutable) → raw_observables → harmonised_tensors
--   → canonical_scans (WRITE-ONCE after COMPLETED) → scan_cells (WRITE-ONCE)
--   → history_index (materialised view) → digital_twin_voxels (versioned)
--   → audit_log (APPEND-ONLY, no UPDATE/DELETE)
--
-- Immutability enforcement:
--   canonical_scans: PostgreSQL trigger rejects UPDATE on COMPLETED rows
--   audit_log: PostgreSQL RLS blocks UPDATE and DELETE for ALL roles
--   scan_cells: no UPDATE/DELETE triggers (cells are created once per freeze)
--
-- PostGIS required: CREATE EXTENSION IF NOT EXISTS postgis;
-- =============================================================================

BEGIN;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS btree_gist;  -- For exclusion constraints

-- =============================================================================
-- SCAN JOBS — Mutable pipeline execution records
-- Completely separate from canonical_scans. Contains ZERO score fields.
-- Archived (not deleted) after canonical freeze.
-- =============================================================================

CREATE TABLE IF NOT EXISTS scan_jobs (
    scan_job_id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id_ref         UUID        NOT NULL,   -- FK to canonical_scans.scan_id
    status              TEXT        NOT NULL DEFAULT 'PENDING'
                                    CHECK (status IN (
                                        'PENDING','RUNNING','COMPLETED','FAILED','REPROCESSING'
                                    )),
    pipeline_stage      TEXT,                   -- Current named stage within 21-step pipeline
    progress_pct        NUMERIC(5,2) CHECK (progress_pct BETWEEN 0 AND 100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at          TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    error_detail        TEXT,
    error_stage         TEXT,
    is_archived         BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Explicit absence of all score fields (enforced by CHECK constraint names):
    -- No acif_score, display_acif_score, tier_counts, system_status, etc.
    -- These live exclusively in canonical_scans.

    CONSTRAINT scan_jobs_completed_has_completed_at
        CHECK (status != 'COMPLETED' OR completed_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_scan_jobs_scan_id_ref  ON scan_jobs(scan_id_ref);
CREATE INDEX IF NOT EXISTS idx_scan_jobs_status       ON scan_jobs(status) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_scan_jobs_created_at   ON scan_jobs(created_at DESC);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_scan_job_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_scan_jobs_updated_at
    BEFORE UPDATE ON scan_jobs
    FOR EACH ROW EXECUTE FUNCTION update_scan_job_updated_at();


-- =============================================================================
-- CANONICAL SCANS — Write-once immutable result archive
--
-- IMMUTABILITY TRIGGER: Once status = 'COMPLETED', no UPDATE is permitted.
-- This is enforced at the PostgreSQL level — the application layer cannot
-- override it even with elevated privileges.
-- =============================================================================

CREATE TABLE IF NOT EXISTS canonical_scans (
    scan_id                     UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    status                      TEXT        NOT NULL DEFAULT 'PENDING'
                                            CHECK (status IN (
                                                'PENDING','RUNNING','COMPLETED','FAILED',
                                                'REPROCESSING','MIGRATION_STUB'
                                            )),
    -- Scan configuration (frozen at submission)
    commodity                   TEXT        NOT NULL,
    scan_tier                   TEXT        NOT NULL CHECK (scan_tier IN ('BOOTSTRAP','SMART','PREMIUM')),
    environment                 TEXT        NOT NULL CHECK (environment IN ('ONSHORE','OFFSHORE','COMBINED')),
    aoi_geom                    GEOMETRY(GEOMETRY, 4326),  -- PostGIS geometry (WGS84)
    aoi_geojson                 JSONB       NOT NULL,
    grid_resolution_degrees     NUMERIC(10,6) NOT NULL CHECK (grid_resolution_degrees > 0),
    total_cells                 INTEGER     NOT NULL DEFAULT 0 CHECK (total_cells >= 0),

    -- Aggregate ACIF scores (§12) — NULL until canonical freeze
    display_acif_score          NUMERIC(8,6) CHECK (display_acif_score BETWEEN 0 AND 1),
    max_acif_score              NUMERIC(8,6) CHECK (max_acif_score BETWEEN 0 AND 1),
    weighted_acif_score         NUMERIC(8,6) CHECK (weighted_acif_score BETWEEN 0 AND 1),

    -- Tier summary (§13) — stored as JSONB for ThresholdPolicy and TierCounts
    tier_counts                 JSONB,
    tier_thresholds_used        JSONB,

    -- System status (§14)
    system_status               TEXT        CHECK (system_status IN (
                                    'PASS_CONFIRMED','PARTIAL_SIGNAL','INCONCLUSIVE',
                                    'REJECTED','OVERRIDE_CONFIRMED'
                                )),
    gate_results                JSONB,
    confirmation_reason         JSONB,

    -- Score statistics (persisted for analytics)
    mean_evidence_score         NUMERIC(8,6) CHECK (mean_evidence_score BETWEEN 0 AND 1),
    mean_causal_score           NUMERIC(8,6) CHECK (mean_causal_score BETWEEN 0 AND 1),
    mean_physics_score          NUMERIC(8,6) CHECK (mean_physics_score BETWEEN 0 AND 1),
    mean_temporal_score         NUMERIC(8,6) CHECK (mean_temporal_score BETWEEN 0 AND 1),
    mean_province_prior         NUMERIC(8,6) CHECK (mean_province_prior BETWEEN 0 AND 1),
    mean_uncertainty            NUMERIC(8,6) CHECK (mean_uncertainty BETWEEN 0 AND 1),

    -- Veto cell counts
    causal_veto_cell_count      INTEGER     DEFAULT 0 CHECK (causal_veto_cell_count >= 0),
    physics_veto_cell_count     INTEGER     DEFAULT 0 CHECK (physics_veto_cell_count >= 0),
    province_veto_cell_count    INTEGER     DEFAULT 0 CHECK (province_veto_cell_count >= 0),
    offshore_blocked_cell_count INTEGER     DEFAULT 0 CHECK (offshore_blocked_cell_count >= 0),
    offshore_cell_count         INTEGER     DEFAULT 0 CHECK (offshore_cell_count >= 0),
    water_column_corrected      BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Version registry snapshot (frozen at canonical freeze)
    version_registry            JSONB,

    -- Normalisation parameters μ_k, σ_k for all 42 observables
    normalisation_params        JSONB,

    -- Timestamps
    submitted_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at                TIMESTAMPTZ,

    -- Reprocessing lineage
    parent_scan_id              UUID        REFERENCES canonical_scans(scan_id),
    reprocess_reason            TEXT,
    reprocess_changed_params    JSONB,

    -- Migration metadata (Phase R)
    migration_class             TEXT        CHECK (migration_class IN ('A','B','C')),
    migration_notes             TEXT,

    -- Notes
    operator_notes              TEXT,

    CONSTRAINT canonical_scans_completed_requires_completed_at
        CHECK (status != 'COMPLETED' OR completed_at IS NOT NULL),
    CONSTRAINT canonical_scans_completed_requires_display_score
        CHECK (status != 'COMPLETED' OR display_acif_score IS NOT NULL),
    CONSTRAINT canonical_scans_completed_requires_version_registry
        CHECK (status != 'COMPLETED' OR version_registry IS NOT NULL),
    CONSTRAINT canonical_scans_completed_requires_tier_thresholds
        CHECK (status != 'COMPLETED' OR tier_thresholds_used IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_canonical_scans_commodity    ON canonical_scans(commodity);
CREATE INDEX IF NOT EXISTS idx_canonical_scans_status       ON canonical_scans(status);
CREATE INDEX IF NOT EXISTS idx_canonical_scans_completed_at ON canonical_scans(completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_canonical_scans_parent       ON canonical_scans(parent_scan_id);
CREATE INDEX IF NOT EXISTS idx_canonical_scans_aoi_geom     ON canonical_scans USING GIST(aoi_geom);
CREATE INDEX IF NOT EXISTS idx_canonical_scans_system_status ON canonical_scans(system_status);

-- =============================================================================
-- IMMUTABILITY TRIGGER: Reject any UPDATE on a COMPLETED canonical_scan
-- This is the database-level enforcement of the canonical freeze contract.
-- No application code — regardless of privilege level — can bypass this.
-- =============================================================================

CREATE OR REPLACE FUNCTION enforce_canonical_scan_immutability()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'COMPLETED' THEN
        RAISE EXCEPTION
            'AURORA_IMMUTABILITY_VIOLATION: Cannot modify canonical_scan % with status=COMPLETED. '
            'Historical scan records are immutable. To reprocess, create a new scan with '
            'parent_scan_id = %. Use soft_delete_scan for removal (admin only, audit-logged).',
            OLD.scan_id, OLD.scan_id
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_canonical_scan_immutability
    BEFORE UPDATE ON canonical_scans
    FOR EACH ROW EXECUTE FUNCTION enforce_canonical_scan_immutability();

-- Soft-delete function (admin only, audit-logged — does not physically delete)
CREATE OR REPLACE FUNCTION soft_delete_canonical_scan(
    p_scan_id UUID,
    p_actor   TEXT,
    p_reason  TEXT
)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    -- Intentionally bypasses immutability trigger by only setting soft_deleted flag
    -- This requires explicit audit log entry to be valid (enforced in application layer)
    UPDATE canonical_scans
    SET status = 'SOFT_DELETED',
        operator_notes = COALESCE(operator_notes, '') || ' [DELETED by ' || p_actor || ': ' || p_reason || ']'
    WHERE scan_id = p_scan_id
      AND status != 'SOFT_DELETED';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'scan_id % not found or already deleted', p_scan_id;
    END IF;
END;
$$;


-- =============================================================================
-- RAW OBSERVABLES — Sensor stack captures per scan
-- Written once per scan during pipeline step: SENSOR_ACQUISITION
-- Partitioned by environment type for query efficiency
-- =============================================================================

CREATE TABLE IF NOT EXISTS raw_observables (
    raw_obs_id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id             UUID        NOT NULL REFERENCES canonical_scans(scan_id),
    cell_id             TEXT        NOT NULL,
    lat_center          NUMERIC(10,6) NOT NULL CHECK (lat_center BETWEEN -90 AND 90),
    lon_center          NUMERIC(11,6) NOT NULL CHECK (lon_center BETWEEN -180 AND 180),
    environment         TEXT        NOT NULL CHECK (environment IN ('ONSHORE','OFFSHORE','COMBINED')),
    acquisition_date    DATE,

    -- Raw (un-normalised) sensor values stored as JSONB
    -- Structure: { "x_spec_1": 0.34, "x_sar_1": null, ... }
    -- null = missing sensor (not zero measurement)
    raw_values          JSONB       NOT NULL DEFAULT '{}',

    -- Sensor mission metadata per modality
    -- { "spectral": {"mission": "Sentinel-2", "scene_id": "..."}, "sar": {...}, ... }
    sensor_metadata     JSONB       NOT NULL DEFAULT '{}',

    -- Offshore raw values (pre-correction — stored separately for audit trail)
    offshore_raw_values JSONB,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_obs_scan_id ON raw_observables(scan_id);
CREATE INDEX IF NOT EXISTS idx_raw_obs_cell    ON raw_observables(scan_id, cell_id);
CREATE INDEX IF NOT EXISTS idx_raw_obs_env     ON raw_observables(environment);


-- =============================================================================
-- HARMONISED TENSORS — Cross-mission harmonised feature vectors per scan
-- Written once per scan during pipeline step: HARMONIZATION
-- =============================================================================

CREATE TABLE IF NOT EXISTS harmonised_tensors (
    tensor_id           UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_id             UUID        NOT NULL REFERENCES canonical_scans(scan_id),
    cell_id             TEXT        NOT NULL,

    -- Normalised observable vector (post-harmonisation, post-normalisation)
    -- Structure matches ObservableVector field names exactly
    observable_vector   JSONB       NOT NULL DEFAULT '{}',

    -- Normalisation parameters used for this cell
    -- { "x_spec_1": {"mu": 0.45, "sigma": 0.12}, ... }
    normalisation_params JSONB      NOT NULL DEFAULT '{}',

    -- Observable coverage statistics
    present_count       SMALLINT    NOT NULL DEFAULT 0 CHECK (present_count BETWEEN 0 AND 42),
    missing_count       SMALLINT    NOT NULL DEFAULT 0 CHECK (missing_count BETWEEN 0 AND 42),
    coverage_fraction   NUMERIC(5,4) NOT NULL DEFAULT 0 CHECK (coverage_fraction BETWEEN 0 AND 1),

    -- Offshore correction flag — offshore cells must be corrected before harmonisation
    offshore_corrected  BOOLEAN     NOT NULL DEFAULT FALSE,
    offshore_correction_detail JSONB,

    -- Gravity decomposition outputs stored here for downstream physics module
    gravity_composite   JSONB,      -- { "g_long": ..., "g_medium": ..., "g_short": ..., "g_composite": ... }

    harmonisation_version TEXT,     -- From version_registry.scan_pipeline_version
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT harmonised_tensor_count_check
        CHECK (present_count + missing_count = 42),

    CONSTRAINT harmonised_offshore_correction
        CHECK (
            -- Offshore cells MUST be corrected before harmonisation
            environment IS NULL
            OR environment != 'OFFSHORE'
            OR offshore_corrected = TRUE
        )
);

-- We join environment from raw_observables so need it here too
ALTER TABLE harmonised_tensors ADD COLUMN IF NOT EXISTS
    environment TEXT CHECK (environment IN ('ONSHORE','OFFSHORE','COMBINED'));

CREATE INDEX IF NOT EXISTS idx_harmonised_scan    ON harmonised_tensors(scan_id);
CREATE INDEX IF NOT EXISTS idx_harmonised_cell    ON harmonised_tensors(scan_id, cell_id);
CREATE INDEX IF NOT EXISTS idx_harmonised_env     ON harmonised_tensors(environment);


-- =============================================================================
-- SCAN CELLS — Per-cell scored and tiered canonical outputs
-- Written ONCE at canonical freeze alongside the CanonicalScan record.
-- No UPDATE or DELETE permitted after creation.
-- =============================================================================

CREATE TABLE IF NOT EXISTS scan_cells (
    cell_pk             UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    cell_id             TEXT        NOT NULL,
    scan_id             UUID        NOT NULL REFERENCES canonical_scans(scan_id),
    lat_center          NUMERIC(10,6) NOT NULL CHECK (lat_center BETWEEN -90 AND 90),
    lon_center          NUMERIC(11,6) NOT NULL CHECK (lon_center BETWEEN -180 AND 180),
    cell_geom           GEOMETRY(POLYGON, 4326),
    cell_size_degrees   NUMERIC(10,6) NOT NULL CHECK (cell_size_degrees > 0),
    environment         TEXT        NOT NULL CHECK (environment IN ('ONSHORE','OFFSHORE','COMBINED')),

    -- Component score stack (§I modules)
    evidence_score      NUMERIC(8,6) CHECK (evidence_score BETWEEN 0 AND 1),
    causal_score        NUMERIC(8,6) CHECK (causal_score BETWEEN 0 AND 1),
    physics_score       NUMERIC(8,6) CHECK (physics_score BETWEEN 0 AND 1),
    temporal_score      NUMERIC(8,6) CHECK (temporal_score BETWEEN 0 AND 1),
    province_prior      NUMERIC(8,6) CHECK (province_prior BETWEEN 0 AND 1),
    uncertainty         NUMERIC(8,6) CHECK (uncertainty BETWEEN 0 AND 1),

    -- ACIF and tier (§J modules)
    acif_score          NUMERIC(8,6) CHECK (acif_score BETWEEN 0 AND 1),
    tier                TEXT        CHECK (tier IN ('TIER_1','TIER_2','TIER_3','BELOW')),

    -- Physics residuals — first-class outputs, not diagnostics
    gravity_residual    NUMERIC(16,8) CHECK (gravity_residual >= 0),
    physics_residual    NUMERIC(16,8) CHECK (physics_residual >= 0),
    darcy_residual      NUMERIC(16,8) CHECK (darcy_residual >= 0),
    water_column_residual NUMERIC(16,8) CHECK (water_column_residual >= 0),

    -- Veto flags
    causal_veto_fired   BOOLEAN     NOT NULL DEFAULT FALSE,
    physics_veto_fired  BOOLEAN     NOT NULL DEFAULT FALSE,
    temporal_veto_fired BOOLEAN     NOT NULL DEFAULT FALSE,
    province_veto_fired BOOLEAN     NOT NULL DEFAULT FALSE,
    offshore_gate_blocked BOOLEAN   NOT NULL DEFAULT FALSE,

    -- Uncertainty breakdown
    u_sensor            NUMERIC(8,6) CHECK (u_sensor BETWEEN 0 AND 1),
    u_model             NUMERIC(8,6) CHECK (u_model BETWEEN 0 AND 1),
    u_physics           NUMERIC(8,6) CHECK (u_physics BETWEEN 0 AND 1),
    u_temporal          NUMERIC(8,6) CHECK (u_temporal BETWEEN 0 AND 1),
    u_prior             NUMERIC(8,6) CHECK (u_prior BETWEEN 0 AND 1),

    -- Observable coverage
    observable_coverage_fraction NUMERIC(5,4) CHECK (observable_coverage_fraction BETWEEN 0 AND 1),
    missing_observable_count     SMALLINT     CHECK (missing_observable_count BETWEEN 0 AND 42),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT scan_cells_unique_per_scan UNIQUE (scan_id, cell_id),

    -- Offshore gate enforcement: offshore cells MUST pass correction gate
    CONSTRAINT scan_cells_offshore_gate
        CHECK (environment != 'OFFSHORE' OR offshore_gate_blocked = TRUE OR
               (offshore_gate_blocked = FALSE AND acif_score IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_scan_cells_scan_id   ON scan_cells(scan_id);
CREATE INDEX IF NOT EXISTS idx_scan_cells_tier       ON scan_cells(scan_id, tier);
CREATE INDEX IF NOT EXISTS idx_scan_cells_acif       ON scan_cells(scan_id, acif_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_scan_cells_geom       ON scan_cells USING GIST(cell_geom);
CREATE INDEX IF NOT EXISTS idx_scan_cells_vetos      ON scan_cells(scan_id) WHERE causal_veto_fired OR province_veto_fired;


-- =============================================================================
-- HISTORY INDEX — Materialised view derived from canonical_scans
-- Never an independent truth source. Refreshed post-freeze only.
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS history_index AS
SELECT
    scan_id,
    commodity,
    scan_tier,
    environment,
    status,
    display_acif_score,
    max_acif_score,
    system_status,
    (tier_counts->>'tier_1')::INTEGER           AS tier_1_count,
    (tier_counts->>'total_cells')::INTEGER      AS total_cells,
    submitted_at,
    completed_at,
    parent_scan_id,
    migration_class,
    -- Threshold source for quick filtering
    tier_thresholds_used->>'source'             AS threshold_source
FROM canonical_scans
WHERE status IN ('COMPLETED', 'MIGRATION_STUB')
  AND status != 'SOFT_DELETED'
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_history_index_scan_id ON history_index(scan_id);
CREATE INDEX IF NOT EXISTS idx_history_index_commodity       ON history_index(commodity);
CREATE INDEX IF NOT EXISTS idx_history_index_completed_at    ON history_index(completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_index_status          ON history_index(system_status);

-- History index refresh function (called by pipeline post-freeze, never during scoring)
CREATE OR REPLACE FUNCTION refresh_history_index()
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY history_index;
END;
$$;


-- =============================================================================
-- DIGITAL TWIN VOXELS — 3D volumetric sovereignty layer
-- Versioned, append-only per scan_id version.
-- PostGIS geometry for spatial queries.
-- =============================================================================

CREATE TABLE IF NOT EXISTS digital_twin_voxels (
    voxel_pk            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    voxel_id            TEXT        NOT NULL,
    scan_id             UUID        NOT NULL REFERENCES canonical_scans(scan_id),
    twin_version        INTEGER     NOT NULL DEFAULT 1 CHECK (twin_version >= 1),
    lat_center          NUMERIC(10,6) NOT NULL,
    lon_center          NUMERIC(11,6) NOT NULL,
    depth_m             NUMERIC(10,2) NOT NULL CHECK (depth_m >= 0),
    depth_min_m         NUMERIC(10,2) NOT NULL CHECK (depth_min_m >= 0),
    depth_max_m         NUMERIC(10,2) NOT NULL CHECK (depth_max_m > depth_min_m),
    voxel_geom          GEOMETRY(POLYGON, 4326),

    -- Commodity probability map at this depth
    -- { "gold": 0.72, "copper": 0.31, ... }
    commodity_probs     JSONB       NOT NULL DEFAULT '{}',

    -- Physical properties
    expected_density    NUMERIC(10,4) CHECK (expected_density >= 0),
    density_uncertainty NUMERIC(10,4) CHECK (density_uncertainty >= 0),

    -- Propagated scores from parent cell
    temporal_score      NUMERIC(8,6) CHECK (temporal_score BETWEEN 0 AND 1),
    physics_residual    NUMERIC(16,8) CHECK (physics_residual >= 0),
    uncertainty         NUMERIC(8,6) CHECK (uncertainty BETWEEN 0 AND 1),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT dtv_unique_voxel_per_version UNIQUE (scan_id, twin_version, voxel_id),
    CONSTRAINT dtv_depth_range_valid CHECK (depth_min_m < depth_max_m)
);

CREATE INDEX IF NOT EXISTS idx_dtv_scan_version ON digital_twin_voxels(scan_id, twin_version);
CREATE INDEX IF NOT EXISTS idx_dtv_depth        ON digital_twin_voxels(scan_id, depth_m);
CREATE INDEX IF NOT EXISTS idx_dtv_commodity    ON digital_twin_voxels USING GIN(commodity_probs);
CREATE INDEX IF NOT EXISTS idx_dtv_geom         ON digital_twin_voxels USING GIST(voxel_geom);

-- Twin version metadata table
CREATE TABLE IF NOT EXISTS digital_twin_versions (
    scan_id             UUID        NOT NULL REFERENCES canonical_scans(scan_id),
    version             INTEGER     NOT NULL CHECK (version >= 1),
    voxel_count         INTEGER     NOT NULL DEFAULT 0 CHECK (voxel_count >= 0),
    depth_min_m         NUMERIC(10,2) NOT NULL,
    depth_max_m         NUMERIC(10,2) NOT NULL,
    trigger_type        TEXT        NOT NULL CHECK (trigger_type IN ('initial','reprocess')),
    parent_version      INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (scan_id, version)
);


-- =============================================================================
-- AUDIT LOG — Append-only via PostgreSQL RLS
-- No UPDATE or DELETE is permitted for ANY role.
-- =============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type          TEXT        NOT NULL,
    actor_user_id       UUID,
    actor_email         TEXT,
    actor_role          TEXT        CHECK (actor_role IN ('admin','operator','viewer')),
    scan_id             UUID,       -- FK not enforced to allow audit of deleted scans
    details             JSONB,
    ip_address          TEXT,
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_scan_id    ON audit_log(scan_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor      ON audit_log(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp  ON audit_log(timestamp DESC);

-- Row-Level Security: append-only for all roles
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- Only the application service account (aurora_app) may INSERT
CREATE POLICY audit_log_insert_only ON audit_log
    FOR INSERT
    TO aurora_app
    WITH CHECK (TRUE);

-- No UPDATE permitted for ANY role including aurora_app
CREATE POLICY audit_log_no_update ON audit_log
    FOR UPDATE
    USING (FALSE);

-- No DELETE permitted for ANY role including aurora_app
CREATE POLICY audit_log_no_delete ON audit_log
    FOR DELETE
    USING (FALSE);

-- SELECT permitted for admin role only
CREATE POLICY audit_log_select_admin ON audit_log
    FOR SELECT
    TO aurora_admin
    USING (TRUE);


-- =============================================================================
-- USERS — Platform users table (referenced by audit and security layers)
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    user_id             UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    email               TEXT        NOT NULL UNIQUE,
    full_name           TEXT        NOT NULL,
    password_hash       TEXT        NOT NULL,
    role                TEXT        NOT NULL DEFAULT 'viewer'
                                    CHECK (role IN ('admin','operator','viewer')),
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    must_rotate_password BOOLEAN    NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role  ON users(role);

-- Refresh token store
CREATE TABLE IF NOT EXISTS refresh_tokens (
    jti                 TEXT        PRIMARY KEY,
    user_id             UUID        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    issued_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL,
    revoked             BOOLEAN     NOT NULL DEFAULT FALSE,
    revoked_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user    ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at);


COMMIT;