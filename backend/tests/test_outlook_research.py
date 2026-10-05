"""Focused presentation-envelope tests; all fixtures are offline."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.outlook import OutlookCategory, OutlookMetadata, OutlookResponse
from app.models.outlook_ai import AIOutlookResponse
from app.models.outlook_evidence import OutlookEvidence
from app.models.outlook_event import (EventIntelligence, EventMeasurement, EventSource, EventValue,
    ExposureAssessment, ExternalEvent, RelevantEvent)
from app.models.outlook_reporting import ReportingIdentity, ReportingPeriodIdentity, ReportingProvenance
from app.models.outlook_taxonomy import CATEGORY_TITLES
from app.services.outlook_ai import build_context_packet
from app.services.outlook_research import build_research_presentation

NOW = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)
URL = "https://example.com/source"


def source(name="Primary source"):
    return EventSource(source=name, source_type="government_source", source_url=URL,
        published_at=NOW - timedelta(days=1), retrieved_at=NOW)


def evidence(identifier, category, event_type, details, *, impact=1, scoring=True):
    return OutlookEvidence(id=identifier, ticker="NVDA", category=category, event_type=event_type,
        title=f"{category.title()} observation", summary="Verified presentation fact.",
        source="Primary source", source_type="market_data" if category in ("industry", "market") else "government_source",
        source_url=URL, published_at=NOW - timedelta(days=1), observed_at=NOW,
        impact=impact, confidence=.9, materiality=.8, materiality_reason="Fixture",
        scoring_eligible=scoring, source_details=details, raw_provider="fred" if identifier.startswith("fred:") else "fixture")


def ai_response(watch=True):
    empty = {"rating": "insufficient_data", "summary": "Not enough verified information."}
    return AIOutlookResponse(overall={"rating": "mostly_positive", "summary": "Grounded fixture."},
        categories={key: empty for key in CATEGORY_TITLES},
        what_to_watch=({"event_id": "earnings:NVDA:next", "reason": "Results may update the outlook."},) if watch else ())


def fixture():
    reporting = ReportingIdentity(status="authoritative", reason="explicit_reporting_identity",
        periods=(ReportingPeriodIdentity(ticker="NVDA", fiscal_year=2027, fiscal_period="Q2", period_end=date(2026, 7, 26)),),
        provenance=(ReportingProvenance(method="explicit_primary_text", source_url=URL,
            document_id="document", basis="Explicit quarter."),))
    earnings = ExternalEvent(event_id="earnings:NVDA:FY2027:Q2", event_type="earnings_release",
        category="earnings", title="NVDA Earnings", summary="Released results.", status="occurred",
        announced_at=NOW - timedelta(days=30), reference_period="FY2027 Q2", reporting_identity=reporting,
        measurements=(EventMeasurement(key="revenue", label="Revenue",
            actual_value=EventValue(amount=96.2, unit="USD_billion")),
            EventMeasurement(key="gross_margin", label="Gross Margin",
            actual_value=EventValue(amount=75, unit="percent"), previous_value=EventValue(amount=72.4, unit="percent"))),
        provenance=(source("SEC EDGAR"),))
    upcoming = ExternalEvent(event_id="earnings:NVDA:next", event_type="earnings_release",
        category="earnings", title="NVDA Earnings", summary="Upcoming results.", status="upcoming",
        scheduled_date=date(2026, 11, 18), market_session="unknown", schedule_certainty="provider_reported",
        provenance=(source("Yahoo Finance — Earnings Calendar"),))
    exposure = ExposureAssessment(True, "Issuer event")
    event_intelligence = EventIntelligence(status="available",
        recent=(RelevantEvent(event=earnings, exposure=exposure),),
        upcoming=(RelevantEvent(event=upcoming, exposure=exposure),))
    rows = [
        evidence("sec:revenue", "earnings", "earnings_result",
            {"reporting_identity": reporting.model_dump(mode="json"), "numeric": {"metric": "revenue",
             "current_value": 96.2, "unit": "USD_billion", "change_percent": 106,
             "comparison": "year_over_year"}}),
        evidence("sec:margin", "earnings", "margin_change",
            {"reporting_identity": reporting.model_dump(mode="json"), "numeric": {"metric": "gross_margin",
             "current_percent": 75, "prior_percent": 72.4, "percentage_points": 2.6,
             "comparison": "year_over_year", "current_period": "Q2 FY2027", "prior_period": "Q2 FY2026"}}),
        evidence("industry:relative", "industry", "industry_other", {
            "raw_sector": "Technology", "raw_industry": "Semiconductors", "normalized_industry": "semiconductors",
            "industry_name": "Semiconductors", "classification_quality": "exact_industry", "taxonomy_version": "1",
            "benchmark_symbol": "SOXX", "benchmark_name": "Semiconductor ETF", "benchmark_type": "industry_etf",
            "company_return_21": .055, "benchmark_return_21": .102, "relative_return_21": -.047,
            "company_return_63": .149, "benchmark_return_63": -.094, "relative_return_63": .243,
            "relative_performance_state": "mixed"}, impact=0),
        evidence("industry:group", "industry", "sector_performance", {
            "breadth_state": "mixed", "configured_peer_count": 9, "valid_peer_count": 8,
            "positive_return_breadth": .625, "above_sma50_breadth": .75,
            "median_peer_return_21": .08, "peer_sample": ["AMD", "AVGO"]}, impact=0),
        evidence("fred:unrate", "economic", "employment", {
            "series_title": "Unemployment Rate", "current_measure": 4.1, "previous_measure": 4.3, "change": -.2,
            "observation_date": "2026-08-01", "comparison_date": "2026-05-01",
            "observations_used": [{"date": "2026-05-01", "value": 4.3}, {"date": "2026-08-01", "value": 4.1}]}),
        evidence("market:trend", "market", "broad_market_trend", {"benchmarks": [
            {"symbol": "SPY", "price": 767.18, "sma50": 759.46, "sma50_five_sessions_ago": 757.65,
             "direction": 1, "published": "2026-09-24T20:00:00Z"}], "history": {
                 "schema_version": "1", "snapshot_id": "m" * 24, "as_of": NOW.isoformat(),
                 "price_adjustment_basis": "yahoo_auto_adjust_true",
                 "equity": {"windows": {"1M": [{"date": (date(2026, 8, 1) + timedelta(days=i)).isoformat(),
                     "spy_cumulative_return": float(i), "qqq_cumulative_return": float(i) * 2} for i in range(22)]},
                     "coverage": {"common_session_count": 22, "has_gaps": False}},
                 "vix": {"points": [{"date": "2026-09-23", "level": 16.0}, {"date": "2026-09-24", "level": 15.67}]},
                 "vix_thresholds": {"low_below": 15, "elevated_at_or_above": 25},
                 "qualifier": "Broad-market proxies; VIX is an index level."}}),
        evidence("market:vix", "market", "volatility", {"symbol": "^VIX", "close": 15.67}, impact=0),
        evidence("sec:metadata", "company", "corporate_other", {"form": "8-K"}, scoring=False),
        evidence("geo:event", "geopolitical", "export_control", {
            "publication_title": "Advanced computing export policy", "document_number": "2026-00789",
            "effective_at": "2026-01-15T00:00:00+00:00", "review_expires_at": "2027-01-15T00:00:00+00:00",
            "countries": ["China", "Macau"], "product_group": "advanced_computing",
            "policy_change": "conditional_licensing_relief", "exposure_reason": "Exact semiconductor industry match."}),
    ]
    grouped = {key: [row for row in rows if row.category == key] for key in CATEGORY_TITLES}
    categories = {key: OutlookCategory(status="available" if grouped[key] else "insufficient_data",
        value=0 if grouped[key] else None, summary="Fixture", evidence_count=len(grouped[key]), evidence=grouped[key])
        for key in CATEGORY_TITLES}
    return OutlookResponse(ticker="NVDA", status="partial", value=0, summary="Fixture",
        categories=categories, metadata=OutlookMetadata(provider="fixture", uses_placeholder_data=False),
        event_intelligence=event_intelligence)


def test_research_serializes_typed_categories_sources_and_resolved_watch_without_internal_ids():
    outlook = fixture()
    packet = build_context_packet(outlook, generated_at=NOW)
    research = build_research_presentation(outlook, packet, ai_response(), as_of=NOW)
    assert research.schema_version == "2" and research.ticker == "NVDA"
    assert research.revenue_history.availability == "unavailable"
    revenue = next(row for row in research.earnings.metrics if row.label == "Revenue")
    assert (revenue.value, revenue.unit, revenue.change, revenue.change_unit) == (96.2, "USD_billion", 106, "percent")
    assert revenue.comparison_basis == "reported_change_only" and revenue.previous_value is None
    margin = next(row for row in research.earnings.metrics if row.label == "Gross Margin")
    assert margin.previous_value == 72.4 and margin.change == pytest.approx(2.6)
    assert margin.change_unit == "percentage_points"
    assert margin.comparison_basis == "exact_values" and margin.comparison_period == "Q2 FY2026"
    assert (research.earnings.fiscal_year, research.earnings.fiscal_period) == (2027, "Q2")
    assert research.industry.classification_quality == "exact_industry"
    assert [row.window_sessions for row in research.industry.comparisons] == [21, 63]
    assert research.industry.breadth.valid_count == 8
    assert research.economic.trends[0].previous_value == 4.3
    assert research.market.benchmarks[0].trend == "above_rising"
    assert research.market.volatility.regime == "normal"
    assert research.market.history.windows[0].points[0].spy_cumulative_return == 0
    assert research.market.history.windows[0].points[-1].qqq_cumulative_return == 42
    assert research.market.history.vix_points[-1].level == 15.67
    assert research.market.history.vix_threshold_high == 25
    assert research.company.events == () and "No qualifying" in research.company.empty_message
    assert research.geopolitical.events[0].details["geography"] == "China, Macau"
    assert "does not establish" in research.geopolitical.events[0].qualifier
    assert research.what_to_watch[0].title == "NVDA Earnings"
    assert research.what_to_watch[0].market_session == "unknown"
    assert research.sources
    dumped = research.model_dump_json()
    assert "sec:metadata" not in dumped and "context_fingerprint" not in dumped


@pytest.mark.parametrize("mismatch", ["value", "unit", "period"])
def test_earnings_comparisons_require_exact_current_period_unit_and_value_provenance(mismatch):
    outlook = fixture()
    revenue = outlook.categories["earnings"].evidence[0]
    numeric = dict(revenue.source_details["numeric"])
    identity = revenue.source_details["reporting_identity"]
    if mismatch == "value":
        numeric["current_value"] = 95.0
    elif mismatch == "unit":
        numeric["unit"] = "USD_million"
    else:
        other_period = ReportingPeriodIdentity(ticker="NVDA", fiscal_year=2027,
            fiscal_period="Q1", period_end=date(2026, 4, 26))
        identity = ReportingIdentity.model_validate(identity).model_copy(
            update={"periods": (other_period,)}).model_dump(mode="json")
    wrong_details = {**revenue.source_details, "reporting_identity": identity, "numeric": numeric}
    categories = dict(outlook.categories)
    categories["earnings"] = categories["earnings"].model_copy(update={"evidence": [
        revenue.model_copy(update={"source_details": wrong_details}), *categories["earnings"].evidence[1:]]})
    changed = outlook.model_copy(update={"categories": categories})
    research = build_research_presentation(changed, build_context_packet(changed, generated_at=NOW), ai_response(), as_of=NOW)
    result = next(row for row in research.earnings.metrics if row.label == "Revenue")
    assert result.value == 96.2
    assert result.change is None and result.comparison_basis is None


def test_earnings_unsupported_metric_and_unverified_prior_are_not_presented():
    outlook = fixture()
    event = outlook.event_intelligence.recent[0].event
    altered = event.model_copy(update={"measurements": (*event.measurements,
        EventMeasurement(key="net_income", label="Net Income",
            actual_value=EventValue(amount=20, unit="USD_billion")),
        EventMeasurement(key="operating_margin", label="Operating Margin",
            actual_value=EventValue(amount=40, unit="percent"),
            previous_value=EventValue(amount=35, unit="percent")))})
    intelligence = outlook.event_intelligence.model_copy(update={"recent": (
        outlook.event_intelligence.recent[0].model_copy(update={"event": altered}),)})
    changed = outlook.model_copy(update={"event_intelligence": intelligence})
    research = build_research_presentation(changed, build_context_packet(changed, generated_at=NOW), ai_response(), as_of=NOW)
    labels = {row.label for row in research.earnings.metrics}
    assert "Net Income" not in labels
    operating = next(row for row in research.earnings.metrics if row.label == "Operating Margin")
    assert operating.value == 40 and operating.previous_value is None
    assert operating.change is None and operating.comparison_basis is None


def test_sparse_earnings_keeps_upcoming_event_without_invented_results():
    outlook = fixture()
    intelligence = outlook.event_intelligence.model_copy(update={"recent": ()})
    changed = outlook.model_copy(update={"event_intelligence": intelligence})
    research = build_research_presentation(changed, build_context_packet(changed, generated_at=NOW), ai_response(), as_of=NOW)
    assert research.earnings.metrics == ()
    assert research.earnings.next_event.schedule_certainty == "provider_reported"
    assert research.earnings.next_event.market_session == "unknown"


def test_sector_fallback_and_sparse_fields_remain_explicit():
    outlook = fixture()
    relative = outlook.categories["industry"].evidence[0]
    details = {**relative.source_details, "classification_quality": "sector_fallback",
        "fallback_reason": "unsupported_industry", "benchmark_type": "sector_etf"}
    categories = dict(outlook.categories)
    categories["industry"] = categories["industry"].model_copy(update={"evidence": [relative.model_copy(update={"source_details": details})]})
    sparse = outlook.model_copy(update={"categories": categories})
    packet = build_context_packet(sparse, generated_at=NOW)
    research = build_research_presentation(sparse, packet, ai_response(watch=False), as_of=NOW)
    assert research.industry.classification_quality == "sector_fallback"
    assert research.industry.fallback_reason == "unsupported_industry"
    assert research.industry.breadth is None
    assert research.what_to_watch == ()


def test_industry_history_contract_is_bounded_and_snapshot_owned():
    outlook = fixture()
    relative = outlook.categories["industry"].evidence[0]
    points = [{"date": (date(2026, 8, 1) + timedelta(days=i)).isoformat(),
        "company_cumulative_return": float(i), "benchmark_cumulative_return": float(i) / 2,
        "relative_performance": float(i) / 2} for i in range(22)]
    history = {"schema_version": "1", "snapshot_id": "a" * 24, "ticker": "NVDA",
        "as_of": NOW.isoformat(), "series_start": points[0]["date"], "series_end": points[-1]["date"],
        "price_adjustment_basis": "yahoo_auto_adjust_true", "currency": "USD",
        "benchmark": {"symbol": "SOXX", "name": "Semiconductor ETF", "benchmark_type": "industry_etf",
            "classification_quality": "exact_industry", "fallback_reason": None,
            "taxonomy_version": "1", "mapping_version": "1"},
        "available_windows": ["1M"], "windows": {"1M": points},
        "coverage": {"common_session_count": 22, "company_missing_session_count": 0,
            "benchmark_missing_session_count": 0, "has_gaps": False,
            "company_last_session": points[-1]["date"], "benchmark_last_session": points[-1]["date"]},
        "qualifier": "Adjusted price return; not a total-return index."}
    details = {**relative.source_details, "history": history}
    categories = dict(outlook.categories)
    categories["industry"] = categories["industry"].model_copy(update={"evidence": [
        relative.model_copy(update={"source_details": details}), *categories["industry"].evidence[1:]]})
    owned = outlook.model_copy(update={"categories": categories})
    research = build_research_presentation(owned, build_context_packet(owned, generated_at=NOW), ai_response(), as_of=NOW)
    assert research.industry.history.snapshot_id == "a" * 24
    assert research.industry.history.ticker == research.ticker
    assert research.industry.history.windows[0].session_count == 22
    assert len(research.industry.history.model_dump_json()) < 10000

    history["ticker"] = "AAPL"
    wrong_details = {**relative.source_details, "history": history}
    categories["industry"] = categories["industry"].model_copy(update={"evidence": [
        relative.model_copy(update={"source_details": wrong_details})]})
    wrong = outlook.model_copy(update={"categories": categories})
    sparse = build_research_presentation(wrong, build_context_packet(wrong, generated_at=NOW), ai_response(), as_of=NOW)
    assert sparse.industry.history is None
