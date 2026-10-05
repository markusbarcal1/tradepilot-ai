"""Vendor-neutral Phase 6A grounded Outlook intelligence contracts."""
from __future__ import annotations
from datetime import date as Date
from enum import Enum
from typing import Iterator, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models.outlook_taxonomy import CategoryKey


class AIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AIRating(str, Enum):
    VERY_POSITIVE = "very_positive"
    MOSTLY_POSITIVE = "mostly_positive"
    MIXED = "mixed"
    MOSTLY_NEGATIVE = "mostly_negative"
    VERY_NEGATIVE = "very_negative"
    INSUFFICIENT_DATA = "insufficient_data"


class ContextSource(AIModel):
    source_id: str
    name: str
    url: HttpUrl | None = None
    published_at: AwareDatetime | None = None


class ContextFact(AIModel):
    fact_id: str
    category: CategoryKey
    fact_type: str
    statement: str
    values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    source_ids: tuple[str, ...] = ()
    materiality: float = Field(default=0, ge=0, le=1)
    directionality: Literal["positive", "negative", "mixed", "informational"] = "informational"
    directionality_reason: str = "No verified directional signal is attached."
    occurred_at: AwareDatetime | None = None
    event_id: str | None = None
    upcoming: bool = False


class ContextDiagnostics(AIModel):
    included_fact_ids: tuple[str, ...] = ()
    omitted_fact_ids: tuple[str, ...] = ()
    omitted_reasons: dict[str, int] = Field(default_factory=dict)


class UpcomingEventReference(AIModel):
    event_id: str
    fact_id: str
    title: str
    event_type: str
    date: Date | None = None


class OutlookContextPacket(AIModel):
    schema_version: Literal["2.2"] = "2.2"
    ticker: str
    issuer: str | None = None
    generated_at: AwareDatetime
    facts: tuple[ContextFact, ...] = ()
    upcoming_events: tuple[UpcomingEventReference, ...] = ()
    sources: tuple[ContextSource, ...] = ()
    diagnostics: ContextDiagnostics = Field(default_factory=ContextDiagnostics)

    @field_validator("ticker")
    @classmethod
    def ticker_is_normalized(cls, value: str) -> str:
        value = value.strip().upper()
        if not value or len(value) > 15 or not all(c.isalnum() or c in ".-" for c in value):
            raise ValueError("Invalid ticker")
        return value

    @model_validator(mode="after")
    def references_exist(self):
        fact_ids = [fact.fact_id for fact in self.facts]
        source_ids = {source.source_id for source in self.sources}
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("Duplicate fact IDs")
        if any(source_id not in source_ids for fact in self.facts for source_id in fact.source_ids):
            raise ValueError("Unknown source ID in context")
        facts_by_id = {fact.fact_id: fact for fact in self.facts}
        for event in self.upcoming_events:
            fact = facts_by_id.get(event.fact_id)
            if fact is None or not fact.upcoming or fact.event_id != event.event_id:
                raise ValueError("Invalid upcoming-event reference")
        return self


class AIKeyPoint(AIModel):
    text: str = Field(min_length=1, max_length=240)
    supporting_fact_ids: tuple[str, ...] = Field(min_length=1, max_length=4, description=
        "Exact opaque fact IDs selected from the supplied context; never construct or modify IDs.")


class AICategoryAnalysis(AIModel):
    rating: AIRating = Field(description="Use insufficient_data when verified evidence cannot support direction.")
    summary: str = Field(min_length=1, max_length=420, description=
        "User-friendly assessment. For insufficient_data, explain only why evidence is insufficient; do not assert direction.")
    key_points: tuple[AIKeyPoint, ...] = Field(default=(), max_length=3, description=
        "Grounded substantive points. Must be empty when rating is insufficient_data.")
    supporting_fact_ids: tuple[str, ...] = Field(default=(), max_length=8)
    limitations: tuple[str, ...] = Field(default=(), max_length=3)

    @model_validator(mode="after")
    def insufficient_is_honest(self):
        if self.rating == AIRating.INSUFFICIENT_DATA and (
                self.key_points or self.supporting_fact_ids or self.limitations):
            raise ValueError("Insufficient-data categories must explain the limitation only in summary")
        if self.rating != AIRating.INSUFFICIENT_DATA and not self.supporting_fact_ids:
            raise ValueError("Substantive category ratings require supporting facts")
        return self


class AIOverallAnalysis(AIModel):
    rating: AIRating
    summary: str = Field(min_length=1, max_length=500)


class AICategories(AIModel):
    """Closed category object compatible with OpenAI strict Structured Outputs."""
    company: AICategoryAnalysis
    earnings: AICategoryAnalysis
    industry: AICategoryAnalysis
    economic: AICategoryAnalysis
    market: AICategoryAnalysis
    geopolitical: AICategoryAnalysis

    def items(self) -> Iterator[tuple[CategoryKey, AICategoryAnalysis]]:
        for key in ("company", "earnings", "industry", "economic", "market", "geopolitical"):
            yield key, getattr(self, key)

    def values(self) -> Iterator[AICategoryAnalysis]:
        return (value for _, value in self.items())


class AIWatchItem(AIModel):
    event_id: str = Field(description="Exact opaque event_id copied from one supplied upcoming_events entry.")
    reason: str = Field(min_length=1, max_length=240,
        description="Concise investor-friendly reason this supplied event is worth monitoring.")


class AIOutlookResponse(AIModel):
    overall: AIOverallAnalysis
    categories: AICategories
    what_to_watch: tuple[AIWatchItem, ...] = Field(default=(), max_length=5)

    @model_validator(mode="after")
    def all_categories_present(self):
        return self


class IntelligenceUsage(AIModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)


class IntelligenceDiagnostics(AIModel):
    provider: str
    model: str
    prompt_version: str
    schema_version: str
    context_fingerprint: str
    context_fact_count: int = Field(ge=0)
    cache_status: Literal["hit", "miss", "disabled"]
    latency_ms: int = Field(ge=0)
    validation_status: Literal["valid", "invalid", "not_run"]
    failure_reason: str | None = None
    usage: IntelligenceUsage = Field(default_factory=IntelligenceUsage)


class IntelligenceResult(AIModel):
    status: Literal["available", "unavailable"]
    response: AIOutlookResponse | None = None
    diagnostics: IntelligenceDiagnostics
