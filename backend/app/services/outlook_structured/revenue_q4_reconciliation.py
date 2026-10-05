"""Pure offline reconciliation of already-qualified direct and derived Q4 revenue."""
from __future__ import annotations

from decimal import Decimal

from app.models.outlook_q4 import DirectQ4Observation
from app.models.outlook_revenue_q4 import RevenueQ4DerivedObservation
from app.models.outlook_revenue_q4_reconciliation import (
    DirectRevenueQ4ReconciliationObservation, RevenueQ4ComparisonDiagnostics,
    RevenueQ4ReconciliationResult,
)


def adapt_direct_revenue_q4(observation: DirectQ4Observation):
    """Normalize representation without changing direct-q4-1 evidence semantics."""
    if (observation.metric != "revenue" or observation.fiscal_quarter != "Q4"
            or observation.share_basis != "not_applicable"
            or observation.version_status != "current" or not observation.comparison_eligible
            or observation.comparison_exclusion_reasons
            or observation.basis != "directly_reported"
            or not isinstance(observation.normalized_value, Decimal)
            or not observation.normalized_value.is_finite()):
        return None
    return DirectRevenueQ4ReconciliationObservation(fiscal_year=observation.fiscal_year,
        period_start=observation.period_start, period_end=observation.period_end,
        duration_days=observation.duration_days,
        exact_decimal_value=observation.normalized_value,
        canonical_unit=observation.original_unit, currency=observation.currency,
        accounting_basis=observation.accounting_basis,
        reporting_scope="consolidated_entity" if observation.reporting_scope == "consolidated" else observation.reporting_scope,
        issuer_identity=observation.ticker, concept_identity=observation.original_concept,
        observation=observation)


def _result(state, *, direct=None, derived=None, authoritative=None,
        source_kind=None, reasons=(), corroboration="none", checked=False,
        compared=False, agreement=None, mismatches=()):
    fiscal_year = (authoritative.fiscal_year if authoritative is not None else
        direct.fiscal_year if direct is not None else derived.fiscal_year if derived is not None else None)
    return RevenueQ4ReconciliationResult(state=state, fiscal_year=fiscal_year,
        authoritative_source_kind=source_kind, authoritative_observation=authoritative,
        direct_observation=direct, derived_observation=derived,
        corroboration_state=corroboration, reasons=tuple(reasons),
        comparison_diagnostics=RevenueQ4ComparisonDiagnostics(
            compatibility_checked=checked, value_compared=compared,
            exact_value_agreement=agreement, mismatch_classes=tuple(mismatches)))


def reconcile_revenue_q4(*, direct=None, derived=None):
    """Choose authority by exact policy; never retrieve, derive, or tolerance-match."""
    if direct is None and derived is None:
        return _result("unavailable", reasons=("q4_evidence_unavailable",))
    if direct is not None and (not isinstance(direct, DirectRevenueQ4ReconciliationObservation)
            or direct.qualification_state != "qualified"):
        return _result("conflict", direct=direct if isinstance(
            direct, DirectRevenueQ4ReconciliationObservation) else None,
            derived=derived if isinstance(derived, RevenueQ4DerivedObservation) else None,
            reasons=("direct_input_invalid",))
    if derived is not None and (not isinstance(derived, RevenueQ4DerivedObservation)
            or derived.derivation_state != "derived" or derived.source_kind != "derived"):
        return _result("conflict", direct=direct, reasons=("derived_input_invalid",))
    if direct is not None and direct.precision_state != "exact":
        return _result("conflict", direct=direct, derived=derived,
            reasons=("rounded_direct_value_unsupported",))
    if direct is None:
        return _result("available", derived=derived, authoritative=derived,
            source_kind="derived")
    if derived is None:
        return _result("available", direct=direct, authoritative=direct,
            source_kind="directly_reported")

    mismatches = []
    if direct.metric != derived.metric: mismatches.append("metric_mismatch")
    if direct.fiscal_year != derived.fiscal_year: mismatches.append("fiscal_year_mismatch")
    if direct.fiscal_period != derived.fiscal_period: mismatches.append("fiscal_period_mismatch")
    if (direct.period_start, direct.period_end, direct.duration_days) != (
            derived.period_start, derived.period_end, derived.duration_days):
        mismatches.append("period_mismatch")
    derived_measures = derived.canonical_unit.numerator_measures
    derived_unit = (derived_measures[0].local_name if len(derived_measures) == 1
        and not derived.canonical_unit.denominator_measures
        and derived.canonical_unit.structural_form == "measure" else None)
    if direct.canonical_unit != derived_unit: mismatches.append("unit_mismatch")
    if direct.currency != derived.canonical_unit.currency: mismatches.append("currency_mismatch")
    if direct.accounting_basis != derived.accounting_basis:
        mismatches.append("accounting_basis_mismatch")
    if direct.reporting_scope != derived.reporting_scope: mismatches.append("scope_mismatch")
    derived_issuer = derived.operand_provenance[0].accession[:10] if derived.operand_provenance else None
    direct_cik = direct.observation.cik
    if direct.issuer_identity != direct.observation.ticker or (
            derived_issuer is not None and direct_cik != derived_issuer):
        mismatches.append("issuer_identity_mismatch")
    if mismatches:
        return _result("conflict", direct=direct, derived=derived,
            reasons=tuple(mismatches), checked=True, mismatches=tuple(mismatches))
    agreement = direct.exact_decimal_value == derived.exact_decimal_value
    if not agreement:
        return _result("conflict", direct=direct, derived=derived,
            reasons=("direct_derived_value_mismatch",), checked=True,
            compared=True, agreement=False)
    return _result("available", direct=direct, derived=derived, authoritative=direct,
        source_kind="directly_reported", corroboration="derived_exact_agreement",
        checked=True, compared=True, agreement=True)
