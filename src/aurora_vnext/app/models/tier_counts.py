"""
Aurora OSI vNext — Tier Count Model
Phase F §F.3

TierCounts: count of scan cells assigned to each tier.

CONSTITUTIONAL RULE: tier_1 + tier_2 + tier_3 + below == total_cells.
This invariant is enforced at model validation time.

No scientific logic. No imports from core/, services/, storage/, api/.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class TierCounts(BaseModel):
    """
    Count of scan cells in each tier after threshold application (§13.4).

    Invariant: tier_1 + tier_2 + tier_3 + below == total_cells.
    This is checked at instantiation time — any mismatch is a pipeline error.
    """

    tier_1: int = Field(ge=0, description="Cells assigned TIER_1 (highest confidence)")
    tier_2: int = Field(ge=0, description="Cells assigned TIER_2")
    tier_3: int = Field(ge=0, description="Cells assigned TIER_3")
    below: int = Field(ge=0, description="Cells below TIER_3 threshold")
    total_cells: int = Field(ge=0, description="Total cells in scan; must equal sum of tiers")

    @model_validator(mode="after")
    def validate_counts_sum(self) -> "TierCounts":
        computed_sum = self.tier_1 + self.tier_2 + self.tier_3 + self.below
        if computed_sum != self.total_cells:
            raise ValueError(
                f"TierCounts invariant violated: tier_1({self.tier_1}) + tier_2({self.tier_2}) "
                f"+ tier_3({self.tier_3}) + below({self.below}) = {computed_sum} "
                f"!= total_cells({self.total_cells}). "
                f"Pipeline must produce tier counts that sum exactly to total cells."
            )
        return self

    @property
    def tier_1_fraction(self) -> float:
        if self.total_cells == 0:
            return 0.0
        return self.tier_1 / self.total_cells

    @property
    def tier_2_fraction(self) -> float:
        if self.total_cells == 0:
            return 0.0
        return self.tier_2 / self.total_cells

    model_config = {"frozen": True}