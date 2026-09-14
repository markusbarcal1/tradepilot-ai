"""Normalized evidence and retained source identity; no provider assessments."""
from datetime import timezone
from typing import Annotated, Literal

from pydantic import (AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl,
                      StringConstraints, field_validator, model_validator)

from app.models.outlook_taxonomy import CategoryKey, EVENT_TYPES, EventType, EvidenceImpact, SourceType

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
UnitValue = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class ExposureLink(BaseModel):
    kind: Literal["geography", "supply_chain", "manufacturing", "revenue", "commodity",
                  "sanctions", "trade_routes", "tariffs", "industry"]
    description: Text
    source_url: HttpUrl | None = None


class CompanyContext(BaseModel):
    ticker: Text
    sector: Text | None = None
    industry: Text | None = None
    peer_group: tuple[str, ...] = ()
    exposures: tuple[ExposureLink, ...] = ()


class OutlookEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    id: Text
    ticker: Text
    category: CategoryKey
    event_type: EventType
    title: Text
    summary: Text
    source: Text
    source_type: SourceType
    source_url: HttpUrl | None = None
    published_at: AwareDatetime
    observed_at: AwareDatetime
    expires_at: AwareDatetime | None = None
    impact: EvidenceImpact
    confidence: UnitValue
    materiality: UnitValue
    materiality_reason: Text
    exposure_links: tuple[ExposureLink, ...] = ()
    raw_provider: Text
    raw_provider_id: Text | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value):
        return value.upper()

    @field_validator("published_at", "observed_at", "expires_at")
    @classmethod
    def normalize_time(cls, value):
        return value.astimezone(timezone.utc) if value is not None else None

    @model_validator(mode="after")
    def validate_event(self):
        if self.event_type.value not in EVENT_TYPES[self.category]:
            raise ValueError("Event type does not belong to this category")
        if self.observed_at < self.published_at:
            raise ValueError("Observed time cannot precede publication")
        if self.expires_at is not None and self.expires_at <= self.published_at:
            raise ValueError("Expiration must follow publication")
        return self
