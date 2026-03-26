"""
Aurora OSI vNext — Raw Observable and Harmonised Tensor Store
Phase G §G (new module, Phase D §H pipeline inputs)

Manages:
  1. raw_observables: un-normalised sensor stacks per cell (written at SENSOR_ACQUISITION)
  2. harmonised_tensors: normalised ObservableVector per cell (written at HARMONIZATION)

ARCHITECTURAL RULE:
  This store provides INPUTS to the scientific core.
  It does not compute, interpret, or score any values.
  Offshore cells are rejected at write time if offshore_corrected=False.
"""

from __future__ import annotations

import json
from typing import Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.base import BaseStore, StorageOffshoreGateError


class RawObservableStore(BaseStore):
    """Stores un-normalised sensor stacks per scan cell."""

    async def write_raw_observables(
        self,
        scan_id: str,
        cell_id: str,
        lat_center: float,
        lon_center: float,
        environment: str,
        raw_values: dict,
        sensor_metadata: dict | None = None,
        offshore_raw_values: dict | None = None,
        acquisition_date=None,
    ) -> str:
        """Write raw sensor values for one cell. Returns raw_obs_id."""
        raw_obs_id = str(uuid4())
        await self._session.execute(
            text("""
                INSERT INTO raw_observables (
                    raw_obs_id, scan_id, cell_id, lat_center, lon_center,
                    environment, acquisition_date, raw_values,
                    sensor_metadata, offshore_raw_values
                ) VALUES (
                    :id, :scan_id, :cell_id, :lat, :lon,
                    :env, :acq_date, :raw_values::jsonb,
                    :sensor_meta::jsonb, :offshore_raw::jsonb
                )
            """),
            {
                "id":            raw_obs_id,
                "scan_id":       scan_id,
                "cell_id":       cell_id,
                "lat":           lat_center,
                "lon":           lon_center,
                "env":           environment,
                "acq_date":      acquisition_date,
                "raw_values":    json.dumps(raw_values),
                "sensor_meta":   json.dumps(sensor_metadata or {}),
                "offshore_raw":  json.dumps(offshore_raw_values) if offshore_raw_values else None,
            }
        )
        await self._session.commit()
        return raw_obs_id

    async def get_raw_observables_for_scan(self, scan_id: str) -> list[dict]:
        rows = await self._session.execute(
            text("SELECT * FROM raw_observables WHERE scan_id = :scan_id ORDER BY cell_id"),
            {"scan_id": scan_id},
        )
        return [dict(r) for r in rows.mappings().fetchall()]


class HarmonisedTensorStore(BaseStore):
    """Stores normalised ObservableVector per scan cell after harmonisation."""

    async def write_harmonised_tensor(
        self,
        scan_id: str,
        cell_id: str,
        environment: str,
        observable_vector: dict,
        normalisation_params: dict,
        present_count: int,
        missing_count: int,
        offshore_corrected: bool = False,
        offshore_correction_detail: dict | None = None,
        gravity_composite: dict | None = None,
        harmonisation_version: str = "0.1.0",
    ) -> str:
        """
        Write harmonised observable tensor for one cell.

        OFFSHORE GATE: Offshore cells must have offshore_corrected=True.
        Raises StorageOffshoreGateError if violated.
        """
        if environment == "OFFSHORE" and not offshore_corrected:
            raise StorageOffshoreGateError(
                f"Cannot write harmonised tensor for offshore cell {cell_id} in scan {scan_id} "
                f"without offshore correction applied. "
                f"services/offshore.py must process the cell before harmonisation."
            )

        coverage = present_count / 42 if 42 > 0 else 0.0
        tensor_id = str(uuid4())
        await self._session.execute(
            text("""
                INSERT INTO harmonised_tensors (
                    tensor_id, scan_id, cell_id, environment,
                    observable_vector, normalisation_params,
                    present_count, missing_count, coverage_fraction,
                    offshore_corrected, offshore_correction_detail,
                    gravity_composite, harmonisation_version
                ) VALUES (
                    :tid, :scan_id, :cell_id, :env,
                    :obs_vec::jsonb, :norm_params::jsonb,
                    :present, :missing, :coverage,
                    :offshore_corrected, :offshore_detail::jsonb,
                    :grav_composite::jsonb, :harm_version
                )
            """),
            {
                "tid":                str(tensor_id),
                "scan_id":            scan_id,
                "cell_id":            cell_id,
                "env":                environment,
                "obs_vec":            json.dumps(observable_vector),
                "norm_params":        json.dumps(normalisation_params),
                "present":            present_count,
                "missing":            missing_count,
                "coverage":           coverage,
                "offshore_corrected": offshore_corrected,
                "offshore_detail":    json.dumps(offshore_correction_detail) if offshore_correction_detail else None,
                "grav_composite":     json.dumps(gravity_composite) if gravity_composite else None,
                "harm_version":       harmonisation_version,
            }
        )
        await self._session.commit()
        return str(tensor_id)

    async def get_harmonised_tensors_for_scan(self, scan_id: str) -> list[dict]:
        rows = await self._session.execute(
            text("SELECT * FROM harmonised_tensors WHERE scan_id = :scan_id ORDER BY cell_id"),
            {"scan_id": scan_id},
        )
        return [dict(r) for r in rows.mappings().fetchall()]

    async def get_tensor_for_cell(self, scan_id: str, cell_id: str) -> Optional[dict]:
        row = await self._session.execute(
            text("SELECT * FROM harmonised_tensors WHERE scan_id = :scan_id AND cell_id = :cell_id"),
            {"scan_id": scan_id, "cell_id": cell_id},
        )
        record = row.mappings().fetchone()
        return dict(record) if record else None