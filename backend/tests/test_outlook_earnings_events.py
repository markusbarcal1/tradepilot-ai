"""Offline earnings-event lifecycle and reuse of deterministic SEC evidence."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.models.outlook_event import EventSource, EventValue, ExpectationSnapshot
from app.models.outlook_evidence import OutlookEvidence
from app.models.outlook_reporting import ReportingIdentity, ReportingPeriodIdentity, ReportingProvenance
from app.services.outlook_structured.earnings import EarningsEventProvider, released_events, schedule_event

NOW = datetime(2026, 9, 19, 18, tzinfo=timezone.utc)
ANNOUNCED = datetime(2026, 8, 20, 20, 5, tzinfo=timezone.utc)
PERIOD = ReportingPeriodIdentity(ticker="NVDA", fiscal_year=2026, fiscal_period="Q2",
                                 period_start=date(2026, 4, 28), period_end=date(2026, 7, 27))
IDENTITY = ReportingIdentity(status="authoritative", reason="explicit_reporting_identity", periods=(PERIOD,),
    provenance=(ReportingProvenance(method="explicit_primary_text", source_url="https://www.sec.gov/Archives/nvda.htm",
        document_id="nvda-exhibit", accession="0000000000-26-000001", basis="Fiscal Q2 2026 ended July 27, 2026"),))


def settings(**changes):
    return Settings(_env_file=None, environment="test", **changes)


def evidence(metric, value, unit, *, event_type="earnings_result", title="Result", numeric=None, url="https://www.sec.gov/Archives/nvda-exhibit.htm"):
    details = {"accession": "0000000000-26-000001", "document_kind": "earnings_exhibit",
        "source_document_ids": ["nvda-exhibit"], "reporting_identity": IDENTITY.model_dump(mode="json"),
        "numeric": numeric or {"metric": metric, "current_value": value, "unit": unit}}
    return OutlookEvidence(id=f"sec:{metric}:{event_type}", ticker="NVDA", category="earnings", event_type=event_type,
        title=title, summary="Frozen primary-source statement.", source="SEC EDGAR", source_type="regulatory_filing",
        source_url=url, published_at=ANNOUNCED, observed_at=ANNOUNCED + timedelta(minutes=2), impact=1,
        confidence=.9, materiality=.8, materiality_reason="Primary issuer result.", raw_provider="sec",
        raw_provider_id="0000000000-26-000001", source_quality="primary_authoritative", source_details=details)


RECORDS = [
    evidence("revenue", 30.04, "USD_billion"),
    evidence("diluted_eps", .67, "USD_per_share"),
    evidence("gross_margin", 75.1, "percent", event_type="margin_change", numeric={"metric": "gross_margin",
        "current_percent": 75.1, "prior_percent": 70.1, "percentage_points": 5.0}),
    evidence("guidance", 0, "text", event_type="guidance_raise", title="Company raises guidance", numeric={}),
]


class Sec:
    def __init__(self, records=RECORDS, fail=False):
        self.records, self.fail, self.calls = records, fail, 0
    def get_evidence(self, ticker):
        self.calls += 1
        if self.fail:
            raise TimeoutError("synthetic SEC failure")
        return self.records


def info(_):
    return {"shortName": "NVIDIA Corporation"}


def row(day=date(2026, 10, 20), at=None, reported=None, certainty="provider_reported"):
    return {"scheduled_date": day, "scheduled_at": at, "eps_estimate": 1.2,
            "reported_eps": reported, "surprise_percent": None, "certainty": certainty}


def provider(rows=None, sec=None, expectations=None, clock=lambda: NOW):
    return EarningsEventProvider(settings(), sec or Sec(), info, calendar_loader=lambda _: rows if rows is not None else [],
                                 expectations=expectations, clock=clock)


def test_released_event_reuses_reporting_identity_and_one_event_for_all_factors():
    events = released_events("NVDA", "NVIDIA Corporation", RECORDS, NOW)
    assert len(events) == 1
    event = events[0]
    assert event.event_id == "earnings:NVDA:FY2026:Q2"
    assert event.reference_period == "FY2026 Q2" and event.reporting_identity == IDENTITY
    assert event.reporting_identity.periods[0].period_end == date(2026, 7, 27)
    assert {m.key for m in event.measurements} == {"revenue", "diluted_eps", "gross_margin"}
    margin = next(m for m in event.measurements if m.key == "gross_margin")
    assert margin.actual_value.amount == 75.1 and margin.previous_value.amount == 70.1
    assert event.guidance_status == "raised"
    assert len(event.provenance) == 1 and "FY2026 Q2 Earnings Release" in event.provenance[0].source


def test_earnings_exhibit_has_precedence_over_periodic_filing_for_same_metric():
    filing = evidence("revenue", 29.0, "USD_billion", url="https://www.sec.gov/Archives/nvda-10q.htm")
    filing = filing.model_copy(update={"id": "sec:filing:revenue", "source_details": {
        **filing.source_details, "document_kind": "filing_item"}})
    event = released_events("NVDA", "NVIDIA Corporation", [filing, RECORDS[0]], NOW)[0]
    revenue = next(m for m in event.measurements if m.key == "revenue")
    assert revenue.actual_value.amount == 30.04
    assert [source.source for source in event.provenance] == [
        "NVIDIA Corporation FY2026 Q2 Earnings Release",
        "NVIDIA Corporation FY2026 Q2 SEC Filing",
    ]


def test_noncalendar_fiscal_identity_not_inferred_from_release_month():
    event = released_events("NVDA", "NVIDIA Corporation", RECORDS, NOW)[0]
    assert event.reporting_identity.periods[0].fiscal_period == "Q2"
    assert event.announced_at.month == 8
    assert event.reporting_identity.periods[0].period_end.month == 7


def test_upcoming_date_only_provider_reported_and_inherent_relevance():
    result = provider([row()]).inspect("NVDA")
    event = result["intelligence"].upcoming[0].event
    assert event.event_id == "earnings:NVDA:next" and event.scheduled_at is None
    assert event.schedule_certainty == "provider_reported" and event.market_session == "unknown"
    assert event.reporting_identity is None and not event.measurements
    assert result["intelligence"].upcoming[0].exposure.relevance == "company_specific"
    assert result["evidence"] == [] and result["diagnostics"]["duplicate_event_evidence"] == 0


@pytest.mark.parametrize("hour,session", [(8, "before_market"), (13, "during_market"), (16, "after_market")])
def test_supported_market_session(hour, session):
    at = datetime(2026, 10, 20, hour, tzinfo=timezone(timedelta(hours=-4)))
    event = provider([row(at=at)]).inspect("NVDA")["intelligence"].upcoming[0].event
    assert event.market_session == session and event.scheduled_at == at


def test_schedule_change_preserves_identity_history_and_confirmation_upgrade():
    current = [row()]
    p = provider(current)
    first = p.inspect("NVDA")["intelligence"].upcoming[0].event
    p.calendar_cache.entries.clear()
    current[:] = [row(date(2026, 10, 22))]
    second = p.inspect("NVDA")["intelligence"].upcoming[0].event
    assert first.event_id == second.event_id and second.scheduled_date == date(2026, 10, 22)
    assert second.schedule_history == first.provenance
    third = schedule_event("NVDA", "NVIDIA Corporation", row(date(2026, 10, 22), certainty="confirmed"), NOW, previous=second)
    assert third.event_id == second.event_id and third.schedule_certainty == "confirmed"


def test_estimated_schedule_is_preserved_as_estimated():
    event = provider([row(certainty="estimated")]).inspect("NVDA")["intelligence"].upcoming[0].event
    assert event.schedule_certainty == "estimated"


def test_upcoming_transitions_to_released_without_duplicate_in_same_process():
    clock = [datetime(2026, 8, 20, 18, tzinfo=timezone.utc)]
    rows = [row(date(2026, 8, 20))]
    p = provider(rows, clock=lambda: clock[0])
    before = p.inspect("NVDA")["intelligence"].upcoming[0].event
    clock[0] = NOW
    p.calendar_cache.entries.clear()
    rows[0] = row(date(2026, 8, 20), reported=.67)
    after = p.inspect("NVDA")["intelligence"]
    assert not after.upcoming
    assert after.recent[0].event.event_id == before.event_id
    assert after.recent[0].event.underlying_event_id == "earnings:NVDA:FY2026:Q2"


def expectation(event, key, amount, unit, **changes):
    observed = event.announced_at - timedelta(hours=2)
    data = dict(snapshot_id=f"synthetic-{key}", event_id=event.event_id, basis="structured_consensus",
        metric="actual_value", measurement_key=key, reference_period=event.reference_period,
        release_type=event.release_type, expected_value=EventValue(amount=amount, unit=unit),
        observed_at=observed, expires_at=event.announced_at + timedelta(minutes=1),
        provenance=EventSource(source="Synthetic pre-release consensus", source_type="market_data",
            source_url="https://example.com/consensus", published_at=observed, retrieved_at=observed))
    return ExpectationSnapshot(**{**data, **changes})


class Consensus:
    def __init__(self, snapshots=(), fail=False): self.snapshots_, self.fail = snapshots, fail
    def snapshots(self, event_id):
        if self.fail: raise TimeoutError("synthetic consensus failure")
        return [s for s in self.snapshots_ if s.event_id == event_id]


def test_eps_revenue_surprise_is_per_metric_and_no_probability():
    event = released_events("NVDA", "NVIDIA Corporation", RECORDS, NOW)[0]
    snapshots = [expectation(event, "diluted_eps", .60, "USD_per_share"),
                 expectation(event, "revenue", 31, "USD_billion")]
    p = provider([], expectations=Consensus(snapshots))
    result = p._expectations(event, NOW)
    values = {m.key: m for m in result.measurements}
    assert values["diluted_eps"].surprise.status == "higher_than_expected"
    assert values["diluted_eps"].surprise.percent_difference == pytest.approx(11.66666667)
    assert values["revenue"].surprise.status == "lower_than_expected"
    assert values["revenue"].surprise.percent_difference == pytest.approx(-3.09677419)
    assert all(not m.expectation.outcomes for m in values.values() if m.expectation)
    assert result.surprise.status == "unavailable"


def test_near_zero_stale_post_release_and_failure_do_not_fabricate_surprise():
    event = released_events("NVDA", "NVIDIA Corporation", RECORDS, NOW)[0]
    near_zero = expectation(event, "diluted_eps", 0, "USD_per_share")
    stale = expectation(event, "revenue", 31, "USD_billion", expires_at=event.announced_at)
    late_time = event.announced_at + timedelta(minutes=1)
    late = expectation(event, "revenue", 31, "USD_billion", snapshot_id="late",
        observed_at=late_time, expires_at=late_time + timedelta(hours=1), provenance=EventSource(source="Late", source_type="market_data",
            source_url="https://example.com/late", published_at=late_time, retrieved_at=late_time))
    result = provider([], expectations=Consensus([near_zero, stale, late]))._expectations(event, NOW)
    eps = next(m for m in result.measurements if m.key == "diluted_eps")
    revenue = next(m for m in result.measurements if m.key == "revenue")
    assert eps.surprise.percent_difference is None
    assert revenue.expectation is None and revenue.surprise.status == "unavailable"
    failed = provider([], expectations=Consensus(fail=True))._expectations(event, NOW)
    assert all(m.expectation_status == "error" for m in failed.measurements)


def test_calendar_sec_and_consensus_fail_independently():
    calendar_failure = EarningsEventProvider(settings(), Sec(), info,
        calendar_loader=lambda _: (_ for _ in ()).throw(TimeoutError()), clock=lambda: NOW).inspect("NVDA")
    assert calendar_failure["intelligence"].recent and calendar_failure["diagnostics"]["schedule_status"] == "unavailable"
    sec_failure = provider([row()], sec=Sec(fail=True)).inspect("NVDA")
    assert sec_failure["intelligence"].upcoming and not sec_failure["intelligence"].recent
    assert sec_failure["diagnostics"]["sec_status"] == "unavailable"


def test_calendar_cache_and_sec_provider_reuse():
    loads = []
    sec = Sec()
    p = EarningsEventProvider(settings(), sec, info, calendar_loader=lambda ticker: loads.append(ticker) or [row()], clock=lambda: NOW)
    first, second = p.inspect("NVDA"), p.inspect("NVDA")
    assert loads == ["NVDA"] and first["diagnostics"]["calendar_loads"] == 1
    assert second["diagnostics"]["calendar_cache_hits"] == 1
    assert sec.calls == 2  # Existing SEC provider caches its network/documents; no independent SEC client exists here.


def test_unknown_or_conflicting_identity_produces_no_released_event():
    unknown = RECORDS[0].model_copy(update={"source_details": {**RECORDS[0].source_details,
        "reporting_identity": ReportingIdentity().model_dump(mode="json")}})
    assert released_events("NVDA", "NVIDIA Corporation", [unknown], NOW) == []


@pytest.mark.parametrize("event_type,status", [
    ("guidance_raise", "raised"),
    ("guidance_cut", "lowered"),
    ("guidance_withdrawal", "withdrawn"),
])
def test_supported_directional_guidance_statuses(event_type, status):
    guidance = evidence("guidance", 0, "text", event_type=event_type, numeric={})
    event = released_events("NVDA", "NVIDIA Corporation", [RECORDS[0], guidance], NOW)[0]
    assert event.guidance_status == status


def test_new_or_ambiguous_guidance_is_not_promoted_to_directional_status():
    ambiguous = evidence("guidance", 0, "text", event_type="earnings_other", numeric={})
    event = released_events("NVDA", "NVIDIA Corporation", [RECORDS[0], ambiguous], NOW)[0]
    assert event.guidance_status == "unavailable"
