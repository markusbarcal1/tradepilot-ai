"""Pure offline assembly of already-qualified quarterly revenue evidence."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256

from app.models.outlook_financial_history import HistoricalFinancialObservation
from app.models.outlook_revenue_history_series import (
    RevenueHistoricalSeriesObservation, RevenueHistoricalSeriesResult,
    RevenueSeriesSourceKindSummary,
)
from app.models.outlook_revenue_q4_reconciliation import RevenueQ4ReconciliationResult


def _quarter_index(year, quarter):
    return year * 4 + int(quarter[1]) - 1


def _period_label(index):
    return f"FY{index // 4}:Q{index % 4 + 1}"


def adapt_historical_revenue(observation: HistoricalFinancialObservation):
    """Adapt only current accepted quarterly revenue; never requalify raw facts."""
    if (observation.metric != "revenue" or observation.frequency != "quarterly"
            or observation.duration_semantics != "standalone_quarter"
            or observation.version_status != "current" or not observation.comparison_eligible
            or observation.comparison_exclusion_reasons
            or observation.original_unit != "USD" or observation.currency != "USD"
            or observation.accounting_basis != "gaap"
            or observation.reporting_scope != "sec_company_fact_entity"
            or observation.share_basis != "not_applicable"):
        return None
    return RevenueHistoricalSeriesObservation(issuer_identity=observation.cik,
        fiscal_year=observation.fiscal_year, fiscal_period=observation.fiscal_quarter,
        period_start=observation.period_start, period_end=observation.period_end,
        duration_days=observation.duration_days,
        exact_decimal_value=observation.normalized_value,
        source_kind="directly_reported", source_policy="historical-financial-observation-schema-1",
        evidence_identity=observation.observation_id,
        historical_provenance=observation)


def adapt_reconciled_revenue_q4(result: RevenueQ4ReconciliationResult):
    """Adapt only available authoritative reconciled Q4; never redo precedence."""
    if (result.state != "available" or result.authoritative_observation is None
            or result.authoritative_source_kind not in ("directly_reported", "derived")):
        return None
    source = result.authoritative_observation
    if source.metric != "revenue" or source.fiscal_period != "Q4":
        return None
    if result.authoritative_source_kind == "directly_reported":
        issuer = source.observation.cik
        value, unit, currency = source.exact_decimal_value, source.canonical_unit, source.currency
        accounting, scope = source.accounting_basis, source.reporting_scope
    else:
        accessions = tuple(row.accession for row in source.operand_provenance)
        ciks = {value[:10] for value in accessions}
        if len(ciks) != 1:
            return None
        issuer = next(iter(ciks)); value = source.exact_decimal_value
        measures = source.canonical_unit.numerator_measures
        unit = measures[0].local_name if (len(measures) == 1
            and not source.canonical_unit.denominator_measures
            and source.canonical_unit.structural_form == "measure") else None
        currency = source.canonical_unit.currency
        accounting, scope = source.accounting_basis, source.reporting_scope
    if (unit != "USD" or currency != "USD" or accounting != "gaap"
            or scope != "consolidated_entity"):
        return None
    identity = sha256(result.model_dump_json().encode("utf-8")).hexdigest()[:32]
    return RevenueHistoricalSeriesObservation(issuer_identity=issuer,
        fiscal_year=source.fiscal_year, fiscal_period="Q4",
        period_start=source.period_start, period_end=source.period_end,
        duration_days=source.duration_days, exact_decimal_value=value,
        source_kind=result.authoritative_source_kind,
        source_policy=result.reconciliation_policy, evidence_identity=identity,
        q4_reconciliation_provenance=result)


def assemble_revenue_historical_series(observations, *, reconciled_q4=None):
    """Assemble, collision-check, and retain the latest bounded consecutive run."""
    accepted = [row for row in observations
        if isinstance(row, RevenueHistoricalSeriesObservation)]
    q4_issue = None
    if reconciled_q4 is not None:
        q4 = adapt_reconciled_revenue_q4(reconciled_q4)
        if q4 is not None:
            accepted.append(q4)
        elif reconciled_q4.state == "conflict":
            q4_issue = "q4_reconciliation_conflict"
        else:
            q4_issue = "q4_reconciliation_unavailable"
    empty_summary = RevenueSeriesSourceKindSummary(directly_reported_count=0, derived_count=0)
    if not accepted:
        return RevenueHistoricalSeriesResult(state="conflict" if q4_issue == "q4_reconciliation_conflict" else "insufficient_data",
            observation_count=0, consecutive_count=0, research_eligible=False,
            reasons=(q4_issue or "revenue_history_unavailable",),
            conflicts=(q4_issue,) if q4_issue == "q4_reconciliation_conflict" else (),
            source_kind_summary=empty_summary)

    conflicts = []
    if any(row.period_start > row.period_end for row in accepted):
        conflicts.append("reversed_period")
    identities = {(row.issuer_identity, row.canonical_unit, row.currency,
        row.accounting_basis, row.reporting_scope, row.metric) for row in accepted}
    if len(identities) != 1:
        fields = (("issuer_identity_mismatch", lambda row: row.issuer_identity),
            ("unit_mismatch", lambda row: row.canonical_unit),
            ("currency_mismatch", lambda row: row.currency),
            ("accounting_basis_mismatch", lambda row: row.accounting_basis),
            ("scope_mismatch", lambda row: row.reporting_scope),
            ("metric_mismatch", lambda row: row.metric))
        conflicts.extend(reason for reason, getter in fields if len({getter(row) for row in accepted}) != 1)
    grouped = {}
    for row in accepted:
        key = (row.issuer_identity, row.metric, row.fiscal_year, row.fiscal_period)
        grouped.setdefault(key, []).append(row)
    unique = []
    for rows in grouped.values():
        semantic = {(row.period_start, row.period_end, row.duration_days,
            row.exact_decimal_value, row.canonical_unit, row.currency,
            row.accounting_basis, row.reporting_scope, row.source_kind,
            row.source_policy, row.evidence_identity) for row in rows}
        if len(semantic) != 1:
            conflicts.append("duplicate_quarter_conflict")
        else:
            unique.append(rows[0])
    ordered = sorted(unique, key=lambda row: (row.period_start, row.period_end,
        _quarter_index(row.fiscal_year, row.fiscal_period)))
    if any(right.period_start <= left.period_end for left, right in zip(ordered, ordered[1:])):
        conflicts.append("overlapping_periods")
    issuer = accepted[0].issuer_identity
    if conflicts:
        return RevenueHistoricalSeriesResult(state="conflict", issuer_identity=issuer,
            observation_count=0, consecutive_count=0, research_eligible=False,
            reasons=tuple(dict.fromkeys(conflicts + ([q4_issue] if q4_issue else []))),
            conflicts=tuple(dict.fromkeys(conflicts)), source_kind_summary=empty_summary)

    runs, run = [], []
    for row in ordered:
        if not run:
            run = [row]
        else:
            previous = run[-1]
            adjacent_identity = (_quarter_index(row.fiscal_year, row.fiscal_period)
                - _quarter_index(previous.fiscal_year, previous.fiscal_period) == 1)
            adjacent_dates = row.period_start == previous.period_end + timedelta(days=1)
            if adjacent_identity and adjacent_dates:
                run.append(row)
            else:
                runs.append(run); run = [row]
    if run: runs.append(run)
    longest = max(runs, key=lambda rows: (len(rows), rows[-1].period_end))
    retained = tuple(longest[-8:])
    indices = {_quarter_index(row.fiscal_year, row.fiscal_period) for row in ordered}
    missing = tuple(_period_label(index) for index in range(min(indices), max(indices) + 1)
        if index not in indices)
    eligible = len(retained) >= 5
    reasons = [] if eligible else ["fewer_than_five_consecutive_quarters"]
    if q4_issue: reasons.append(q4_issue)
    derived = tuple(row for row in retained if row.source_kind == "derived")
    summary = RevenueSeriesSourceKindSummary(
        directly_reported_count=sum(row.source_kind == "directly_reported" for row in retained),
        derived_count=len(derived),
        derived_periods=tuple(f"FY{row.fiscal_year}:{row.fiscal_period}" for row in derived),
        derived_policies=tuple(row.source_policy for row in derived))
    final_state = ("conflict" if q4_issue == "q4_reconciliation_conflict" else
        "available" if eligible else "insufficient_data")
    return RevenueHistoricalSeriesResult(state=final_state,
        issuer_identity=issuer, observations=retained, observation_count=len(retained),
        consecutive_count=len(retained), research_eligible=eligible and final_state == "available",
        reasons=tuple(reasons), missing_periods=missing,
        conflicts=(q4_issue,) if q4_issue == "q4_reconciliation_conflict" else (),
        source_kind_summary=summary)
