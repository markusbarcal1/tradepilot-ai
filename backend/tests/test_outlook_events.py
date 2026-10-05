"""Offline FOMC vertical slice: frozen primary HTML plus explicit synthetic controls."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models.outlook_event import EventSource, EventValue, ExpectationSnapshot, OutcomeProbability
from app.models.outlook_evidence import CompanyContext
from app.services.outlook import assess_providers
from app.services.outlook_evidence import assess_evidence
from app.services.outlook_events import FomcEventProvider, fomc_exposure, lifecycle, with_expectations, event_evidence
from app.services.outlook_structured.fomc import (CALENDAR_URL, FomcSource, parse_calendar, parse_decision,
    statement_document, target_range)
from app.services.outlook_structured.fred import FredEvidenceProvider
from tests.test_outlook_structured import FredClient

FIXTURES = Path(__file__).parent / "fixtures" / "fomc"
NOW = datetime(2026, 9, 18, 20, tzinfo=timezone.utc)
ANNOUNCED = datetime(2026, 9, 16, 18, tzinfo=timezone.utc)
STATEMENT = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm"
NOTE = STATEMENT.replace("a.htm", "a1.htm")


def html(name):
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


def settings(**kwargs):
    return Settings(_env_file=None, environment="test", **kwargs)


def decision():
    return parse_decision(statement_document(html("september-statement"), STATEMENT, NOW),
                          note_html=html("september-implementation"), note_url=NOTE)


def info(ticker="ABTC"):
    return {"quoteType": "EQUITY", "exchange": "NCM", "sector": "Financial Services", "industry": "Capital Markets",
            "shortName": "American Bitcoin Corp.", "longBusinessSummary": "American Bitcoin Corp. engages in bitcoin mining and strategic Bitcoin accumulation."}


class Client:
    def __init__(self):
        self.calls = []
        self.fail = False
    def get_text(self, url, **kwargs):
        self.calls.append(url)
        if self.fail:
            raise TimeoutError("fixture source failure")
        if url == CALENDAR_URL:
            return html("calendar")
        return html({STATEMENT: "september-statement", NOTE: "september-implementation",
            "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm": "july-statement",
            "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a1.htm": "july-implementation"}[url])


def provider(client=None, metadata=info, expectations=None, clock=lambda: NOW):
    config = settings()
    return FomcEventProvider(config, source=FomcSource(config, client or Client(), clock), metadata=metadata,
                             expectations=expectations, clock=clock)


def expectation(amount=25, **changes):
    observed = ANNOUNCED - timedelta(hours=2)
    payload = dict(snapshot_id="fixture-expectation", event_id="fomc:2026-09-16", basis="structured_consensus",
        metric="change", expected_value=EventValue(amount=amount, unit="basis_points"),
        observed_at=observed, expires_at=ANNOUNCED + timedelta(hours=1),
        provenance=EventSource(source="Synthetic consensus fixture", source_type="market_data",
            source_url="https://example.com/fixture", published_at=observed, retrieved_at=observed))
    return ExpectationSnapshot(**{**payload, **changes})


def test_frozen_primary_decision_and_hold():
    event = decision()
    assert event.event_id == "fomc:2026-09-16"
    assert event.previous_value.lower == 3.5 and event.previous_value.upper == 3.75
    assert event.actual_value.lower == 3.75 and event.actual_value.upper == 4
    assert event.change.amount == 25 and event.change.unit == "basis_points"
    assert event.announced_at == ANNOUNCED and event.scheduled_at is None
    assert event.effective_date == date(2026, 9, 17) and event.effective_at is None
    assert str(event.provenance[0].source_url) == STATEMENT
    assert str(event.provenance[1].source_url) == NOTE
    held = parse_decision(statement_document(html("july-statement"), STATEMENT.replace("20260916", "20260729"), NOW))
    assert held.previous_value == held.actual_value
    assert held.change.amount == 0
    # A dissenting voter's desired hike must not be interpreted as the decision.
    assert "raise" in html("july-statement")


def test_calendar_upcoming_identity_and_lifecycle():
    rows = parse_calendar(html("calendar"))
    assert rows[-2]["date"] == date(2026, 10, 28)
    result = provider().inspect("ABTC")
    future = result["intelligence"].upcoming[0].event
    assert future.status == "upcoming" and future.scheduled_date == date(2026, 10, 28)
    assert future.announced_at is None and future.actual_value is None and future.scheduled_at is None
    assert future.expectation is None and future.surprise.status == "unavailable"
    upcoming_september = future.model_copy(update={"event_id": "fomc:2026-09-16", "scheduled_date": date(2026, 9, 16)})
    assert upcoming_september.event_id == decision().event_id
    assert lifecycle(decision(), ANNOUNCED).status == "occurred"
    assert lifecycle(decision(), NOW).status == "effective"
    assert lifecycle(decision(), NOW + timedelta(days=100)).status == "expired"
    assert lifecycle(upcoming_september, NOW).status == "expired"  # no invented announcement


@pytest.mark.parametrize("replacement", ["raise", "lower"])
def test_deterministic_basis_points(replacement):
    document = statement_document(html("september-statement"), STATEMENT, NOW)
    document = document.model_copy(update={"extracted_text": document.extracted_text.replace("decided to raise", f"decided to {replacement}")})
    assert parse_decision(document).change.amount == (25 if replacement == "raise" else -25)


@pytest.mark.parametrize("low,high", [("3-3/4", "4"), ("3.75", "4.00"), ("3 3/4", "4")])
def test_range_formats(low, high):
    assert target_range(f"target range of {low} to {high} percent").lower == 3.75


def test_malformed_authority_and_decision_fail_closed():
    with pytest.raises(ValueError):
        statement_document(html("september-statement"), STATEMENT.replace("www.federalreserve.gov", "example.com"), NOW)
    with pytest.raises(ValueError):
        statement_document(html("september-statement").replace("2:00 p.m. EDT", "time unknown"), STATEMENT, NOW)
    document = statement_document(html("september-statement"), STATEMENT, NOW)
    with pytest.raises(ValueError):
        parse_decision(document.model_copy(update={"extracted_text": document.extracted_text.replace("decided to raise", "may raise")}))
    with pytest.raises(ValueError):
        parse_decision(document, note_html=html("september-implementation").replace("3-3/4", "3-1/2"), note_url=NOTE)
    with pytest.raises(ValueError):
        parse_calendar(html("calendar").replace("27-28", "TBD"))


@pytest.mark.parametrize("amount,status", [(25, "as_expected"), (0, "different_from_expected")])
def test_expected_vs_actual(amount, status):
    event = with_expectations(decision(), [expectation(amount)], NOW)
    assert event.surprise.status == status
    assert event.surprise.difference.amount == 25 - amount
    assert event.surprise.expectation_snapshot_id == "fixture-expectation"


def test_probability_is_event_outcome_not_stock_reaction():
    outcomes = tuple(OutcomeProbability(title=title, outcome=EventValue(amount=value, unit="basis_points"), probability=p)
        for title, value, p in [("Hold", 0, .3), ("+25 bp", 25, .7)])
    event = with_expectations(decision(), [expectation(expected_value=None, outcomes=outcomes)], NOW)
    assert event.surprise.status == "probability_based"
    assert event.surprise.actual_outcome_probability == .7
    assert "stock_probability" not in event.model_dump_json()
    assert with_expectations(decision(), [], NOW).surprise.status == "unavailable"


@pytest.mark.parametrize("changes", [
    {"expires_at": ANNOUNCED - timedelta(minutes=1)},
    {"observed_at": ANNOUNCED - timedelta(days=2)},
    {"provenance": EventSource(source="Late survey", source_type="market_data", source_url="https://example.com/late",
        published_at=NOW, retrieved_at=NOW)},
])
def test_stale_or_late_expectations_not_used(changes):
    event = with_expectations(decision(), [expectation(**changes)], NOW)
    assert event.expectation is None and event.surprise.status == "unavailable"
    assert len(event.expectation_history) == 1  # provenance is not overwritten


@pytest.mark.parametrize("probability", [-.1, 1.1, float("nan"), float("inf"), True])
def test_invalid_probability_rejected(probability):
    with pytest.raises(ValidationError):
        OutcomeProbability(title="Hold", outcome=EventValue(amount=0, unit="basis_points"), probability=probability)


def test_invalid_distribution_and_non_numeric_event_value():
    row = OutcomeProbability(title="Hold", outcome=EventValue(amount=0, unit="basis_points"), probability=.6)
    with pytest.raises(ValidationError):
        expectation(outcomes=(row,))
    assert EventValue(text="License granted", unit="decision").amount is None


def test_supported_abtc_exposure_and_non_directional_evidence():
    result = provider().inspect("ABTC")
    recent = result["intelligence"].recent[0]
    assert recent.exposure.relevance == "company_specific" and recent.exposure.directness == "business"
    assert recent.exposure.direction is None and not recent.directional_evidence
    assert "Bitcoin mining" in recent.exposure.reason
    assert all(not e.scoring_eligible and e.impact == 0 for e in result["evidence"])
    categories, contributions = assess_evidence("ABTC", result["evidence"], now=NOW)
    assert categories["economic"].evidence_count == 0
    assert all(c.exclusion for c in contributions)


@pytest.mark.parametrize("description", ["A technology business.", "The company plans bitcoin mining.",
    "The company does not operate as a bitcoin miner.", "A customer engages in bitcoin mining.", "Formerly, the company engages in bitcoin mining."])
def test_no_vague_crypto_mapping(description):
    values = {**info(), "longBusinessSummary": description}
    result = provider(metadata=lambda _: values).inspect("ABTC")
    assert result["intelligence"].recent[0].exposure.relevance == "broad"


@pytest.mark.parametrize("industry", ["Banks - Diversified", "REIT - Industrial"])
def test_explicit_industry_channels(industry):
    values = {**info(), "industry": industry, "longBusinessSummary": None}
    exposure = fomc_exposure(CompanyContext(ticker="TEST", industry=industry), values)
    assert exposure.relevance == "company_specific" and exposure.direction is None


def test_unsupported_instrument_and_missing_classification():
    result = provider(metadata=lambda _: {**info(), "quoteType": "ETF"}).inspect("TEST")
    assert result["intelligence"].status == "no_supported_exposure"
    assert not result["evidence"] and not result["intelligence"].recent
    result = provider(metadata=lambda _: None).inspect("TEST")
    assert result["intelligence"].status == "classification_unavailable"


def test_source_cache_reuse_across_tickers_and_failure_backoff():
    client = Client()
    p = provider(client)
    p.inspect("ABTC"); p.inspect("NVDA"); p.inspect("JPM")
    assert len(client.calls) == 5 and p.source.loads == 1
    client = Client(); client.fail = True
    p = provider(client)
    assert p.inspect("ABTC")["intelligence"].status == "temporarily_unavailable"
    assert p.inspect("NVDA")["intelligence"].status == "temporarily_unavailable"
    assert len(client.calls) == 1


def test_probability_failure_does_not_remove_event_and_history_is_immutable():
    class Broken:
        def snapshots(self, event_id):
            raise TimeoutError("fixture")
    result = provider(expectations=Broken()).inspect("ABTC")
    assert result["intelligence"].recent and result["intelligence"].upcoming
    assert result["intelligence"].recent[0].event.expectation_status == "error"
    class Malformed:
        def snapshots(self, event_id):
            return [{"probability": 140}]
    assert provider(expectations=Malformed()).inspect("ABTC")["intelligence"].recent[0].event.expectation_status == "invalid"
    p = provider()
    first = expectation()
    p.history[first.event_id] = {first.snapshot_id: first}
    class Revised:
        def snapshots(self, event_id):
            return [expectation(0)]
    p.expectations = Revised()
    p._expectations(decision(), NOW)
    assert p.history[first.event_id][first.snapshot_id] == first


def test_fred_related_observation_cannot_be_double_counted_or_recalibrated():
    fred = FredEvidenceProvider(settings(fred_api_key="offline-test"), FredClient(), lambda: NOW)
    before = assess_providers("ABTC", [fred], now=NOW)
    after = assess_providers("ABTC", [fred, provider()], now=NOW)
    assert before.label == after.label and before.value == after.value
    for key in before.categories:
        left, right = before.categories[key], after.categories[key]
        assert left.model_dump(exclude={"evidence"}) == right.model_dump(exclude={"evidence"})
    evidence = after.categories["economic"].evidence
    # Replaying all provenance still cannot add a monetary-policy support vote.
    replayed, _ = assess_evidence("ABTC", evidence + [e for e in evidence if e.raw_provider == "fomc"], now=NOW)
    assert replayed["economic"].evidence_count == before.categories["economic"].evidence_count
    assert replayed["economic"].value == before.categories["economic"].value
    assert after.event_intelligence.recent


def test_event_failure_isolated_from_existing_categories():
    fred = FredEvidenceProvider(settings(fred_api_key="offline-test"), FredClient(), lambda: NOW)
    before = assess_providers("ABTC", [fred], now=NOW)
    client = Client(); client.fail = True
    after = assess_providers("ABTC", [fred, provider(client)], now=NOW)
    assert before.categories == after.categories
    assert before.value == after.value
    assert after.event_intelligence.status == "temporarily_unavailable"


def test_cli_diagnostics_offline(capsys):
    from app.cli.inspect_events import main
    with patch("app.cli.inspect_events.configured_providers", return_value=[provider()]), patch("sys.argv", ["inspect_events", "ABTC", "NVDA", "--json"]):
        assert main() == 0
    output = capsys.readouterr().out
    assert "fomc:2026-09-16" in output and '"source_loads": 1' in output
    assert '"directional_evidence": false' in output



def test_live_abtc_business_wording_and_july_unicode_fraction():
    description = "The company is engaged in the operation of application-specific integrated circuit miners for the purpose of mining Bitcoin and the strategic accumulation of a Bitcoin reserve."
    result = provider(metadata=lambda _: {**info(), "longBusinessSummary": description}).inspect("ABTC")
    assert result["intelligence"].status == "available"
    assert result["intelligence"].recent[0].exposure.relevance == "company_specific"
    july = result["intelligence"].recent[1].event
    assert july.effective_date == date(2026, 7, 30) and july.status == "effective"
    assert july.change.amount == 0
    negative = provider(metadata=lambda _: {**info(), "longBusinessSummary": "A competitor engages in bitcoin mining."}).inspect("ABTC")
    assert negative["intelligence"].recent[0].exposure.relevance == "broad"


def test_diagnostics_preserve_events_and_existing_unavailable_states():
    from app.services.outlook_diagnostics import inspect_snapshot
    from app.services.outlook_providers import PlaceholderOutlookProvider
    result = assess_providers("ABTC", [PlaceholderOutlookProvider(), provider()], now=NOW)
    inspected, _ = inspect_snapshot(result, now=NOW)
    assert inspected.event_intelligence == result.event_intelligence
    assert inspected.status == result.status


def test_common_lowercase_committee_and_unicode_fraction_constructions():
    raw = html("september-statement").replace("The Committee decided", "In support of its goals, the Committee decided").replace("3-3/4", "3¾")
    event = parse_decision(statement_document(raw, STATEMENT, NOW))
    assert event.actual_value.lower == 3.75 and event.change.amount == 25


def test_same_instant_publication_is_not_a_preannouncement_expectation():
    provenance = EventSource(source="At release", source_type="market_data", source_url="https://example.com/at-release",
        published_at=ANNOUNCED, retrieved_at=ANNOUNCED)
    event = with_expectations(decision(), [expectation(provenance=provenance)], NOW)
    assert event.expectation is None and event.surprise.status == "unavailable"


def test_cached_provider_upcoming_to_announced_retains_identity_and_expectation():
    current = [ANNOUNCED - timedelta(hours=1)]
    monotonic = [0]
    class ChangingCalendar(Client):
        def get_text(self, url, **kwargs):
            value = super().get_text(url, **kwargs)
            if url == CALENDAR_URL and current[0] < ANNOUNCED:
                value = value.replace('/newsevents/pressreleases/monetary20260916a.htm', '#not-yet-published')
                value = value.replace('/newsevents/pressreleases/monetary20260916a1.htm', '#not-yet-published')
            return value
    class Consensus:
        def snapshots(self, event_id):
            return [expectation()] if event_id == "fomc:2026-09-16" else []
    p = provider(ChangingCalendar(), expectations=Consensus(), clock=lambda: current[0])
    p.source.cache.clock = lambda: monotonic[0]
    before = p.inspect("ABTC")["intelligence"].upcoming[0].event
    assert before.event_id == "fomc:2026-09-16" and before.status == "upcoming"
    assert before.expectation is not None and before.actual_value is None
    current[0] = ANNOUNCED + timedelta(hours=1)
    monotonic[0] = 1801
    after = p.inspect("ABTC")["intelligence"].recent[0].event
    assert after.event_id == before.event_id and after.status == "occurred"
    assert after.expectation_history == before.expectation_history
    assert after.surprise.status == "as_expected"
