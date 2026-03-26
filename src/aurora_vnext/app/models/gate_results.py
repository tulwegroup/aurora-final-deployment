"""
Aurora OSI vNext — Gate Results and System Status Models
Phase F §F.4

GateResult: single gate evaluation output.
GateResults: complete gate evaluation set for one scan.
ConfirmationReason: structured explanation of system_status derivation.
SystemStatus: complete status record for one scan.

CONSTITUTIONAL RULE: system_status is derived EXCLUSIVELY by core/gates.py.
These model types carry the RESULT of that derivation.
No API, service, or frontend code may derive system_status independently.

No scientific logic. No imports from core/, services/, storage/, api/.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.models.enums import SystemStatusEnum


class GateResult(BaseModel):
    """Result of evaluating one commodity-family gate G_k ∈ {0, 1} (§14.1)."""

    gate_id: str = Field(min_length=1, description="Unique gate identifier")
    gate_name: str = Field(min_length=1, description="Human-readable gate name")
    passed: bool = Field(description="True if gate passes (G_k = 1)")
    score_at_gate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Aggregate score value that was evaluated at this gate (optional diagnostic)"
    )
    veto_triggered: bool = Field(
        default=False,
        description="True if this gate result was driven by a hard veto (C=0, P=0, or Ψ veto)"
    )
    veto_reason: Optional[str] = Field(
        default=None,
        description="Which veto triggered, if any (e.g. 'causal_veto_1', 'province_veto')"
    )

    model_config = {"frozen": True}


class GateResults(BaseModel):
    """Complete set of gate evaluations for one scan (§14.2)."""

    gates: list[GateResult] = Field(
        min_length=0,
        description="All gate results for this scan"
    )
    gates_passed: int = Field(ge=0, description="Count of gates that passed (Σ G_k)")
    gates_total: int = Field(ge=0, description="Total gate count (m)")

    @model_validator(mode="after")
    def validate_gate_counts(self) -> "GateResults":
        if len(self.gates) != self.gates_total:
            raise ValueError(
                f"GateResults.gates length ({len(self.gates)}) must equal "
                f"gates_total ({self.gates_total})."
            )
        computed_passed = sum(1 for g in self.gates if g.passed)
        if computed_passed != self.gates_passed:
            raise ValueError(
                f"GateResults.gates_passed ({self.gates_passed}) does not match "
                f"count of passing gates in list ({computed_passed})."
            )
        return self

    @property
    def gate_ratio(self) -> float:
        """ρ_g = gates_passed / m (§14.3)"""
        if self.gates_total == 0:
            return 0.0
        return self.gates_passed / self.gates_total

    model_config = {"frozen": True}


class ConfirmationReason(BaseModel):
    """
    Structured explanation of how system_status was derived (§14.3).
    Persisted verbatim in every CanonicalScan — enables full audit trail.
    """

    gate_ratio: float = Field(
        ge=0.0,
        le=1.0,
        description="ρ_g = gates_passed / gates_total"
    )
    dominant_veto: Optional[str] = Field(
        default=None,
        description="Primary veto type if status is REJECTED (e.g. 'causal', 'province', 'physics')"
    )
    supporting_gates: list[str] = Field(
        default_factory=list,
        description="Gate IDs that passed and contributed to confirmation"
    )
    blocking_gates: list[str] = Field(
        default_factory=list,
        description="Gate IDs that failed and contributed to rejection"
    )
    narrative: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Human-readable summary of the status derivation for analyst review"
    )

    model_config = {"frozen": True}


class SystemStatus(BaseModel):
    """
    Complete system status record for one CanonicalScan (§14.3).
    Written at canonical freeze by core/gates.py — never modified after.
    """

    status: SystemStatusEnum
    gate_results: GateResults
    confirmation_reason: ConfirmationReason

    model_config = {"frozen": True}