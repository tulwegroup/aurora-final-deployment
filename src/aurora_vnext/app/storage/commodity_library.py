"""
Aurora OSI vNext — Commodity Spectral Library Store
Phase G (new module)

Read-only access to the commodity spectral registry.
This store is READ-ONLY from the pipeline's perspective.
Commodity definitions are populated by the Phase A/F build process.

Supports queries for:
  - Commodity definitions by name or family
  - Observable weighting vectors per commodity
  - Spectral response curves per commodity
  - Depth kernel parameters per commodity
  - Environmental regime modifiers per commodity + environment

NO scoring logic. NO spectral coefficients returned here — only
structural definitions needed for pipeline configuration.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.base import BaseStore, StorageNotFoundError


class CommodityLibraryStore(BaseStore):
    """Read-only access to the 40-commodity spectral registry."""

    async def get_commodity(self, name: str, library_version: str = "0.1.0") -> dict:
        """Retrieve full commodity definition by name."""
        row = await self._session.execute(
            text("""
                SELECT cd.*, f.family_name, f.dag_template, f.hard_veto_conditions
                FROM commodity_definitions cd
                JOIN mineral_system_families f ON f.family_id = cd.family_id
                WHERE cd.name = :name AND cd.is_active = TRUE
            """),
            {"name": name},
        )
        record = row.mappings().fetchone()
        if not record:
            raise StorageNotFoundError(f"Commodity not found: {name}")
        return dict(record)

    async def get_observable_weights(self, commodity_name: str, library_version: str = "0.1.0") -> dict:
        """Retrieve evidence weight vector w^(c)_k for a commodity."""
        row = await self._session.execute(
            text("""
                SELECT owv.*
                FROM observable_weighting_vectors owv
                JOIN commodity_definitions cd ON cd.commodity_id = owv.commodity_id
                WHERE cd.name = :name AND owv.library_version = :version
            """),
            {"name": commodity_name, "version": library_version},
        )
        record = row.mappings().fetchone()
        if not record:
            return {}  # Weights not yet populated (expected at Phase G scaffold)
        return dict(record)

    async def get_spectral_curve(self, commodity_name: str, library_version: str = "0.1.0") -> dict:
        """Retrieve spectral response curve for a commodity."""
        row = await self._session.execute(
            text("""
                SELECT src.*
                FROM spectral_response_curves src
                JOIN commodity_definitions cd ON cd.commodity_id = src.commodity_id
                WHERE cd.name = :name AND src.library_version = :version
                LIMIT 1
            """),
            {"name": commodity_name, "version": library_version},
        )
        record = row.mappings().fetchone()
        return dict(record) if record else {}

    async def get_depth_kernel(self, commodity_name: str, library_version: str = "0.1.0") -> dict:
        """Retrieve depth kernel D^(c) parameters for a commodity."""
        row = await self._session.execute(
            text("""
                SELECT dkp.*
                FROM depth_kernel_params dkp
                JOIN commodity_definitions cd ON cd.commodity_id = dkp.commodity_id
                WHERE cd.name = :name AND dkp.library_version = :version
            """),
            {"name": commodity_name, "version": library_version},
        )
        record = row.mappings().fetchone()
        return dict(record) if record else {}

    async def get_environmental_modifier(
        self,
        commodity_name: str,
        environment: str,
        library_version: str = "0.1.0",
    ) -> dict:
        """Retrieve environment-specific modifier for a commodity."""
        row = await self._session.execute(
            text("""
                SELECT erm.*
                FROM environmental_regime_modifiers erm
                JOIN commodity_definitions cd ON cd.commodity_id = erm.commodity_id
                WHERE cd.name = :name
                  AND erm.environment = :env
                  AND erm.library_version = :version
            """),
            {"name": commodity_name, "env": environment, "version": library_version},
        )
        record = row.mappings().fetchone()
        return dict(record) if record else {}

    async def list_active_commodities(self) -> list[dict]:
        """List all active commodity definitions."""
        rows = await self._session.execute(
            text("""
                SELECT cd.name, cd.symbol, cd.family_id, f.family_name,
                       cd.offshore_applicable, cd.depth_kernel_defined,
                       cd.dominant_modalities
                FROM commodity_definitions cd
                JOIN mineral_system_families f ON f.family_id = cd.family_id
                WHERE cd.is_active = TRUE
                ORDER BY cd.family_id, cd.name
            """)
        )
        return [dict(r) for r in rows.mappings().fetchall()]

    async def list_families(self) -> list[dict]:
        """List all 9 mineral-system families."""
        rows = await self._session.execute(
            text("SELECT * FROM mineral_system_families ORDER BY family_id")
        )
        return [dict(r) for r in rows.mappings().fetchall()]