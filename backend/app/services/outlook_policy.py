"""Provisional evidence policy, centralized for fixture calibration."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.outlook_taxonomy import CategoryKey, EventType, CATEGORY_TITLES


class FreshnessRule(BaseModel):
    model_config = ConfigDict(frozen=True)
    half_life_days: float = Field(gt=0, allow_inf_nan=False)
    max_age_days: float = Field(gt=0, allow_inf_nan=False)


class EvidencePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    category_freshness: dict[CategoryKey, FreshnessRule] = Field(default_factory=lambda: {
        "company": FreshnessRule(half_life_days=7, max_age_days=30),
        "earnings": FreshnessRule(half_life_days=45, max_age_days=120),
        "industry": FreshnessRule(half_life_days=14, max_age_days=60),
        "economic": FreshnessRule(half_life_days=30, max_age_days=90),
        "market": FreshnessRule(half_life_days=1, max_age_days=5),
        "geopolitical": FreshnessRule(half_life_days=7, max_age_days=30),
    })
    event_freshness: dict[EventType, FreshnessRule] = Field(default_factory=lambda: {
        EventType.CYBERSECURITY_EVENT: FreshnessRule(half_life_days=30, max_age_days=120),
        EventType.RESTRUCTURING: FreshnessRule(half_life_days=45, max_age_days=180),
        EventType.MANAGEMENT_CHANGE: FreshnessRule(half_life_days=14, max_age_days=60),
        EventType.BROAD_MARKET_TREND: FreshnessRule(half_life_days=5, max_age_days=7),
        EventType.VOLATILITY: FreshnessRule(half_life_days=5, max_age_days=7),
        EventType.GUIDANCE_RAISE: FreshnessRule(half_life_days=60, max_age_days=180),
        EventType.GUIDANCE_CUT: FreshnessRule(half_life_days=60, max_age_days=180),
        EventType.EARNINGS_UPCOMING: FreshnessRule(half_life_days=3, max_age_days=14),
        EventType.RISK_SENTIMENT: FreshnessRule(half_life_days=0.5, max_age_days=2),
        EventType.INTEREST_RATES: FreshnessRule(half_life_days=45, max_age_days=120),
    })
    duplicate_window_hours: float = Field(default=48, gt=0, allow_inf_nan=False)
    headline_similarity: float = Field(default=0.9, ge=0, le=1, allow_inf_nan=False)
    minimum_events: int = Field(default=2, ge=1)
    minimum_weight: float = Field(default=0.75, gt=0, allow_inf_nan=False)
    minimum_materiality: float = Field(default=0.1, gt=0, le=1, allow_inf_nan=False)
    minimum_confidence: float = Field(default=0.4, gt=0, le=1, allow_inf_nan=False)
    positive_threshold: float = Field(default=0.35, gt=0, le=2, allow_inf_nan=False)
    strong_threshold: float = Field(default=1.2, gt=0, le=2, allow_inf_nan=False)
    strong_minimum_events: int = Field(default=3, ge=2)

    @model_validator(mode="after")
    def validate_policy(self):
        if set(self.category_freshness) != set(CATEGORY_TITLES):
            raise ValueError("Freshness policy must cover all categories")
        if self.strong_threshold <= self.positive_threshold:
            raise ValueError("Strong threshold must exceed positive threshold")
        if self.strong_minimum_events < self.minimum_events:
            raise ValueError("Strong classifications require at least the minimum event count")
        return self


DEFAULT_EVIDENCE_POLICY = EvidencePolicy()
