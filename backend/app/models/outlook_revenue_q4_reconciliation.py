"""Immutable contracts for offline direct/derived revenue-Q4 reconciliation."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.outlook_q4 import DirectQ4Observation
from app.models.outlook_revenue_q4 import RevenueQ4DerivedObservation


RECONCILIATION_POLICY_VERSION = "revenue-q4-reconciliation-1"
RECONCILIATION_SCHEMA_VERSION = "1"


class RevenueQ4ReconciliationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DirectRevenueQ4ReconciliationObservation(RevenueQ4ReconciliationModel):
    source_kind: Literal["directly_reported"] = "directly_reported"
    qualification_policy: Literal["direct-q4-1"] = "direct-q4-1"
    qualification_state: Literal["qualified"] = "qualified"
    precision_state: Literal["exact", "rounded"] = "exact"
    metric: Literal["revenue"] = "revenue"
    fiscal_year: int
    fiscal_period: Literal["Q4"] = "Q4"
    period_start: date
    period_end: date
    duration_days: int
    exact_decimal_value: Decimal
    canonical_unit: str
    currency: str
    accounting_basis: str
    reporting_scope: str
    issuer_identity: str
    concept_identity: str
    observation: DirectQ4Observation

    @field_validator("exact_decimal_value", mode="before")
    @classmethod
    def no_float(cls, value):
        if isinstance(value, float):
            raise ValueError("binary floating point is forbidden")
        return value

    @model_validator(mode="after")
    def coherent(self):
        if not self.exact_decimal_value.is_finite():
            raise ValueError("non-finite value")
        if self.duration_days != (self.period_end - self.period_start).days + 1:
            raise ValueError("duration mismatch")
        return self


class RevenueQ4ComparisonDiagnostics(RevenueQ4ReconciliationModel):
    compatibility_checked: bool
    value_compared: bool
    exact_value_agreement: bool | None = None
    mismatch_classes: tuple[str, ...] = ()


class RevenueQ4ReconciliationResult(RevenueQ4ReconciliationModel):
    schema_version: Literal["1"] = RECONCILIATION_SCHEMA_VERSION
    reconciliation_policy: Literal["revenue-q4-reconciliation-1"] = RECONCILIATION_POLICY_VERSION
    state: Literal["available", "unavailable", "conflict"]
    metric: Literal["revenue"] = "revenue"
    fiscal_year: int | None = None
    fiscal_period: Literal["Q4"] = "Q4"
    authoritative_source_kind: Literal["directly_reported", "derived"] | None = None
    authoritative_observation: DirectRevenueQ4ReconciliationObservation | RevenueQ4DerivedObservation | None = None
    direct_observation: DirectRevenueQ4ReconciliationObservation | None = None
    derived_observation: RevenueQ4DerivedObservation | None = None
    corroboration_state: Literal["none", "derived_exact_agreement"] = "none"
    reasons: tuple[str, ...] = ()
    comparison_diagnostics: RevenueQ4ComparisonDiagnostics

    @model_validator(mode="after")
    def coherent(self):
        available = self.state == "available"
        if available != (self.authoritative_observation is not None):
            raise ValueError("only available results have authoritative evidence")
        if available != (self.authoritative_source_kind is not None):
            raise ValueError("available source kind mismatch")
        return self
