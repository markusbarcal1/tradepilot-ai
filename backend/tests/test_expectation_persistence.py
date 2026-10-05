"""Offline persistence, compatibility, temporal selection, and surprise tests."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.db import Base, create_database_engine
from app.models.outlook_event import (EarningsMetricIdentity, EventMeasurement, EventSource,
    EventValue, ExpectationSnapshot, ExternalEvent)
from app.models.outlook_reporting import ReportingIdentity, ReportingPeriodIdentity, ReportingProvenance
from app.repositories.expectations import ExpectationRepository
from app.services.earnings_expectations import calculate_surprise, compare_measurement, select_snapshot

RELEASE = datetime(2026, 8, 20, 20, 5, tzinfo=timezone.utc)
PERIOD = ReportingPeriodIdentity(ticker="NVDA", fiscal_year=2026, fiscal_period="Q2",
    period_start=date(2026, 4, 28), period_end=date(2026, 7, 27))
IDENTITY = ReportingIdentity(status="authoritative", reason="fixture", periods=(PERIOD,),
    provenance=(ReportingProvenance(method="explicit_primary_text", source_url="https://sec.gov/nvda",
        document_id="release", basis="Fiscal Q2 2026"),))
REVENUE = EarningsMetricIdentity(metric="revenue", accounting_basis="not_applicable",
    share_basis="not_applicable", scope="total_company")
EPS_GAAP = EarningsMetricIdentity(metric="eps", accounting_basis="gaap",
    share_basis="diluted", scope="total_company")
EPS_ADJUSTED = EPS_GAAP.model_copy(update={"accounting_basis": "adjusted"})


def source(captured):
    return EventSource(source="Fixture consensus", source_type="market_data",
        source_url="https://example.test/consensus", published_at=captured,
        retrieved_at=captured)


def snapshot(key="revenue", amount=94.7, unit="USD_billion", captured=None,
             identity=IDENTITY, metric=REVENUE, snapshot_id=None, currency="USD", **changes):
    captured = RELEASE - timedelta(hours=2) if captured is None else captured
    data = dict(snapshot_id=snapshot_id or f"fixture-{key}-{amount}-{captured.isoformat() if captured else 'unknown'}",
        event_id="earnings:NVDA:FY2026:Q2", basis="structured_consensus", metric="actual_value",
        measurement_key=key, ticker="NVDA", reporting_identity=identity, metric_identity=metric,
        reference_period="FY2026 Q2", release_type="Earnings release",
        expected_value=EventValue(amount=amount, unit=unit), currency=currency,
        analyst_count=30, captured_at=captured, expires_at=RELEASE + timedelta(days=1),
        provider="fixture", provenance=source(captured or RELEASE - timedelta(days=1)))
    return ExpectationSnapshot(**{**data, **changes})


def measurement(key="revenue", amount=96.2, unit="USD_billion", metric=REVENUE, currency="USD"):
    return EventMeasurement(key=key, label=key, actual_value=EventValue(amount=amount, unit=unit),
        metric_identity=metric, currency=currency)


def event(**changes):
    data = dict(event_id="earnings:NVDA:FY2026:Q2", event_type="earnings_release",
        category="earnings", ticker="NVDA", title="NVDA Earnings", summary="Fixture",
        announced_at=RELEASE, scheduled_date=RELEASE.date(), status="occurred",
        reference_period="FY2026 Q2", reporting_identity=IDENTITY,
        release_type="Earnings release", provenance=(source(RELEASE),))
    return ExternalEvent(**{**data, **changes})


@pytest.fixture
def repository(tmp_path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'expectations.db').as_posix()}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield ExpectationRepository(session)
    finally:
        session.close()
        engine.dispose()


def test_persistence_is_global_immutable_deduplicated_and_chronological(repository):
    monday = snapshot(snapshot_id="monday")
    same_payload = snapshot(snapshot_id="poll-repeat", captured=RELEASE - timedelta(hours=1),
        provenance=monday.provenance.model_copy(update={"retrieved_at": RELEASE - timedelta(hours=1)}))
    thursday = snapshot(amount=95.1, snapshot_id="thursday", captured=RELEASE - timedelta(minutes=30))
    assert repository.persist(monday)[1] is True
    duplicate, inserted = repository.persist(same_payload)
    assert inserted is False and duplicate.snapshot_id == "monday"
    assert repository.persist(thursday)[1] is True
    history = repository.history("NVDA", IDENTITY, "revenue")
    assert [row.snapshot_id for row in history] == ["monday", "thursday"]
    assert repository.newest("NVDA", IDENTITY, "revenue").expected_value.amount == 95.1
    assert repository.newest_pre_release("NVDA", IDENTITY, "revenue", RELEASE).snapshot_id == "thursday"
    with pytest.raises(ValueError, match="immutable"):
        repository.persist(snapshot(amount=99, snapshot_id="monday"))


def test_valid_revenue_snapshot_calculates_tradepilot_surprise():
    compared, selection = compare_measurement(event(), measurement(), [snapshot()])
    assert selection.selected.snapshot_id.startswith("fixture-revenue")
    assert compared.surprise.comparison_result == "beat"
    assert compared.surprise.difference.amount == 1.5
    assert compared.surprise.percent_difference == pytest.approx(1.58394931)
    assert compared.surprise.origin == "tradepilot_calculated"
    assert compared.expectation_diagnostics.candidate_count == 1
    assert compared.expectation_diagnostics.compatibility_result == "compatible"
    assert compared.expectation_diagnostics.release_at == RELEASE


def test_newest_valid_pre_release_snapshot_wins_and_post_release_is_rejected():
    old = snapshot(amount=94, snapshot_id="old", captured=RELEASE - timedelta(days=1))
    newest = snapshot(amount=95, snapshot_id="newest", captured=RELEASE - timedelta(seconds=1))
    exact = snapshot(amount=99, snapshot_id="exact", captured=RELEASE)
    after = snapshot(amount=100, snapshot_id="after", captured=RELEASE + timedelta(seconds=1),
        expires_at=RELEASE + timedelta(days=2))
    selected = select_snapshot(event(), measurement(), [after, exact, old, newest])
    assert selected.selected.snapshot_id == "newest" and selected.temporal_count == 2
    rejected = select_snapshot(event(), measurement(), [exact, after])
    assert rejected.selected is None and rejected.rejection_reason == "post_release_only"


def test_unknown_release_time_fails_closed():
    unknown = event(announced_at=None, market_session="unknown")
    result = select_snapshot(unknown, measurement(), [snapshot()])
    assert result.selected is None and result.rejection_reason == "timestamp_unknown"


def test_reporting_period_and_metric_compatibility_rejections():
    other_period = ReportingIdentity(status="authoritative", reason="fixture", periods=(
        PERIOD.model_copy(update={"fiscal_period": "Q1"}),), provenance=IDENTITY.provenance)
    assert select_snapshot(event(), measurement(), [snapshot(identity=other_period)]).rejection_reason == "reporting_period_mismatch"
    eps = measurement("diluted_eps", 1.31, "USD_per_share", EPS_GAAP)
    assert select_snapshot(event(), eps, [snapshot("diluted_eps", 1.25, "USD_per_share",
        metric=EPS_ADJUSTED)]).rejection_reason == "accounting_basis_mismatch"


def test_unit_currency_and_scope_compatibility():
    converted = select_snapshot(event(), measurement(), [snapshot(amount=94700, unit="USD_million")])
    assert converted.expected_value.amount == pytest.approx(94.7)
    assert select_snapshot(event(), measurement(), [snapshot(currency="EUR")]).rejection_reason == "currency_mismatch"
    segment = REVENUE.model_copy(update={"scope": "other"})
    assert select_snapshot(event(), measurement(), [snapshot(metric=segment)]).rejection_reason == "scope_mismatch"


@pytest.mark.parametrize("actual,expected,result,difference,crosses,percent", [
    (-.10, -.20, "beat", .10, False, 50.0),
    (-.30, -.20, "miss", -.10, False, -50.0),
    (.10, -.20, "beat", .30, True, None),
    (-.10, .20, "miss", -.30, True, None),
    (.005, 0, "approximately_in_line", .005, False, None),
])
def test_eps_loss_profit_and_zero_denominator_semantics(actual, expected, result, difference, crosses, percent):
    surprise = calculate_surprise(EventValue(amount=actual, unit="USD_per_share"),
        EventValue(amount=expected, unit="USD_per_share"), EPS_GAAP, "eps-snapshot")
    assert surprise.comparison_result == result
    assert surprise.difference.amount == pytest.approx(difference)
    assert surprise.crosses_zero is crosses and surprise.percent_difference == percent


def test_tolerances_are_metric_specific_and_provider_origin_is_distinct():
    revenue = calculate_surprise(EventValue(amount=100.4, unit="USD_billion"),
        EventValue(amount=100, unit="USD_billion"), REVENUE, "revenue")
    eps = calculate_surprise(EventValue(amount=1.005, unit="USD_per_share"),
        EventValue(amount=1, unit="USD_per_share"), EPS_GAAP, "eps")
    assert revenue.comparison_result == eps.comparison_result == "approximately_in_line"
    provider_reported = revenue.model_copy(update={"origin": "provider_reported"})
    assert provider_reported.origin != revenue.origin
