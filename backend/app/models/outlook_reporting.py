"""Source-grounded reporting identity. These models never supply scoring inputs."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReportingModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReportingPeriodIdentity(ReportingModel):
    ticker: str
    fiscal_year: int = Field(ge=1900, le=2200)
    fiscal_period: Literal["Q1", "Q2", "Q3", "Q4", "FY"]
    period_start: date | None = None
    period_end: date | None = None

    @field_validator("ticker")
    @classmethod
    def normalized_ticker(cls, value):
        return value.strip().upper()

    @model_validator(mode="after")
    def valid_dates(self):
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("Period start follows period end")
        return self

    @property
    def key(self):
        return f"{self.ticker.upper()}:FY{self.fiscal_year}:{self.fiscal_period}"


class ReportingProvenance(ReportingModel):
    method: Literal["inline_xbrl_dei", "explicit_primary_text", "validated_gaap_header"]
    source_url: str
    document_id: str
    accession: str | None = None
    basis: str


class ReportingRevision(ReportingModel):
    kind: Literal["amendment", "correction", "supersession"]
    original_document_id: str | None = None
    original_accession: str | None = None
    basis: str


class ReportingIdentity(ReportingModel):
    status: Literal["authoritative", "unknown", "conflict"] = "unknown"
    reason: str = "source_lacks_authoritative_reporting_identity"
    periods: tuple[ReportingPeriodIdentity, ...] = ()
    provenance: tuple[ReportingProvenance, ...] = ()
    revision: ReportingRevision | None = None

    @model_validator(mode="after")
    def supported_identity(self):
        if self.status == "authoritative" and (not self.periods or not self.provenance):
            raise ValueError("Authoritative identity requires periods and provenance")
        if self.status != "authoritative" and self.periods:
            raise ValueError("Unresolved identity cannot assert periods")
        return self


class KnownFiscalCalendar(ReportingModel):
    """Observed ends only; no projected dates or assumed three-month durations."""
    ticker: str
    known_periods: tuple[ReportingPeriodIdentity, ...] = ()
    provenance: tuple[ReportingProvenance, ...] = ()


def quarter_index(period):
    return period.fiscal_year * 4 + int(period.fiscal_period[1]) - 1 if period.fiscal_period != "FY" else None


def consecutive(previous, current):
    """None means unknown/annual ambiguity, never an inferred Q4."""
    if previous is None or current is None or previous.ticker.upper() != current.ticker.upper():
        return None
    left, right = quarter_index(previous), quarter_index(current)
    if left is None or right is None:
        return None
    if previous.period_end and current.period_end and previous.period_end >= current.period_end:
        return False
    return right - left == 1
