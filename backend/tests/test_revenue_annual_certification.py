from datetime import datetime, timezone

from app.config import Settings
from app.models.outlook_financial_history import AnnualRevenueYearOutcome
from app.models.outlook_research import RevenueHistoryResearch
from app.services.outlook_research import _Sources, _revenue_history
from app.services.outlook_structured.revenue_history_snapshot import RevenueHistorySnapshotService
from app.services.outlook_structured.sec_history import (
    _acquisition_fingerprint, adapt_sec_submissions, normalize_companyfacts,
)


NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)
CIK = "0000320193"


def annual(year, value, accession, *, form="10-K", filed=None, start=None, end=None,
           concept="RevenueFromContractWithCustomerExcludingAssessedTax", fp="FY"):
    end = end or f"{year}-09-27"
    start = start or f"{year - 1}-09-29"
    return concept, {"start": start, "end": end, "val": value, "accn": accession,
        "fy": year, "fp": fp, "form": form, "filed": filed or f"{year}-10-31"}


def payload(rows, *, unit="USD"):
    by_concept = {}
    metadata = []
    for concept, row in rows:
        by_concept.setdefault(concept, {"units": {unit: []}})["units"][unit].append(row)
        metadata.append(row)
    facts = {"cik": int(CIK), "entityName": "Apple Inc.", "facts": {"us-gaap": by_concept}}
    submissions = {"cik": int(CIK), "name": "Apple Inc.", "filings": {"recent": {
        "accessionNumber": [row["accn"] for row in metadata],
        "form": [row["form"] for row in metadata],
        "filingDate": [row["filed"] for row in metadata],
        "acceptanceDateTime": [f"{row['filed']}T20:00:00Z" for row in metadata],
        "reportDate": [row["end"] for row in metadata],
        "primaryDocument": ["annual.htm" for _ in metadata],
    }}}
    return facts, submissions


def normalize(rows, *, unit="USD", **options):
    facts, submissions = payload(rows, unit=unit)
    return normalize_companyfacts(facts, submissions, "AAPL", NOW,
        max_source_facts=256, max_quarters=8, max_annual_periods=5, **options)


def test_aapl_style_taxonomy_transition_retains_five_most_recent_certified_years():
    rows = []
    for year in range(2016, 2026):
        concept = ("SalesRevenueNet" if year <= 2018
            else "RevenueFromContractWithCustomerExcludingAssessedTax")
        rows.append(annual(year, year * 100, f"0000320193-{year % 100:02d}-{year:06d}", concept=concept))
    result = normalize(rows)
    assert [row.fiscal_year for row in result.annual_revenue_observations] == [2021, 2022, 2023, 2024, 2025]
    diagnostics = result.diagnostics.annual_revenue
    assert diagnostics.source_limit_state == "complete"
    assert diagnostics.discovered_fiscal_year_count == diagnostics.certified_fiscal_year_count == 10
    assert diagnostics.retained_fiscal_year_count == 5
    assert diagnostics.excluded_fiscal_years == (2016, 2017, 2018, 2019, 2020)
    assert [(row.fiscal_year, row.state) for row in diagnostics.year_outcomes] == [
        (2016, "retention_excluded"), (2017, "retention_excluded"),
        (2018, "retention_excluded"), (2019, "retention_excluded"),
        (2020, "retention_excluded"), (2021, "certified"), (2022, "certified"),
        (2023, "certified"), (2024, "certified"), (2025, "certified")]


def test_annual_budget_never_partially_certifies_a_fiscal_year():
    rows = [
        annual(2025, 100, "0000320193-25-000001", concept="Revenues"),
        annual(2025, 100, "0000320193-25-000002", concept="SalesRevenueNet"),
        annual(2025, 100, "0000320193-25-000003"),
        annual(2024, 90, "0000320193-24-000001"),
    ]
    result = normalize(rows, max_annual_source_facts=2)
    assert result.annual_revenue_observations == ()
    diagnostics = result.diagnostics.annual_revenue
    assert diagnostics.source_limit_state == "limit_exceeded"
    assert diagnostics.source_limit_excluded_fiscal_years == (2025, 2024)
    assert diagnostics.validated_candidate_count == 0
    assert diagnostics.rejected_candidate_count == 4
    assert [(row.fiscal_year, row.state) for row in diagnostics.year_outcomes] == [
        (2024, "source_limit_excluded"), (2025, "source_limit_excluded")]
    assert any(row.reason == "annual_source_limit_exceeded" for row in result.rejected)


def test_successful_annual_certification_preserves_gaps_and_computes_only_adjacent_yoy():
    rows = [annual(2022, 100, "0000320193-22-000001"),
        annual(2023, 120, "0000320193-23-000001"),
        annual(2025, 180, "0000320193-25-000001")]
    result = normalize(rows)
    assert [row.fiscal_year for row in result.annual_revenue_observations] == [2022, 2023, 2025]
    assert result.annual_revenue_observations[1].yoy_growth_pct == 20
    assert result.annual_revenue_observations[2].yoy_growth_pct is None
    assert all(row.classification == "reported" for row in result.annual_revenue_observations)
    missing = next(row for row in result.diagnostics.annual_revenue.year_outcomes
        if row.fiscal_year == 2024)
    assert missing.state == "no_supported_candidate"
    assert missing.reasons == ("no_supported_candidate",)


def test_amendment_supersedes_original_but_conflicting_regular_restatement_fails_closed():
    original = annual(2025, 100, "0000320193-25-000001", filed="2025-10-30")
    amendment = annual(2025, 105, "0000320193-25-000002", form="10-K/A", filed="2025-11-10")
    amended = normalize([original, amendment])
    assert len(amended.annual_revenue_observations) == 1
    assert amended.annual_revenue_observations[0].exact_revenue == 105
    assert amended.annual_revenue_observations[0].provenance_label.endswith("(amended)")

    conflicting = normalize([original,
        annual(2025, 106, "0000320193-25-000003", filed="2025-11-11")])
    assert conflicting.annual_revenue_observations == ()
    assert any(row.reason == "unresolved_annual_version_conflict" for row in conflicting.rejected)
    outcome = conflicting.diagnostics.annual_revenue.year_outcomes[0]
    assert outcome.state == "conflict"
    assert outcome.reasons == ("unresolved_annual_version_conflict",)


def test_duplicate_fact_is_deduplicated_and_does_not_create_an_extra_point():
    row = annual(2025, 100, "0000320193-25-000001")
    result = normalize([row, row])
    assert len(result.annual_revenue_observations) == 1
    assert any(item.reason == "duplicate_source_fact" for item in result.rejected)


def test_unsupported_unit_and_invalid_fiscal_period_are_rejected():
    unsupported = normalize([annual(2025, 100, "0000320193-25-000001")], unit="EUR")
    assert unsupported.annual_revenue_observations == ()
    assert any(row.reason == "incompatible_unit" for row in unsupported.rejected)

    invalid = normalize([annual(2025, 100, "0000320193-25-000001", fp="Q4")])
    assert invalid.annual_revenue_observations == ()
    assert any(row.reason in {"ambiguous_annual_filing_context", "not_standalone_quarter"}
        for row in invalid.rejected)


def test_invalid_period_boundaries_and_filing_context_fail_closed():
    too_short = normalize([annual(2025, 100, "0000320193-25-000001",
        start="2025-01-01", end="2025-09-27")])
    assert too_short.annual_revenue_observations == ()
    assert any(row.reason == "annual_period_duration_invalid" for row in too_short.rejected)

    facts, submissions = payload([annual(2025, 100, "0000320193-25-000001")])
    submissions["filings"]["recent"]["reportDate"][0] = "2025-09-26"
    mismatched = normalize_companyfacts(facts, submissions, "AAPL", NOW)
    assert mismatched.annual_revenue_observations == ()
    assert any(row.reason == "annual_filing_context_invalid" for row in mismatched.rejected)
    outcome = mismatched.diagnostics.annual_revenue.year_outcomes[0]
    assert outcome.state == "rejected"
    assert outcome.reasons == ("annual_filing_context_invalid",)


def test_public_dto_uses_source_ids_safe_labels_and_has_no_projected_points():
    certified = normalize([annual(2025, 416161000000, "0000320193-25-000079")])
    dto = _revenue_history(None, certified.annual_revenue_observations, _Sources())
    assert len(dto.annual_points) == 1
    point = dto.annual_points[0]
    assert point.observation_type == "reported"
    assert point.source_ids and point.provenance_label == "SEC 10-K annual revenue"
    assert all(row.observation_type != "projected" for row in dto.annual_points)


def test_master_feature_flag_prevents_acquisition_and_annual_bypass():
    called = []
    settings = Settings(_env_file=None, environment="test",
        outlook_historical_revenue_enabled=False,
        outlook_sec_user_agent="TradePilot test@example.com", outlook_http_attempts=1)
    service = RevenueHistorySnapshotService(settings,
        acquire_history=lambda ticker: called.append(ticker), retrieve_documents=lambda _: None)
    result = service.get_snapshot("AAPL")
    assert result.state == "unavailable" and result.reasons == ("feature_disabled",)
    assert result.annual_revenue_observations == () and called == []


def test_contract_is_backward_compatible_when_annual_points_are_absent():
    legacy = RevenueHistoryResearch(availability="unavailable")
    assert legacy.annual_points == ()
    assert "annual_points" in legacy.model_dump()


def test_annual_source_budget_default_does_not_change_feature_flag_defaults():
    settings = Settings(_env_file=None, environment="test")
    assert settings.outlook_sec_history_max_annual_source_facts == 128
    assert not settings.outlook_historical_revenue_enabled
    assert not settings.outlook_historical_revenue_q4_derivation_enabled


def test_year_outcome_reasons_are_allowlisted_and_fingerprint_is_deterministic():
    rows = [annual(2024, 90, "0000320193-24-000001"),
        annual(2025, 100, "0000320193-25-000001")]
    facts, submissions = payload(rows)
    first = normalize_companyfacts(facts, submissions, "AAPL", NOW)
    second = normalize_companyfacts(facts, submissions, "AAPL", NOW)
    typed = adapt_sec_submissions(submissions, issuer="Apple Inc.", cik=CIK,
        source_identity="annual-diagnostic-fixture")
    assert _acquisition_fingerprint(first, typed) == _acquisition_fingerprint(second, typed)
    assert first.diagnostics.annual_revenue.year_outcomes == second.diagnostics.annual_revenue.year_outcomes
    from pydantic import ValidationError
    try:
        AnnualRevenueYearOutcome(fiscal_year=2025, discovered_candidate_count=1,
            validated_candidate_count=0, state="rejected", reasons=("secret_reason",))
    except ValidationError:
        pass
    else:
        raise AssertionError("unapproved diagnostic reason was accepted")
