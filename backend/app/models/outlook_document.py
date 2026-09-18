"""Provider-independent, bounded source material; never a directional assessment."""
from datetime import timezone
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, JsonValue, field_validator, model_validator

from app.models.outlook_evidence import Text
from app.models.outlook_taxonomy import SourceType
from app.models.outlook_reporting import ReportingIdentity

SourceQuality = Literal["primary_authoritative", "secondary_reporting", "unknown"]


class SourceTableCell(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    text: str = Field(max_length=500)
    colspan: int = Field(default=1, ge=1, le=24)


class SourceTable(BaseModel):
    """Bounded source structure, without inferred metrics or financial meaning."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    rows: tuple[Annotated[tuple[SourceTableCell, ...], Field(max_length=24)], ...] = Field(max_length=40)


class SourceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: Text
    ticker: Text
    title: Text
    extracted_text: str = Field(default="", max_length=60000)
    description: str | None = Field(default=None, max_length=4000)
    published_at: AwareDatetime
    observed_at: AwareDatetime
    source_name: Text
    source_type: SourceType
    source_url: HttpUrl
    provider: Text
    provider_document_id: Text
    source_quality: SourceQuality = "unknown"
    related_tickers: tuple[str, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    tables: tuple[SourceTable, ...] = Field(default=(), max_length=8)
    reporting_identity: ReportingIdentity | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value):
        return value.upper()

    @field_validator("published_at", "observed_at")
    @classmethod
    def normalize_time(cls, value):
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_times(self):
        if self.observed_at < self.published_at:
            raise ValueError("Observed time cannot precede publication")
        if self.reporting_identity:
            for period in self.reporting_identity.periods:
                if period.ticker.upper() != self.ticker or (period.period_end and period.period_end > self.published_at.date()):
                    raise ValueError("Reporting identity must describe this issuer and an ended period")
        return self
