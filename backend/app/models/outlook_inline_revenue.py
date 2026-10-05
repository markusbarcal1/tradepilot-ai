"""Frozen internal contracts for selected-filing inline-XBRL revenue operands."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


POLICY_VERSION = "sec-inline-xbrl-revenue-operand-2"
SCHEMA_VERSION = "1"
OperandRole = Literal["FY", "Q1", "Q2", "Q3"]
QualificationState = Literal["qualified", "unavailable", "ambiguous", "conflict"]


class InlineRevenueModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExpandedQName(InlineRevenueModel):
    namespace_uri: str
    local_name: str


class TaxonomyConceptEquivalence(InlineRevenueModel):
    taxonomy_family: str
    local_name: str
    from_namespace: str
    to_namespace: str
    source_package_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    target_package_sha256: str = Field(pattern=r"^[A-F0-9]{64}$")
    certification_identity: str
    record_identity: str
    policy_version: str
    symmetric_for_identity: bool


class CertifiedConceptEquivalenceUse(InlineRevenueModel):
    record_identity: str
    source_package_sha256: str
    target_package_sha256: str


class RevenueConceptIdentityDiagnostic(InlineRevenueModel):
    state: Literal["exact_qname", "certified_cross_version_equivalence", "mismatch"]
    original_qnames: tuple[ExpandedQName, ...] = Field(min_length=4, max_length=4)
    equivalence_policy_version: str
    certified_records: tuple[CertifiedConceptEquivalenceUse, ...] = ()


class SelectedFilingDocument(InlineRevenueModel):
    ticker: str
    issuer: str
    cik: str
    target_fiscal_year: int = Field(ge=1900, le=2200)
    expected_role: OperandRole
    accession: str
    form: Literal["10-Q", "10-Q/A", "10-K", "10-K/A"]
    filing_date: date
    acceptance_time: AwareDatetime | None = None
    report_period_end: date
    primary_document: str
    source_url: str
    source_kind: Literal["inline_primary", "xbrl_instance"] = "inline_primary"
    selector_policy: str
    selection_state: Literal["selected", "unavailable", "ambiguous", "conflict"] = "selected"

    @model_validator(mode="after")
    def safe_identity(self):
        import re
        from urllib.parse import urlsplit

        if not re.fullmatch(r"\d{10}", self.cik):
            raise ValueError("CIK must contain exactly ten digits")
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", self.accession):
            raise ValueError("Unsafe accession")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}", self.primary_document):
            raise ValueError("Unsafe primary document identity")
        parts = urlsplit(self.source_url)
        if parts.scheme != "https" or parts.hostname not in {"www.sec.gov", "sec.gov"}:
            raise ValueError("Source must be an official SEC HTTPS URL")
        return self


class ContextIdentity(InlineRevenueModel):
    context_id: str
    entity_scheme: str
    entity_value: str
    period_kind: Literal["duration", "instant", "unavailable"]
    period_start: date | None = None
    period_end: date | None = None
    segment_present: bool = False
    scenario_present: bool = False
    explicit_dimensions: tuple[tuple[ExpandedQName, ExpandedQName], ...] = ()
    typed_dimension_count: int = Field(default=0, ge=0, le=16)


class UnitIdentity(InlineRevenueModel):
    unit_id: str
    numerator_measures: tuple[ExpandedQName, ...]
    denominator_measures: tuple[ExpandedQName, ...] = ()
    structural_form: Literal["measure", "divide", "malformed"]
    currency: str | None = None


class NumericIdentity(InlineRevenueModel):
    nil: bool
    decimals: str | None = None
    scale: int = 0
    sign: Literal["absent", "positive", "negative"] = "absent"
    transform: str = "absent"
    lexical_category: Literal["integer", "decimal", "grouped", "parenthesized", "invalid"]
    normalized_value: Decimal | None = None


class DeiAnchor(InlineRevenueModel):
    fiscal_year: int
    fiscal_period: Literal["FY", "Q1", "Q2", "Q3", "Q4"]
    period_end: date
    document_type: Literal["10-Q", "10-Q/A", "10-K", "10-K/A"]
    fact_ordinals: tuple[int, ...]


class RevenueOperandReplayContext(InlineRevenueModel):
    entity_scheme: str = Field(min_length=1, max_length=512)
    entity_value: str = Field(min_length=1, max_length=512)
    period_start: date
    period_end: date
    explicit_dimensions: tuple[tuple[ExpandedQName, ExpandedQName], ...] = Field(max_length=16)
    typed_dimension_count: int = Field(ge=0, le=16)


class RevenueOperandReplayUnit(InlineRevenueModel):
    numerator_measures: tuple[ExpandedQName, ...] = Field(min_length=1, max_length=16)
    denominator_measures: tuple[ExpandedQName, ...] = Field(max_length=16)
    structural_form: Literal["measure", "divide", "malformed"]
    currency: str | None = Field(max_length=32)


class RevenueOperandReplayProvenance(InlineRevenueModel):
    policy_version: str = Field(min_length=1, max_length=128)
    selector_policy: str = Field(min_length=1, max_length=128)
    fact_ordinal: int = Field(ge=0)
    node_ordinal: int = Field(ge=0)
    occurrence_ordinals: tuple[int, ...] = Field(max_length=256)
    context_id: str = Field(min_length=1, max_length=512)
    unit_id: str = Field(min_length=1, max_length=512)
    dei_anchor: DeiAnchor


class RevenueOperandReplayEvidence(InlineRevenueModel):
    schema_version: Literal["1"]
    role: OperandRole
    expanded_qname: ExpandedQName
    canonical_unit: RevenueOperandReplayUnit
    context: RevenueOperandReplayContext
    accounting_basis: Literal["gaap"]
    target_fiscal_year: int = Field(ge=1900, le=2200)
    reporting_scope: Literal["consolidated_entity"]
    provenance: RevenueOperandReplayProvenance


class RevenueOperandReplayOperand(InlineRevenueModel):
    role: OperandRole
    expanded_qname: ExpandedQName
    unit: RevenueOperandReplayUnit
    context: RevenueOperandReplayContext
    accounting_basis: Literal["gaap"]
    target_fiscal_year: int = Field(ge=1900, le=2200)
    reporting_scope: Literal["consolidated_entity"]
    provenance: RevenueOperandReplayProvenance


class PartitionReplayCompleteness(InlineRevenueModel):
    state: Literal["complete", "incomplete"]
    missing_fields: tuple[str, ...] = Field(default=(), max_length=32)


class FiscalAnchorObservationDiagnostic(InlineRevenueModel):
    raw_lexical_category: Literal["safe", "control_characters", "over_length"]
    raw_lexical_value: str | None = Field(default=None, max_length=64)
    occurrence_count: int = Field(ge=1, le=50_000)
    fact_ordinals: tuple[int, ...] = Field(default=(), max_length=32)
    namespace_identities: tuple[str, ...] = Field(default=(), max_length=16)
    source_kinds: tuple[Literal["inline", "instance"], ...] = Field(default=(), max_length=2)
    context_ref_present_count: int = Field(ge=0)
    context_ref_absent_count: int = Field(ge=0)
    visibility_categories: tuple[Literal["hidden", "visible"], ...] = Field(default=(), max_length=2)
    transform_categories: tuple[str, ...] = Field(default=(), max_length=16)
    transform_application_state: Literal["not_applicable", "applied", "unsupported",
        "unresolved", "invalid_lexical"] = "not_applicable"
    transformed_canonical_value: str | None = Field(default=None, max_length=64)
    continued_at_present_count: int = Field(ge=0)
    continued_at_absent_count: int = Field(ge=0)
    continuation_target_categories: tuple[Literal["not_applicable", "target_present", "target_absent"], ...] = Field(default=(), max_length=3)
    semantic_outcome: Literal["parsed", "parse_invalid"]
    normalized_semantic_value: str | None = Field(default=None, max_length=64)


class FiscalAnchorDiagnostic(InlineRevenueModel):
    required_local_name: Literal["DocumentFiscalYearFocus", "DocumentFiscalPeriodFocus",
        "DocumentPeriodEndDate", "DocumentType"]
    observation_count: int = Field(ge=0)
    distinct_stripped_raw_value_count: int = Field(ge=0)
    observations: tuple[FiscalAnchorObservationDiagnostic, ...] = Field(default=(), max_length=16)
    comparison: Literal["match", "mismatch", "not_comparable"]
    qualification_branch: Literal["duplicate_distinct", "fiscal_year_parse_invalid",
        "fiscal_period_parse_invalid", "period_end_parse_invalid",
        "period_end_transform_unsupported", "period_end_transform_unresolved",
        "period_end_transform_invalid_lexical",
        "document_type_parse_invalid", "year_mismatch", "role_mismatch",
        "period_end_mismatch", "form_mismatch", "anchor_unavailable", "anchor_valid"]
    diagnostic_cap_exceeded: bool = False


class FiscalAnchorSetDiagnostic(InlineRevenueModel):
    diagnostic_identity: Literal["inline-revenue-fiscal-anchor-diagnostic-2"] = (
        "inline-revenue-fiscal-anchor-diagnostic-2")
    schema_version: Literal["2"] = "2"
    anchors: tuple[FiscalAnchorDiagnostic, ...] = Field(min_length=4, max_length=4)
    diagnostic_cap_exceeded: bool = False


class SecInlineRevenueSourceFact(InlineRevenueModel):
    expanded_qname: ExpandedQName
    fact_ordinal: int = Field(ge=0)
    node_ordinal: int = Field(ge=0)
    occurrence_ordinals: tuple[int, ...]
    context: ContextIdentity | None = None
    unit: UnitIdentity | None = None
    numeric: NumericIdentity | None = None
    rejection_reasons: tuple[str, ...] = ()


class SecInlineRevenueOperand(InlineRevenueModel):
    schema_version: Literal["1"] = SCHEMA_VERSION
    policy_version: Literal["sec-inline-xbrl-revenue-operand-2"] = POLICY_VERSION
    metric: Literal["revenue"] = "revenue"
    role: OperandRole
    target_fiscal_year: int
    ticker: str
    issuer: str
    cik: str
    expanded_qname: ExpandedQName
    context: ContextIdentity
    unit: UnitIdentity
    numeric: NumericIdentity
    accounting_basis: Literal["gaap"] = "gaap"
    reporting_scope: Literal["consolidated_entity"] = "consolidated_entity"
    accession: str
    form: Literal["10-Q", "10-Q/A", "10-K", "10-K/A"]
    filing_date: date
    acceptance_time: AwareDatetime | None = None
    report_period_end: date
    primary_document: str
    source_url: str
    source_kind: Literal["inline_primary", "xbrl_instance"]
    selector_policy: str
    fact_ordinal: int
    node_ordinal: int
    occurrence_ordinals: tuple[int, ...]
    unit_id: str
    context_id: str
    dei_anchor: DeiAnchor
    duplicate_count: int = Field(ge=0)
    basis: Literal["source_operand"] = "source_operand"

    @model_validator(mode="after")
    def qualified_shape(self):
        if self.numeric.nil or self.numeric.normalized_value is None:
            raise ValueError("Qualified operand requires an exact numeric value")
        if self.context.period_kind != "duration" or not self.context.period_start or not self.context.period_end:
            raise ValueError("Qualified operand requires a duration context")
        if self.context.explicit_dimensions or self.context.typed_dimension_count:
            raise ValueError("Version 1 accepts zero-dimensional contexts only")
        return self


class SecInlineRevenueOperandResult(InlineRevenueModel):
    schema_version: Literal["1"] = SCHEMA_VERSION
    policy_version: Literal["sec-inline-xbrl-revenue-operand-2"] = POLICY_VERSION
    state: QualificationState
    selected_document: SelectedFilingDocument
    source_facts: tuple[SecInlineRevenueSourceFact, ...] = ()
    operand: SecInlineRevenueOperand | None = None
    failure_reasons: tuple[str, ...] = ()
    cap_states: tuple[str, ...] = ()
    dei_anchor: DeiAnchor | None = None
    fiscal_anchor_diagnostic: FiscalAnchorSetDiagnostic | None = None

    @model_validator(mode="after")
    def state_coherence(self):
        if (self.state == "qualified") != (self.operand is not None):
            raise ValueError("Only qualified results contain an operand")
        return self


class RevenueOperandPartitionResult(InlineRevenueModel):
    partition_policy_version: str
    state: Literal["valid", "unavailable", "conflict"]
    reasons: tuple[str, ...] = ()
    concept_identity: RevenueConceptIdentityDiagnostic | None = None
    residual_period_start: date | None = None
    residual_period_end: date | None = None
    residual_duration_days: int | None = None
