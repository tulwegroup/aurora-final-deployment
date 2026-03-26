-- Aurora OSI vNext — Spatial Indexes & Query Acceleration
-- Phase S §S.1 — Migration 004
--
-- Adds:
--   1. PostGIS spatial indexes on scan_cells and digital_twin_voxels
--   2. B-tree composite indexes for common filter patterns
--   3. Partial indexes for completed scans and active query paths
--   4. Covering indexes for list-view projections (avoids heap fetch)
--
-- CONSTITUTIONAL RULE — Phase S:
--   This migration adds indexes ONLY. No column values are altered.
--   No scientific field is recomputed. No data is migrated or transformed.
--   Indexes are infrastructure — they accelerate reads without changing results.
--
-- Rollback: DROP INDEX statements at bottom of file (commented).

-- ── Enable PostGIS (idempotent) ───────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. canonical_scans — query acceleration indexes
-- ─────────────────────────────────────────────────────────────────────────────

-- Primary list-view filter: status + completed_at (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_canonical_scans_status_completed
    ON canonical_scans (status, completed_at DESC NULLS LAST)
    WHERE status = 'COMPLETED';

-- Commodity filter for history page
CREATE INDEX IF NOT EXISTS idx_canonical_scans_commodity_completed
    ON canonical_scans (commodity, completed_at DESC NULLS LAST)
    WHERE status = 'COMPLETED';

-- Migration class filter (Phase R backfill queries)
CREATE INDEX IF NOT EXISTS idx_canonical_scans_migration_class
    ON canonical_scans (migration_class)
    WHERE migration_class IS NOT NULL;

-- Covering index for ScanHistory list view:
-- Returns scan_id, commodity, status, completed_at, display_acif_score, scan_tier
-- without heap fetch — avoids reading full wide row.
CREATE INDEX IF NOT EXISTS idx_canonical_scans_list_covering
    ON canonical_scans (status, completed_at DESC NULLS LAST)
    INCLUDE (scan_id, commodity, scan_tier, display_acif_score, system_status)
    WHERE status = 'COMPLETED';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. scan_cells — spatial + composite indexes
-- ─────────────────────────────────────────────────────────────────────────────

-- Add PostGIS geometry column for spatial queries (idempotent guard via DO block)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scan_cells' AND column_name = 'geom'
    ) THEN
        ALTER TABLE scan_cells
            ADD COLUMN geom geometry(Point, 4326)
            GENERATED ALWAYS AS (
                ST_SetSRID(ST_MakePoint(lon_center, lat_center), 4326)
            ) STORED;
    END IF;
END $$;

-- GIST spatial index on generated geometry column
CREATE INDEX IF NOT EXISTS idx_scan_cells_geom
    ON scan_cells USING GIST (geom)
    WHERE geom IS NOT NULL;

-- Primary filter: scan_id lookup (foreign key traversal)
CREATE INDEX IF NOT EXISTS idx_scan_cells_scan_id
    ON scan_cells (scan_id);

-- Tier filter within a scan (DatasetView tier breakdown)
CREATE INDEX IF NOT EXISTS idx_scan_cells_scan_tier
    ON scan_cells (scan_id, tier)
    WHERE tier IS NOT NULL;

-- Offshore gate filter (common exclusion filter in twin builder)
CREATE INDEX IF NOT EXISTS idx_scan_cells_offshore
    ON scan_cells (scan_id, offshore_gate_blocked)
    WHERE offshore_gate_blocked = TRUE;

-- Covering index for cell list view (avoids heap fetch for table display)
CREATE INDEX IF NOT EXISTS idx_scan_cells_list_covering
    ON scan_cells (scan_id, acif_score DESC NULLS LAST)
    INCLUDE (cell_id, lat_center, lon_center, tier, uncertainty);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. digital_twin_voxels — spatial + depth + version indexes
-- ─────────────────────────────────────────────────────────────────────────────

-- Add PostGIS 3D geometry column for voxel spatial queries (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'digital_twin_voxels' AND column_name = 'geom3d'
    ) THEN
        ALTER TABLE digital_twin_voxels
            ADD COLUMN geom3d geometry(PointZ, 4326)
            GENERATED ALWAYS AS (
                ST_SetSRID(ST_MakePoint(lon_center, lat_center, depth_m), 4326)
            ) STORED;
    END IF;
END $$;

-- GIST 3D spatial index
CREATE INDEX IF NOT EXISTS idx_voxels_geom3d
    ON digital_twin_voxels USING GIST (geom3d)
    WHERE geom3d IS NOT NULL;

-- Primary filter: scan_id + twin_version (most common query)
CREATE INDEX IF NOT EXISTS idx_voxels_scan_version
    ON digital_twin_voxels (scan_id, twin_version);

-- Depth range filter (slice queries from TwinView)
CREATE INDEX IF NOT EXISTS idx_voxels_depth
    ON digital_twin_voxels (scan_id, twin_version, depth_m);

-- Covering index for progressive voxel loading (avoids wide heap fetch)
CREATE INDEX IF NOT EXISTS idx_voxels_load_covering
    ON digital_twin_voxels (scan_id, twin_version, depth_m)
    INCLUDE (voxel_id, lat_center, lon_center, source_cell_id, kernel_weight);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. audit_log — scan_id lookup acceleration
-- ─────────────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_audit_log_scan_id
    ON audit_log (scan_id, created_at DESC NULLS LAST)
    WHERE scan_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_audit_log_actor
    ON audit_log (actor_email, created_at DESC NULLS LAST);

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Table statistics — update planner stats after index creation
-- ─────────────────────────────────────────────────────────────────────────────

ANALYZE canonical_scans;
ANALYZE scan_cells;
ANALYZE digital_twin_voxels;
ANALYZE audit_log;

-- ─────────────────────────────────────────────────────────────────────────────
-- Rollback (run manually if needed):
-- ─────────────────────────────────────────────────────────────────────────────
-- DROP INDEX IF EXISTS idx_canonical_scans_status_completed;
-- DROP INDEX IF EXISTS idx_canonical_scans_commodity_completed;
-- DROP INDEX IF EXISTS idx_canonical_scans_migration_class;
-- DROP INDEX IF EXISTS idx_canonical_scans_list_covering;
-- DROP INDEX IF EXISTS idx_scan_cells_geom;
-- DROP INDEX IF EXISTS idx_scan_cells_scan_id;
-- DROP INDEX IF EXISTS idx_scan_cells_scan_tier;
-- DROP INDEX IF EXISTS idx_scan_cells_offshore;
-- DROP INDEX IF EXISTS idx_scan_cells_list_covering;
-- DROP INDEX IF EXISTS idx_voxels_geom3d;
-- DROP INDEX IF EXISTS idx_voxels_scan_version;
-- DROP INDEX IF EXISTS idx_voxels_depth;
-- DROP INDEX IF EXISTS idx_voxels_load_covering;
-- DROP INDEX IF EXISTS idx_audit_log_scan_id;
-- DROP INDEX IF EXISTS idx_audit_log_actor;
-- ALTER TABLE scan_cells DROP COLUMN IF EXISTS geom;
-- ALTER TABLE digital_twin_voxels DROP COLUMN IF EXISTS geom3d;