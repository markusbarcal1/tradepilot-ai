"""Pure bridge from selected/retrieved filings to reviewed revenue-Q4 input."""
from __future__ import annotations

import hashlib
import json

from app.models.outlook_inline_revenue import (
    RevenueOperandReplayContext, RevenueOperandReplayProvenance, RevenueOperandReplayUnit,
)
from app.models.outlook_revenue_filing_document import RevenueFilingDocumentBatchResult
from app.models.outlook_revenue_filing_selection import RevenueFilingSelectionResult
from app.models.outlook_revenue_q4 import RevenueQ4DerivationInput, RevenueQ4Operand
from app.models.outlook_revenue_runtime_input import (
    RevenueQ4RuntimeInputBuildResult, RuntimeOperandEvidence, RuntimeQualificationOutcome,
)
from .inline_revenue_operand import (
    PARTITION_IDENTITY_POLICY_VERSION, POLICY_VERSION as QUALIFIER_POLICY,
    qualify_inline_revenue_operand, validate_revenue_operand_partition,
)
from .revenue_filing_document import POLICY_VERSION as RETRIEVAL_POLICY
from .revenue_filing_selection import POLICY_VERSION as SELECTION_POLICY


BUILDER_POLICY = "revenue-q4-runtime-input-builder-1"
_ROLES = ("FY", "Q1", "Q2", "Q3")


def _failed(selection, state, reason, *, role=None, outcomes=(), evidence=(), partition=None):
    return RevenueQ4RuntimeInputBuildResult(builder_policy=BUILDER_POLICY, state=state,
        issuer=selection.issuer, cik=selection.cik,
        target_fiscal_year=selection.target_fiscal_year, reason=reason, failed_role=role,
        qualification_outcomes=tuple(outcomes), operand_evidence=tuple(evidence),
        partition=partition)


def _derivation_operand(operand):
    return RevenueQ4Operand(role=operand.role,
        exact_decimal_value=operand.numeric.normalized_value,
        expanded_qname=operand.expanded_qname,
        canonical_unit=RevenueOperandReplayUnit(
            numerator_measures=operand.unit.numerator_measures,
            denominator_measures=operand.unit.denominator_measures,
            structural_form=operand.unit.structural_form, currency=operand.unit.currency),
        context=RevenueOperandReplayContext(entity_scheme=operand.context.entity_scheme,
            entity_value=operand.context.entity_value, period_start=operand.context.period_start,
            period_end=operand.context.period_end,
            explicit_dimensions=operand.context.explicit_dimensions,
            typed_dimension_count=operand.context.typed_dimension_count),
        accounting_basis=operand.accounting_basis, target_fiscal_year=operand.target_fiscal_year,
        reporting_scope=operand.reporting_scope, ticker=operand.ticker,
        accession=operand.accession, primary_document=operand.primary_document,
        source_url=operand.source_url, qualifier_state="qualified", replay_state="complete",
        provenance=RevenueOperandReplayProvenance(policy_version=operand.policy_version,
            selector_policy=operand.selector_policy, fact_ordinal=operand.fact_ordinal,
            node_ordinal=operand.node_ordinal, occurrence_ordinals=operand.occurrence_ordinals,
            context_id=operand.context_id, unit_id=operand.unit_id,
            dei_anchor=operand.dei_anchor))


def _fingerprint(selection, documents, evidence, partition):
    content = {"builder_policy": BUILDER_POLICY, "selection_policy": SELECTION_POLICY,
        "retrieval_policy": RETRIEVAL_POLICY, "qualifier_policy": QUALIFIER_POLICY,
        "partition_policy": partition.partition_policy_version, "issuer": selection.issuer,
        "cik": selection.cik, "target_fiscal_year": selection.target_fiscal_year,
        "documents": [{"role": row.role, "accession": row.selected_document.accession,
            "primary_document": row.selected_document.primary_document,
            "sha256": row.fingerprint} for row in documents],
        "operands": [row.qualified_operand.model_dump(mode="json") for row in evidence],
        "concept_identity": partition.concept_identity.model_dump(mode="json")
            if partition.concept_identity else None}
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_revenue_q4_runtime_input(selection: RevenueFilingSelectionResult,
        retrieval: RevenueFilingDocumentBatchResult, *, qualifier=qualify_inline_revenue_operand,
        partition_validator=validate_revenue_operand_partition):
    """Qualify exact retrieved bytes and construct input; performs no Q4 arithmetic."""
    if selection.state != "selected":
        return _failed(selection, "unavailable", "selection_unavailable")
    if retrieval.state != "available":
        return _failed(selection, "unavailable", "retrieval_unavailable")
    if selection.policy_version != SELECTION_POLICY:
        return _failed(selection, "conflict", "selection_policy_unsupported")
    if retrieval.policy_version != RETRIEVAL_POLICY:
        return _failed(selection, "conflict", "retrieval_policy_unsupported")
    selected = {row.role: row for row in selection.selected_filings}
    documents = {row.role: row for row in retrieval.documents}
    if tuple(selected) != _ROLES or tuple(documents) != _ROLES:
        return _failed(selection, "conflict", "role_set_invalid")
    ordered_documents = []
    for role in _ROLES:
        expected, retrieved = selected[role], documents[role]
        if (expected.document != retrieved.selected_document
                or expected.metadata_provenance != retrieved.selection_provenance
                or retrieval.issuer != selection.issuer or retrieval.cik != selection.cik
                or retrieval.target_fiscal_year != selection.target_fiscal_year
                or retrieved.role != retrieved.selected_document.expected_role):
            return _failed(selection, "conflict", "identity_mismatch", role=role)
        if (retrieved.retrieval_policy != RETRIEVAL_POLICY
                or retrieved.byte_length != len(retrieved.body)
                or hashlib.sha256(retrieved.body).hexdigest() != retrieved.fingerprint):
            return _failed(selection, "conflict", "document_integrity_conflict", role=role)
        ordered_documents.append(retrieved)

    outcomes, evidence, qualified = [], [], {}
    for document in ordered_documents:
        try:
            result = qualifier(document.selected_document, document.body)
        except Exception:
            return _failed(selection, "unavailable", "qualification_unavailable",
                role=document.role, outcomes=outcomes, evidence=evidence)
        outcome = RuntimeQualificationOutcome(role=document.role, state=result.state,
            reasons=result.failure_reasons[:32], document_sha256=document.fingerprint,
            qualifier_policy=result.policy_version,
            fiscal_anchor_diagnostic=result.fiscal_anchor_diagnostic)
        outcomes.append(outcome)
        if result.state != "qualified":
            state = "conflict" if result.state in {"conflict", "ambiguous"} else "unavailable"
            reason = "qualification_conflict" if state == "conflict" else "qualification_unavailable"
            return _failed(selection, state, reason, role=document.role,
                outcomes=outcomes, evidence=evidence)
        operand = result.operand
        converted = _derivation_operand(operand)
        qualified[document.role] = operand
        evidence.append(RuntimeOperandEvidence(role=document.role,
            document_sha256=document.fingerprint, retrieval_policy=document.retrieval_policy,
            qualifier_policy=operand.policy_version, qualified_operand=operand,
            derivation_operand=converted))

    try:
        partition = partition_validator(annual=qualified["FY"], q1=qualified["Q1"],
            q2=qualified["Q2"], q3=qualified["Q3"])
    except Exception:
        return _failed(selection, "conflict", "builder_internal_failure",
            outcomes=outcomes, evidence=evidence)
    if partition.partition_policy_version != PARTITION_IDENTITY_POLICY_VERSION:
        return _failed(selection, "conflict", "partition_conflict",
            outcomes=outcomes, evidence=evidence, partition=partition)
    if partition.state != "valid":
        state = "conflict" if partition.state == "conflict" else "unavailable"
        return _failed(selection, state, "partition_conflict" if state == "conflict"
            else "partition_unavailable", outcomes=outcomes, evidence=evidence, partition=partition)
    converted = {row.role: row.derivation_operand for row in evidence}
    derivation_input = RevenueQ4DerivationInput(annual=converted["FY"], q1=converted["Q1"],
        q2=converted["Q2"], q3=converted["Q3"], partition=partition)
    fingerprint = _fingerprint(selection, ordered_documents, evidence, partition)
    return RevenueQ4RuntimeInputBuildResult(builder_policy=BUILDER_POLICY, state="ready",
        issuer=selection.issuer, cik=selection.cik,
        target_fiscal_year=selection.target_fiscal_year,
        qualification_outcomes=tuple(outcomes), operand_evidence=tuple(evidence),
        partition=partition, derivation_input=derivation_input,
        evidence_fingerprint=fingerprint)
