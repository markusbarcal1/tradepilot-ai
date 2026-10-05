"""Internal contracts for directly reported standalone fourth-quarter facts."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Q4Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DirectQ4Document(Q4Model):
    ticker: str
    issuer: str
    cik: str
    fiscal_year: int = Field(ge=1900, le=2200)
    accession: str
    form: Literal["10-K", "10-K/A", "8-K", "8-K/A"]
    document_url: str
    document_id: str
    filing_date: date
    publication_time: AwareDatetime | None = None
    source_family: Literal["filing_xbrl", "earnings_release_table"]
    content: str


class DirectQ4Candidate(Q4Model):
    ticker: str
    issuer: str
    cik: str
    metric: Literal["revenue", "diluted_eps"]
    fiscal_year: int
    fiscal_quarter: Literal["Q4"] = "Q4"
    period_start: date | None = None
    period_end: date | None = None
    original_value: Decimal | None = None
    original_concept: str | None = None
    original_unit: str | None = None
    scale: int | None = None
    currency: str | None = None
    accounting_basis: Literal["gaap", "non_gaap", "unknown"] = "unknown"
    share_basis: Literal["not_applicable", "diluted", "basic", "unknown"] = "unknown"
    reporting_scope: Literal["consolidated", "dimensional", "unknown"] = "unknown"
    source_family: Literal["filing_xbrl", "earnings_release_table"]
    basis: Literal["directly_reported"] = "directly_reported"
    accession: str
    form: Literal["10-K", "10-K/A", "8-K", "8-K/A"]
    document_url: str
    document_id: str
    filing_date: date
    publication_time: AwareDatetime | None = None
    locator: str
    amendment: bool = False
    exact: bool = True
    rejection_reasons: tuple[str, ...] = ()


class DirectQ4Observation(Q4Model):
    observation_id: str
    ticker: str
    issuer: str
    cik: str
    metric: Literal["revenue", "diluted_eps"]
    fiscal_year: int
    fiscal_quarter: Literal["Q4"] = "Q4"
    period_start: date
    period_end: date
    duration_days: int
    original_value: Decimal
    normalized_value: Decimal
    original_concept: str
    original_unit: str
    scale: int
    currency: Literal["USD"]
    accounting_basis: Literal["gaap"] = "gaap"
    share_basis: Literal["not_applicable", "diluted"]
    reporting_scope: Literal["consolidated"] = "consolidated"
    source_family: Literal["filing_xbrl", "earnings_release_table"]
    basis: Literal["directly_reported"] = "directly_reported"
    accession: str
    form: Literal["10-K", "10-K/A", "8-K", "8-K/A"]
    document_url: str
    document_id: str
    filing_date: date
    publication_time: AwareDatetime | None = None
    locator: str
    version_status: Literal["current", "corroborating", "superseded", "conflict"]
    superseded_by: str | None = None
    comparison_eligible: bool
    comparison_exclusion_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def coherent(self):
        if self.duration_days != (self.period_end - self.period_start).days + 1:
            raise ValueError("Duration does not match dates")
        if self.comparison_eligible != (self.version_status == "current"):
            raise ValueError("Only current observations are comparison eligible")
        return self


class DirectQ4Result(Q4Model):
    schema_version: Literal["1"] = "1"
    status: Literal["available", "partial", "unavailable", "conflict"]
    candidates: tuple[DirectQ4Candidate, ...] = ()
    observations: tuple[DirectQ4Observation, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    requests: int = 0
    cache_hits: int = 0
