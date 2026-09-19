"""External events and outcome expectations, independent of stock-price predictions."""
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models.outlook_evidence import ExposureLink, Text, UnitValue
from app.models.outlook_taxonomy import CategoryKey, EvidenceImpact, SourceType


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


class ExpectationSnapshot(EventModel):
    """One immutable, timestamped distribution/consensus for one event outcome."""
    snapshot_id: Text
    event_id: Text
    basis: Literal["market_implied", "structured_consensus", "options_implied"]
    metric: Literal["change", "actual_value"]
    expected_value: EventValue | None = None
    outcomes: tuple[OutcomeProbability, ...] = Field(default=(), max_length=20)
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    provenance: EventSource

    @model_validator(mode="after")
    def validate_snapshot(self):
        if not self.outcomes and self.expected_value is None:
            raise ValueError("Empty expectation")
        if self.expires_at <= self.observed_at or self.provenance.retrieved_at < self.observed_at:
            raise ValueError("Invalid expectation timestamps")
        if self.provenance.published_at is None:
            raise ValueError("Expectation availability must be documented")
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
    status: Literal["unavailable", "as_expected", "different_from_expected", "probability_based"] = "unavailable"
    difference: EventValue | None = None
    actual_outcome_probability: UnitValue | None = None
    expectation_snapshot_id: str | None = None


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
