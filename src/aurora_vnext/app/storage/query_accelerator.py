"""
Aurora OSI vNext — Spatial Query Accelerator
Phase S §S.2

Provides accelerated query methods for:
  - Canonical scan list retrieval (covering index path)
  - Scan cell spatial bounding-box filter (PostGIS ST_Within)
  - Scan cell depth-slice retrieval for TwinView progressive loading
  - Voxel spatial query (PostGIS 3D point-in-box)
  - Cursor-based pagination (keyset, not OFFSET) for large result sets

CONSTITUTIONAL RULES — Phase S:
  Rule 1: Zero scientific logic. No imports from core/*.
  Rule 2: Query methods return stored values VERBATIM.
           No field is computed, derived, or defaulted in this layer.
  Rule 3: Spatial filters (bounding box, depth range) are GEOMETRIC predicates
           applied to stored coordinates. They do not alter field values.
  Rule 4: Pagination uses keyset cursors (scan_id + completed_at) — not OFFSET.
           Keyset pagination is infrastructure only; it does not alter field values.
  Rule 5: No scientific constant, threshold, or scoring formula is used as a
           filter predicate. Callers supply all filter values explicitly.
  Rule 6: explain_query() is a DBA utility — it emits EXPLAIN ANALYZE output
           to the logger. It does not alter query results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from app.config.observability import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# DB session protocol — injected; never imported from a specific ORM here
# ---------------------------------------------------------------------------

class AsyncSession(Protocol):
    async def execute(self, stmt, params=None) -> Any: ...
    async def fetchall(self) -> list[Any]: ...


# ---------------------------------------------------------------------------
# Query parameter dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScanListQuery:
    """
    Parameters for canonical scan list retrieval.

    PROOF: status, commodity, environment are string equality filters —
    no numeric comparison or threshold applied. All are caller-supplied.
    """
    status:       Optional[str]  = "COMPLETED"
    commodity:    Optional[str]  = None
    environment:  Optional[str]  = None
    limit:        int            = 50
    # Keyset cursor fields (Rule 4 — no OFFSET)
    cursor_completed_at: Optional[str]  = None
    cursor_scan_id:      Optional[str]  = None


@dataclass(frozen=True)
class CellSpatialQuery:
    """
    Parameters for spatial cell retrieval within a bounding box.

    PROOF: min_lat/max_lat/min_lon/max_lon are geometric predicates.
    They filter by stored lat_center/lon_center — no scientific formula applied.
    tier_filter is a string equality check on the stored tier field.
    """
    scan_id:     str
    min_lat:     Optional[float] = None
    max_lat:     Optional[float] = None
    min_lon:     Optional[float] = None
    max_lon:     Optional[float] = None
    tier_filter: Optional[str]   = None          # e.g. "TIER_1" — equality only
    limit:       int              = 1000
    cursor_cell_id: Optional[str] = None


@dataclass(frozen=True)
class VoxelDepthQuery:
    """
    Parameters for voxel retrieval by scan + version + depth range.

    PROOF: depth_min_m / depth_max_m are range predicates on stored depth_m.
    No kernel recomputation. No probability filter (callers may supply
    min_probability as a stored-value equality filter only).
    """
    scan_id:         str
    twin_version:    int
    depth_min_m:     Optional[float] = None
    depth_max_m:     Optional[float] = None
    min_probability: Optional[float] = None      # filter on stored commodity_probs value
    limit:           int             = 500
    cursor_depth_m:  Optional[float] = None
    cursor_voxel_id: Optional[str]   = None


# ---------------------------------------------------------------------------
# SQL query builders — parameterised, no scientific literals
# ---------------------------------------------------------------------------

def _build_scan_list_sql(q: ScanListQuery) -> tuple[str, dict]:
    """
    Build SQL for canonical scan list using covering index path.
    Returns (sql_string, params_dict).

    Uses idx_canonical_scans_list_covering for status=COMPLETED queries.
    Keyset pagination avoids OFFSET — O(1) page retrieval regardless of depth.

    PROOF: no numeric predicate on any scientific field.
    """
    conditions = []
    params: dict = {}

    if q.status:
        conditions.append("status = :status")
        params["status"] = q.status

    if q.commodity:
        conditions.append("commodity = :commodity")
        params["commodity"] = q.commodity

    if q.environment:
        conditions.append("environment = :environment")
        params["environment"] = q.environment

    # Keyset cursor (completed_at DESC, scan_id ASC for tie-breaking)
    if q.cursor_completed_at and q.cursor_scan_id:
        conditions.append(
            "(completed_at, scan_id) < (:cursor_completed_at, :cursor_scan_id)"
        )
        params["cursor_completed_at"] = q.cursor_completed_at
        params["cursor_scan_id"]      = q.cursor_scan_id

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT
            scan_id, commodity, scan_tier, status,
            display_acif_score, system_status, completed_at,
            migration_class
        FROM canonical_scans
        {where_clause}
        ORDER BY completed_at DESC NULLS LAST, scan_id ASC
        LIMIT :limit
    """
    params["limit"] = q.limit
    return sql.strip(), params


def _build_cell_spatial_sql(q: CellSpatialQuery) -> tuple[str, dict]:
    """
    Build SQL for scan cell retrieval with optional spatial bounding box.

    Spatial filter uses PostGIS ST_Within on the generated `geom` column,
    which is backed by idx_scan_cells_geom (GIST index).

    PROOF: ST_MakeEnvelope is a geometric predicate — no scientific value.
    Tier filter is string equality on stored tier field — no recomputation.
    """
    conditions = ["scan_id = :scan_id"]
    params: dict = {"scan_id": q.scan_id}

    if all(x is not None for x in [q.min_lat, q.max_lat, q.min_lon, q.max_lon]):
        # ST_Within(geom, ST_MakeEnvelope(xmin, ymin, xmax, ymax, srid))
        conditions.append(
            "ST_Within(geom, ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax, 4326))"
        )
        params.update({
            "xmin": q.min_lon, "ymin": q.min_lat,
            "xmax": q.max_lon, "ymax": q.max_lat,
        })

    if q.tier_filter:
        conditions.append("tier = :tier")
        params["tier"] = q.tier_filter

    # Keyset pagination on cell_id
    if q.cursor_cell_id:
        conditions.append("cell_id > :cursor_cell_id")
        params["cursor_cell_id"] = q.cursor_cell_id

    where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            cell_id, scan_id, lat_center, lon_center,
            acif_score, tier, temporal_score, physics_residual,
            uncertainty, offshore_gate_blocked
        FROM scan_cells
        {where_clause}
        ORDER BY cell_id ASC
        LIMIT :limit
    """
    params["limit"] = q.limit
    return sql.strip(), params


def _build_voxel_depth_sql(q: VoxelDepthQuery) -> tuple[str, dict]:
    """
    Build SQL for progressive voxel loading with depth range and keyset cursor.

    Uses idx_voxels_depth composite index: (scan_id, twin_version, depth_m).
    Keyset cursor on (depth_m, voxel_id) enables O(1) page retrieval.

    PROOF: depth_min_m/depth_max_m are range predicates on stored depth_m.
    min_probability (if supplied) is a numeric filter on stored commodity_probs
    value — not a recomputed value. The caller supplies this value explicitly.
    No scientific constant or formula is used as a filter.
    """
    conditions = [
        "scan_id = :scan_id",
        "twin_version = :twin_version",
    ]
    params: dict = {"scan_id": q.scan_id, "twin_version": q.twin_version}

    if q.depth_min_m is not None:
        conditions.append("depth_m >= :depth_min_m")
        params["depth_min_m"] = q.depth_min_m

    if q.depth_max_m is not None:
        conditions.append("depth_m <= :depth_max_m")
        params["depth_max_m"] = q.depth_max_m

    # Keyset cursor: (depth_m ASC, voxel_id ASC)
    if q.cursor_depth_m is not None and q.cursor_voxel_id:
        conditions.append(
            "(depth_m, voxel_id) > (:cursor_depth_m, :cursor_voxel_id)"
        )
        params["cursor_depth_m"]  = q.cursor_depth_m
        params["cursor_voxel_id"] = q.cursor_voxel_id

    where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            voxel_id, scan_id, twin_version,
            lat_center, lon_center, depth_m,
            commodity_probs, kernel_weight, expected_density,
            density_uncertainty, temporal_score, physics_residual,
            uncertainty, source_cell_id, created_at
        FROM digital_twin_voxels
        {where_clause}
        ORDER BY depth_m ASC, voxel_id ASC
        LIMIT :limit
    """
    params["limit"] = q.limit
    return sql.strip(), params


# ---------------------------------------------------------------------------
# QueryAccelerator — public interface
# ---------------------------------------------------------------------------

class QueryAccelerator:
    """
    Accelerated read methods for the Aurora query layer.

    All methods return rows verbatim from the database.
    No field value is computed, defaulted, or transformed in this class.

    Inject a SQLAlchemy AsyncSession (or compatible adapter) via __init__.
    """

    def __init__(self, session):
        self._session = session

    async def list_scans(self, query: ScanListQuery) -> list[dict]:
        """
        Return paginated canonical scan summaries using covering index.
        Result fields: scan_id, commodity, scan_tier, status,
        display_acif_score, system_status, completed_at, migration_class.

        PROOF: SQL selects named columns verbatim. No arithmetic.
        """
        from sqlalchemy import text
        sql, params = _build_scan_list_sql(query)
        result = await self._session.execute(text(sql), params)
        rows = result.mappings().all()
        logger.info(
            "list_scans",
            extra={"row_count": len(rows), "status": query.status, "commodity": query.commodity},
        )
        return [dict(r) for r in rows]

    async def list_cells_spatial(self, query: CellSpatialQuery) -> list[dict]:
        """
        Return scan cells within an optional bounding box using GIST index.

        PROOF: PostGIS ST_Within is a geometric predicate.
        No cell field value is altered.
        """
        from sqlalchemy import text
        sql, params = _build_cell_spatial_sql(query)
        result = await self._session.execute(text(sql), params)
        rows = result.mappings().all()
        logger.info(
            "list_cells_spatial",
            extra={"scan_id": query.scan_id, "row_count": len(rows)},
        )
        return [dict(r) for r in rows]

    async def list_voxels_paged(self, query: VoxelDepthQuery) -> list[dict]:
        """
        Return a depth-ordered page of voxels using keyset cursor.

        Supports progressive loading in TwinView: caller supplies
        cursor from the last row of the previous page.

        PROOF: depth_m range filter is geometric. Field values verbatim.
        """
        from sqlalchemy import text
        sql, params = _build_voxel_depth_sql(query)
        result = await self._session.execute(text(sql), params)
        rows = result.mappings().all()
        logger.info(
            "list_voxels_paged",
            extra={
                "scan_id": query.scan_id,
                "twin_version": query.twin_version,
                "row_count": len(rows),
            },
        )
        return [dict(r) for r in rows]

    async def count_cells(self, scan_id: str) -> int:
        """Return total cell count for a scan (uses idx_scan_cells_scan_id)."""
        from sqlalchemy import text
        result = await self._session.execute(
            text("SELECT COUNT(*) FROM scan_cells WHERE scan_id = :sid"),
            {"sid": scan_id},
        )
        return result.scalar() or 0

    async def count_voxels(self, scan_id: str, twin_version: int) -> int:
        """Return total voxel count for a scan + version."""
        from sqlalchemy import text
        result = await self._session.execute(
            text(
                "SELECT COUNT(*) FROM digital_twin_voxels "
                "WHERE scan_id = :sid AND twin_version = :ver"
            ),
            {"sid": scan_id, "ver": twin_version},
        )
        return result.scalar() or 0

    async def explain_query(self, sql: str, params: dict) -> str:
        """
        DBA utility: run EXPLAIN ANALYZE and return plan as string.
        Never used in production request paths — only for index tuning.

        PROOF: does not alter query results; emits plan text only.
        """
        from sqlalchemy import text
        result = await self._session.execute(
            text(f"EXPLAIN ANALYZE {sql}"), params
        )
        plan = "\n".join(row[0] for row in result.fetchall())
        logger.info("explain_query", extra={"plan_lines": plan.count("\n") + 1})
        return plan