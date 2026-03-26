"""
Aurora OSI vNext — Province Prior Dataset Store
Phase G (new module)

Read-only access to tectono-stratigraphic province prior probabilities.
Provides:
  - Province lookup by spatial coordinates (PostGIS intersection)
  - Prior probability Π^(c)(r_i) per commodity per province
  - Impossible province veto detection (prior_probability=0.0 + flag)
  - Bayesian posterior retrieval by ground-truth dataset ID
  - Cell-to-province cache read/write for pipeline performance

No scientific logic. No scoring. No imports from core/ or services/.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.base import BaseStore


class ProvincePriorStore(BaseStore):
    """Read-mostly access to the tectono-stratigraphic province prior database."""

    async def lookup_province_for_cell(
        self,
        lat: float,
        lon: float,
        cell_resolution: float = 0.01,
        cache_version: str = "0.1.0",
    ) -> Optional[dict]:
        """
        Determine which tectono-stratigraphic province contains this cell.
        First checks the province_cell_cache for a pre-computed result.
        Falls back to PostGIS spatial intersection if not cached.
        """
        # Check cache first
        cached = await self._session.execute(
            text("""
                SELECT province_id, province_code, is_offshore
                FROM province_cell_cache
                WHERE lat_center = :lat AND lon_center = :lon
                  AND cell_resolution = :res AND cache_version = :version
            """),
            {"lat": lat, "lon": lon, "res": cell_resolution, "version": cache_version},
        )
        cached_row = cached.mappings().fetchone()
        if cached_row:
            return dict(cached_row)

        # Fall back to spatial intersection
        row = await self._session.execute(
            text("""
                SELECT province_id, province_code, geological_age,
                       tectonic_setting, is_offshore
                FROM tectono_stratigraphic_provinces
                WHERE ST_Contains(
                    province_geom,
                    ST_SetSRID(ST_Point(:lon, :lat), 4326)
                )
                LIMIT 1
            """),
            {"lat": lat, "lon": lon},
        )
        record = row.mappings().fetchone()
        return dict(record) if record else None

    async def get_prior_probability(
        self,
        province_code: str,
        commodity_name: str,
        prior_type: str = "baseline",
        library_version: str = "0.1.0",
    ) -> Optional[dict]:
        """
        Retrieve Π^(c)(r_i) for a commodity in a province.
        Returns None if no prior defined (caller handles as unknown province).
        """
        row = await self._session.execute(
            text("""
                SELECT ppp.*
                FROM province_prior_probabilities ppp
                JOIN tectono_stratigraphic_provinces tsp ON tsp.province_id = ppp.province_id
                JOIN commodity_definitions cd ON cd.commodity_id = ppp.commodity_id
                WHERE tsp.province_code = :province_code
                  AND cd.name = :commodity_name
                  AND ppp.prior_type = :prior_type
                  AND ppp.library_version = :version
            """),
            {
                "province_code":   province_code,
                "commodity_name":  commodity_name,
                "prior_type":      prior_type,
                "version":         library_version,
            },
        )
        record = row.mappings().fetchone()
        return dict(record) if record else None

    async def is_impossible_province(
        self,
        province_code: str,
        commodity_name: str,
        library_version: str = "0.1.0",
    ) -> bool:
        """
        Check if a province-commodity combination is geologically impossible (§8.3).
        Returns True if province veto should fire (prior_probability=0.0).
        """
        row = await self._session.execute(
            text("""
                SELECT is_impossible_province
                FROM province_prior_probabilities ppp
                JOIN tectono_stratigraphic_provinces tsp ON tsp.province_id = ppp.province_id
                JOIN commodity_definitions cd ON cd.commodity_id = ppp.commodity_id
                WHERE tsp.province_code = :province_code
                  AND cd.name = :commodity
                  AND ppp.library_version = :version
                  AND ppp.is_impossible_province = TRUE
                LIMIT 1
            """),
            {"province_code": province_code, "commodity": commodity_name, "version": library_version},
        )
        return row.fetchone() is not None

    async def cache_province_lookup(
        self,
        lat: float,
        lon: float,
        cell_resolution: float,
        province_id: Optional[str],
        province_code: Optional[str],
        is_offshore: bool,
        cache_version: str = "0.1.0",
    ) -> None:
        """Cache a spatial province lookup result to avoid repeated PostGIS queries."""
        await self._session.execute(
            text("""
                INSERT INTO province_cell_cache (
                    lat_center, lon_center, cell_resolution,
                    province_id, province_code, is_offshore, cache_version
                ) VALUES (
                    :lat, :lon, :res, :province_id, :province_code, :is_offshore, :version
                )
                ON CONFLICT (lat_center, lon_center, cell_resolution, cache_version)
                DO NOTHING
            """),
            {
                "lat": lat, "lon": lon, "res": cell_resolution,
                "province_id": province_id, "province_code": province_code,
                "is_offshore": is_offshore, "version": cache_version,
            }
        )
        await self._session.commit()