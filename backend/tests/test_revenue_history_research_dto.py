"""Offline integration tests for revenue history in research DTO schema 2."""
from datetime import datetime, timezone
from decimal import Decimal
import inspect
import json
from pathlib import Path

import pytest

from app.models.outlook_financial_history import HistoricalFinancialObservation
from app.models.outlook_revenue_research import RevenueResearchProjectionResult
from app.services.outlook_research import _revenue_history
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


def projection(ticker, year):
    certified = json.loads(CERTIFICATION.read_text(encoding="utf-8"))
    derived = derive_revenue_q4(derivation_input_from_certified_artifact(
        certified, ticker=ticker, fiscal_year=year)).observation
    reconciled = reconcile_revenue_q4(derived=derived)
    artifact = json.loads((ROOT / f"docs/diagnostics/phase6b5c2a2-{ticker.lower()}.json").read_text(encoding="utf-8"))
    history = []
    for payload in artifact["observations"]:
        try:
            adapted = adapt_historical_revenue(HistoricalFinancialObservation.model_validate(payload))
        except Exception:
            adapted = None
        if adapted is not None:
            history.append(adapted)
    return project_revenue_research(assemble_revenue_historical_series(
        history, reconciled_q4=reconciled))


@pytest.mark.parametrize("ticker,year,points,direct,derived,qoq,yoy", [
    ("AAPL", 2025, 7, 6, 1, 6, 3),
    ("NVDA", 2026, 6, 5, 1, 5, 2),
])
def test_actual_projection_maps_exact_counts_and_derived_provenance(
        ticker, year, points, direct, derived, qoq, yoy):
    dto = _revenue_history(projection(ticker, year))
    assert dto.availability == "available"
    assert (dto.observation_count, dto.directly_reported_count, dto.derived_count) == (
        points, direct, derived)
    assert (dto.qoq_comparison_count, dto.yoy_comparison_count) == (qoq, yoy)
    derived_point = next(row for row in dto.points if row.derived)
    assert derived_point.source_kind == "derived"
    assert derived_point.derivation_policy == "revenue-q4-derivation-1"
    assert derived_point.derivation_formula_identity == "FY-minus-Q1-minus-Q2-minus-Q3"
    assert derived_point.reconciliation_policy == "revenue-q4-reconciliation-1"


def test_decimal_values_and_growth_serialize_as_strings_without_float_change():
    dto = _revenue_history(projection("AAPL", 2025))
    raw = json.loads(dto.model_dump_json())
    derived = next(row for row in raw["points"] if row["derived"])
    assert derived["exact_revenue"] == "102466000000"
    assert derived["qoq"]["exact_growth_pct"] == (
        "8.9646518354672678548640946020672933770045514483815")
    assert derived["qoq"]["display_growth_pct"] == "9.0"
    assert derived["qoq"]["uses_derived_evidence"] is True
    assert isinstance(raw["latest_exact_revenue"], str)


def test_direct_and_derived_points_never_serialize_identically():
    dto = _revenue_history(projection("NVDA", 2026))
    raw = json.loads(dto.model_dump_json())
    direct = next(row for row in raw["points"] if not row["derived"])
    derived = next(row for row in raw["points"] if row["derived"])
    assert direct["source_kind"] == "directly_reported"
    assert derived["source_kind"] == "derived"
    assert direct["derivation_policy"] is None
    assert derived["derivation_policy"] == "revenue-q4-derivation-1"


def test_unavailable_insufficient_and_conflict_are_explicit():
    assert _revenue_history(None).availability == "unavailable"
    insufficient = RevenueResearchProjectionResult(state="unavailable",
        reasons=("research_eligible_series_required",))
    mapped = _revenue_history(insufficient)
    assert mapped.availability == "insufficient_data" and mapped.points == ()
    conflict = RevenueResearchProjectionResult(state="conflict",
        reasons=("series_conflict",))
    mapped = _revenue_history(conflict)
    assert mapped.availability == "conflict" and mapped.reasons == ("series_conflict",)


def test_mapper_copies_projection_values_without_financial_calculation():
    source = projection("AAPL", 2025)
    dto = _revenue_history(source)
    assert tuple(row.exact_revenue for row in dto.points) == tuple(
        row.exact_revenue for row in source.points)
    assert tuple(row.qoq.exact_growth_pct for row in dto.points) == tuple(
        row.qoq.exact_growth_pct for row in source.points)
    assert tuple(row.yoy.exact_growth_pct for row in dto.points) == tuple(
        row.yoy.exact_growth_pct for row in source.points)


def test_mapper_has_no_arithmetic_network_frontend_ai_or_eps_path():
    import app.services.outlook_research as module
    source = inspect.getsource(module._revenue_history).lower()
    for forbidden in (" + ", " - ", " * ", " / ", "float(", "requests", "httpx",
            "transport", "diluted_eps", "outlook_ai", "frontend"):
        assert forbidden not in source
