"""Frozen result contracts for generic runtime revenue-Q4 input construction."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.outlook_inline_revenue import (
    FiscalAnchorSetDiagnostic, RevenueOperandPartitionResult, SecInlineRevenueOperand,
)
from app.models.outlook_revenue_q4 import RevenueQ4DerivationInput, RevenueQ4Operand


BuildReason = Literal["selection_unavailable", "retrieval_unavailable", "role_set_invalid",
    "identity_mismatch", "document_integrity_conflict", "selection_policy_unsupported",
    "retrieval_policy_unsupported", "qualification_unavailable", "qualification_conflict",
    "partition_unavailable", "partition_conflict", "builder_internal_failure"]


class RuntimeInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RuntimeQualificationOutcome(RuntimeInputModel):
    role: Literal["FY", "Q1", "Q2", "Q3"]
    state: Literal["qualified", "unavailable", "ambiguous", "conflict"]
    reasons: tuple[str, ...] = Field(default=(), max_length=32)
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    qualifier_policy: Literal["sec-inline-xbrl-revenue-operand-2"]
    fiscal_anchor_diagnostic: FiscalAnchorSetDiagnostic | None = None


class RuntimeOperandEvidence(RuntimeInputModel):
    role: Literal["FY", "Q1", "Q2", "Q3"]
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    retrieval_policy: Literal["revenue-filing-document-retrieval-1"]
    qualifier_policy: Literal["sec-inline-xbrl-revenue-operand-2"]
    qualified_operand: SecInlineRevenueOperand
    derivation_operand: RevenueQ4Operand


class RevenueQ4RuntimeInputBuildResult(RuntimeInputModel):
    builder_policy: Literal["revenue-q4-runtime-input-builder-1"]
    state: Literal["ready", "unavailable", "conflict"]
    issuer: str
    cik: str
    target_fiscal_year: int
    reason: BuildReason | None = None
    failed_role: Literal["FY", "Q1", "Q2", "Q3"] | None = None
    qualification_outcomes: tuple[RuntimeQualificationOutcome, ...] = Field(default=(), max_length=4)
    operand_evidence: tuple[RuntimeOperandEvidence, ...] = Field(default=(), max_length=4)
    partition: RevenueOperandPartitionResult | None = None
    derivation_input: RevenueQ4DerivationInput | None = None
    evidence_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def coherent(self):
        if self.state == "ready":
            if (self.reason is not None or self.failed_role is not None
                    or len(self.operand_evidence) != 4 or self.partition is None
                    or self.partition.state != "valid" or self.derivation_input is None
                    or self.evidence_fingerprint is None):
                raise ValueError("ready result requires complete validated runtime evidence")
        elif self.reason is None or self.derivation_input is not None or self.evidence_fingerprint is not None:
            raise ValueError("failed result cannot contain derivation input or evidence fingerprint")
        return self
