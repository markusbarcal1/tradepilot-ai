"""Provider-independent qualitative Outlook contract (no public 0–100 score)."""
from typing import Literal
from enum import Enum

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
CATEGORY_TITLES = {
    "company": "Company Outlook", "earnings": "Earnings Outlook",
    "industry": "Industry Outlook", "economic": "Economic Outlook",
    "market": "Market Outlook", "geopolitical": "Geopolitical Outlook",
}
CategoryKey = Literal["company", "earnings", "industry", "economic", "market", "geopolitical"]
CategoryStatus = Literal["available", "insufficient_data", "unavailable", "error", "not_material"]
ClassificationValue = Literal[-2, -1, 0, 1, 2]


def classification_label(value: float) -> OutlookLabel:
    # Symmetric midpoint thresholds; ties classify away from Mixed.
    bucket = 2 if value >= 1.5 else 1 if value >= 0.5 else -2 if value <= -1.5 else -1 if value <= -0.5 else 0
    return CLASSIFICATIONS[bucket]


class OutlookFactor(BaseModel):
    title: str
    impact: OutlookLabel
    description: str


class OutlookCategory(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: CategoryStatus = "unavailable"
    value: ClassificationValue | None = None
    summary: str = "No evidence is available."
    factors: list[OutlookFactor] = Field(default_factory=list)

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
    version: str = "1.0"


class OutlookResponse(BaseModel):
    ticker: str
    status: Literal["available", "partial", "unavailable", "error", "placeholder"]
    value: float | None = Field(default=None, ge=-2, le=2)
    summary: str
    categories: dict[CategoryKey, OutlookCategory]
    metadata: OutlookMetadata

    @model_validator(mode="after")
    def validate_assessment(self):
        if set(self.categories) != set(CATEGORY_TITLES):
            raise ValueError("Outlook must include all six categories")
        if (self.status in ("available", "partial")) != (self.value is not None):
            raise ValueError("Only available or partial Outlooks must have an aggregate value")
        return self

    @computed_field
    @property
    def label(self) -> OutlookLabel | None:
        return classification_label(self.value) if self.value is not None else None
