"""Internal, source-grounded SEC financial history contracts.

These models are intentionally not part of the public research or AI schemas.
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class HistoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HistoricalFinancialObservation(HistoryModel):
    observation_id: str
    issuer: str
    ticker: str
    cik: str
    metric: Literal["revenue", "diluted_eps"]
    fiscal_year: int = Field(ge=1900, le=2200)
    fiscal_quarter: Literal["Q1", "Q2", "Q3", "Q4"]
    period_start: date
    period_end: date
    duration_days: int = Field(ge=1)
    frequency: Literal["quarterly"] = "quarterly"
    duration_semantics: Literal["standalone_quarter"] = "standalone_quarter"
    taxonomy: Literal["us-gaap"] = "us-gaap"
    original_concept: str
    original_value: Decimal
    original_unit: str
    normalized_value: Decimal
    currency: str
    share_basis: Literal["not_applicable", "diluted"]
    accounting_basis: Literal["gaap"] = "gaap"
    reporting_scope: Literal["sec_company_fact_entity"] = "sec_company_fact_entity"
    accession: str
    form: Literal["10-Q", "10-Q/A", "10-K", "10-K/A"]
    filing_date: date
    acceptance_time: AwareDatetime | None = None
    source_url: str
    retrieved_at: AwareDatetime
    version_status: Literal["current", "superseded", "duplicate", "conflict"]
    superseded_by: str | None = None
    comparison_eligible: bool
    comparison_exclusion_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def coherent_observation(self):
        if self.period_start > self.period_end:
            raise ValueError("Period start follows period end")
        if self.duration_days != (self.period_end - self.period_start).days + 1:
            raise ValueError("Duration does not match period dates")
        if self.metric == "revenue" and (self.original_unit != "USD" or
                self.currency != "USD" or self.share_basis != "not_applicable"):
            raise ValueError("Revenue requires consolidated USD monetary units")
        if self.metric == "diluted_eps" and (self.original_unit != "USD/shares" or
                self.currency != "USD" or self.share_basis != "diluted"):
            raise ValueError("Diluted EPS requires USD/share diluted units")
        if self.comparison_eligible != (self.version_status == "current"):
            raise ValueError("Only current unconflicted observations are comparison eligible")
        return self

    @property
    def period_id(self):
        return f"{self.ticker}:FY{self.fiscal_year}:{self.fiscal_quarter}"


class AnnualRevenueObservation(HistoryModel):
    """Independently certified full-fiscal-year SEC revenue fact."""
    observation_id: str
    issuer: str
    ticker: str
    cik: str
    fiscal_year: int = Field(ge=1900, le=2200)
    period_start: date
    period_end: date
    duration_days: int = Field(ge=300, le=380)
    exact_revenue: Decimal
    yoy_growth_pct: Decimal | None = None
    currency: Literal["USD"] = "USD"
    taxonomy: Literal["us-gaap"] = "us-gaap"
    original_concept: str
    original_unit: Literal["USD"] = "USD"
    accounting_basis: Literal["gaap"] = "gaap"
    reporting_scope: Literal["sec_company_fact_entity"] = "sec_company_fact_entity"
    accession: str
    form: Literal["10-K", "10-K/A"]
    filing_date: date
    acceptance_time: AwareDatetime | None = None
    source_url: str
    retrieved_at: AwareDatetime
    classification: Literal["reported"] = "reported"
    provenance_label: Literal["SEC 10-K annual revenue", "SEC 10-K/A annual revenue (amended)"]

    @model_validator(mode="after")
    def coherent_annual_observation(self):
        if self.period_start > self.period_end:
            raise ValueError("Period start follows period end")
        if self.duration_days != (self.period_end - self.period_start).days + 1:
            raise ValueError("Duration does not match period dates")
        if not self.exact_revenue.is_finite():
            raise ValueError("Annual revenue must be finite")
        return self


class RejectedFinancialFact(HistoryModel):
    metric: Literal["revenue", "diluted_eps"] | None = None
    concept: str
    accession: str | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    reason: str


class MissingFinancialPeriod(HistoryModel):
    metric: Literal["revenue", "diluted_eps"]
    fiscal_year: int
    fiscal_quarter: Literal["Q1", "Q2", "Q3", "Q4"]
    reason: Literal["no_accepted_observation"] = "no_accepted_observation"


class AnnualRevenueDiagnostics(HistoryModel):
    source_limit_state: Literal["complete", "limit_exceeded"] = "complete"
    source_fact_limit: int = Field(default=128, ge=1)
    discovered_source_fact_count: int = Field(default=0, ge=0)
    discovered_fiscal_year_count: int = Field(default=0, ge=0)
    validated_candidate_count: int = Field(default=0, ge=0)
    rejected_candidate_count: int = Field(default=0, ge=0)
    conflicted_fiscal_year_count: int = Field(default=0, ge=0)
    certified_fiscal_year_count: int = Field(default=0, ge=0)
    retained_fiscal_year_count: int = Field(default=0, ge=0, le=5)
    excluded_fiscal_years: tuple[int, ...] = Field(default=(), max_length=64)
    source_limit_excluded_fiscal_years: tuple[int, ...] = Field(default=(), max_length=64)
    year_outcomes: tuple["AnnualRevenueYearOutcome", ...] = Field(default=(), max_length=16)


AnnualRevenueDiagnosticReason = Literal[
    "no_supported_candidate",
    "invalid_period_or_filing_date",
    "annual_filing_context_invalid",
    "annual_period_duration_invalid",
    "invalid_value_or_accession",
    "ambiguous_concept_mapping",
    "ambiguous_annual_context",
    "unresolved_annual_version_conflict",
    "annual_source_limit_exceeded",
    "annual_retention_limit",
]


class AnnualRevenueYearOutcome(HistoryModel):
    fiscal_year: int = Field(ge=1900, le=2200)
    discovered_candidate_count: int = Field(ge=0)
    validated_candidate_count: int = Field(ge=0)
    state: Literal["certified", "no_supported_candidate", "rejected", "conflict",
        "source_limit_excluded", "retention_excluded"]
    reasons: tuple[AnnualRevenueDiagnosticReason, ...] = Field(default=(), max_length=8)


AnnualRevenueDiagnostics.model_rebuild()


class HistoricalFinancialDiagnostics(HistoryModel):
    source_status: str
    requests: int = Field(ge=0)
    cache_reads: int = Field(ge=0)
    cache_loads: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    source_fact_count: int = Field(ge=0)
    processed_fact_count: int = Field(ge=0)
    accepted_observation_count: int = Field(ge=0)
    rejected_fact_count: int = Field(ge=0)
    request_budget: int = Field(ge=1)
    cache_ttl_seconds: int = Field(ge=1)
    failure_cache_ttl_seconds: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0)
    attempts: int = Field(ge=1)
    max_source_facts: int = Field(ge=1)
    max_quarterly_periods: int = Field(ge=1)
    max_annual_periods_inspected: int = Field(ge=0)
    annual_revenue: AnnualRevenueDiagnostics = Field(default_factory=AnnualRevenueDiagnostics)
    concurrent_behavior: str = "single_flight_per_ticker"


class HistoricalFinancialSnapshot(HistoryModel):
    schema_version: Literal["1"] = "1"
    ticker: str
    issuer: str
    cik: str
    retrieved_at: AwareDatetime
    status: Literal["available", "partial", "unavailable", "conflict"]
    observations: tuple[HistoricalFinancialObservation, ...] = ()
    annual_revenue_observations: tuple[AnnualRevenueObservation, ...] = Field(default=(), max_length=5)
    rejected: tuple[RejectedFinancialFact, ...] = Field(default=(), max_length=256)
    missing_periods: tuple[MissingFinancialPeriod, ...] = Field(default=(), max_length=32)
    diagnostics: HistoricalFinancialDiagnostics
