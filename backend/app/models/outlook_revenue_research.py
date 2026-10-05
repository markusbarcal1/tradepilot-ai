"""Immutable contracts for offline quarterly revenue research projection."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PROJECTION_POLICY_VERSION = "revenue-research-projection-1"
PROJECTION_SCHEMA_VERSION = "1"


class RevenueResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RevenueGrowthResult(RevenueResearchModel):
    state: Literal["available", "unavailable"]
    exact_growth_pct: Decimal | None = None
    display_growth_pct: Decimal | None = None
    reason: Literal["first_observation", "prior_quarter_unavailable",
        "prior_same_fiscal_quarter_unavailable", "zero_denominator"] | None = None
    current_source_kind: Literal["directly_reported", "derived"]
    comparison_source_kind: Literal["directly_reported", "derived"] | None = None
    uses_derived_evidence: bool

    @model_validator(mode="after")
    def coherent(self):
        available = self.state == "available"
        if available != (self.exact_growth_pct is not None and self.display_growth_pct is not None):
            raise ValueError("growth state/value mismatch")
        if available == (self.reason is not None):
            raise ValueError("growth reason mismatch")
        return self


class RevenueResearchQuarter(RevenueResearchModel):
    fiscal_year: int = Field(ge=1900, le=2200)
    fiscal_quarter: Literal["Q1", "Q2", "Q3", "Q4"]
    display_label: str
    period_start: date
    period_end: date
    duration_days: int
    exact_revenue: Decimal
    revenue_billions: Decimal
    canonical_unit: Literal["USD"] = "USD"
    currency: Literal["USD"] = "USD"
    accounting_basis: Literal["gaap"] = "gaap"
    source_kind: Literal["directly_reported", "derived"]
    source_policy: str
    derived: bool
    evidence_identity: str
    derivation_policy: str | None = None
    reconciliation_policy: str | None = None
    qoq: RevenueGrowthResult
    yoy: RevenueGrowthResult


class RevenueResearchSummary(RevenueResearchModel):
    observation_count: int = Field(ge=0, le=8)
    directly_reported_count: int = Field(ge=0, le=8)
    derived_count: int = Field(ge=0, le=8)
    earliest_quarter: str
    latest_quarter: str
    latest_exact_revenue: Decimal
    latest_qoq_growth_pct: Decimal | None = None
    latest_yoy_growth_pct: Decimal | None = None
    available_qoq_comparisons: int = Field(ge=0, le=7)
    available_yoy_comparisons: int = Field(ge=0, le=4)
    minimum_exact_revenue: Decimal
    maximum_exact_revenue: Decimal
    absolute_change_first_to_latest: Decimal


class RevenueResearchProjectionResult(RevenueResearchModel):
    schema_version: Literal["1"] = PROJECTION_SCHEMA_VERSION
    projection_policy: Literal["revenue-research-projection-1"] = PROJECTION_POLICY_VERSION
    state: Literal["available", "unavailable", "conflict"]
    metric: Literal["revenue"] = "revenue"
    issuer_identity: str | None = None
    points: tuple[RevenueResearchQuarter, ...] = Field(default=(), max_length=8)
    summary: RevenueResearchSummary | None = None
    reasons: tuple[str, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def coherent(self):
        available = self.state == "available"
        if available != (self.summary is not None and len(self.points) >= 5):
            raise ValueError("projection state mismatch")
        return self
