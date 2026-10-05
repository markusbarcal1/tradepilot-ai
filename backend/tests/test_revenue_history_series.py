"""Offline quarterly revenue historical-series assembly tests."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import inspect
import json
from pathlib import Path

import pytest

from app.models.outlook_financial_history import HistoricalFinancialObservation
from app.models.outlook_revenue_history_series import RevenueHistoricalSeriesObservation
from app.services.outlook_structured.revenue_history_series import (
    adapt_historical_revenue, adapt_reconciled_revenue_q4,
    assemble_revenue_historical_series,
)
from app.services.outlook_structured.revenue_q4_derivation import (
    derivation_input_from_certified_artifact, derive_revenue_q4,
)
from app.services.outlook_structured.revenue_q4_reconciliation import reconcile_revenue_q4


ROOT = Path(__file__).parents[2]
CERTIFICATION = ROOT / "docs/diagnostics/phase6b5c2a5w10a-schema2-live-revenue-partition-certification-20261002.json"


def point(index, *, issuer="0000000001", value=None, source_kind="directly_reported",
        evidence_identity=None, **changes):
    year, quarter = index // 4, f"Q{index % 4 + 1}"
    start = date(2024, 1, 1) + timedelta(days=(index - 8096) * 91)
    data = dict(issuer_identity=issuer, fiscal_year=year, fiscal_period=quarter,
        period_start=start, period_end=start + timedelta(days=90), duration_days=91,
        exact_decimal_value=Decimal(value if value is not None else index),
        source_kind=source_kind, source_policy="synthetic-qualified-1",
        evidence_identity=evidence_identity or f"evidence-{index}")
    data.update(changes)
    return RevenueHistoricalSeriesObservation(**data)


def consecutive(count, start=8096, **changes):
    return [point(start + offset, **changes) for offset in range(count)]


@pytest.mark.parametrize("count,state,eligible", [(5, "available", True),
    (4, "insufficient_data", False), (8, "available", True)])
def test_consecutive_direct_thresholds(count, state, eligible):
    result = assemble_revenue_historical_series(consecutive(count))
    assert result.state == state and result.research_eligible is eligible
    assert result.consecutive_count == count and result.observation_count == count


def test_more_than_eight_retains_latest_consecutive_eight():
    rows = consecutive(10)
    result = assemble_revenue_historical_series(rows)
    assert result.observation_count == result.consecutive_count == 8
    assert result.observations == tuple(rows[-8:])


def test_missing_middle_breaks_continuity_and_is_reported():
    rows = consecutive(6); missing = rows.pop(2)
    result = assemble_revenue_historical_series(rows)
    assert result.state == "insufficient_data" and result.consecutive_count == 3
    assert f"FY{missing.fiscal_year}:{missing.fiscal_period}" in result.missing_periods


def test_non_adjacent_dates_break_continuity_without_calendar_guessing():
    rows = consecutive(5)
    rows[3] = rows[3].model_copy(update={"period_start": rows[3].period_start + timedelta(days=1),
        "duration_days": 90})
    result = assemble_revenue_historical_series(rows)
    assert result.state == "insufficient_data" and result.consecutive_count == 3


def test_identical_duplicate_collapses_but_distinct_duplicate_conflicts():
    rows = consecutive(5); duplicate = rows[2].model_copy()
    assert assemble_revenue_historical_series(rows + [duplicate]).state == "available"
    changed = rows[2].model_copy(update={"exact_decimal_value": rows[2].exact_decimal_value + 1})
    result = assemble_revenue_historical_series(rows + [changed])
    assert result.state == "conflict" and "duplicate_quarter_conflict" in result.conflicts


@pytest.mark.parametrize("field,value,reason", [
    ("canonical_unit", "EUR", "unit_mismatch"),
    ("currency", "EUR", "currency_mismatch"),
    ("accounting_basis", "other", "accounting_basis_mismatch"),
    ("reporting_scope", "other", "scope_mismatch"),
    ("issuer_identity", "0000000002", "issuer_identity_mismatch"),
])
def test_comparability_mismatch_is_conflict(field, value, reason):
    rows = consecutive(5); rows[-1] = rows[-1].model_copy(update={field: value})
    result = assemble_revenue_historical_series(rows)
    assert result.state == "conflict" and reason in result.conflicts


def test_overlap_and_reversed_period_fail_closed():
    rows = consecutive(5)
    rows[1] = rows[1].model_copy(update={"period_start": rows[0].period_end})
    assert "overlapping_periods" in assemble_revenue_historical_series(rows).conflicts
    reversed_row = rows[0].model_copy(update={"period_start": rows[0].period_end,
        "period_end": rows[0].period_start})
    assert "reversed_period" in assemble_revenue_historical_series([reversed_row]).conflicts


def historical(index, **changes):
    base = point(index); now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    data = dict(observation_id=base.evidence_identity, issuer="Issuer",
        ticker="TEST", cik=base.issuer_identity, metric="revenue",
        fiscal_year=base.fiscal_year, fiscal_quarter=base.fiscal_period,
        period_start=base.period_start, period_end=base.period_end,
        duration_days=base.duration_days, original_concept="Revenues",
        original_value=base.exact_decimal_value, original_unit="USD",
        normalized_value=base.exact_decimal_value, currency="USD",
        share_basis="not_applicable", accession="0000000001-26-000001",
        form="10-Q", filing_date=base.period_end, source_url="https://www.sec.gov/test",
        retrieved_at=now, version_status="current", comparison_eligible=True)
    data.update(changes)
    return HistoricalFinancialObservation(**data)


def test_existing_history_adapter_accepts_only_current_revenue():
    accepted = historical(8096)
    adapted = adapt_historical_revenue(accepted)
    assert adapted.source_kind == "directly_reported"
    assert adapted.historical_provenance is accepted
    rejected = accepted.model_copy(update={"version_status": "conflict",
        "comparison_eligible": False, "comparison_exclusion_reasons": ("conflict",)})
    assert adapt_historical_revenue(rejected) is None
    assert adapt_historical_revenue(accepted.model_copy(update={"metric": "diluted_eps"})) is None


@pytest.fixture(scope="module")
def artifact_context():
    certification = json.loads(CERTIFICATION.read_text(encoding="utf-8"))
    values = {}
    for ticker, year in (("AAPL", 2025), ("NVDA", 2026)):
        derived = derive_revenue_q4(derivation_input_from_certified_artifact(
            certification, ticker=ticker, fiscal_year=year)).observation
        values[ticker] = reconcile_revenue_q4(derived=derived)
    return values


@pytest.mark.parametrize("ticker,expected_count", [("AAPL", 7), ("NVDA", 6)])
def test_retained_artifact_longest_run_with_derived_q4_is_eligible(
        artifact_context, ticker, expected_count):
    path = ROOT / f"docs/diagnostics/phase6b5c2a2-{ticker.lower()}.json"
    artifact = json.loads(path.read_text(encoding="utf-8"))
    history = []
    for payload in artifact["observations"]:
        try:
            observation = HistoricalFinancialObservation.model_validate(payload)
        except Exception:
            continue
        adapted = adapt_historical_revenue(observation)
        if adapted is not None:
            history.append(adapted)
    result = assemble_revenue_historical_series(history,
        reconciled_q4=artifact_context[ticker])
    assert result.state == "available" and result.research_eligible
    assert result.consecutive_count == expected_count
    assert result.source_kind_summary.derived_count == 1
    assert result.source_kind_summary.directly_reported_count == expected_count - 1
    derived = next(row for row in result.observations if row.source_kind == "derived")
    assert derived.fiscal_period == "Q4"
    assert derived.q4_reconciliation_provenance is artifact_context[ticker]


def test_four_direct_plus_authoritative_derived_is_eligible(artifact_context):
    q4 = adapt_reconciled_revenue_q4(artifact_context["AAPL"])
    q4_index = q4.fiscal_year * 4 + 3
    rows = consecutive(3, start=q4_index - 3, issuer=q4.issuer_identity)
    next_q1 = point(q4_index + 1, issuer=q4.issuer_identity)
    rows[0] = rows[0].model_copy(update={"period_start": q4.period_start - timedelta(days=273),
        "period_end": q4.period_start - timedelta(days=183)})
    rows[1] = rows[1].model_copy(update={"period_start": rows[0].period_end + timedelta(days=1),
        "period_end": rows[0].period_end + timedelta(days=91)})
    rows[2] = rows[2].model_copy(update={"period_start": rows[1].period_end + timedelta(days=1),
        "period_end": q4.period_start - timedelta(days=1)})
    rows[2] = rows[2].model_copy(update={"duration_days": (rows[2].period_end-rows[2].period_start).days+1})
    next_q1 = next_q1.model_copy(update={"period_start": q4.period_end + timedelta(days=1),
        "period_end": q4.period_end + timedelta(days=91)})
    result = assemble_revenue_historical_series(rows + [next_q1],
        reconciled_q4=artifact_context["AAPL"])
    assert result.state == "available" and result.source_kind_summary.derived_count == 1


def test_unavailable_and_conflicted_q4_never_enter_series(artifact_context):
    four = consecutive(4)
    unavailable = reconcile_revenue_q4()
    result = assemble_revenue_historical_series(four, reconciled_q4=unavailable)
    assert result.state == "insufficient_data" and result.observation_count == 4
    conflict = artifact_context["AAPL"].model_copy(update={"state": "conflict",
        "authoritative_source_kind": None, "authoritative_observation": None,
        "reasons": ("synthetic",)})
    result = assemble_revenue_historical_series(four, reconciled_q4=conflict)
    assert result.state == "conflict" and "q4_reconciliation_conflict" in result.conflicts
    assert all(row.q4_reconciliation_provenance is None for row in result.observations)


def test_assembler_contains_no_growth_derivation_reconciliation_eps_or_network_path():
    import app.services.outlook_structured.revenue_history_series as module
    source = inspect.getsource(module).lower()
    for forbidden in ("yoy", "qoq", "growth", "fy -", "reconcile_revenue_q4",
            "derive_revenue_q4", "diluted_eps", "requests", "httpx", "transport"):
        assert forbidden not in source
