"""
Aurora OSI vNext — Digital Twin Voxel Store
Phase G §G.5 (schema) — Phase N (full query implementation)

APPEND-ONLY per scan_id version.
Previous twin versions are NEVER overwritten — the full history is preserved.

Twin construction:
  1. services/twin_builder.py reads frozen CanonicalScan
  2. Projects 2D cells to 3D voxels via depth kernel D^(c)(z)
  3. Calls write_voxels() here
  4. Increments twin_version counter
  5. Canonical scan record is NOT modified (builder is read-only against canonical)
"""

from __future__ import annotations

import json
from typing import Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.digital_twin_model import (
    DigitalTwinVoxel,
    TwinMetadata,
    TwinQuery,
    TwinQueryResult,
    TwinVersion,
)
from app.storage.base import BaseStore, StorageNotFoundError


class DigitalTwinStore(BaseStore):

    async def write_voxels(
        self,
        scan_id: str,
        voxels: list[DigitalTwinVoxel],
        twin_version: int,
        trigger_type: str = "initial",
        parent_version: Optional[int] = None,
    ) -> None:
        """
        Write a full voxel set for one twin version.
        Does not overwrite previous versions — new version row is appended.
        """
        for v in voxels:
            await self._session.execute(
                text("""
                    INSERT INTO digital_twin_voxels (
                        voxel_id, scan_id, twin_version,
                        lat_center, lon_center, depth_m, depth_min_m, depth_max_m,
                        commodity_probs, expected_density, density_uncertainty,
                        temporal_score, physics_residual, uncertainty,
                        created_at
                    ) VALUES (
                        :voxel_id, :scan_id, :version,
                        :lat, :lon, :depth_m, :depth_min, :depth_max,
                        :probs::jsonb, :density, :density_unc,
                        :temporal, :physics_res, :uncertainty,
                        NOW()
                    )
                    ON CONFLICT (scan_id, twin_version, voxel_id) DO NOTHING
                """),
                {
                    "voxel_id":     v.voxel_id,
                    "scan_id":      scan_id,
                    "version":      twin_version,
                    "lat":          v.lat_center,
                    "lon":          v.lon_center,
                    "depth_m":      v.depth_m,
                    "depth_min":    v.depth_range_m[0],
                    "depth_max":    v.depth_range_m[1],
                    "probs":        json.dumps(v.commodity_probs),
                    "density":      v.expected_density,
                    "density_unc":  v.density_uncertainty,
                    "temporal":     v.temporal_score,
                    "physics_res":  v.physics_residual,
                    "uncertainty":  v.uncertainty,
                }
            )

        # Write version metadata
        depth_min = min(v.depth_range_m[0] for v in voxels) if voxels else 0.0
        depth_max = max(v.depth_range_m[1] for v in voxels) if voxels else 0.0
        await self._session.execute(
            text("""
                INSERT INTO digital_twin_versions (
                    scan_id, version, voxel_count, depth_min_m, depth_max_m,
                    trigger_type, parent_version, created_at
                ) VALUES (
                    :scan_id, :version, :count, :d_min, :d_max,
                    :trigger, :parent, NOW()
                )
                ON CONFLICT (scan_id, version) DO NOTHING
            """),
            {
                "scan_id":  scan_id,
                "version":  twin_version,
                "count":    len(voxels),
                "d_min":    depth_min,
                "d_max":    depth_max,
                "trigger":  trigger_type,
                "parent":   parent_version,
            }
        )
        await self._session.commit()

    async def get_twin_metadata(self, scan_id: str) -> TwinMetadata:
        row = await self._session.execute(
            text("""
                SELECT v.*, cs.commodity
                FROM digital_twin_versions v
                JOIN canonical_scans cs ON cs.scan_id = v.scan_id
                WHERE v.scan_id = :scan_id
                ORDER BY v.version DESC LIMIT 1
            """),
            {"scan_id": scan_id},
        )
        record = row.mappings().fetchone()
        if not record:
            raise StorageNotFoundError(f"No twin found for scan_id={scan_id}")
        d = dict(record)
        return TwinMetadata(
            scan_id=scan_id,
            current_version=d["version"],
            total_voxels=d["voxel_count"],
            depth_range_m=(float(d["depth_min_m"]), float(d["depth_max_m"])),
            commodity=d["commodity"],
            created_at=d["created_at"],
            updated_at=d["created_at"],
        )

    async def query_voxels(self, query: TwinQuery) -> TwinQueryResult:
        """
        Filter voxels by commodity probability, depth range, and spatial bounds.
        All values are read from stored voxel data — no recomputation.
        """
        version = query.version
        if version is None:
            v_row = await self._session.execute(
                text("SELECT MAX(version) FROM digital_twin_versions WHERE scan_id = :sid"),
                {"sid": query.scan_id},
            )
            version = v_row.scalar() or 1

        filters = ["scan_id = :scan_id", "twin_version = :version"]
        params: dict = {"scan_id": query.scan_id, "version": version, "limit": query.limit}

        if query.depth_min_m is not None:
            filters.append("depth_m >= :depth_min")
            params["depth_min"] = query.depth_min_m
        if query.depth_max_m is not None:
            filters.append("depth_m <= :depth_max")
            params["depth_max"] = query.depth_max_m
        if query.commodity and query.min_probability is not None:
            filters.append("(commodity_probs->>:commodity)::numeric >= :min_prob")
            params["commodity"] = query.commodity
            params["min_prob"] = query.min_probability

        where = " AND ".join(filters)
        rows = await self._session.execute(
            text(f"""
                SELECT * FROM digital_twin_voxels
                WHERE {where}
                ORDER BY depth_m ASC
                LIMIT :limit
            """),
            params,
        )
        voxels = [_row_to_voxel(r) for r in rows.mappings().fetchall()]
        return TwinQueryResult(
            scan_id=query.scan_id,
            twin_version=version,
            voxels=voxels,
            total_matching=len(voxels),
            query=query,
        )

    async def get_twin_history(self, scan_id: str) -> list[TwinVersion]:
        rows = await self._session.execute(
            text("""
                SELECT * FROM digital_twin_versions
                WHERE scan_id = :scan_id
                ORDER BY version ASC
            """),
            {"scan_id": scan_id},
        )
        return [
            TwinVersion(
                scan_id=scan_id,
                version=r["version"],
                voxel_count=r["voxel_count"],
                created_at=r["created_at"],
                trigger=r["trigger_type"],
                parent_version=r.get("parent_version"),
            )
            for r in rows.mappings().fetchall()
        ]


def _row_to_voxel(row) -> DigitalTwinVoxel:
    d = dict(row)
    from datetime import datetime, timezone
    return DigitalTwinVoxel(
        voxel_id=d["voxel_id"],
        scan_id=str(d["scan_id"]),
        twin_version=d["twin_version"],
        lat_center=float(d["lat_center"]),
        lon_center=float(d["lon_center"]),
        depth_m=float(d["depth_m"]),
        depth_range_m=(float(d["depth_min_m"]), float(d["depth_max_m"])),
        commodity_probs=d["commodity_probs"] or {},
        expected_density=float(d["expected_density"]) if d.get("expected_density") is not None else None,
        density_uncertainty=float(d["density_uncertainty"]) if d.get("density_uncertainty") is not None else None,
        temporal_score=float(d["temporal_score"]) if d.get("temporal_score") is not None else None,
        physics_residual=float(d["physics_residual"]) if d.get("physics_residual") is not None else None,
        uncertainty=float(d["uncertainty"]) if d.get("uncertainty") is not None else None,
        created_at=d["created_at"],
    )