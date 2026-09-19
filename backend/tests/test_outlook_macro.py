"""Frozen official releases; all modified dates/values and consensus below are synthetic controls."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from app.models.outlook_event import EventSource, EventValue, ExpectationSnapshot
from app.services.outlook import assess_providers
from app.services.outlook_diagnostics import inspect_snapshot
from app.services.outlook_events import MacroEventProvider, lifecycle, with_expectations
from app.services.outlook_structured.macro import (BLS_CALENDAR, BEA_CALENDAR, BEA_CURRENT,
    BLS_RELEASES, TITLES, MacroSource, parse_calendar, parse_release, release_links, next_bls_release)
from app.services.outlook_structured.fred import FredEvidenceProvider
from tests.test_outlook_events import settings, info, provider as fomc_provider
from tests.test_outlook_structured import FredClient

NOW = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
FIXTURES = Path(__file__).parent / "fixtures" / "macro"


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


URLS = {**BLS_RELEASES, **release_links(fixture("bea-current.html"))}


def release(kind, raw=None):
    return parse_release(raw or fixture(kind + ".html"), kind, URLS[kind], NOW)


class Client:
    def __init__(self, fail=()):
        self.fail, self.calls = fail, []
        self.files = {BLS_CALENDAR: "bls.ics", BEA_CALENDAR: "bea.ics", BEA_CURRENT: "bea-current.html",
                      **{url: kind + ".html" for kind, url in URLS.items()}}

    def get_text(self, url, **kwargs):
        self.calls.append(url)
        if any(part in url for part in self.fail):
            raise TimeoutError("synthetic failure")
        return fixture(self.files[url])


def provider(client=None, clock=lambda: NOW, **kwargs):
    config = settings()
    return MacroEventProvider(config, source=MacroSource(config, client or Client(), clock),
                              metadata=info, clock=clock, **kwargs)


@pytest.mark.parametrize("kind,period,expected", [
    ("cpi", "2026-08", {"headline_mom": .4, "core_mom": .3, "headline_yoy": 3.4, "core_yoy": 2.4}),
    ("pce", "2026-07", {"headline_mom": .2, "core_mom": .2, "headline_yoy": 3.7, "core_yoy": 3.3}),
    ("employment", "2026-08", {"payrolls": 162000, "unemployment": 4.1}),
    ("gdp", "2026-Q2", {"real_gdp": 1.5}),
])
def test_primary_release_measurements(kind, period, expected):
    event = release(kind)
    assert event.reference_period == period
    assert {m.key: m.actual_value.amount for m in event.measurements} == expected
    assert event.underlying_event_id == f"{kind}:{period}"
    assert event.event_id == f"{kind}:{event.announced_at.date()}"
    assert event.announced_at < NOW and event.announced_at.utcoffset() is not None
    assert all(m.expectation is None and m.surprise.status == "unavailable" for m in event.measurements)


def test_authoritative_calendars_periods_estimates_and_dst():
    bls = parse_calendar(fixture("bls.ics"), BLS_CALENDAR, NOW)
    bea = parse_calendar(fixture("bea.ics"), BEA_CALENDAR, NOW)
    assert {e.event_type for e in bls + bea} == {"macro_" + k for k in TITLES}
    next_gdp = next(e for e in bea if e.event_type == "macro_gdp" and e.scheduled_at > NOW)
    assert next_gdp.reference_period == "2026-Q2" and next_gdp.release_type == "Third Estimate"
    assert next_gdp.underlying_event_id == release("gdp").underlying_event_id
    assert next_gdp.event_id != release("gdp").event_id
    winter = next(e for e in bls if e.scheduled_date.isoformat() == "2026-11-06")
    assert winter.scheduled_at.utcoffset() == timedelta(hours=-5)
    unusual = next(e for e in bea if e.event_type == "macro_pce" and e.scheduled_date.isoformat() == "2026-01-22")
    assert unusual.scheduled_at.hour == 10  # Explicit source time, not a universal 08:30.
    assert unusual.reference_period is None  # Combined October/November release is not guessed.


@pytest.mark.parametrize("kind", ["cpi", "employment"])
def test_bls_footer_explicit_next_period(kind):
    event = next_bls_release(fixture(kind + ".html"), kind, NOW)
    assert event.reference_period == "2026-09"
    assert event.scheduled_at.hour == 8 and event.scheduled_at.minute == 30


def test_revisions_belong_to_one_underlying_report():
    jobs = release("employment")
    assert len(jobs.measurements) == 2 and len(jobs.revisions) == 2
    assert [(r.reference_period, r.previous_value.amount, r.actual_value.amount) for r in jobs.revisions] == [
        ("2026-06", 20000, 31000), ("2026-07", -23000, 21000)]
    gdp = release("gdp")
    assert gdp.release_type == "Second Estimate"
    assert gdp.revisions[0].reference_period == gdp.reference_period
    assert gdp.measurements[0].previous_value.amount == 1.5
    assert gdp.revisions[0].provenance == gdp.provenance[0]


@pytest.mark.parametrize("kind", list(TITLES))
def test_announcement_not_request_time_and_no_future_release(kind):
    event = release(kind)
    later = parse_release(fixture(kind + ".html"), kind, URLS[kind], NOW + timedelta(days=2))
    assert event.event_id == later.event_id and event.announced_at == later.announced_at
    with pytest.raises(ValueError):
        parse_release(fixture(kind + ".html"), kind, URLS[kind], event.announced_at - timedelta(seconds=1))
    assert lifecycle(event, NOW + timedelta(days=100)).status == "expired"


@pytest.mark.parametrize("kind,old,new", [
    ("cpi", "Aug.<br />2026", "Jul.<br />2026"),
    ("pce", "From the same month one year ago", "Unknown comparison basis"),
    ("employment", "162,000", "unavailable"),
    ("gdp", "Real GDP", "Nominal GDP"),
])
def test_changed_or_incomplete_formats_fail_closed(kind, old, new):
    with pytest.raises(ValueError):
        release(kind, fixture(kind + ".html").replace(old, new))


def test_unknown_timezone_and_non_authoritative_url_rejected():
    with pytest.raises(ValueError):
        parse_calendar(fixture("bls.ics").replace("TZID=US-Eastern", "TZID=Unknown"), BLS_CALENDAR, NOW)
    with pytest.raises(ValueError):
        parse_release(fixture("pce.html"), "pce", "https://example.com/news/2026/pce", NOW)
    assert release_links('<a href="https://example.com/news/2026/pce">Personal Income and Outlays, July 2026</a>') == {}


def test_shared_cache_multi_metric_events_and_non_scoring_relevance():
    client = Client()
    p = provider(client)
    first = p.inspect("ABTC")
    second = p.inspect("NVDA")
    assert first["intelligence"].status == "available", first["diagnostics"]
    assert len(first["intelligence"].recent) == 4
    assert len(first["intelligence"].upcoming) == 6
    assert len(client.calls) == 7 and second["diagnostics"]["source_cache_hits"] == 1
    assert len(first["evidence"]) == 4
    assert all(not e.scoring_eligible for e in first["evidence"])
    assert all(not row.directional_evidence and row.exposure.direction is None for row in first["intelligence"].recent)


@pytest.mark.parametrize("failed,kept", [("bls.gov", {"macro_pce", "macro_gdp"}),
                                        ("bea.gov", {"macro_cpi", "macro_employment"}),
                                        ("cpi.nr0", {"macro_pce", "macro_gdp", "macro_employment"})])
def test_sources_fail_independently(failed, kept):
    result = provider(Client(fail=(failed,))).inspect("ABTC")
    assert result["intelligence"].status == "partial"
    assert {r.event.event_type for r in result["intelligence"].recent} == kept


def consensus(event, key="headline_mom", amount=.3, **changes):
    observed = event.announced_at - timedelta(hours=2)
    return ExpectationSnapshot(**{**dict(snapshot_id="synthetic-consensus", event_id=event.event_id,
        basis="structured_consensus", metric="actual_value", measurement_key=key,
        reference_period=event.reference_period, release_type=event.release_type,
        expected_value=EventValue(amount=amount, unit="percent"), observed_at=observed,
        expires_at=event.announced_at + timedelta(hours=1),
        provenance=EventSource(source="Synthetic control", source_type="market_data", source_url="https://example.com/fixture",
            published_at=observed, retrieved_at=observed)), **changes})


@pytest.mark.parametrize("expected,status", [(.3, "higher_than_expected"), (.5, "lower_than_expected"), (.4, "as_expected")])
def test_metric_consensus_comparison_is_not_probability_or_stock_direction(expected, status):
    event = release("cpi")
    result = with_expectations(event, [consensus(event, amount=expected)], NOW)
    assert result.measurements[0].surprise.status == status
    assert result.measurements[0].expectation.outcomes == ()
    assert all(m.expectation is None for m in result.measurements[1:])
    assert result.expected_value is None and result.surprise.status == "unavailable"


@pytest.mark.parametrize("change", ["late", "stale", "period", "estimate", "units", "wrong_metric"])
def test_invalid_consensus_never_produces_surprise(change):
    event = release("cpi")
    s = consensus(event)
    if change == "late":
        s = s.model_copy(update={"provenance": s.provenance.model_copy(update={"retrieved_at": event.announced_at})})
    elif change == "stale":
        s = s.model_copy(update={"expires_at": event.announced_at})
    elif change == "period":
        s = s.model_copy(update={"reference_period": "2026-07"})
    elif change == "estimate":
        s = s.model_copy(update={"release_type": "Third Estimate"})
    elif change == "units":
        s = s.model_copy(update={"expected_value": EventValue(amount=.3, unit="jobs")})
    else:
        s = s.model_copy(update={"measurement_key": "nonexistent"})
    result = with_expectations(event, [s], NOW)
    assert all(m.surprise.status == "unavailable" for m in result.measurements)


def test_fred_scoring_unchanged_and_event_providers_merge():
    fred = FredEvidenceProvider(settings(fred_api_key="offline-test"), FredClient(), lambda: NOW)
    before = assess_providers("ABTC", [fred], now=NOW)
    after = assess_providers("ABTC", [fred, fomc_provider(), provider()], now=NOW)
    assert len(after.event_intelligence.recent) == 6
    for key in before.categories:
        assert before.categories[key].model_dump(exclude={"evidence"}) == after.categories[key].model_dump(exclude={"evidence"})
    assert before.value == after.value and before.label == after.label
    inspected, _ = inspect_snapshot(after, now=NOW)
    assert inspected.event_intelligence == after.event_intelligence
    assert inspected.categories["economic"].evidence_count == before.categories["economic"].evidence_count
    broken = provider(Client(fail=("gov",)))
    failed = assess_providers("ABTC", [fred, fomc_provider(), broken], now=NOW)
    assert len(failed.event_intelligence.recent) == 2 and failed.event_intelligence.status == "partial"


def test_release_window_cache_transitions_same_id_without_background_work():
    announced = release("cpi").announced_at
    current, elapsed = [announced - timedelta(minutes=1)], [0]
    class ChangingClient(Client):
        def get_text(self, url, **kwargs):
            text = super().get_text(url, **kwargs)
            if url == BLS_RELEASES["cpi"] and current[0] < announced:
                raise TimeoutError("Synthetic not-yet-published release")
            return text
    p = provider(ChangingClient(), clock=lambda: current[0])
    p.source.cache.clock = lambda: elapsed[0]
    before = p.inspect("ABTC")["intelligence"]
    scheduled = next(row.event for row in before.upcoming if row.event.event_id == "cpi:2026-09-11")
    assert all(m.actual_value is None for m in scheduled.measurements)
    current[0], elapsed[0] = announced + timedelta(minutes=1), 121
    after = p.inspect("ABTC")["intelligence"]
    actual = next(row.event for row in after.recent if row.event.event_type == "macro_cpi")
    assert scheduled.event_id == actual.event_id and actual.status == "occurred"
    assert not any(row.event.event_id == actual.event_id for row in after.upcoming)


def test_cli_includes_macro_diagnostics_and_measurements(capsys):
    from app.cli.inspect_events import main
    with patch("app.cli.inspect_events.configured_providers", return_value=[fomc_provider(), provider()]), patch("sys.argv", ["inspect_events", "ABTC", "--json"]):
        assert main() == 0
    output = capsys.readouterr().out
    assert '"macro"' in output and '"measurements"' in output and '"reference_period": "2026-Q2"' in output


def test_horizons_ordering_and_repeated_poll_dedup():
    p = provider()
    first = p.inspect("ABTC")["intelligence"]
    second = p.inspect("ABTC")["intelligence"]
    assert first == second
    assert all(NOW <= r.event.scheduled_at <= NOW + timedelta(days=45) for r in first.upcoming)
    assert all(NOW - timedelta(days=60) < r.event.announced_at <= NOW for r in first.recent)
    assert [r.event.scheduled_at for r in first.upcoming] == sorted(r.event.scheduled_at for r in first.upcoming)
    assert [r.event.announced_at for r in first.recent] == sorted((r.event.announced_at for r in first.recent), reverse=True)
    later = provider(clock=lambda: NOW + timedelta(days=100)).inspect("ABTC")["intelligence"]
    assert not later.recent


@pytest.mark.parametrize("kind", ["cpi", "pce"])
def test_observed_correction_retains_event_id_and_previous_provenance(kind):
    p = provider()
    original = release(kind)
    p.source._reconcile(original)
    changed = original.model_copy(update={"measurements": (
        original.measurements[0].model_copy(update={"actual_value": EventValue(amount=.8, unit="percent")}),
        *original.measurements[1:]), "provenance": (
            original.provenance[0].model_copy(update={"retrieved_at": NOW + timedelta(hours=2)}),)})
    revised = p.source._reconcile(changed)
    assert revised.event_id == original.event_id and revised.announced_at == original.announced_at
    assert revised.release_type == "Updated release"
    assert revised.revisions[-1].previous_value == original.measurements[0].actual_value
    assert revised.revisions[-1].previous_provenance == original.provenance[0]
    assert revised.revisions[-1].provenance.published_at is None  # Correction timing was not published.
    assert p.source._reconcile(changed).revisions == revised.revisions


@pytest.mark.parametrize("kind,key,amount,unit", [("pce", "core_mom", .1, "percent"),
                                               ("gdp", "real_gdp", 1.0, "percent_saar")])
def test_pce_and_gdp_metric_expectations(kind, key, amount, unit):
    event = release(kind)
    snapshot = consensus(event, key, amount, expected_value=EventValue(amount=amount, unit=unit))
    updated = with_expectations(event, [snapshot], NOW)
    row = next(m for m in updated.measurements if m.key == key)
    assert row.surprise.status == "higher_than_expected"


def test_jobs_mixed_surprises_stay_in_one_release():
    event = release("employment")
    payroll = consensus(event, "payrolls", expected_value=EventValue(amount=150000, unit="jobs"))
    unemployment = consensus(event, "unemployment", amount=4.2, snapshot_id="synthetic-unemployment")
    updated = with_expectations(event, [payroll, unemployment], NOW)
    assert [m.surprise.status for m in updated.measurements] == ["higher_than_expected", "lower_than_expected"]
    assert updated.surprise.status == "unavailable"
    assert updated.event_id == event.event_id


def test_gdp_estimate_variants_link_to_same_quarter():
    events = parse_calendar(fixture("bea.ics"), BEA_CALENDAR, NOW)
    q2 = [e for e in events if e.underlying_event_id == "gdp:2026-Q2"]
    assert {e.release_type for e in q2} == {"Advance Estimate", "Second Estimate", "Third Estimate"}
    assert len({e.event_id for e in q2}) == 3


def test_corrected_gdp_does_not_compare_revised_value_to_initial_consensus():
    event = release("gdp")
    p = provider()
    p.source._reconcile(event)
    updated = event.model_copy(update={"measurements": (
        event.measurements[0].model_copy(update={"actual_value": EventValue(amount=1.6, unit="percent_saar")}),)})
    corrected = p.source._reconcile(updated)
    s = consensus(event, "real_gdp", expected_value=EventValue(amount=1.0, unit="percent_saar"))
    result = with_expectations(corrected, [s], NOW)
    assert result.release_type == "Second Estimate"
    assert result.measurements[0].surprise.status == "unavailable"


def test_metric_expectation_survives_upcoming_to_actual():
    actual = release("pce")
    upcoming = next(e for e in parse_calendar(fixture("bea.ics"), BEA_CALENDAR, NOW) if e.event_id == actual.event_id)
    s = consensus(actual)
    before = with_expectations(upcoming, [s], actual.announced_at - timedelta(hours=1))
    assert next(m for m in before.measurements if m.key == "headline_mom").expectation == s
    after = with_expectations(actual, list(before.expectation_history), NOW)
    assert next(m for m in after.measurements if m.key == "headline_mom").surprise.status == "lower_than_expected"
