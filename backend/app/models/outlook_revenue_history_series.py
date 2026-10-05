"""Immutable contracts for offline quarterly revenue-series assembly."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.outlook_financial_history import HistoricalFinancialObservation
from app.models.outlook_revenue_q4_reconciliation import RevenueQ4ReconciliationResult


ASSEMBLY_POLICY_VERSION = "revenue-historical-series-assembly-1"
ASSEMBLY_SCHEMA_VERSION = "1"


class RevenueSeriesModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RevenueHistoricalSeriesObservation(RevenueSeriesModel):
    schema_version: Literal["1"] = ASSEMBLY_SCHEMA_VERSION
    metric: Literal["revenue"] = "revenue"
    issuer_identity: str = Field(min_length=1, max_length=64)
    fiscal_year: int = Field(ge=1900, le=2200)
    fiscal_period: Literal["Q1", "Q2", "Q3", "Q4"]
    period_start: date
    period_end: date
    duration_days: int = Field(ge=1)
    exact_decimal_value: Decimal
    canonical_unit: Literal["USD"] = "USD"
    currency: Literal["USD"] = "USD"
    accounting_basis: Literal["gaap"] = "gaap"
    reporting_scope: Literal["consolidated_entity"] = "consolidated_entity"
    source_kind: Literal["directly_reported", "derived"]
    source_policy: str = Field(min_length=1, max_length=128)
    evidence_identity: str = Field(min_length=1, max_length=128)
    historical_provenance: HistoricalFinancialObservation | None = None
    q4_reconciliation_provenance: RevenueQ4ReconciliationResult | None = None

    @model_validator(mode="after")
    def coherent(self):
        if self.period_start > self.period_end:
            raise ValueError("reversed period")
        if self.duration_days != (self.period_end - self.period_start).days + 1:
            raise ValueError("duration mismatch")
        if not self.exact_decimal_value.is_finite():
            raise ValueError("non-finite value")
        if self.source_kind == "derived" and self.q4_reconciliation_provenance is None:
            raise ValueError("derived series points require reconciliation provenance")
        return self


class RevenueSeriesSourceKindSummary(RevenueSeriesModel):
    directly_reported_count: int = Field(ge=0, le=8)
    derived_count: int = Field(ge=0, le=8)
    derived_periods: tuple[str, ...] = Field(default=(), max_length=8)
    derived_policies: tuple[str, ...] = Field(default=(), max_length=8)


class RevenueHistoricalSeriesResult(RevenueSeriesModel):
    schema_version: Literal["1"] = ASSEMBLY_SCHEMA_VERSION
    assembly_policy: Literal["revenue-historical-series-assembly-1"] = ASSEMBLY_POLICY_VERSION
    state: Literal["available", "insufficient_data", "conflict"]
    metric: Literal["revenue"] = "revenue"
    issuer_identity: str | None = None
    observations: tuple[RevenueHistoricalSeriesObservation, ...] = Field(default=(), max_length=8)
    observation_count: int = Field(ge=0, le=8)
    consecutive_count: int = Field(ge=0, le=8)
    research_eligible: bool
    reasons: tuple[str, ...] = Field(default=(), max_length=32)
    missing_periods: tuple[str, ...] = Field(default=(), max_length=32)
    conflicts: tuple[str, ...] = Field(default=(), max_length=32)
    source_kind_summary: RevenueSeriesSourceKindSummary

    @model_validator(mode="after")
    def coherent(self):
        if self.observation_count != len(self.observations):
            raise ValueError("observation count mismatch")
        if self.research_eligible != (self.state == "available" and self.consecutive_count >= 5):
            raise ValueError("eligibility mismatch")
        return self
