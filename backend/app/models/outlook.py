"""Provider-independent qualitative Outlook contract (no public 0–100 score)."""
from datetime import date
from typing import Literal
from enum import Enum

from app.models.outlook_taxonomy import CATEGORY_TITLES, CategoryKey
from app.models.outlook_evidence import OutlookEvidence, UnitValue
from app.models.outlook_event import EventIntelligence

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

class OutlookLabel(str, Enum):
    VERY_NEGATIVE = "Very Negative"
    NEGATIVE = "Negative"
    MIXED = "Mixed"
    POSITIVE = "Positive"
    VERY_POSITIVE = "Very Positive"


CLASSIFICATIONS = {
    -2: OutlookLabel.VERY_NEGATIVE, -1: OutlookLabel.NEGATIVE,
    0: OutlookLabel.MIXED, 1: OutlookLabel.POSITIVE, 2: OutlookLabel.VERY_POSITIVE,
}
CategoryStatus = Literal["available", "insufficient_data", "unavailable", "error", "not_material"]
ClassificationValue = Literal[-2, -1, 0, 1, 2]
DriverDirection = Literal["positive", "negative", "neutral", "mixed"]
Importance = Literal["high", "medium", "low"]


class IntelligenceSource(BaseModel):
    model_config = ConfigDict(frozen=True)
    evidence_id: str | None = None
    name: str
    url: str | None = None
    published_at: str | None = None


class CategoryDriver(BaseModel):
    model_config = ConfigDict(frozen=True)
    label: str
    direction: DriverDirection
    importance: Importance | None = None
    value: str | None = None
    change: str | None = None
    sources: tuple[IntelligenceSource, ...] = ()
    related_event_id: str | None = None


class IntelligenceMetric(BaseModel):
    model_config = ConfigDict(frozen=True)
    key: str
    label: str
    actual: str | None = None
    expected: str | None = None
    previous: str | None = None
    result: str | None = None
    indicator: Literal["Beat", "In Line", "Miss", "Improved", "Declined", "Unchanged"] | None = None
    comparison_status: Literal["available", "unavailable", "invalid", "stale", "error"] = "unavailable"
    sources: tuple[IntelligenceSource, ...] = ()


class MaterialEventSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    title: str
    status: str
    event_date: date | None = None
    importance: Importance
    timing: str | None = None
    certainty: str | None = None


class CategoryIntelligence(BaseModel):
    model_config = ConfigDict(frozen=True)
    category: CategoryKey
    rating: OutlookLabel | None = None
    availability: CategoryStatus
    summary: str
    positive_drivers: tuple[CategoryDriver, ...] = ()
    negative_drivers: tuple[CategoryDriver, ...] = ()
    neutral_mixed_drivers: tuple[CategoryDriver, ...] = ()
    important_metrics: tuple[IntelligenceMetric, ...] = ()
    latest_material_event: MaterialEventSummary | None = None
    next_material_event: MaterialEventSummary | None = None
    sources: tuple[IntelligenceSource, ...] = ()
    evidence_sufficiency: str
    omitted_driver_count: int = Field(default=0, ge=0)
    beat_probability: float | None = Field(default=None, ge=0, le=1)
    implied_move: float | None = Field(default=None, ge=0)


def classification_label(value: float) -> OutlookLabel:
    # Symmetric midpoint thresholds; ties classify away from Mixed.
    bucket = 2 if value >= 1.5 else 1 if value >= 0.5 else -2 if value <= -1.5 else -1 if value <= -0.5 else 0
    return CLASSIFICATIONS[bucket]


class OutlookFactor(BaseModel):
    title: str
    impact: OutlookLabel
    description: str
    evidence_ids: list[str] = Field(default_factory=list)


class OutlookCategory(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: CategoryStatus = "unavailable"
    value: ClassificationValue | None = None
    summary: str = "No evidence is available."
    factors: list[OutlookFactor] = Field(default_factory=list)
    evidence_count: int | None = Field(default=None, ge=0)
    confidence: UnitValue | None = None
    evidence: list[OutlookEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence(self):
        if (self.status == "available") != (self.value is not None):
            raise ValueError("Only available categories must have a classification value")
        return self

    @computed_field
    @property
    def label(self) -> OutlookLabel | None:
        return CLASSIFICATIONS[self.value] if self.value is not None else None


class OutlookMetadata(BaseModel):
    provider: str
    uses_placeholder_data: bool
    version: str = "1.2"
    provider_status: dict[str, str] = Field(default_factory=dict)


class OutlookResponse(BaseModel):
    ticker: str
    status: Literal["available", "partial", "unavailable", "error", "placeholder"]
    value: float | None = Field(default=None, ge=-2, le=2)
    summary: str
    categories: dict[CategoryKey, OutlookCategory]
    metadata: OutlookMetadata
    event_intelligence: EventIntelligence = Field(default_factory=EventIntelligence)
    category_intelligence: dict[CategoryKey, CategoryIntelligence] = Field(default_factory=dict)
    key_events: tuple[MaterialEventSummary, ...] = ()

    @model_validator(mode="after")
    def validate_assessment(self):
        if set(self.categories) != set(CATEGORY_TITLES):
            raise ValueError("Outlook must include all six categories")
        if self.category_intelligence and set(self.category_intelligence) != set(CATEGORY_TITLES):
            raise ValueError("Category intelligence must include all six categories")
        if (self.status in ("available", "partial")) != (self.value is not None):
            raise ValueError("Only available or partial Outlooks must have an aggregate value")
        return self

    @computed_field
    @property
    def available_categories(self) -> int:
        return sum(category.status == "available" for category in self.categories.values())

    @computed_field
    @property
    def label(self) -> OutlookLabel | None:
        return classification_label(self.value) if self.value is not None else None
