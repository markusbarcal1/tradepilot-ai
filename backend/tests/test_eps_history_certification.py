"""Offline certification tests for internal GAAP diluted EPS history."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

from app.services.outlook_structured.sec_history import (
    _acquisition_fingerprint, adapt_sec_submissions, normalize_companyfacts,
)


NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)
CIK = "0001045810"


def fact(value, *, fy=2026, fp="Q2", start="2026-04-28", end="2026-07-27",
         filed="2026-08-20", accn="0001045810-26-000100", form="10-Q"):
    return {"start": start, "end": end, "val": value, "accn": accn,
        "fy": fy, "fp": fp, "form": form, "filed": filed}


def annual(year, value, ordinal=1, **changes):
    defaults = {"fy": year, "fp": "FY", "start": f"{year - 1}-01-29",
        "end": f"{year}-01-28", "filed": f"{year}-02-20",
        "accn": f"0001045810-{year % 100:02d}-{ordinal:06d}", "form": "10-K"}
    defaults.update(changes)
    return fact(value, **defaults)


def payload(*, diluted=None, basic=None, diluted_units=None, revenue=None):
    units = diluted_units or {"USD/shares": diluted or []}
    facts = {"EarningsPerShareDiluted": {"units": units}}
    if basic is not None:
        facts["EarningsPerShareBasic"] = {"units": {"USD/shares": basic}}
    if revenue is not None:
        facts["RevenueFromContractWithCustomerExcludingAssessedTax"] = {
            "units": {"USD": revenue}}
    rows = [row for node in facts.values() for values in node["units"].values() for row in values]
    unique = {row["accn"]: row for row in rows}
    metadata = list(unique.values())
    submissions = {"cik": int(CIK), "name": "Synthetic Issuer", "filings": {"recent": {
        "accessionNumber": [row["accn"] for row in metadata],
        "form": [row["form"] for row in metadata],
        "filingDate": [row["filed"] for row in metadata],
        "acceptanceDateTime": [f"{row['filed']}T20:00:00Z" for row in metadata],
        "reportDate": [row["end"] for row in metadata],
        "primaryDocument": ["report.htm" for _ in metadata],
    }}}
    return {"cik": int(CIK), "entityName": "Synthetic Issuer",
        "facts": {"us-gaap": facts}}, submissions


def normalize(**kwargs):
    options = {key: kwargs.pop(key) for key in list(kwargs)
        if key.startswith("max_") or key == "annual_eps_comparability_evidence"}
    companyfacts, submissions = payload(**kwargs)
    return normalize_companyfacts(companyfacts, submissions, "NVDA", NOW, **options)


def test_annual_diluted_eps_preserves_signed_exact_values_and_retains_latest_five():
    rows = [annual(year, value) for year, value in zip(range(2020, 2027),
        ("-1.20", "0", "0.10", "0.25", "0.50", "0.75", "1.00"))]
    result = normalize(diluted=rows)
    assert [row.fiscal_year for row in result.annual_eps_observations] == list(range(2022, 2027))
    assert [row.exact_eps for row in result.annual_eps_observations] == [
        Decimal("0.10"), Decimal("0.25"), Decimal("0.50"), Decimal("0.75"), Decimal("1.00")]
    diagnostics = result.diagnostics.eps.annual
    assert diagnostics.state == "available"
    assert diagnostics.certified_fiscal_year_count == 7
    assert diagnostics.retained_fiscal_year_count == 5
    assert diagnostics.excluded_fiscal_years == (2020, 2021)
    assert all(row.accounting_basis == "gaap" and row.share_basis == "diluted"
        for row in result.annual_eps_observations)


def test_negative_and_zero_annual_eps_are_certified_without_growth_calculation():
    result = normalize(diluted=[annual(2025, "-0.42"), annual(2026, "0", 2)])
    assert [row.exact_eps for row in result.annual_eps_observations] == [Decimal("-0.42"), Decimal("0")]
    assert all("growth" not in row.model_dump() for row in result.annual_eps_observations)


def test_basic_only_never_substitutes_and_basic_plus_diluted_remains_diluted_only():
    basic = annual(2026, "1.25")
    basic_only = normalize(basic=[basic])
    assert basic_only.annual_eps_observations == ()
    assert any(row.reason == "basic_eps_not_diluted" for row in basic_only.rejected)

    diluted = annual(2026, "1.10", 2)
    together = normalize(diluted=[diluted], basic=[basic])
    assert [row.exact_eps for row in together.annual_eps_observations] == [Decimal("1.10")]
    assert together.annual_eps_observations[0].share_basis == "diluted"


def test_incompatible_units_and_non_gaap_alternatives_are_not_certified():
    wrong_unit = annual(2026, "1.10")
    result = normalize(diluted_units={"USD": [wrong_unit]})
    assert result.annual_eps_observations == ()
    assert any(row.reason == "incompatible_unit" for row in result.rejected)
    assert result.diagnostics.eps.annual.rejection_reasons == ("incompatible_unit",)

    companyfacts, submissions = payload(diluted=[])
    companyfacts["facts"]["us-gaap"]["AdjustedEarningsPerShareDiluted"] = {
        "units": {"USD/shares": [annual(2026, "2.10")]}}
    result = normalize_companyfacts(companyfacts, submissions, "NVDA", NOW)
    assert result.annual_eps_observations == ()


def test_quarterly_eps_rejects_ytd_accepts_noncalendar_zero_and_direct_q4():
    q1 = fact("0", fy=2027, fp="Q1", start="2026-01-26", end="2026-05-03",
        filed="2026-05-20", accn="0001045810-26-000001")
    ytd = fact("0.30", fy=2027, fp="Q2", start="2026-01-26", end="2026-08-02",
        filed="2026-08-20", accn="0001045810-26-000002")
    q4 = fact("-0.15", fy=2026, fp="FY", start="2025-10-27", end="2026-01-25",
        filed="2026-02-20", accn="0001045810-26-000003", form="10-K")
    result = normalize(diluted=[q1, ytd, q4])
    current = [row for row in result.observations
        if row.metric == "diluted_eps" and row.version_status == "current"]
    assert [(row.fiscal_year, row.fiscal_quarter, row.normalized_value) for row in current] == [
        (2026, "Q4", Decimal("-0.15")), (2027, "Q1", Decimal("0"))]
    assert any(row.reason == "not_standalone_quarter" for row in result.rejected)
    assert result.diagnostics.eps.quarterly.validated_candidate_count == 2
    assert "not_standalone_quarter" in result.diagnostics.eps.quarterly.rejection_reasons


def test_annual_53_week_period_is_valid_and_context_mismatch_fails_closed():
    long_year = annual(2026, "1.50", start="2025-01-27", end="2026-02-01")
    result = normalize(diluted=[long_year])
    assert result.annual_eps_observations[0].duration_days == 371

    companyfacts, submissions = payload(diluted=[long_year])
    submissions["filings"]["recent"]["reportDate"][0] = "2026-01-31"
    rejected = normalize_companyfacts(companyfacts, submissions, "NVDA", NOW)
    assert rejected.annual_eps_observations == ()
    assert rejected.diagnostics.eps.annual.year_outcomes[0].state == "rejected"


def test_amendment_supersedes_but_conflicting_regular_restatement_fails_closed():
    original = annual(2026, "1.00", filed="2026-02-20")
    amendment = annual(2026, "0.90", 2, filed="2026-03-01", form="10-K/A")
    amended = normalize(diluted=[original, amendment])
    assert amended.annual_eps_observations[0].exact_eps == Decimal("0.90")
    assert amended.annual_eps_observations[0].form == "10-K/A"

    restatement = annual(2026, "0.80", 3, filed="2026-03-02")
    conflict = normalize(diluted=[original, restatement])
    assert conflict.annual_eps_observations == ()
    assert conflict.diagnostics.eps.annual.year_outcomes[0].state == "conflict"


def test_duplicate_comparative_disclosures_and_ambiguous_contexts_are_conservative():
    row = annual(2026, "1.00")
    duplicate = normalize(diluted=[row, deepcopy(row)])
    assert len(duplicate.annual_eps_observations) == 1
    assert any(item.reason == "duplicate_source_fact" for item in duplicate.rejected)

    repeated = annual(2026, "1.00", 2, filed="2027-02-20")
    same_value = normalize(diluted=[row, repeated])
    assert len(same_value.annual_eps_observations) == 1

    other_context = annual(2026, "1.00", 3, start="2025-02-03", end="2026-02-01")
    conflicted = normalize(diluted=[row, other_context])
    assert conflicted.annual_eps_observations == ()
    assert conflicted.diagnostics.eps.annual.year_outcomes[0].reasons == ("ambiguous_annual_context",)


def test_missing_quarter_is_diagnostic_and_no_q4_is_fabricated():
    q3 = fact("0.30", fy=2025, fp="Q3", start="2025-07-01", end="2025-09-30",
        filed="2025-11-01", accn="0001045810-25-000003")
    q1 = fact("0.40", fy=2026, fp="Q1", start="2026-01-01", end="2026-03-31",
        filed="2026-05-01", accn="0001045810-26-000001")
    result = normalize(diluted=[q3, q1])
    assert result.diagnostics.eps.quarterly.missing_periods == ("FY2025:Q4",)
    assert not any(row.fiscal_quarter == "Q4" for row in result.observations)


def test_annual_eps_budget_never_partially_admits_a_year():
    newest = [annual(2026, "1.00", ordinal) for ordinal in range(1, 4)]
    older = annual(2025, "0.75")
    result = normalize(diluted=[*newest, older], max_annual_eps_source_facts=2)
    diagnostics = result.diagnostics.eps.annual
    assert result.annual_eps_observations == ()
    assert diagnostics.source_limit_state == "limit_exceeded"
    assert diagnostics.source_limit_excluded_fiscal_years == (2026, 2025)
    assert [(row.fiscal_year, row.state) for row in diagnostics.year_outcomes] == [
        (2025, "source_limit_excluded"), (2026, "source_limit_excluded")]


def test_eps_ordering_fingerprint_and_diagnostics_are_deterministic_and_sanitized():
    rows = [annual(2025, "-0.25"), annual(2026, "0.50", 2)]
    companyfacts, submissions = payload(diluted=list(reversed(rows)))
    first = normalize_companyfacts(companyfacts, submissions, "NVDA", NOW)
    second = normalize_companyfacts(companyfacts, submissions, "NVDA", NOW)
    typed = adapt_sec_submissions(submissions, issuer="Synthetic Issuer", cik=CIK,
        source_identity="eps-certification-fixture")
    assert [row.fiscal_year for row in first.annual_eps_observations] == [2025, 2026]
    assert _acquisition_fingerprint(first, typed) == _acquisition_fingerprint(second, typed)
    serialized = first.diagnostics.eps.model_dump(mode="json")
    forbidden = ("-0.25", "0.50", "0001045810", "https://", "fingerprint")
    assert not any(token in str(serialized) for token in forbidden)


def test_eps_certification_does_not_change_revenue_results():
    revenue = annual(2026, 100, accn="0001045810-26-000099")
    revenue["val"] = 100_000_000
    without_eps = normalize(revenue=[revenue])
    with_eps = normalize(revenue=[revenue], diluted=[annual(2026, "-0.10")])
    assert without_eps.annual_revenue_observations == with_eps.annual_revenue_observations
    assert without_eps.diagnostics.annual_revenue == with_eps.diagnostics.annual_revenue


def split_fixture(*, adjusted="1.19", evidence=True, direction="split", action_ids=("split-2024-10-for-1",)):
    original = annual(2024, "11.93", start="2023-01-30", end="2024-01-28",
        filed="2024-02-21", accn="0001045810-24-000029")
    current = annual(2025, "2.94", start="2024-01-29", end="2025-01-26",
        filed="2025-02-26", accn="0001045810-25-000023")
    comparative = annual(2025, adjusted, start="2023-01-30", end="2024-01-28",
        filed="2025-02-26", accn="0001045810-25-000023")
    companyfacts, submissions = payload(diluted=[original, current, comparative])
    index = submissions["filings"]["recent"]["accessionNumber"].index(current["accn"])
    submissions["filings"]["recent"]["reportDate"][index] = current["end"]
    proof = ({"accession": current["accn"],
        "adjustment_direction": direction, "action_identities": action_ids,
        "explicitly_retrospective_per_share": True,
        "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/report.htm"},) if evidence else ()
    return normalize_companyfacts(companyfacts, submissions, "NVDA", NOW,
        annual_eps_comparability_evidence=proof)


def test_nvda_like_split_selects_evidenced_comparative_without_arithmetic():
    result = split_fixture()
    assert [(row.fiscal_year, row.exact_eps) for row in result.annual_eps_observations] == [
        (2024, Decimal("1.19")), (2025, Decimal("2.94"))]
    assert result.annual_eps_observations[0].disclosure_type == "later_comparative"
    assert result.annual_eps_observations[0].split_adjustment_status == "explicit_retrospective"
    assert result.annual_eps_observations[1].comparison_break_before is False
    assert {row.exact_eps for row in result.annual_eps_source_observations
        if row.fiscal_year == 2024} == {Decimal("11.93"), Decimal("1.19")}
    assert Decimal("1.193") not in {row.exact_eps for row in result.annual_eps_source_observations}


def test_changed_comparative_without_filing_evidence_breaks_series():
    result = split_fixture(evidence=False)
    assert [row.exact_eps for row in result.annual_eps_observations] == [
        Decimal("11.93"), Decimal("2.94")]
    assert result.annual_eps_observations[1].comparison_break_before is True
    assert any(row.reason == "comparative_adjustment_evidence_missing" for row in result.rejected)


def test_reverse_split_and_multiple_actions_use_explicit_evidence_only():
    reverse = split_fixture(adjusted="119.3", direction="reverse_split",
        action_ids=("reverse-split-2024-1-for-10",))
    assert reverse.annual_eps_observations[0].exact_eps == Decimal("119.3")
    multiple = split_fixture(adjusted="2.38", direction="multiple_actions",
        action_ids=("split-one", "reverse-split-two"))
    assert multiple.annual_eps_observations[0].exact_eps == Decimal("2.38")


def test_conflicting_evidenced_comparatives_fail_closed():
    original_result = split_fixture()
    sources = [row for row in original_result.annual_eps_source_observations]
    original = annual(2024, "11.93", start="2023-01-30", end="2024-01-28",
        filed="2024-02-21", accn="0001045810-24-000029")
    current = annual(2025, "2.94", start="2024-01-29", end="2025-01-26",
        filed="2025-02-26", accn="0001045810-25-000023")
    one = annual(2025, "1.19", start=original["start"], end=original["end"],
        filed="2025-02-26", accn=current["accn"])
    two = annual(2026, "1.20", start=original["start"], end=original["end"],
        filed="2026-02-25", accn="0001045810-26-000021")
    host_two = annual(2026, "4.90", start="2025-01-27", end="2026-01-25",
        filed="2026-02-25", accn=two["accn"])
    companyfacts, submissions = payload(diluted=[original, current, one, host_two, two])
    recent = submissions["filings"]["recent"]
    recent["reportDate"][recent["accessionNumber"].index(current["accn"])] = current["end"]
    recent["reportDate"][recent["accessionNumber"].index(two["accn"])] = host_two["end"]
    proofs = tuple({"accession": accession, "adjustment_direction": "multiple_actions",
        "action_identities": (f"action-{index}",), "explicitly_retrospective_per_share": True,
        "source_url": ("https://www.sec.gov/Archives/edgar/data/1045810/"
            f"{accession.replace('-', '')}/report.htm")}
        for index, accession in enumerate((current["accn"], two["accn"]), 1))
    result = normalize_companyfacts(companyfacts, submissions, "NVDA", NOW,
        annual_eps_comparability_evidence=proofs)
    assert 2024 not in {row.fiscal_year for row in result.annual_eps_observations}
    assert any(row.reason == "conflicting_comparative_adjustments" for row in result.rejected)


def test_equal_comparative_chain_establishes_aapl_like_control_and_noncalendar_identity():
    fy2024 = annual(2024, "6.08", start="2023-10-01", end="2024-09-28",
        filed="2024-11-01", accn="0001045810-24-000123")
    fy2025 = annual(2025, "7.46", start="2024-09-29", end="2025-09-27",
        filed="2025-10-31", accn="0001045810-25-000079")
    comparative = annual(2025, "6.08", start=fy2024["start"], end=fy2024["end"],
        filed=fy2025["filed"], accn=fy2025["accn"])
    companyfacts, submissions = payload(diluted=[fy2024, fy2025, comparative])
    recent = submissions["filings"]["recent"]
    recent["reportDate"][recent["accessionNumber"].index(fy2025["accn"])] = fy2025["end"]
    result = normalize_companyfacts(companyfacts, submissions, "AAPL", NOW)
    assert [row.exact_eps for row in result.annual_eps_observations] == [Decimal("6.08"), Decimal("7.46")]
    assert result.annual_eps_observations[1].comparison_break_before is False
