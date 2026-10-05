"""Immutable contracts for unregistered revenue-history snapshot orchestration."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.outlook_financial_history import HistoricalFinancialSnapshot
from app.models.outlook_revenue_filing_document import RevenueFilingDocumentBatchResult, RevenueFilingDocumentRequestAccounting
from app.models.outlook_revenue_filing_selection import RevenueFilingSelectionResult, SecSubmissionsSelectionInput
from app.models.outlook_revenue_history_series import RevenueHistoricalSeriesResult
from app.models.outlook_revenue_q4 import RevenueQ4DerivationResult
from app.models.outlook_revenue_q4_reconciliation import RevenueQ4ReconciliationResult
from app.models.outlook_revenue_research import RevenueResearchProjectionResult
from app.models.outlook_revenue_runtime_input import RevenueQ4RuntimeInputBuildResult

class SnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class RevenueHistoricalAcquisition(SnapshotModel):
    acquisition_policy: Literal["revenue-historical-acquisition-1"] = "revenue-historical-acquisition-1"
    snapshot: HistoricalFinancialSnapshot
    submissions: SecSubmissionsSelectionInput | None = None
    evidence_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    logical_requests: int = Field(ge=0, le=3)
    http_attempts: int = Field(ge=0, le=3)
    cache_state: Literal["miss", "success_hit"]

class RevenueSnapshotRequestAccounting(SnapshotModel):
    acquisition_cache_state: Literal["miss", "success_hit"] | None = None
    historical_logical_requests: int | None = Field(default=None, ge=0, le=3)
    historical_http_attempts: int | None = Field(default=None, ge=0, le=3)
    document_accounting: RevenueFilingDocumentRequestAccounting | None = None
    total_sec_http_attempts: int | None = Field(default=None, ge=0, le=7)

class RevenueHistorySnapshotResult(SnapshotModel):
    snapshot_policy: Literal["revenue-history-snapshot-1"]
    ticker: str
    state: Literal["available", "insufficient_data", "conflict", "unavailable"]
    reasons: tuple[str, ...] = Field(default=(), max_length=32)
    historical_evidence_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    q4_considered: bool = False
    q4_attempted: bool = False
    q4_skip_reason: str | None = Field(default=None, max_length=128)
    target_fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    selection: RevenueFilingSelectionResult | None = None
    retrieval: RevenueFilingDocumentBatchResult | None = None
    runtime_input: RevenueQ4RuntimeInputBuildResult | None = None
    derivation: RevenueQ4DerivationResult | None = None
    reconciliation: RevenueQ4ReconciliationResult | None = None
    series: RevenueHistoricalSeriesResult | None = None
    projection: RevenueResearchProjectionResult | None = None
    evidence_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    request_accounting: RevenueSnapshotRequestAccounting

    @model_validator(mode="after")
    def coherent(self):
        if self.state == "available" and (self.projection is None or self.projection.state != "available"):
            raise ValueError("available snapshot requires available projection")
        if self.q4_attempted and not self.q4_considered:
            raise ValueError("attempted Q4 must be considered")
        return self
