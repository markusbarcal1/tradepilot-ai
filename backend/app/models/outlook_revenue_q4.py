"""Immutable contracts for offline deterministic revenue-only Q4 derivation."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.outlook_inline_revenue import (
    ExpandedQName, RevenueConceptIdentityDiagnostic, RevenueOperandPartitionResult,
    RevenueOperandReplayContext, RevenueOperandReplayProvenance, RevenueOperandReplayUnit,
)


DERIVATION_POLICY_VERSION = "revenue-q4-derivation-1"
DERIVATION_SCHEMA_VERSION = "1"
FORMULA_IDENTITY = "FY-minus-Q1-minus-Q2-minus-Q3"


class RevenueQ4Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RevenueQ4Operand(RevenueQ4Model):
    role: Literal["FY", "Q1", "Q2", "Q3"]
    metric: Literal["revenue"] = "revenue"
    exact_decimal_value: Decimal
    expanded_qname: ExpandedQName
    canonical_unit: RevenueOperandReplayUnit
    context: RevenueOperandReplayContext
    accounting_basis: Literal["gaap"]
    target_fiscal_year: int = Field(ge=1900, le=2200)
    reporting_scope: Literal["consolidated_entity"]
    ticker: str = Field(min_length=1, max_length=16)
    accession: str = Field(pattern=r"^\d{10}-\d{2}-\d{6}$")
    primary_document: str = Field(min_length=1, max_length=255)
    source_url: str = Field(min_length=1, max_length=2048)
    qualifier_state: Literal["qualified"]
    replay_state: Literal["complete"]
    provenance: RevenueOperandReplayProvenance

    @field_validator("exact_decimal_value", mode="before")
    @classmethod
    def exact_decimal_only(cls, value):
        if isinstance(value, float):
            raise ValueError("binary floating point is forbidden")
        if not isinstance(value, (Decimal, str, int)) or isinstance(value, bool):
            raise ValueError("exact Decimal-compatible value required")
        return value

    @model_validator(mode="after")
    def finite_value(self):
        if not self.exact_decimal_value.is_finite():
            raise ValueError("non-finite monetary value")
        return self


class RevenueQ4DerivationInput(RevenueQ4Model):
    annual: RevenueQ4Operand | None
    q1: RevenueQ4Operand | None
    q2: RevenueQ4Operand | None
    q3: RevenueQ4Operand | None
    partition: RevenueOperandPartitionResult | None


class RevenueQ4OperandProvenance(RevenueQ4Model):
    role: Literal["FY", "Q1", "Q2", "Q3"]
    original_qname: ExpandedQName
    exact_decimal_value: Decimal
    period_start: date
    period_end: date
    accession: str
    primary_document: str
    source_url: str
    context_id: str
    unit_id: str
    fact_ordinal: int
    node_ordinal: int
    occurrence_ordinals: tuple[int, ...]
    qualifier_policy: str
    selector_policy: str
    replay_state: Literal["complete"]


class RevenueQ4DerivedObservation(RevenueQ4Model):
    schema_version: Literal["1"] = DERIVATION_SCHEMA_VERSION
    derivation_policy: Literal["revenue-q4-derivation-1"] = DERIVATION_POLICY_VERSION
    metric: Literal["revenue"] = "revenue"
    source_kind: Literal["derived"] = "derived"
    fiscal_year: int
    fiscal_period: Literal["Q4"] = "Q4"
    period_start: date
    period_end: date
    duration_days: int
    exact_decimal_value: Decimal
    canonical_unit: RevenueOperandReplayUnit
    accounting_basis: Literal["gaap"]
    reporting_scope: Literal["consolidated_entity"]
    concept_identity: RevenueConceptIdentityDiagnostic
    derivation_formula_identity: Literal["FY-minus-Q1-minus-Q2-minus-Q3"] = FORMULA_IDENTITY
    operand_provenance: tuple[RevenueQ4OperandProvenance, ...] = Field(min_length=4, max_length=4)
    partition_policy: str
    equivalence_policy: str
    derivation_state: Literal["derived"] = "derived"


class RevenueQ4DerivationResult(RevenueQ4Model):
    schema_version: Literal["1"] = DERIVATION_SCHEMA_VERSION
    derivation_policy: Literal["revenue-q4-derivation-1"] = DERIVATION_POLICY_VERSION
    state: Literal["derived", "unavailable", "conflict"]
    reasons: tuple[str, ...] = ()
    observation: RevenueQ4DerivedObservation | None = None

    @model_validator(mode="after")
    def coherent_state(self):
        if (self.state == "derived") != (self.observation is not None):
            raise ValueError("only a derived result contains an observation")
        return self
