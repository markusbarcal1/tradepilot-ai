"""External events and outcome expectations, independent of stock-price predictions."""
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models.outlook_evidence import ExposureLink, Text, UnitValue
from app.models.outlook_taxonomy import CategoryKey, EvidenceImpact, SourceType
from app.models.outlook_reporting import ReportingIdentity


class EventModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EventValue(EventModel):
    """A scalar, range, or non-numeric outcome; units are explicit."""
    amount: float | None = Field(default=None, allow_inf_nan=False)
    lower: float | None = Field(default=None, allow_inf_nan=False)
    upper: float | None = Field(default=None, allow_inf_nan=False)
    text: Text | None = None
    unit: Text

    @model_validator(mode="after")
    def shape(self):
        is_range = self.lower is not None or self.upper is not None
        if sum((self.amount is not None, is_range, self.text is not None)) != 1:
            raise ValueError("Exactly one value representation is required")
        if is_range and (self.lower is None or self.upper is None or self.lower > self.upper):
            raise ValueError("Invalid range")
        return self


class EventSource(EventModel):
    source: Text
    source_type: SourceType
    source_url: HttpUrl
    published_at: AwareDatetime | None = None
    retrieved_at: AwareDatetime

    @model_validator(mode="after")
    def timing(self):
        if self.published_at and self.published_at > self.retrieved_at:
            raise ValueError("Publication cannot follow retrieval")
        return self


class OutcomeProbability(EventModel):
    title: Text
    outcome: EventValue
    probability: UnitValue

    @field_validator("probability", mode="before")
    @classmethod
    def numeric_probability(cls, value):
        if isinstance(value, bool):
            raise ValueError("A probability must be numeric, not a boolean")
        return value


class EarningsMetricIdentity(EventModel):
    """Exact earnings measurement semantics; matching labels are not enough."""
    metric: Literal["revenue", "eps"]
    accounting_basis: Literal["gaap", "adjusted", "provider_defined", "not_applicable", "unknown"]
    share_basis: Literal["diluted", "basic", "not_applicable", "unknown"]
    scope: Literal["total_company", "continuing_operations", "other", "unknown"]
    constant_currency: bool = False

    @model_validator(mode="after")
    def valid_shape(self):
        if self.metric == "revenue" and (
                self.accounting_basis != "not_applicable" or self.share_basis != "not_applicable"):
            raise ValueError("Revenue does not have an EPS accounting/share basis")
        if self.metric == "eps" and self.share_basis == "not_applicable":
            raise ValueError("EPS requires a share basis")
        return self


class ExpectationSnapshot(EventModel):
    """One immutable, timestamped distribution/consensus for one event outcome."""
    snapshot_id: Text
    event_id: Text
    basis: Literal["market_implied", "structured_consensus", "options_implied"]
    metric: Literal["change", "actual_value"]
    measurement_key: Text | None = None
    ticker: Text | None = None
    reporting_identity: ReportingIdentity | None = None
    metric_identity: EarningsMetricIdentity | None = None
    reference_period: Text | None = None
    release_type: Text | None = None
    expected_value: EventValue | None = None
    low_estimate: EventValue | None = None
    high_estimate: EventValue | None = None
    currency: Text | None = None
    analyst_count: int | None = Field(default=None, ge=0)
    outcomes: tuple[OutcomeProbability, ...] = Field(default=(), max_length=20)
    observed_at: AwareDatetime | None = None
    captured_at: AwareDatetime | None = None
    provider_as_of_at: AwareDatetime | None = None
    expires_at: AwareDatetime
    provider: Text | None = None
    temporal_status: Literal["unvalidated", "pre_release_verified", "upcoming_current", "post_release", "timestamp_unknown", "incompatible", "stale", "invalid"] = "unvalidated"
    origin: Literal["tradepilot_captured", "provider_point_in_time", "provider_reported_history"] = "tradepilot_captured"
    provenance: EventSource

    @model_validator(mode="before")
    @classmethod
    def capture_alias(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            if value.get("captured_at") is None and value.get("observed_at") is not None:
                value["captured_at"] = value["observed_at"]
            if value.get("observed_at") is None and value.get("captured_at") is not None:
                value["observed_at"] = value["captured_at"]
        return value

    @model_validator(mode="after")
    def validate_snapshot(self):
        if not self.outcomes and self.expected_value is None:
            raise ValueError("Empty expectation")
        if self.captured_at and self.expires_at <= self.captured_at:
            raise ValueError("Invalid expectation timestamps")
        if self.low_estimate and self.high_estimate:
            if (self.low_estimate.unit != self.high_estimate.unit
                    or self.low_estimate.amount is None or self.high_estimate.amount is None
                    or self.low_estimate.amount > self.high_estimate.amount):
                raise ValueError("Invalid expectation range")
        if self.expected_value and any(value and value.unit != self.expected_value.unit
                                       for value in (self.low_estimate, self.high_estimate)):
            raise ValueError("Expectation value and range units must agree")
        if self.outcomes:
            if abs(sum(row.probability for row in self.outcomes) - 1) > 0.000001:
                raise ValueError("Distribution must sum to one")
            keys = [row.outcome.model_dump_json() for row in self.outcomes]
            if len(keys) != len(set(keys)):
                raise ValueError("Duplicate outcomes")
        values = [row.outcome for row in self.outcomes] + ([self.expected_value] if self.expected_value else [])
        if len({v.unit for v in values}) != 1:
            raise ValueError("Expectation units must agree")
        return self


class EventScope(EventModel):
    countries: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    commodities: tuple[str, ...] = ()
    technologies: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()


class EventSurprise(EventModel):
    status: Literal["unavailable", "as_expected", "different_from_expected", "higher_than_expected", "lower_than_expected", "probability_based"] = "unavailable"
    difference: EventValue | None = None
    percent_difference: float | None = Field(default=None, allow_inf_nan=False)
    actual_outcome_probability: UnitValue | None = None
    expectation_snapshot_id: str | None = None
    comparison_result: Literal["beat", "miss", "approximately_in_line", "unavailable"] = "unavailable"
    origin: Literal["tradepilot_calculated", "provider_reported"] | None = None
    actual_value: EventValue | None = None
    expected_value: EventValue | None = None
    rejection_reason: Text | None = None
    crosses_zero: bool = False


class ExpectationDiagnostics(EventModel):
    candidate_count: int = Field(default=0, ge=0)
    compatible_count: int = Field(default=0, ge=0)
    temporal_count: int = Field(default=0, ge=0)
    selected_snapshot_id: Text | None = None
    captured_at: AwareDatetime | None = None
    release_at: AwareDatetime | None = None
    compatibility_result: Literal["compatible", "incompatible", "unavailable"] = "unavailable"
    rejection_reason: Text | None = None
    surprise_origin: Literal["tradepilot_calculated", "provider_reported"] | None = None


class EventMeasurement(EventModel):
    """One measurement within a release, never an independent support event."""
    key: Text
    label: Text
    metric_identity: EarningsMetricIdentity | None = None
    currency: Text | None = None
    actual_value: EventValue | None = None
    previous_value: EventValue | None = None
    expectation: ExpectationSnapshot | None = None
    expectation_status: Literal["unavailable", "available", "stale", "invalid", "error"] = "unavailable"
    surprise: EventSurprise = Field(default_factory=EventSurprise)
    expectation_diagnostics: ExpectationDiagnostics = Field(default_factory=ExpectationDiagnostics)


class EventRevision(EventModel):
    reference_period: Text
    measurement_key: Text
    previous_value: EventValue
    actual_value: EventValue
    provenance: EventSource
    previous_provenance: EventSource | None = None


class ExternalEvent(EventModel):
    event_id: Text
    event_type: Text
    category: CategoryKey
    title: Text
    summary: Text
    # Date-only sources stay date-only; never manufacture a midnight or 2pm release.
    scheduled_date: date | None = None
    scheduled_at: AwareDatetime | None = None
    announced_at: AwareDatetime | None = None
    effective_date: date | None = None
    effective_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    status: Literal["upcoming", "occurred", "effective", "expired"]
    reference_period: Text | None = None
    underlying_event_id: Text | None = None
    release_type: Text | None = None
    ticker: Text | None = None
    issuer: Text | None = None
    reporting_identity: ReportingIdentity | None = None
    schedule_certainty: Literal["confirmed", "provider_reported", "estimated", "unknown"] | None = None
    market_session: Literal["before_market", "after_market", "during_market", "unknown"] | None = None
    schedule_history: tuple[EventSource, ...] = Field(default=(), max_length=8)
    guidance_status: Literal["raised", "lowered", "maintained", "new", "withdrawn", "ambiguous", "unavailable"] | None = None
    scheduled_timezone: Text | None = None
    measurements: tuple[EventMeasurement, ...] = Field(default=(), max_length=12)
    revisions: tuple[EventRevision, ...] = Field(default=(), max_length=12)
    previous_value: EventValue | None = None
    expected_value: EventValue | None = None
    actual_value: EventValue | None = None
    change: EventValue | None = None
    expectation: ExpectationSnapshot | None = None
    expectation_status: Literal["unavailable", "available", "stale", "invalid", "error"] = "unavailable"
    expectation_history: tuple[ExpectationSnapshot, ...] = Field(default=(), max_length=32)
    surprise: EventSurprise = Field(default_factory=EventSurprise)
    provenance: tuple[EventSource, ...] = Field(min_length=1)
    scope: EventScope = Field(default_factory=EventScope)

    @model_validator(mode="after")
    def unique_measurements(self):
        keys = [m.key for m in self.measurements]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate release measurements")
        return self


@dataclass(frozen=True)
class ExposureAssessment:
    """Shared with Geopolitical: a supported link is distinct from its direction."""
    matched: bool
    reason: str
    link: ExposureLink | None = None
    relevance: Literal["unsupported", "broad", "company_specific"] = "unsupported"
    directness: Literal["unknown", "broad", "industry", "business"] = "unknown"
    confidence: UnitValue = 0
    materiality: UnitValue = 0
    direction: EvidenceImpact | None = None


class RelevantEvent(EventModel):
    event: ExternalEvent
    exposure: ExposureAssessment
    directional_evidence: bool = False


class EventIntelligence(EventModel):
    status: str = "unavailable"
    upcoming: tuple[RelevantEvent, ...] = ()
    recent: tuple[RelevantEvent, ...] = ()
