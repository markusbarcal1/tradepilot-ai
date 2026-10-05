"""Offline SEC Company Facts historical normalization tests."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.config import Settings
from app.cli.inspect_sec_history import AggregateSecRequestClient, main as inspect_main
from app.services.outlook_structured.sec_history import (
    SecHistoricalFinancialProvider, comparison_compatibility, normalize_companyfacts,
)
from app.services.outlook_structured.transport import ProviderUnavailable

NOW = datetime(2026, 9, 27, 18, tzinfo=timezone.utc)
CIK = 1045810


def settings(**changes):
    return Settings(_env_file=None, environment="test", outlook_sec_history_enabled=True,
        outlook_sec_user_agent="TradePilot test operator@example.com", **changes)


def fact(value, *, fy=2026, fp="Q2", start="2026-04-28", end="2026-07-27",
         filed="2026-08-20", accn="0001045810-26-000100", form="10-Q", frame=None):
    row = {"start": start, "end": end, "val": value, "accn": accn,
        "fy": fy, "fp": fp, "form": form, "filed": filed}
    if frame:
        row["frame"] = frame
    return row


def payload(revenue=None, diluted=None, basic=None, extra_facts=None):
    facts = {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {
            "units": {"USD": revenue or []}},
        "EarningsPerShareDiluted": {"units": {"USD/shares": diluted or []}},
    }
    if basic is not None:
        facts["EarningsPerShareBasic"] = {"units": {"USD/shares": basic}}
    facts.update(extra_facts or {})
    return {"cik": CIK, "entityName": "Synthetic Issuer", "facts": {"us-gaap": facts}}


def submissions(*rows):
    return {"filings": {"recent": {
        "accessionNumber": [row["accn"] for row in rows],
        "form": [row["form"] for row in rows],
        "filingDate": [row["filed"] for row in rows],
        "acceptanceDateTime": [row.get("accepted", row["filed"] + "T20:05:00Z") for row in rows],
        "primaryDocument": [row.get("primary", "report.htm") for row in rows],
        "reportDate": [row.get("report_date", row["end"]) for row in rows],
    }}}


def normalize(data, metadata=None, **limits):
    return normalize_companyfacts(data, metadata or submissions(), "NVDA", NOW, **limits)


def test_standard_quarterly_revenue_and_exact_diluted_eps_with_provenance():
    revenue = fact(30_040_000_000)
    eps = fact("0.67")
    result = normalize(payload([revenue], [eps]), submissions(revenue, eps))
    assert result.status == "available"
    assert {row.metric for row in result.observations} == {"revenue", "diluted_eps"}
    revenue_row = next(row for row in result.observations if row.metric == "revenue")
    eps_row = next(row for row in result.observations if row.metric == "diluted_eps")
    assert revenue_row.normalized_value == 30_040_000_000 and revenue_row.original_unit == "USD"
    assert eps_row.normalized_value == Decimal("0.67") and eps_row.share_basis == "diluted"
    assert revenue_row.period_id == "NVDA:FY2026:Q2" and revenue_row.duration_days == 91
    assert revenue_row.acceptance_time == datetime(2026, 8, 20, 20, 5, tzinfo=timezone.utc)
    assert revenue_row.source_url.endswith("/report.htm") and revenue_row.comparison_eligible


def test_missing_diluted_eps_and_basic_eps_never_substitute():
    revenue = fact(100)
    basic = fact("1.25")
    result = normalize(payload([revenue], [], [basic]), submissions(revenue, basic))
    assert result.status == "partial"
    assert [row.metric for row in result.observations] == ["revenue"]
    assert any(row.reason == "basic_eps_not_diluted" for row in result.rejected)


def test_noncalendar_fiscal_identity_and_53_week_quarter_use_explicit_fy_fp():
    row = fact(100, fy=2027, fp="Q1", start="2026-01-26", end="2026-05-03")
    result = normalize(payload([row]), submissions(row))
    accepted = result.observations[0]
    assert (accepted.fiscal_year, accepted.fiscal_quarter) == (2027, "Q1")
    assert accepted.duration_days == 98


def test_year_to_date_and_annual_contexts_are_not_quarterly_observations():
    ytd = fact(200, start="2026-01-27", end="2026-07-27")
    annual = fact(500, fp="FY", start="2025-01-27", end="2026-01-25", form="10-K")
    result = normalize(payload([ytd, annual]), submissions(ytd, annual))
    assert result.observations == ()
    assert {row.reason for row in result.rejected} >= {
        "not_standalone_quarter", "annual_period_not_normalized_in_this_phase"}


def test_missing_quarters_are_explicit_and_never_filled():
    q1 = fact(100, fp="Q1", start="2026-01-27", end="2026-04-27",
        accn="0001045810-26-000001", filed="2026-05-20")
    q3 = fact(130, fp="Q3", start="2026-07-28", end="2026-10-26",
        accn="0001045810-26-000003", filed="2026-11-20")
    result = normalize(payload([q1, q3]), submissions(q1, q3))
    assert [(row.fiscal_year, row.fiscal_quarter) for row in result.missing_periods] == [(2026, "Q2")]
    assert len(result.observations) == 2


def test_amendment_retains_original_and_selects_latest_supported_version():
    original = fact(100, accn="0001045810-26-000010", filed="2026-08-20")
    amended = fact(102, accn="0001045810-26-000011", filed="2026-09-01", form="10-Q/A")
    result = normalize(payload([original, amended]), submissions(original, amended))
    assert [row.version_status for row in result.observations] == ["superseded", "current"]
    assert result.observations[0].superseded_by == result.observations[1].observation_id
    assert result.observations[1].normalized_value == 102


def test_conflicting_non_amendment_values_suppress_comparison():
    original = fact(100, accn="0001045810-26-000010", filed="2026-08-20")
    conflict = fact(102, accn="0001045810-27-000010", filed="2027-02-20")
    result = normalize(payload([original, conflict]), submissions(original, conflict))
    assert result.status == "conflict"
    assert {row.version_status for row in result.observations} == {"conflict"}
    assert not any(row.comparison_eligible for row in result.observations)


def test_later_non_amendment_cannot_silently_override_an_amendment():
    original = fact(100, accn="0001045810-26-000010", filed="2026-08-20")
    amended = fact(102, accn="0001045810-26-000011", filed="2026-09-01", form="10-Q/A")
    later = fact(103, accn="0001045810-27-000010", filed="2027-02-20")
    result = normalize(payload([original, amended, later]), submissions(original, amended, later))
    assert result.status == "conflict"
    assert {row.version_status for row in result.observations} == {"conflict"}


def test_incompatible_currency_ambiguous_concepts_and_contexts_fail_closed():
    usd = fact(100)
    eur = fact(90, accn="0001045810-26-000101")
    legacy = fact(100, accn="0001045810-26-000102")
    alternate_context = fact(100, start="2026-04-21", accn="0001045810-26-000103")
    data = payload([usd, alternate_context], extra_facts={
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [usd, alternate_context], "EUR": [eur]}},
        "Revenues": {"units": {"USD": [legacy]}},
    })
    result = normalize(data, submissions(usd, eur, legacy, alternate_context))
    assert result.observations == ()
    reasons = {row.reason for row in result.rejected}
    assert "incompatible_unit" in reasons and "ambiguous_concept_mapping" in reasons


def test_ambiguous_context_same_concept_fails_closed():
    first = fact(100)
    second = fact(100, start="2026-04-21", accn="0001045810-26-000104")
    result = normalize(payload([first, second]), submissions(first, second))
    assert result.observations == ()
    assert any(row.reason == "ambiguous_quarterly_context" for row in result.rejected)


def test_negative_diluted_eps_and_duplicate_source_fact():
    eps = fact("-0.42")
    result = normalize(payload([], [eps, deepcopy(eps)]), submissions(eps))
    assert len(result.observations) == 1 and result.observations[0].normalized_value == Decimal("-0.42")
    assert any(row.reason == "duplicate_source_fact" for row in result.rejected)


def test_later_filing_comparative_fact_inherits_original_period_identity():
    original = fact(100, fy=2025, fp="Q1", start="2025-01-27", end="2025-04-27",
        filed="2025-05-20", accn="0001045810-25-000100")
    repeated = fact(100, fy=2026, fp="Q1", start="2025-01-27", end="2025-04-27",
        filed="2026-05-20", accn="0001045810-26-000100")
    repeated["report_date"] = "2026-04-26"
    result = normalize(payload([original, repeated]), submissions(original, repeated))
    assert result.status == "partial"
    assert {(row.fiscal_year, row.fiscal_quarter) for row in result.observations} == {(2025, "Q1")}
    assert [row.version_status for row in result.observations] == ["current", "duplicate"]
    assert sum(row.comparison_eligible for row in result.observations) == 1


def test_conflicting_anchored_fiscal_identities_fail_closed():
    first = fact(100, fy=2025, fp="Q1", start="2025-01-01", end="2025-03-31",
        filed="2025-05-01", accn="0001045810-25-000100")
    second = fact(100, fy=2026, fp="Q1", start="2025-01-01", end="2025-03-31",
        filed="2026-05-01", accn="0001045810-26-000100")
    result = normalize(payload([first, second]), submissions(first, second))
    assert result.observations == ()
    assert any(row.reason == "conflicting_fiscal_identity" for row in result.rejected)


def test_direct_standalone_q4_10k_is_accepted_but_annual_and_unanchored_are_not():
    q4 = fact(125, fy=2025, fp="FY", start="2025-10-01", end="2025-12-31",
        filed="2026-02-20", accn="0001045810-26-000010", form="10-K")
    annual = fact(500, fy=2025, fp="FY", start="2025-01-01", end="2025-12-31",
        filed="2026-02-20", accn="0001045810-26-000010", form="10-K")
    unanchored = fact(120, fy=2024, fp="FY", start="2024-10-01", end="2024-12-31",
        filed="2025-02-20", accn="0001045810-25-000010", form="10-K")
    unanchored["report_date"] = "2025-12-31"
    result = normalize(payload([q4, annual, unanchored]), submissions(q4, annual, unanchored))
    assert [(row.fiscal_year, row.fiscal_quarter, row.form, row.normalized_value)
        for row in result.observations] == [(2025, "Q4", "10-K", 125)]
    reasons = {row.reason for row in result.rejected}
    assert "annual_period_not_normalized_in_this_phase" in reasons
    assert "unresolved_fiscal_identity" in reasons


def test_supported_fact_rejections_precede_bounded_basic_eps_diagnostics():
    unsupported = fact(100, form="8-K")
    basics = [fact(index, accn=f"0001045810-26-{index:06}") for index in range(300)]
    result = normalize(payload([unsupported], basic=basics), submissions(unsupported))
    assert any(row.reason == "unsupported_form" for row in result.rejected)
    assert sum(row.reason == "basic_eps_not_diluted" for row in result.rejected) == 8


def test_source_cap_is_applied_after_newest_first_sorting():
    old = [fact(index, fy=2010, fp="Q1", start="2010-01-01", end="2010-03-31",
        filed="2010-05-01", accn=f"0001045810-10-{index:06}") for index in range(40)]
    recent = fact(999, fy=2026, fp="Q2", accn="0001045810-26-000999")
    result = normalize(payload([*old, recent]), submissions(recent), max_source_facts=32)
    assert any(row.fiscal_year == 2026 and row.normalized_value == 999 for row in result.observations)


def test_source_cap_interleaves_supported_concept_unit_streams():
    revenue = [fact(index, fy=2026, fp="Q2", accn=f"0001045810-26-{index:06}")
        for index in range(40)]
    eps = fact("0.67", accn="0001045810-26-000999")
    result = normalize(payload(revenue, [eps]), submissions(*revenue, eps), max_source_facts=8)
    assert any(row.metric == "diluted_eps" for row in result.observations)


def test_direct_q4_amendment_supersedes_exact_original_identity():
    original = fact(125, fy=2025, fp="FY", start="2025-10-01", end="2025-12-31",
        filed="2026-02-20", accn="0001045810-26-000010", form="10-K")
    amended = fact(127, fy=2025, fp="FY", start="2025-10-01", end="2025-12-31",
        filed="2026-03-01", accn="0001045810-26-000011", form="10-K/A")
    result = normalize(payload([original, amended]), submissions(original, amended))
    assert [(row.version_status, row.normalized_value) for row in result.observations] == [
        ("superseded", 125), ("current", 127)]


def test_strict_comparison_gate_checks_concept_period_and_active_version():
    q1 = fact(100, fy=2025, fp="Q2", start="2025-04-29", end="2025-07-28",
        accn="0001045810-25-000100", filed="2025-08-20")
    q2 = fact(120)
    result = normalize(payload([q1, q2]), submissions(q1, q2))
    left, right = result.observations
    assert comparison_compatibility(left, right, "year_over_year") == (True, ())
    assert not comparison_compatibility(left, right, "sequential")[0]
    incompatible = right.model_copy(update={"original_concept": "Revenues"})
    assert "incompatible_original_concept" in comparison_compatibility(left, incompatible, "year_over_year")[1]


class Client:
    def __init__(self, data, metadata, fail=False):
        self.data, self.metadata, self.fail, self.calls = data, metadata, fail, []
    def get(self, url, **kwargs):
        self.calls.append(url)
        if self.fail:
            raise TimeoutError("offline synthetic failure")
        if "company_tickers" in url:
            return {"0": {"ticker": "NVDA", "cik_str": CIK}}
        return self.data if "companyfacts" in url else self.metadata


def test_provider_cache_reuse_singleflight_and_bounded_requests():
    revenue = fact(100)
    client = Client(payload([revenue]), submissions(revenue))
    provider = SecHistoricalFinancialProvider(settings(), client, lambda: NOW)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: provider.get_history("nvda"), range(4)))
    assert all(result.observations[0].normalized_value == 100 for result in results)
    assert len(client.calls) == 3
    assert results[-1].diagnostics.cache_reads == 4
    assert results[-1].diagnostics.cache_loads == 1
    assert results[-1].diagnostics.cache_hits == 3


def test_provider_failure_is_cached_and_request_budget_is_enforced():
    broken = Client({}, {}, fail=True)
    provider = SecHistoricalFinancialProvider(settings(), broken, lambda: NOW)
    for _ in range(2):
        with pytest.raises(ProviderUnavailable):
            provider.get_history("NVDA")
    assert len(broken.calls) == 1

    revenue = fact(100)
    limited_client = Client(payload([revenue]), submissions(revenue))
    limited = SecHistoricalFinancialProvider(settings(outlook_sec_history_request_budget=2), limited_client, lambda: NOW)
    with pytest.raises(ProviderUnavailable):
        limited.get_history("NVDA")
    assert len(limited_client.calls) == 2


def test_provider_is_disabled_by_default_and_not_analyze_registered():
    provider = SecHistoricalFinancialProvider(Settings(_env_file=None, environment="test"), Client({}, {}), lambda: NOW)
    with pytest.raises(ProviderUnavailable):
        provider.get_history("NVDA")
    from app.services.outlook import configured_providers
    assert all(item.name != "sec_historical_financials" for item in configured_providers())


def test_offline_diagnostic_reports_periods_rejections_provenance_and_stats(capsys):
    fixture_path = Path(__file__).parent / "fixtures" / "sec-companyfacts-history.json"
    assert inspect_main(["--fixture", str(fixture_path)]) == 0
    output = capsys.readouterr().out
    assert '"accepted_periods": [' in output
    assert '"NVDA:FY2026:Q2"' in output
    assert '"comparison_eligibility"' in output and '"request_and_cache_statistics"' in output
    assert '"acceptance_time": "2026-08-20T20:05:00+00:00"' in output


def test_live_diagnostic_is_restricted_to_explicit_certification_tickers(capsys):
    with pytest.raises(SystemExit):
        inspect_main(["--live", "--ticker", "MSFT"])
    assert "restricted to AAPL, NVDA and ABTC" in capsys.readouterr().err


def test_aggregate_live_certification_client_counts_attempts_and_refuses_overrun():
    class Delegate:
        def __init__(self):
            self.calls = []
        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return {"ok": True}

    delegate = Delegate()
    client = AggregateSecRequestClient(delegate, limit=9)
    for index in range(9):
        assert client.get(f"https://data.sec.gov/{index}", provider="sec") == {"ok": True}
    with pytest.raises(ProviderUnavailable, match="aggregate_sec_request_budget_exceeded"):
        client.get("https://data.sec.gov/blocked", provider="sec")
    assert client.attempts == 9 and len(delegate.calls) == 9
