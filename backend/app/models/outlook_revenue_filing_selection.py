"""Immutable contracts for offline SEC revenue-operand filing selection."""
from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models.outlook_inline_revenue import OperandRole, SelectedFilingDocument


SelectionState = Literal["selected", "unavailable", "ambiguous", "conflict"]
SelectionReason = Literal[
    "issuer_identity_missing", "target_fiscal_year_missing", "issuer_mismatch",
    "annual_filing_missing", "quarter_filing_missing", "multiple_annual_candidates",
    "multiple_quarter_candidates", "amendment_ambiguous", "report_period_missing",
    "primary_document_missing", "primary_document_invalid", "fiscal_geometry_invalid",
    "quarter_order_invalid", "filing_date_missing", "accession_invalid",
]


class RevenueFilingSelectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RevenueFilingQuarterAnchor(RevenueFilingSelectionModel):
    role: Literal["Q1", "Q2", "Q3"]
    report_period_end: date


class RevenueFilingSelectionRequest(RevenueFilingSelectionModel):
    ticker: str = Field(min_length=1, max_length=32)
    issuer: str = Field(min_length=1, max_length=512)
    cik: str = Field(min_length=1, max_length=32)
    target_fiscal_year: int = Field(ge=1900, le=2200)
    quarter_anchors: tuple[RevenueFilingQuarterAnchor, ...] = Field(min_length=3, max_length=3)


class SecSubmissionFilingRow(RevenueFilingSelectionModel):
    accession: str | None = Field(default=None, max_length=64)
    form: str | None = Field(default=None, max_length=32)
    filing_date: date | None = None
    acceptance_time: AwareDatetime | None = None
    report_period_end: date | None = None
    primary_document: str | None = Field(default=None, max_length=512)
    source_ordinal: int = Field(ge=0, le=100_000)


class SecSubmissionsSelectionInput(RevenueFilingSelectionModel):
    issuer: str | None = Field(default=None, max_length=512)
    cik: str | None = Field(default=None, max_length=32)
    source_identity: str = Field(min_length=1, max_length=512)
    rows: tuple[SecSubmissionFilingRow, ...] = Field(max_length=4096)


class FilingMetadataProvenance(RevenueFilingSelectionModel):
    source_identity: str
    source_ordinals: tuple[int, ...] = Field(min_length=1, max_length=4096)


class SelectedRevenueFiling(RevenueFilingSelectionModel):
    role: OperandRole
    amendment_state: Literal["original"] = "original"
    document: SelectedFilingDocument
    metadata_provenance: FilingMetadataProvenance


class RevenueFilingSelectionResult(RevenueFilingSelectionModel):
    policy_version: Literal["revenue-operand-filing-selection-1"]
    issuer: str
    cik: str
    target_fiscal_year: int
    state: SelectionState
    reason: SelectionReason | None = None
    selected_filings: tuple[SelectedRevenueFiling, ...] = Field(default=(), max_length=4)

    @model_validator(mode="after")
    def coherent_result(self):
        roles = tuple(item.role for item in self.selected_filings)
        if self.state == "selected":
            if self.reason is not None or roles != ("FY", "Q1", "Q2", "Q3"):
                raise ValueError("selected result requires exactly FY/Q1/Q2/Q3 and no reason")
        elif self.reason is None or self.selected_filings:
            raise ValueError("non-selected result requires one reason and no selected filings")
        return self
