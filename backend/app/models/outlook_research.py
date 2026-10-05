"""Bounded user-facing research presentation contracts."""
from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.models.outlook_ai import AIOutlookResponse
from app.models.outlook_taxonomy import CategoryKey


class ResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResearchSource(ResearchModel):
    id: str
    name: str
    title: str | None = None
    url: str
    source_type: str
    date: Date | None = None


class ResearchMetric(ResearchModel):
    id: str
    label: str
    value: float
    unit: str
    previous_value: float | None = None
    change: float | None = None
    change_unit: str | None = None
    observation_date: Date | None = None
    comparison_date: Date | None = None
    period: str | None = None
    comparison_label: str | None = None
    comparison_type: Literal["year_over_year"] | None = None
    comparison_basis: Literal["exact_values", "reported_change_only"] | None = None
    comparison_period: str | None = None
    source_ids: tuple[str, ...] = ()
    qualifier: str | None = None


class ResearchSeriesPoint(ResearchModel):
    date: Date
    value: float


class ResearchSeries(ResearchModel):
    id: str
    label: str
    unit: str
    points: tuple[ResearchSeriesPoint, ...] = ()
    source_ids: tuple[str, ...] = ()
    qualifier: str | None = None


class ResearchEvent(ResearchModel):
    id: str
    category: CategoryKey
    event_type: str
    title: str
    summary: str | None = None
    date: Date | None = None
    scheduled_at: AwareDatetime | None = None
    timezone: str | None = None
    market_session: str | None = None
    schedule_certainty: str | None = None
    reference_period: str | None = None
    direction: Literal["positive", "negative", "neutral", "informational"] = "informational"
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    source_ids: tuple[str, ...] = ()
    qualifier: str | None = None


class ResearchCatalyst(ResearchEvent):
    reason: str


class EarningsResearch(ResearchModel):
    schema_version: Literal["1"] = "1"
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    period_end: Date | None = None
    release_date: Date | None = None
    metrics: tuple[ResearchMetric, ...] = ()
    guidance: tuple[ResearchEvent, ...] = ()
    next_event: ResearchEvent | None = None
    qualifier: str = ("Verified recent issuer results from the accepted research snapshot. "
                      "Two observations are a comparison, not a historical trend.")


class ResearchBenchmark(ResearchModel):
    symbol: str
    name: str | None = None
    benchmark_type: str | None = None


class ResearchComparison(ResearchModel):
    window_sessions: int
    company_return: float
    benchmark_return: float
    relative_difference: float
    unit: Literal["decimal_return"] = "decimal_return"


class ResearchBreadth(ResearchModel):
    state: str
    configured_count: int
    valid_count: int
    positive_return_participation: float
    above_sma50_participation: float
    median_return_21: float | None = None
    constituent_sample: tuple[str, ...] = ()
    qualifier: str = "Benchmark constituents used in breadth; not verified direct competitors."


class IndustryHistoryPoint(ResearchModel):
    date: Date
    company_cumulative_return: float
    benchmark_cumulative_return: float
    relative_performance: float


class IndustryHistoryWindow(ResearchModel):
    label: Literal["1M", "3M", "6M"]
    session_count: int = Field(ge=2, le=128)
    points: tuple[IndustryHistoryPoint, ...] = Field(min_length=2, max_length=128)


class IndustryHistoryCoverage(ResearchModel):
    common_session_count: int = Field(ge=2, le=128)
    company_missing_session_count: int = Field(ge=0)
    benchmark_missing_session_count: int = Field(ge=0)
    has_gaps: bool
    company_last_session: Date
    benchmark_last_session: Date


class IndustryHistory(ResearchModel):
    schema_version: Literal["1"] = "1"
    snapshot_id: str = Field(min_length=24, max_length=24, pattern=r"^[0-9a-f]+$")
    ticker: str
    as_of: AwareDatetime
    series_start: Date
    series_end: Date
    price_adjustment_basis: Literal["yahoo_auto_adjust_true"]
    currency: Literal["USD"]
    benchmark: ResearchBenchmark
    classification_quality: Literal["exact_industry", "sector_fallback"]
    fallback_reason: str | None = None
    taxonomy_version: str
    mapping_version: str
    available_windows: tuple[Literal["1M", "3M", "6M"], ...]
    windows: tuple[IndustryHistoryWindow, ...] = Field(max_length=3)
    coverage: IndustryHistoryCoverage
    cumulative_return_unit: Literal["percentage_points"] = "percentage_points"
    relative_performance_unit: Literal["percentage_points"] = "percentage_points"
    source_ids: tuple[str, ...] = ()
    qualifier: str


class IndustryResearch(ResearchModel):
    raw_sector: str | None = None
    raw_industry: str | None = None
    normalized_industry: str | None = None
    industry_name: str | None = None
    classification_quality: str | None = None
    fallback_reason: str | None = None
    taxonomy_version: str | None = None
    benchmark: ResearchBenchmark | None = None
    relative_state: str | None = None
    comparisons: tuple[ResearchComparison, ...] = ()
    breadth: ResearchBreadth | None = None
    history: IndustryHistory | None = None
    source_ids: tuple[str, ...] = ()


class EconomicResearch(ResearchModel):
    trends: tuple[ResearchMetric, ...] = ()
    releases: tuple[ResearchEvent, ...] = ()
    series: tuple[ResearchSeries, ...] = ()
    qualifier: str = "FRED comparisons use the latest available vintage; no economist consensus or surprise is implied."


class MarketBenchmark(ResearchModel):
    symbol: str
    close: float
    sma50: float
    prior_sma50: float
    trend: Literal["above_rising", "below_falling", "mixed"]
    observation_date: Date
    source_ids: tuple[str, ...] = ()


class MarketVolatility(ResearchModel):
    symbol: str
    close: float
    regime: Literal["low", "normal", "elevated"]
    observation_date: Date
    source_ids: tuple[str, ...] = ()


class MarketHistoryPoint(ResearchModel):
    date: Date
    spy_cumulative_return: float
    qqq_cumulative_return: float


class MarketHistoryWindow(ResearchModel):
    label: Literal["1M", "3M", "6M"]
    session_count: int = Field(ge=2, le=128)
    points: tuple[MarketHistoryPoint, ...] = Field(min_length=2, max_length=128)


class VixHistoryPoint(ResearchModel):
    date: Date
    level: float = Field(gt=0)


class MarketHistory(ResearchModel):
    schema_version: Literal["1"]
    snapshot_id: str = Field(min_length=24, max_length=24)
    as_of: AwareDatetime
    price_adjustment_basis: Literal["yahoo_auto_adjust_true"]
    windows: tuple[MarketHistoryWindow, ...] = Field(max_length=3)
    equity_coverage: dict[str, int | bool | str] | None = None
    vix_points: tuple[VixHistoryPoint, ...] = Field(default=(), max_length=128)
    vix_threshold_low: float
    vix_threshold_high: float
    qualifier: str


class MarketResearch(ResearchModel):
    benchmarks: tuple[MarketBenchmark, ...] = ()
    volatility: MarketVolatility | None = None
    history: MarketHistory | None = None


class EventResearch(ResearchModel):
    events: tuple[ResearchEvent, ...] = ()
    empty_message: str


class RevenueHistoryGrowth(ResearchModel):
    state: Literal["available", "unavailable"]
    exact_growth_pct: Decimal | None = None
    display_growth_pct: Decimal | None = None
    reason: str | None = None
    current_source_kind: Literal["directly_reported", "derived"]
    comparison_source_kind: Literal["directly_reported", "derived"] | None = None
    uses_derived_evidence: bool


class RevenueHistoryPoint(ResearchModel):
    fiscal_year: int
    fiscal_quarter: Literal["Q1", "Q2", "Q3", "Q4"]
    display_label: str
    period_start: Date
    period_end: Date
    duration_days: int
    exact_revenue: Decimal
    revenue_billions: Decimal
    currency: Literal["USD"]
    source_kind: Literal["directly_reported", "derived"]
    derived: bool
    source_policy: str
    evidence_identity: str
    derivation_policy: str | None = None
    derivation_formula_identity: Literal["FY-minus-Q1-minus-Q2-minus-Q3"] | None = None
    reconciliation_policy: str | None = None
    qoq: RevenueHistoryGrowth
    yoy: RevenueHistoryGrowth


class RevenueHistoryResearch(ResearchModel):
    schema_version: Literal["1"] = "1"
    availability: Literal["available", "insufficient_data", "conflict", "unavailable"]
    policy: str | None = None
    reasons: tuple[str, ...] = ()
    observation_count: int = 0
    directly_reported_count: int = 0
    derived_count: int = 0
    earliest_quarter: str | None = None
    latest_quarter: str | None = None
    latest_exact_revenue: Decimal | None = None
    latest_qoq_growth_pct: Decimal | None = None
    latest_yoy_growth_pct: Decimal | None = None
    qoq_comparison_count: int = 0
    yoy_comparison_count: int = 0
    points: tuple[RevenueHistoryPoint, ...] = Field(default=(), max_length=8)


class ResearchPresentation(ResearchModel):
    schema_version: Literal["2"] = "2"
    as_of: AwareDatetime
    ticker: str
    earnings: EarningsResearch
    industry: IndustryResearch
    economic: EconomicResearch
    market: MarketResearch
    company: EventResearch
    geopolitical: EventResearch
    revenue_history: RevenueHistoryResearch
    what_to_watch: tuple[ResearchCatalyst, ...] = ()
    sources: tuple[ResearchSource, ...] = ()


class AIResearchReportResult(ResearchModel):
    status: Literal["available", "unavailable"]
    analysis: AIOutlookResponse | None = None
    research: ResearchPresentation | None = None
