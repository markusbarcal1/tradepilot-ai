"""Offline EPS-history public contract and Analyze integration tests."""
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace

from app.config import Settings
from app.services.outlook_research import _Sources, _eps_history
from app.services.outlook_structured.sec_history import (
    SecHistoricalFinancialProvider, normalize_companyfacts,
)


NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)
CIK = 1045810


def fact(value, *, fy=2026, fp="Q2", start="2026-04-28", end="2026-07-27",
         filed="2026-08-20", accn="0001045810-26-000100", form="10-Q"):
    return {"start": start, "end": end, "val": value, "accn": accn,
        "fy": fy, "fp": fp, "form": form, "filed": filed}


def annual(year, value, ordinal=1, **changes):
    values = {"fy": year, "fp": "FY", "start": f"{year - 1}-01-29",
        "end": f"{year}-01-28", "filed": f"{year}-02-20",
        "accn": f"0001045810-{year % 100:02d}-{ordinal:06d}", "form": "10-K"}
    values.update(changes)
    return fact(value, **values)


def inputs(diluted=(), basic=()):
    facts = {"EarningsPerShareDiluted": {"units": {"USD/shares": list(diluted)}}}
    if basic:
        facts["EarningsPerShareBasic"] = {"units": {"USD/shares": list(basic)}}
    rows = list(diluted) + list(basic)
    unique = list({row["accn"]: row for row in rows}.values())
    submissions = {"cik": CIK, "name": "Synthetic Issuer", "filings": {"recent": {
        "accessionNumber": [row["accn"] for row in unique],
        "form": [row["form"] for row in unique],
        "filingDate": [row["filed"] for row in unique],
        "acceptanceDateTime": [f"{row['filed']}T20:00:00Z" for row in unique],
        "reportDate": [row["end"] for row in unique],
        "primaryDocument": ["report.htm" for _ in unique],
    }}}
    return {"cik": CIK, "entityName": "Synthetic Issuer",
        "facts": {"us-gaap": facts}}, submissions


def snapshot(diluted=(), basic=()):
    companyfacts, submissions = inputs(diluted, basic)
    return normalize_companyfacts(companyfacts, submissions, "NVDA", NOW)


def test_disabled_contract_is_stable_and_defaults_are_off():
    dto = _eps_history(unavailable_reason="feature_disabled")
    assert dto.annual.state == dto.quarterly.state == "unavailable"
    assert dto.annual.reasons == dto.quarterly.reasons == ("feature_disabled",)
    assert dto.annual_points == dto.quarterly_points == ()
    settings = Settings(_env_file=None, environment="test")
    assert settings.outlook_historical_eps_enabled is False
    assert "OUTLOOK_HISTORICAL_EPS_ENABLED=false" in (
        Path(__file__).parents[2] / ".env.example").read_text(encoding="utf-8")


def test_enabled_contract_preserves_exact_signed_decimals_and_resolvable_sources():
    q1 = fact("-0.42", fy=2026, fp="Q1", start="2026-01-27", end="2026-04-27",
        filed="2026-05-20", accn="0001045810-26-000001")
    q2 = fact("0", accn="0001045810-26-000002")
    source_registry = _Sources()
    dto = _eps_history(snapshot([annual(2025, "-1.20"), annual(2026, "0", 3), q1, q2]),
        source_registry, None)
    assert dto.annual.state == dto.quarterly.state == "available"
    assert dto.share_basis == "diluted" and dto.accounting_basis == "gaap"
    assert [row.exact_eps for row in dto.annual_points] == [Decimal("-1.20"), Decimal("0")]
    assert [row.exact_eps for row in dto.quarterly_points] == [Decimal("-0.42"), Decimal("0")]
    raw = json.loads(dto.model_dump_json())
    assert [row["exact_eps"] for row in raw["annual_points"]] == ["-1.20", "0"]
    assert [row["exact_eps"] for row in raw["quarterly_points"]] == ["-0.42", "0"]
    public_ids = {source.id for source in source_registry.rows.values()}
    assert all(set(row.source_ids) <= public_ids for row in (*dto.annual_points, *dto.quarterly_points))
    serialized = dto.model_dump_json()
    for forbidden in ("evidence_fingerprint", "observation_id", "accession", "source_url"):
        assert forbidden not in serialized


def test_missing_periods_make_only_the_affected_frequency_partial():
    q3 = fact("0.30", fy=2025, fp="Q3", start="2025-07-01", end="2025-09-30",
        filed="2025-11-01", accn="0001045810-25-000003")
    q1 = fact("0.40", fy=2026, fp="Q1", start="2026-01-01", end="2026-03-31",
        filed="2026-05-01", accn="0001045810-26-000001")
    dto = _eps_history(snapshot([annual(2024, "0.50"), annual(2026, "0.75", 2), q3, q1]),
        _Sources(), None)
    assert dto.annual.state == dto.quarterly.state == "partial"
    assert dto.annual.reasons == dto.quarterly.reasons == ("missing_fiscal_periods",)
    assert len(dto.annual_points) == len(dto.quarterly_points) == 2
    assert dto.annual.earliest_fiscal_period == "FY2024"
    assert dto.quarterly.latest_fiscal_period == "FY2026:Q1"


def test_conflicted_quarter_does_not_suppress_certified_annual_history():
    first = fact("0.50", accn="0001045810-26-000001")
    second = fact("0.60", accn="0001045810-27-000001", filed="2027-02-20")
    dto = _eps_history(snapshot([annual(2026, "1.00", 3), first, second]), _Sources(), None)
    assert dto.annual.state == "available" and len(dto.annual_points) == 1
    assert dto.quarterly.state == "conflict" and dto.quarterly_points == ()
    assert dto.quarterly.reasons == ("conflicted_fiscal_periods",)


def test_basic_only_is_unavailable_and_never_publicly_substituted():
    dto = _eps_history(snapshot(basic=[annual(2026, "1.25")]), _Sources(), None)
    assert dto.annual.state == dto.quarterly.state == "unavailable"
    assert dto.annual.reasons == dto.quarterly.reasons == ("no_certified_observations",)
    assert dto.annual_points == dto.quarterly_points == ()


def test_amendment_status_and_safe_provenance_are_public():
    original = annual(2026, "1.00")
    amended = annual(2026, "0.90", 2, filed="2026-03-01", form="10-K/A")
    q_original = fact("0.20", accn="0001045810-26-000003")
    q_amended = fact("0.18", filed="2026-09-01", accn="0001045810-26-000004", form="10-Q/A")
    dto = _eps_history(snapshot([original, amended, q_original, q_amended]), _Sources(), None)
    assert dto.annual_points[0].reporting_status == "amended"
    assert dto.quarterly_points[0].reporting_status == "amended"
    assert "amended" in dto.annual_points[0].provenance_label.lower()
    assert "amended" in dto.quarterly_points[0].provenance_label.lower()


class Client:
    def __init__(self, companyfacts, submissions):
        self.companyfacts, self.submissions, self.calls = companyfacts, submissions, []

    def get(self, url, **kwargs):
        self.calls.append(url)
        if "company_tickers" in url:
            return {"0": {"ticker": "NVDA", "cik_str": CIK}}
        return self.companyfacts if "companyfacts" in url else self.submissions


def test_shared_cold_and_warm_acquisition_has_no_incremental_requests():
    companyfacts, submissions = inputs([annual(2026, "1.00")])
    client = Client(companyfacts, submissions)
    settings = Settings(_env_file=None, environment="test", outlook_historical_eps_enabled=True,
        outlook_sec_user_agent="TradePilot test operator@example.com")
    provider = SecHistoricalFinancialProvider(settings, client, lambda: NOW, enabled=True)
    cold = provider.get_acquisition("NVDA")
    warm = provider.get_acquisition("NVDA")
    assert len(client.calls) == 3
    assert cold.logical_requests == cold.http_attempts == 3
    assert warm.logical_requests == warm.http_attempts == 0
    assert warm.cache_state == "success_hit"


def test_analyze_eps_failure_isolated_from_revenue_and_report(monkeypatch):
    from tests.test_revenue_history_analyze_integration import route_fixture, unavailable_snapshot

    main, _, _ = route_fixture(monkeypatch, unavailable_snapshot())
    monkeypatch.setattr(main.settings, "outlook_historical_eps_enabled", True)
    monkeypatch.setattr(main, "get_historical_financial_acquisition",
        lambda ticker: (_ for _ in ()).throw(RuntimeError("synthetic internal failure")))
    result = main.outlook_analysis("NVDA")
    assert result.status == "available" and result.analysis is not None
    assert result.research.revenue_history.availability == "unavailable"
    assert result.research.eps_history.annual.reasons == ("historical_acquisition_unavailable",)
    assert result.research.industry is not None and result.research.market is not None


def test_analyze_disabled_does_not_touch_shared_eps_acquisition(monkeypatch):
    from tests.test_revenue_history_analyze_integration import route_fixture, unavailable_snapshot

    main, _, _ = route_fixture(monkeypatch, unavailable_snapshot())
    monkeypatch.setattr(main.settings, "outlook_historical_eps_enabled", False)
    monkeypatch.setattr(main, "get_historical_financial_acquisition",
        lambda ticker: (_ for _ in ()).throw(AssertionError("EPS acquisition must remain disabled")))
    result = main.outlook_analysis("NVDA")
    assert result.status == "available"
    assert result.research.eps_history.annual.reasons == ("feature_disabled",)
    assert result.research.eps_history.quarterly.reasons == ("feature_disabled",)


def test_analyze_enabled_projects_supplied_cached_snapshot(monkeypatch):
    from tests.test_revenue_history_analyze_integration import route_fixture, unavailable_snapshot

    certified = snapshot([annual(2026, "-0.10")])
    main, _, _ = route_fixture(monkeypatch, unavailable_snapshot())
    monkeypatch.setattr(main.settings, "outlook_historical_eps_enabled", True)
    monkeypatch.setattr(main, "get_historical_financial_acquisition",
        lambda ticker: SimpleNamespace(snapshot=certified))
    result = main.outlook_analysis("NVDA")
    assert result.research.eps_history.annual.state == "available"
    assert result.research.eps_history.annual_points[0].exact_eps == Decimal("-0.10")
    source_ids = {source.id for source in result.research.sources}
    assert set(result.research.eps_history.annual_points[0].source_ids) <= source_ids


def test_public_annual_points_expose_only_safe_comparison_break_metadata():
    certified = snapshot([annual(2025, "1.00"), annual(2026, "2.00", 2)])
    dto = _eps_history(certified, _Sources(), None)
    assert dto.annual_points[1].comparison_break_before is True
    assert dto.annual_points[0].disclosure_type == "original_period"
    serialized = dto.model_dump_json()
    assert "comparison_group" not in serialized
    assert "action_identities" not in serialized
    assert "eps_document_evidence_state" not in serialized
    assert "eps_document_failure_reasons" not in serialized
    assert "loader_error" not in serialized


def test_quarterly_points_from_distinct_filings_do_not_assume_comparability():
    q1 = fact("0.10", fy=2026, fp="Q1", start="2026-01-27", end="2026-04-27",
        filed="2026-05-20", accn="0001045810-26-000001")
    q2 = fact("0.20", fy=2026, fp="Q2", start="2026-04-28", end="2026-07-27",
        filed="2026-08-20", accn="0001045810-26-000002")
    dto = _eps_history(snapshot([q1, q2]), _Sources(), None)
    assert [row.comparison_break_before for row in dto.quarterly_points] == [False, True]
