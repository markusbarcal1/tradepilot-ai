from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.config import Settings
from app.models.outlook_document import SourceDocument
from app.models.outlook_evidence import CompanyContext
from app.services.outlook import assess_providers
from app.services.outlook_evidence import assess_evidence, freshness
from app.services.outlook_geopolitical import normalize_event, resolve_exposure, current_events, interpret_exposure
from app.services.outlook_structured.geopolitical import FederalRegisterSource, GeopoliticalEvidenceProvider
from app.services.outlook_structured.transport import Cache, ProviderUnavailable

NOW = datetime(2026, 9, 18, 22, tzinfo=timezone.utc)
INFO = {"sector": "Technology", "industry": "Semiconductors", "country": "United States", "quoteType": "EQUITY"}
FIXTURE = Path(__file__).parent / "fixtures" / "outlook-geopolitical-bis.json"


def settings(**kwargs):
    return Settings(_env_file=None, environment="test", **kwargs)


def row(number="2026-10001", destination="China", days=1, **updates):
    date = (NOW - timedelta(days=days)).date().isoformat()
    result = {"title": f"Advanced Computing Export Controls for {destination}",
        "abstract": f"BIS is imposing new export license requirements for advanced computing exports to {destination}.",
        "document_number": number, "publication_date": date, "effective_on": date,
        "type": "Rule", "action": "Final rule.", "dates": f"Effective {date}.",
        "regulation_id_numbers": [f"0694-{number}"], "correction_of": None,
        "html_url": f"https://www.federalregister.gov/documents/{date.replace('-', '/')}/{number}/advanced-computing",
        "agencies": [{"slug": "industry-and-security-bureau"}]}
    return {**result, **updates}


def provider(rows=None, info=None):
    rows = [row()] if rows is None else rows
    client = Mock()
    client.get.return_value = {"count": len(rows), "results": rows}
    source = FederalRegisterSource(settings(), client, lambda: NOW)
    metadata = Mock(return_value=INFO if info is None else info)
    return GeopoliticalEvidenceProvider(settings(), source, metadata, clock=lambda: NOW), client, metadata


def event(**updates):
    p, _, _ = provider([row(**updates)])
    return normalize_event(p.source.get_documents()["documents"][0])


def test_real_frozen_source_positive_conditional_relationship():
    document = SourceDocument.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    normalized = normalize_event(document)
    assert normalized.change == "conditional_licensing_relief" and normalized.reason is None
    assert normalized.effective_at == datetime(2026, 1, 15, tzinfo=timezone.utc)
    context = CompanyContext(ticker="NVDA", **{k: INFO[k] for k in ("sector", "industry", "country")})
    evidence, reason = interpret_exposure(normalized, context, NOW)
    assert reason is None and evidence.impact == 1
    assert "approval is not guaranteed" in evidence.summary
    assert evidence.exposure_links and evidence.confidence == .8 and evidence.materiality == .6
    assert "revenue percentage" in evidence.summary


def test_direct_exposure_one_event_keeps_existing_gate():
    p, *_ = provider()
    result = assess_providers("NVDA", [p], now=NOW)
    geo = result.categories["geopolitical"]
    assert geo.evidence_count == 1 and geo.status == "insufficient_data" and geo.label is None
    assert geo.evidence[0].impact == -1 and geo.evidence[0].exposure_links
    assert "potential restrictions" in geo.evidence[0].summary
    assert result.available_categories == 0


def test_two_independent_destination_actions_can_populate_existing_ui_contract():
    p, *_ = provider([row(), row(number="2026-10002", destination="Russia", days=4)])
    result = assess_providers("NVDA", [p], now=NOW)
    geo = result.categories["geopolitical"]
    assert geo.evidence_count == 2 and geo.label == "Negative" and result.available_categories == 1
    assert len(geo.factors) == 2
    assert all("classified in Semiconductors" in factor.description for factor in geo.factors)


@pytest.mark.parametrize("ticker,industry,sector", [("KO", "Beverages - Non-Alcoholic", "Consumer Defensive"),
    ("AAPL", "Consumer Electronics", "Technology"), ("MSFT", "Software - Infrastructure", "Technology"),
    ("JPM", "Banks - Diversified", "Financial Services"), ("XOM", "Oil & Gas Integrated", "Energy"),
    ("TSLA", "Auto Manufacturers", "Consumer Cyclical")])
def test_negative_controls_not_generic_technology_or_multinational_exposure(ticker, industry, sector):
    p, *_ = provider(info={**INFO, "industry": industry, "sector": sector})
    snapshot = p.inspect(ticker)
    assert snapshot["evidence"] == [] and snapshot["matched"] == []
    assert snapshot["excluded"][-1]["reason"] == "no_controlled_product_industry_relationship"
    category = assess_providers(ticker, [p], now=NOW).categories["geopolitical"]
    assert not category.evidence and not category.factors and category.status == "insufficient_data"


@pytest.mark.parametrize("info,reason", [({}, "classification_unavailable"),
    ({**INFO, "industry": None}, "missing_industry_classification"),
    ({**INFO, "country": "Unknown"}, "unsupported_company_jurisdiction"),
    ({**INFO, "quoteType": "ETF"}, "unsupported_instrument")])
def test_missing_or_ambiguous_classification(info, reason):
    p, *_ = provider(info=info)
    snapshot = p.inspect("TEST")
    assert snapshot["evidence"] == [] and snapshot["excluded"][-1]["reason"] == reason


def test_lifecycle_future_expired_and_complex_dates():
    p, *_ = provider([row(effective_on="2026-09-20")])
    assert p.inspect("NVDA")["excluded"][-1]["reason"] == "future_effective"
    p, *_ = provider([row(days=370)])
    assert p.inspect("NVDA")["excluded"][-1]["reason"] == "expired_review_window"
    p, *_ = provider([row(dates="Effective September 17, 2026 until October 1, 2026.")])
    assert p.inspect("NVDA")["excluded"][-1]["reason"] == "complex_effective_period"
    p, *_ = provider([row(effective_on=None)])
    assert p.inspect("NVDA")["excluded"][-1]["reason"] == "missing_effective_date"


def test_duplicate_amendment_and_unclear_replacement_never_multiply_votes():
    p, *_ = provider([row(), row(), row(number="2026-10002", days=5)])
    snapshot = p.inspect("NVDA")
    assert len(snapshot["evidence"]) == 1
    assert len(snapshot["excluded"]) == 2
    p, *_ = provider([row(days=5), row(number="2026-10002", abstract="BIS revises advanced computing policy for China.")])
    snapshot = p.inspect("NVDA")
    assert snapshot["evidence"] == []
    assert {x["reason"] for x in snapshot["excluded"]} == {
        "superseded_or_duplicate_family_observation", "ambiguous_or_unsupported_policy_change"}


def test_future_amendment_does_not_remove_current_effective_rule():
    p, *_ = provider([row(days=5), row(number="2026-10002", effective_on="2026-10-01")])
    assert len(p.get_evidence("NVDA")) == 1
    assert p.get_evidence("NVDA")[0].source_details["document_number"] == "2026-10001"


def test_same_day_conflicts_and_corrections_fail_closed():
    p, *_ = provider([row(), row(number="2026-10002")])
    assert p.get_evidence("NVDA") == []
    p, *_ = provider([row(days=5), row(number="C1-2026-10001", action="Correction.", correction_of="2026-10001")])
    assert p.get_evidence("NVDA") == []


@pytest.mark.parametrize("abstract", ["BIS is not imposing new export license requirements for advanced computing exports to China.",
    "BIS may impose new export license requirements for advanced computing exports to China.",
    "Previously, BIS is imposing new export license requirements for advanced computing exports to China.",
    "The old rule stated: BIS is imposing new export license requirements for advanced computing exports to China.",
    "A company expects controls on advanced computing exports to China."])
def test_ambiguous_assertions_are_not_directional(abstract):
    p, *_ = provider([row(abstract=abstract)])
    assert p.get_evidence("NVDA") == []


def test_entity_controls_never_become_industry_wide_sanctions_exposure():
    p, *_ = provider([row(abstract="BIS is imposing new export license requirements for advanced computing exports to China for listed entities.")])
    snapshot = p.inspect("NVDA")
    assert snapshot["evidence"] == []
    assert snapshot["excluded"][-1]["reason"] == "entity_specific_relationship_not_established"


def test_no_speculative_commodity_winner_or_loser():
    synthetic = replace(event(), family="oil_supply_disruption", change="supply_disruption")
    producer = CompanyContext(ticker="XOM", industry="Oil & Gas Integrated", country="United States")
    consumer = CompanyContext(ticker="DAL", industry="Airlines", country="United States")
    for context in (producer, consumer):
        assert not resolve_exposure(synthetic, context).matched
        assert interpret_exposure(synthetic, context, NOW)[0] is None


def test_source_shared_cache_metadata_cache_and_failure_backoff():
    p, client, metadata = provider()
    for ticker in ("NVDA", "AAPL", "NVDA"):
        p.get_evidence(ticker)
    assert client.get.call_count == 1 and metadata.call_count == 2
    assert len(client.get.call_args.kwargs["params"]) < 25
    ticks = [0.0]
    p.source.cache.entries.clear()
    p.source.cache.clock = lambda: ticks[0]
    client.get.side_effect = RuntimeError("offline failure")
    for ticker in ("NVDA", "AAPL"):
        with pytest.raises(ProviderUnavailable): p.get_evidence(ticker)
    assert client.get.call_count == 2
    ticks[0] = 61
    client.get.side_effect = None
    assert p.get_evidence("NVDA")
    assert client.get.call_count == 3


def test_partial_source_failure_suppresses_direction_but_keeps_diagnostics():
    p, *_ = provider([row(), row(number="2026-10002", html_url="https://example.com/untrusted")])
    snapshot = p.inspect("NVDA")
    assert snapshot["source_complete"] is False and snapshot["evidence"] == []
    assert snapshot["status"] == "incomplete_source_snapshot"
    assert "invalid_source_record" in {x["reason"] for x in snapshot["excluded"]}


def test_source_failure_isolated_from_industry_and_other_categories():
    from tests.test_outlook_industry import setup as industry_fixture
    industry, *_ = industry_fixture()
    p, client, _ = provider()
    client.get.side_effect = RuntimeError("fixture")
    result = assess_providers("NVDA", [industry, p], now=NOW)
    assert result.categories["industry"].status == "available"
    assert result.categories["geopolitical"].status == "error"


def test_classification_cache_can_be_shared_without_industry_history_calls():
    p, _, metadata = provider()
    shared = Cache()
    shared.get("NVDA", lambda: INFO, 604800)
    p.classifications = shared
    assert p.get_evidence("NVDA") and metadata.call_count == 0


def test_truncated_snapshot_fails_closed_and_empty_is_not_not_material():
    p, client, _ = provider()
    client.get.return_value["count"] = 101
    with pytest.raises(ProviderUnavailable): p.get_evidence("NVDA")
    p, *_ = provider([])
    geo = assess_providers("NVDA", [p], now=NOW).categories["geopolitical"]
    assert geo.status == "insufficient_data" and geo.evidence == []


def test_exposure_is_required_by_existing_central_guard():
    p, *_ = provider([row(), row(number="2026-10002", destination="Russia", days=4)])
    evidence = [e.model_copy(update={"exposure_links": ()}) for e in p.get_evidence("NVDA")]
    cats, _ = assess_evidence("NVDA", evidence, now=NOW)
    assert cats["geopolitical"].evidence_count == 0


def test_freshness_does_not_refresh_publication_and_policy_is_not_political_approval():
    p, *_ = provider()
    e = p.get_evidence("NVDA")[0]
    assert freshness(e, NOW + timedelta(days=365)) == 0
    assert e.published_at < e.observed_at
    for text in ("good government", "bad government", "good policy", "bad policy", "profits will"):
        assert text not in e.summary.lower()


def test_disabled_provider_makes_no_calls():
    metadata = Mock()
    p = GeopoliticalEvidenceProvider(settings(outlook_geopolitical_enabled=False), metadata=metadata)
    assert p.get_evidence("NVDA") == [] and metadata.call_count == 0


def test_renamed_amendment_with_structured_rin_suppresses_older_direction():
    previous = row(days=5)
    amendment = row(number="2026-10002", title="Revisions to Export Administration Regulations",
                    regulation_id_numbers=previous["regulation_id_numbers"], abstract="The provisions are revised.")
    p, *_ = provider([previous, amendment])
    assert p.get_evidence("NVDA") == []
    assert p.inspect("NVDA")["normalized_event_count"] == 2


def test_conflicting_duplicate_identity_is_not_arbitrarily_selected():
    original = row()
    p, *_ = provider([original, {**original, "abstract": "BIS revises export policy to China."}])
    assert p.get_evidence("NVDA") == []


def test_source_cache_single_flight_and_expiry():
    from concurrent.futures import ThreadPoolExecutor
    p, client, _ = provider()
    ticks = [0.0]
    p.source.cache.clock = lambda: ticks[0]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(p.get_evidence, ["NVDA"] * 4))
    assert client.get.call_count == 1
    ticks[0] = 21601
    p.get_evidence("NVDA")
    assert client.get.call_count == 2


def test_authenticated_http_and_cli_diagnostics_are_offline(monkeypatch, capsys):
    import asyncio
    from unittest.mock import patch
    from app.cli import inspect_outlook
    from app.main import app
    from app.auth import get_current_user
    from tests.test_authenticated_api_isolation import call_asgi
    p, *_ = provider([row(), row(number="2026-10002", destination="Russia", days=4)])
    analyze = lambda ticker: assess_providers(ticker, [p], now=NOW)
    monkeypatch.setattr("app.main.analyze_outlook", analyze)
    with patch.dict(app.dependency_overrides, {get_current_user: lambda: object()}):
        status, _, payload = asyncio.run(call_asgi("GET", "/outlook/NVDA"))
    assert status == 200 and payload["categories"]["geopolitical"]["label"] == "Negative"
    monkeypatch.setattr(inspect_outlook, "analyze_outlook", analyze)
    monkeypatch.setattr("app.services.outlook_structured.configured_providers", lambda: [p])
    monkeypatch.setattr("sys.argv", ["inspect_outlook", "NVDA", "--json"])
    assert inspect_outlook.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result["geopolitical_diagnostics"]["matched"]) == 2
    assert result["geopolitical_diagnostics"]["normalized_event_count"] == 2
