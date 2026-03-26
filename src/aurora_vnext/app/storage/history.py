"""
Aurora OSI vNext — History Index Store
Phase G §G.4

History index is a DERIVED VIEW from canonical_scans.
It is NEVER an independent truth source.

Rules:
  - All field values are sourced directly from canonical_scans
  - No field in this index may differ from its canonical_scans equivalent
  - refresh_history_index() is called POST-FREEZE only — never during scoring
  - List queries route here (lighter than full canonical_scans table scan)
  - Detail queries route to CanonicalScanStore.get_canonical_scan()
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canonical_scan import CanonicalScanSummary
from app.models.enums import ScanEnvironment, ScanStatus, ScanTier
from app.storage.base import BaseStore, PaginatedResult, PaginationParams
from app.storage.scans import _row_to_summary


class HistoryIndexStore(BaseStore):

    async def refresh_history_index(self, scan_id: Optional[str] = None) -> None:
        """
        Refresh the materialised history_index view.
        Called post-freeze by the pipeline — NEVER during scoring or recomputation.
        scan_id param is ignored (CONCURRENTLY refreshes the full view);
        kept in signature for future incremental refresh support.
        """
        await self._session.execute(text("SELECT refresh_history_index()"))
        await self._session.commit()

    async def get_history(
        self,
        commodity: Optional[str] = None,
        system_status: Optional[str] = None,
        scan_tier: Optional[str] = None,
        pagination: PaginationParams | None = None,
    ) -> PaginatedResult:
        """
        Paginated history list. Reads from history_index materialised view.
        All returned fields are read-only projections of canonical records.
        """
        p = pagination or PaginationParams.default()
        filters = ["1=1"]
        params: dict = {"limit": p.page_size, "offset": p.offset}

        if commodity:
            filters.append("commodity = :commodity")
            params["commodity"] = commodity
        if system_status:
            filters.append("system_status = :system_status")
            params["system_status"] = system_status
        if scan_tier:
            filters.append("scan_tier = :scan_tier")
            params["scan_tier"] = scan_tier

        where = " AND ".join(filters)
        rows = await self._session.execute(
            text(f"""
                SELECT * FROM history_index
                WHERE {where}
                ORDER BY completed_at DESC NULLS LAST
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
        count_row = await self._session.execute(
            text(f"SELECT COUNT(*) FROM history_index WHERE {where}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        )
        total = count_row.scalar() or 0
        items = [_row_to_summary(r) for r in rows.mappings().fetchall()]
        return PaginatedResult(items=items, total=total, params=p)