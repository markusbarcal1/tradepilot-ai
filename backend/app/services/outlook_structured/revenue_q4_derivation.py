"""Pure offline deterministic revenue-only Q4 derivation."""
from __future__ import annotations

from decimal import Decimal, DecimalException, localcontext
from datetime import timedelta

from pydantic import ValidationError

from app.models.outlook_inline_revenue import RevenueOperandPartitionResult
from app.models.outlook_revenue_q4 import (
    RevenueQ4DerivationInput, RevenueQ4DerivationResult, RevenueQ4DerivedObservation,
    RevenueQ4Operand, RevenueQ4OperandProvenance,
)
from .inline_revenue_document_certification import (
    ARTIFACT_SCHEMA, RUNNER_VERSION, replay_certification_artifact_partitions,
)


def _failed(state, *reasons):
    return RevenueQ4DerivationResult(state=state, reasons=tuple(dict.fromkeys(reasons)))


def derive_revenue_q4(inputs: RevenueQ4DerivationInput) -> RevenueQ4DerivationResult:
    """Subtract exact values only after independently rechecking every strict gate."""
    operands = (inputs.annual, inputs.q1, inputs.q2, inputs.q3)
    missing = tuple(f"missing_{role.lower()}_operand" for role, value in
        zip(("FY", "Q1", "Q2", "Q3"), operands) if value is None)
    if missing:
        return _failed("unavailable", *missing)
    annual, q1, q2, q3 = operands
    if (annual.role, q1.role, q2.role, q3.role) != ("FY", "Q1", "Q2", "Q3"):
        return _failed("conflict", "role_mismatch")
    if any(row.qualifier_state != "qualified" for row in operands):
        return _failed("unavailable", "operand_unqualified")
    if any(row.replay_state != "complete" for row in operands):
        return _failed("unavailable", "incomplete_replay_evidence")
    if any(not isinstance(row.exact_decimal_value, Decimal) for row in operands):
        return _failed("unavailable", "exact_decimal_value_unavailable")
    if any(not row.exact_decimal_value.is_finite() for row in operands):
        return _failed("conflict", "non_finite_operand_value")
    if inputs.partition is None:
        return _failed("unavailable", "partition_unavailable")
    partition = inputs.partition
    if partition.state != "valid":
        return _failed("unavailable" if partition.state == "unavailable" else "conflict",
            "partition_not_valid", *partition.reasons)
    if partition.reasons:
        return _failed("conflict", "partition_reasons_nonempty", *partition.reasons)
    if partition.concept_identity is None or partition.concept_identity.state == "mismatch":
        return _failed("conflict", "concept_identity_mismatch")
    if tuple(row.expanded_qname for row in operands) != partition.concept_identity.original_qnames:
        return _failed("conflict", "concept_provenance_mismatch")
    reference = annual
    identity_reasons = []
    if any(row.canonical_unit != reference.canonical_unit for row in operands[1:]):
        identity_reasons.append("unit_mismatch")
    if any(row.canonical_unit.currency != reference.canonical_unit.currency for row in operands[1:]):
        identity_reasons.append("currency_mismatch")
    if any((row.context.entity_scheme, row.context.entity_value) !=
            (reference.context.entity_scheme, reference.context.entity_value) for row in operands[1:]):
        identity_reasons.append("entity_mismatch")
    if any((row.context.explicit_dimensions, row.context.typed_dimension_count) !=
            (reference.context.explicit_dimensions, reference.context.typed_dimension_count)
            for row in operands[1:]):
        identity_reasons.append("dimension_mismatch")
    if any(row.accounting_basis != reference.accounting_basis for row in operands[1:]):
        identity_reasons.append("accounting_basis_mismatch")
    if any(row.reporting_scope != reference.reporting_scope for row in operands[1:]):
        identity_reasons.append("reporting_scope_mismatch")
    if any(row.target_fiscal_year != reference.target_fiscal_year for row in operands[1:]):
        identity_reasons.append("fiscal_year_mismatch")
    if any(row.ticker != reference.ticker for row in operands[1:]):
        identity_reasons.append("issuer_mismatch")
    if identity_reasons:
        return _failed("conflict", *identity_reasons)
    if any(row.context.explicit_dimensions or row.context.typed_dimension_count for row in operands):
        return _failed("conflict", "scope_mismatch")
    if (partition.residual_period_start is None or partition.residual_period_end is None
            or partition.residual_duration_days is None):
        return _failed("unavailable", "residual_period_unavailable")
    quarter_durations = tuple((row.context.period_end - row.context.period_start).days + 1
        for row in (q1, q2, q3))
    if (any(not 70 <= value <= 105 for value in quarter_durations)
            or annual.context.period_start != q1.context.period_start
            or q1.context.period_end + timedelta(days=1) != q2.context.period_start
            or q2.context.period_end + timedelta(days=1) != q3.context.period_start
            or q3.context.period_end >= annual.context.period_end):
        return _failed("conflict", "period_geometry_invalid")
    expected_start = q3.context.period_end + timedelta(days=1)
    duration = (partition.residual_period_end - partition.residual_period_start).days + 1
    if (partition.residual_period_start != expected_start
            or partition.residual_period_end != annual.context.period_end
            or duration != partition.residual_duration_days or not 70 <= duration <= 105):
        return _failed("conflict", "residual_period_invalid")
    try:
        with localcontext() as context:
            context.prec = max(100, *(len(row.exact_decimal_value.as_tuple().digits) +
                abs(row.exact_decimal_value.as_tuple().exponent) + 10 for row in operands))
            residual = (annual.exact_decimal_value - q1.exact_decimal_value
                - q2.exact_decimal_value - q3.exact_decimal_value)
            if not residual.is_finite():
                return _failed("conflict", "non_finite_derived_revenue")
            if residual < Decimal(0):
                return _failed("conflict", "negative_derived_revenue")
            if residual + q1.exact_decimal_value + q2.exact_decimal_value + q3.exact_decimal_value != annual.exact_decimal_value:
                return _failed("conflict", "arithmetic_invariant_failed")
    except (ArithmeticError, DecimalException):
        return _failed("conflict", "arithmetic_invalid")
    provenance = tuple(RevenueQ4OperandProvenance(role=row.role,
        original_qname=row.expanded_qname, exact_decimal_value=row.exact_decimal_value,
        period_start=row.context.period_start, period_end=row.context.period_end,
        accession=row.accession, primary_document=row.primary_document,
        source_url=row.source_url, context_id=row.provenance.context_id,
        unit_id=row.provenance.unit_id, fact_ordinal=row.provenance.fact_ordinal,
        node_ordinal=row.provenance.node_ordinal,
        occurrence_ordinals=row.provenance.occurrence_ordinals,
        qualifier_policy=row.provenance.policy_version,
        selector_policy=row.provenance.selector_policy, replay_state=row.replay_state)
        for row in operands)
    observation = RevenueQ4DerivedObservation(fiscal_year=annual.target_fiscal_year,
        period_start=partition.residual_period_start, period_end=partition.residual_period_end,
        duration_days=partition.residual_duration_days, exact_decimal_value=residual,
        canonical_unit=annual.canonical_unit, accounting_basis=annual.accounting_basis,
        reporting_scope=annual.reporting_scope, concept_identity=partition.concept_identity,
        operand_provenance=provenance, partition_policy=partition.partition_policy_version,
        equivalence_policy=partition.concept_identity.equivalence_policy_version)
    return RevenueQ4DerivationResult(state="derived", observation=observation)


def derivation_input_from_certified_artifact(artifact, *, ticker, fiscal_year):
    """Build an input only from complete schema-2 replay evidence and retained values."""
    if (not isinstance(artifact, dict) or artifact.get("schema_version") != ARTIFACT_SCHEMA
            or artifact.get("runner") != RUNNER_VERSION):
        return RevenueQ4DerivationInput(annual=None, q1=None, q2=None, q3=None, partition=None)
    replay = replay_certification_artifact_partitions(artifact)
    replayed = next((row for row in replay["partitions"] if row["ticker"] == ticker
        and row["target_fiscal_year"] == fiscal_year), None)
    partition = None
    if replayed and replayed["state"] == "replayed":
        partition = RevenueOperandPartitionResult.model_validate(replayed["partition_result"])
    values = {}
    for role in ("FY", "Q1", "Q2", "Q3"):
        row = next((item for item in artifact.get("roles", ()) if item.get("ticker") == ticker
            and item.get("target_fiscal_year") == fiscal_year and item.get("role") == role), None)
        if not row or row.get("qualifier_state") != "qualified" or row.get(
                "partition_replay_completeness", {}).get("state") != "complete":
            values[role] = None
            continue
        evidence, summary = row.get("partition_replay_evidence"), row.get("qualified_operand")
        try:
            if not isinstance(evidence, dict) or not isinstance(summary, dict):
                raise ValueError
            values[role] = RevenueQ4Operand(role=role,
                exact_decimal_value=summary["exact_decimal_value"],
                expanded_qname=evidence["expanded_qname"], canonical_unit=evidence["canonical_unit"],
                context=evidence["context"], accounting_basis=evidence["accounting_basis"],
                target_fiscal_year=evidence["target_fiscal_year"],
                reporting_scope=evidence["reporting_scope"], ticker=ticker,
                accession=row["accession"], primary_document=row["primary_document"],
                source_url=row["source_url"], qualifier_state="qualified", replay_state="complete",
                provenance=evidence["provenance"])
        except (KeyError, TypeError, ValueError, ValidationError):
            values[role] = None
    return RevenueQ4DerivationInput(annual=values["FY"], q1=values["Q1"],
        q2=values["Q2"], q3=values["Q3"], partition=partition)
