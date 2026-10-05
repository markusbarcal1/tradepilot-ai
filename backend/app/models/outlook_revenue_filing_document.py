"""Immutable contracts for bounded SEC filing-document retrieval."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.outlook_inline_revenue import OperandRole, SelectedFilingDocument
from app.models.outlook_revenue_filing_selection import FilingMetadataProvenance


RetrievalReason = Literal["input_not_selected", "role_set_invalid", "url_policy_rejected",
    "redirect_rejected", "http_403", "http_404", "http_429", "http_5xx",
    "http_error", "timeout", "connection_failure", "transport_failure",
    "response_size_rejected", "empty_response", "content_type_rejected"]


class FilingDocumentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RetrievedRevenueFilingDocument(FilingDocumentModel):
    role: OperandRole
    selected_document: SelectedFilingDocument
    selection_provenance: FilingMetadataProvenance
    canonical_url: str
    body: bytes
    byte_length: int = Field(ge=1)
    fingerprint_algorithm: Literal["sha256"] = "sha256"
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    content_type: str
    retrieval_policy: Literal["revenue-filing-document-retrieval-1"]
    cache_state: Literal["miss", "success_hit"]


class RevenueFilingDocumentRequestAccounting(FilingDocumentModel):
    logical_documents_requested: int = Field(ge=0, le=4)
    cache_success_hits: int = Field(ge=0, le=4)
    cache_failure_hits: int = Field(ge=0, le=4)
    http_attempts_charged: int = Field(ge=0, le=4)
    successes: int = Field(ge=0, le=4)
    failures: int = Field(ge=0, le=1)
    bytes_accepted: int = Field(ge=0)
    failure_position: int | None = Field(default=None, ge=1, le=4)
    failure_role: OperandRole | None = None
    failure_reason: RetrievalReason | None = None


class RevenueFilingDocumentBatchResult(FilingDocumentModel):
    policy_version: Literal["revenue-filing-document-retrieval-1"]
    state: Literal["available", "unavailable", "conflict"]
    issuer: str
    cik: str
    target_fiscal_year: int
    documents: tuple[RetrievedRevenueFilingDocument, ...] = Field(default=(), max_length=4)
    reason: RetrievalReason | None = None
    request_accounting: RevenueFilingDocumentRequestAccounting

    @model_validator(mode="after")
    def coherent(self):
        if self.state == "available":
            if self.reason is not None or tuple(row.role for row in self.documents) != ("FY", "Q1", "Q2", "Q3"):
                raise ValueError("available batch requires FY/Q1/Q2/Q3")
        elif self.reason is None or self.documents:
            raise ValueError("failed batch cannot expose partial documents")
        return self
