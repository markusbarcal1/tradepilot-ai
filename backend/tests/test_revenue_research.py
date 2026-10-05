"""Offline tests for deterministic quarterly revenue research projection."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
import inspect
import json
from pathlib import Path

import pytest

from app.models.outlook_financial_history import HistoricalFinancialObservation
from app.models.outlook_revenue_history_series import (
    RevenueHistoricalSeriesObservation, RevenueHistoricalSeriesResult,
    RevenueSeriesSourceKindSummary,
)
from app.services.outlook_structured.revenue_history_series import (
    adapt_historical_revenue, assemble_revenue_historical_series,
)
from app.services.outlook_structured.revenue_q4_derivation import (
    derivation_input_from_certified_artifact, derive_revenue_q4,
)
from app.services.outlook_structured.revenue_q4_reconciliation import reconcile_revenue_q4
from app.services.outlook_structured.revenue_research import project_revenue_research


ROOT = Path(__file__).parents[2]
CERTIFICATION = ROOT / "docs/diagnostics/phase6b5c2a5w10a-schema2-live-revenue-partition-certification-20261002.json"


def point(index, value, *, source_kind="directly_reported"):
    year, quarter = index // 4, f"Q{index % 4 + 1}"
    start = date(2024, 1, 1) + timedelta(days=(index - 8096) * 91)
    return RevenueHistoricalSeriesObservation(issuer_identity="0000000001",
        fiscal_year=year, fiscal_period=quarter, period_start=start,
        period_end=start + timedelta(days=90), duration_days=91,
        exact_decimal_value=Decimal(value), source_kind=source_kind,
        source_policy="synthetic-qualified-1", evidence_identity=f"e-{index}",
        q4_reconciliation_provenance=None if source_kind == "directly_reported" else None)


def eligible(values):
    rows = tuple(point(8096 + index, value) for index, value in enumerate(values))
    return RevenueHistoricalSeriesResult(state="available", issuer_identity="0000000001",
        observations=rows, observation_count=len(rows), consecutive_count=len(rows),
        research_eligible=True, source_kind_summary=RevenueSeriesSourceKindSummary(
            directly_reported_count=len(rows), derived_count=0))


def actual_series(ticker, year):
    certification = json.loads(CERTIFICATION.read_text(encoding="utf-8"))
    derived = derive_revenue_q4(derivation_input_from_certified_artifact(
        certification, ticker=ticker, fiscal_year=year)).observation
    reconciled = reconcile_revenue_q4(derived=derived)
    artifact = json.loads((ROOT / f"docs/diagnostics/phase6b5c2a2-{ticker.lower()}.json").read_text(encoding="utf-8"))
    history = []
    for payload in artifact["observations"]:
        try:
            adapted = adapt_historical_revenue(HistoricalFinancialObservation.model_validate(payload))
        except Exception:
            adapted = None
        if adapted is not None: history.append(adapted)
    return assemble_revenue_historical_series(history, reconciled_q4=reconciled)


def test_five_quarter_eligible_series_projects_exact_values_and_labels():
    result = project_revenue_research(eligible([100, 110, 120, 130, 140]))
    assert result.state == "available" and len(result.points) == 5
    assert result.points[0].display_label == "FY2024 Q1"
    assert result.points[-1].exact_revenue == Decimal(140)
    assert result.points[-1].revenue_billions == Decimal("0.00000014")


def test_four_quarter_and_conflict_series_are_rejected():
    valid = eligible([100, 110, 120, 130, 140])
    four = valid.model_copy(update={"observations": valid.observations[:4],
        "observation_count": 4, "consecutive_count": 4, "research_eligible": False,
        "state": "insufficient_data"})
    assert project_revenue_research(four).state == "unavailable"
    conflict = valid.model_copy(update={"state": "conflict", "research_eligible": False,
        "reasons": ("synthetic",)})
    assert project_revenue_research(conflict).state == "conflict"


def test_qoq_exact_decimal_and_display_quantization():
    result = project_revenue_research(eligible([3, 4, 5, 6, 7]))
    growth = result.points[1].qoq
    with localcontext() as context:
        context.prec = 50
        expected = (Decimal(4) - Decimal(3)) / Decimal(3) * Decimal(100)
    assert growth.exact_growth_pct == expected
    assert growth.display_growth_pct == expected.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    assert growth.exact_growth_pct != growth.display_growth_pct


def test_zero_qoq_denominator_is_unavailable_not_infinite():
    result = project_revenue_research(eligible([0, 10, 20, 30, 40]))
    growth = result.points[1].qoq
    assert growth.state == "unavailable" and growth.reason == "zero_denominator"
    assert growth.exact_growth_pct is None


def test_yoy_uses_same_fiscal_quarter_one_year_apart():
    result = project_revenue_research(eligible([100, 200, 300, 400, 150, 300]))
    assert [point.yoy.state for point in result.points] == [
        "unavailable", "unavailable", "unavailable", "unavailable", "available", "available"]
    assert result.points[4].yoy.exact_growth_pct == Decimal(50)
    assert result.points[5].yoy.exact_growth_pct == Decimal(50)


def test_yoy_does_not_use_calendar_or_array_position_without_exact_fiscal_identity():
    series = eligible([100, 110, 120, 130, 140])
    last = series.observations[-1].model_copy(update={"fiscal_year": 2026})
    malformed = series.model_copy(update={"observations": (*series.observations[:-1], last)})
    result = project_revenue_research(malformed)
    assert result.state == "conflict" and "series_not_consecutive" in result.reasons


@pytest.mark.parametrize("ticker,year,count,yoy_count", [
    ("AAPL", 2025, 7, 3), ("NVDA", 2026, 6, 2)])
def test_actual_retained_series_projection(ticker, year, count, yoy_count):
    series = actual_series(ticker, year)
    result = project_revenue_research(series)
    assert result.state == "available" and len(result.points) == count
    assert result.summary.observation_count == count
    assert result.summary.derived_count == 1
    assert result.summary.directly_reported_count == count - 1
    assert result.summary.available_qoq_comparisons == count - 1
    assert result.summary.available_yoy_comparisons == yoy_count
    derived = next(point for point in result.points if point.derived)
    assert derived.source_kind == "derived"
    assert derived.derivation_policy == "revenue-q4-derivation-1"
    assert derived.reconciliation_policy == "revenue-q4-reconciliation-1"


def test_growth_on_both_sides_of_derived_q4_is_disclosed():
    result = project_revenue_research(actual_series("AAPL", 2025))
    q4_index = next(index for index, point in enumerate(result.points) if point.derived)
    assert result.points[q4_index].qoq.uses_derived_evidence is True
    assert result.points[q4_index - 1].source_kind == "directly_reported"
    assert result.points[q4_index + 1].qoq.uses_derived_evidence is True
    assert result.points[q4_index + 1].source_kind == "directly_reported"


@pytest.mark.parametrize("current_kind", ["directly_reported", "derived"])
def test_yoy_marks_derived_prior_or_current_evidence(current_kind):
    series = actual_series("AAPL", 2025)
    prior_q4 = next(row for row in series.observations if row.source_kind == "derived")
    previous = series.observations[-1]
    current_q4 = prior_q4.model_copy(update={"fiscal_year": 2026,
        "period_start": previous.period_end + timedelta(days=1),
        "period_end": previous.period_end + timedelta(days=91),
        "exact_decimal_value": Decimal("120000000000"),
        "source_kind": current_kind, "evidence_identity": f"synthetic-{current_kind}"})
    observations = (*series.observations, current_q4)
    summary = series.source_kind_summary.model_copy(update={
        "directly_reported_count": sum(row.source_kind == "directly_reported" for row in observations),
        "derived_count": sum(row.source_kind == "derived" for row in observations)})
    extended = series.model_copy(update={"observations": observations,
        "observation_count": 8, "consecutive_count": 8,
        "source_kind_summary": summary})
    growth = project_revenue_research(extended).points[-1].yoy
    assert growth.state == "available" and growth.uses_derived_evidence is True
    assert growth.comparison_source_kind == "derived"
    assert growth.current_source_kind == current_kind


def test_summary_latest_growth_and_descriptive_values_are_exact():
    result = project_revenue_research(eligible([100, 110, 120, 130, 150]))
    summary = result.summary
    assert summary.latest_exact_revenue == Decimal(150)
    assert summary.latest_qoq_growth_pct == result.points[-1].qoq.exact_growth_pct
    assert summary.latest_yoy_growth_pct == Decimal(50)
    assert summary.minimum_exact_revenue == Decimal(100)
    assert summary.maximum_exact_revenue == Decimal(150)
    assert summary.absolute_change_first_to_latest == Decimal(50)


def test_zero_yoy_denominator_is_unavailable():
    result = project_revenue_research(eligible([0, 10, 20, 30, 40]))
    assert result.points[-1].yoy.state == "unavailable"
    assert result.points[-1].yoy.reason == "zero_denominator"


def test_projection_has_no_float_network_eps_scoring_forecasting_or_production_dto_path():
    import app.services.outlook_structured.revenue_research as module
    source = inspect.getsource(module).lower()
    for forbidden in ("float(", "requests", "httpx", "transport", "diluted_eps",
            "score_", "bullish", "bearish", "forecast_", "outlook_research import"):
        assert forbidden not in source
