"""Pure offline research projection over an eligible assembled revenue series."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext

from app.models.outlook_revenue_history_series import RevenueHistoricalSeriesResult
from app.models.outlook_revenue_research import (
    RevenueGrowthResult, RevenueResearchProjectionResult, RevenueResearchQuarter,
    RevenueResearchSummary,
)


DISPLAY_QUANTUM = Decimal("0.1")
REVENUE_BILLION = Decimal("1000000000")
GROWTH_PRECISION = 50


def _quarter_index(year, quarter):
    return year * 4 + int(quarter[1]) - 1


def _unavailable(reason, current, comparison=None):
    return RevenueGrowthResult(state="unavailable", reason=reason,
        current_source_kind=current.source_kind,
        comparison_source_kind=comparison.source_kind if comparison else None,
        uses_derived_evidence=(current.source_kind == "derived" or
            (comparison is not None and comparison.source_kind == "derived")))


def _growth(current, comparison):
    if comparison.exact_decimal_value == Decimal(0):
        return _unavailable("zero_denominator", current, comparison)
    with localcontext() as context:
        context.prec = GROWTH_PRECISION
        exact = ((current.exact_decimal_value - comparison.exact_decimal_value)
            / comparison.exact_decimal_value * Decimal(100))
        display = exact.quantize(DISPLAY_QUANTUM, rounding=ROUND_HALF_UP)
    return RevenueGrowthResult(state="available", exact_growth_pct=exact,
        display_growth_pct=display, current_source_kind=current.source_kind,
        comparison_source_kind=comparison.source_kind,
        uses_derived_evidence=(current.source_kind == "derived"
            or comparison.source_kind == "derived"))


def project_revenue_research(series: RevenueHistoricalSeriesResult):
    """Project exact revenue and descriptive growth; never fetch, score, or forecast."""
    if not isinstance(series, RevenueHistoricalSeriesResult):
        return RevenueResearchProjectionResult(state="unavailable",
            reasons=("typed_series_required",))
    if series.state == "conflict":
        return RevenueResearchProjectionResult(state="conflict",
            issuer_identity=series.issuer_identity, reasons=("series_conflict", *series.reasons))
    if (series.state != "available" or not series.research_eligible
            or series.observation_count < 5 or len(series.observations) < 5):
        return RevenueResearchProjectionResult(state="unavailable",
            issuer_identity=series.issuer_identity, reasons=("research_eligible_series_required",))
    rows = series.observations
    incompatibilities = []
    identity = {(row.issuer_identity, row.metric, row.canonical_unit, row.currency,
        row.accounting_basis, row.reporting_scope) for row in rows}
    if len(identity) != 1: incompatibilities.append("series_comparability_conflict")
    for previous, current in zip(rows, rows[1:]):
        if (_quarter_index(current.fiscal_year, current.fiscal_period)
                - _quarter_index(previous.fiscal_year, previous.fiscal_period) != 1
                or current.period_start != previous.period_end + timedelta(days=1)):
            incompatibilities.append("series_not_consecutive")
        if current.period_start <= previous.period_end:
            incompatibilities.append("series_chronology_conflict")
    if incompatibilities:
        return RevenueResearchProjectionResult(state="conflict",
            issuer_identity=series.issuer_identity,
            reasons=tuple(dict.fromkeys(incompatibilities)))

    by_fiscal_identity = {(row.fiscal_year, row.fiscal_period): row for row in rows}
    points = []
    for index, row in enumerate(rows):
        previous = rows[index - 1] if index else None
        qoq = (_growth(row, previous) if previous is not None else
            _unavailable("first_observation", row))
        prior_year = by_fiscal_identity.get((row.fiscal_year - 1, row.fiscal_period))
        yoy = (_growth(row, prior_year) if prior_year is not None else
            _unavailable("prior_same_fiscal_quarter_unavailable", row))
        reconciliation_policy = derivation_policy = None
        if row.q4_reconciliation_provenance is not None:
            reconciliation_policy = row.q4_reconciliation_provenance.reconciliation_policy
            authoritative = row.q4_reconciliation_provenance.authoritative_observation
            if row.source_kind == "derived" and authoritative is not None:
                derivation_policy = authoritative.derivation_policy
        points.append(RevenueResearchQuarter(fiscal_year=row.fiscal_year,
            fiscal_quarter=row.fiscal_period,
            display_label=f"FY{row.fiscal_year} {row.fiscal_period}",
            period_start=row.period_start, period_end=row.period_end,
            duration_days=row.duration_days, exact_revenue=row.exact_decimal_value,
            revenue_billions=row.exact_decimal_value / REVENUE_BILLION,
            source_kind=row.source_kind, source_policy=row.source_policy,
            derived=row.source_kind == "derived", evidence_identity=row.evidence_identity,
            derivation_policy=derivation_policy,
            reconciliation_policy=reconciliation_policy, qoq=qoq, yoy=yoy))
    latest = points[-1]
    summary = RevenueResearchSummary(observation_count=len(points),
        directly_reported_count=sum(point.source_kind == "directly_reported" for point in points),
        derived_count=sum(point.source_kind == "derived" for point in points),
        earliest_quarter=points[0].display_label, latest_quarter=latest.display_label,
        latest_exact_revenue=latest.exact_revenue,
        latest_qoq_growth_pct=latest.qoq.exact_growth_pct,
        latest_yoy_growth_pct=latest.yoy.exact_growth_pct,
        available_qoq_comparisons=sum(point.qoq.state == "available" for point in points),
        available_yoy_comparisons=sum(point.yoy.state == "available" for point in points),
        minimum_exact_revenue=min(point.exact_revenue for point in points),
        maximum_exact_revenue=max(point.exact_revenue for point in points),
        absolute_change_first_to_latest=latest.exact_revenue - points[0].exact_revenue)
    return RevenueResearchProjectionResult(state="available",
        issuer_identity=series.issuer_identity, points=tuple(points), summary=summary)
