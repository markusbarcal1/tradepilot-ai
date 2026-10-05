"""Offline decision-intelligence presentation tests."""
from datetime import date, datetime, timedelta, timezone

from app.models.outlook import OutlookCategory, OutlookFactor
from app.models.outlook_event import (EventIntelligence, EventMeasurement, EventSource, EventValue,
    ExpectationSnapshot, ExposureAssessment, ExternalEvent, RelevantEvent)
from app.services.outlook_intelligence import build_category_intelligence, build_key_events
from app.models.outlook_taxonomy import CATEGORY_TITLES

NOW = datetime(2026, 9, 19, 18, tzinfo=timezone.utc)
SOURCE = EventSource(source="Issuer FY2026 Q3 Earnings Release", source_type="regulatory_filing",
    source_url="https://www.sec.gov/Archives/aapl.htm", published_at=NOW - timedelta(days=1), retrieved_at=NOW)
EXPOSURE = ExposureAssessment(True, "Issuer event", relevance="company_specific", directness="business",
                              confidence=1, materiality=1)


def categories(earnings=None):
    result = {key: OutlookCategory(status="insufficient_data", evidence_count=0,
        summary="Insufficient independent evidence: 0 qualifying events.") for key in CATEGORY_TITLES}
    if earnings:
        result["earnings"] = earnings
    return result


def expectation(event_id, key, amount, unit):
    observed = NOW - timedelta(days=1, hours=2)
    return ExpectationSnapshot(snapshot_id=f"consensus-{key}", event_id=event_id, basis="structured_consensus",
        metric="actual_value", measurement_key=key, reference_period="FY2026 Q3", release_type="Earnings release",
        expected_value=EventValue(amount=amount, unit=unit), observed_at=observed,
        expires_at=NOW - timedelta(days=1) + timedelta(minutes=1),
        provenance=EventSource(source="Frozen consensus", source_type="market_data", source_url="https://example.com/consensus",
            published_at=observed, retrieved_at=observed))


def earnings_event(measurements=(), guidance="unavailable", status="occurred"):
    event_id = "earnings:AAPL:FY2026:Q3" if status != "upcoming" else "earnings:AAPL:next"
    return ExternalEvent(event_id=event_id, event_type="earnings_release", category="earnings", title="AAPL Earnings",
        summary="Issuer earnings.", status=status, scheduled_date=date(2026, 10, 29) if status == "upcoming" else date(2026, 9, 18),
        announced_at=None if status == "upcoming" else NOW - timedelta(days=1), reference_period="FY2026 Q3",
        schedule_certainty="provider_reported", guidance_status=guidance, measurements=measurements, provenance=(SOURCE,))


def intelligence(recent=(), upcoming=()):
    return EventIntelligence(status="available",
        recent=tuple(RelevantEvent(event=e, exposure=EXPOSURE) for e in recent),
        upcoming=tuple(RelevantEvent(event=e, exposure=EXPOSURE) for e in upcoming))


def test_actual_only_metrics_remain_non_directional_and_retain_provenance():
    event = earnings_event((EventMeasurement(key="diluted_eps", label="Diluted EPS",
        actual_value=EventValue(amount=2.02, unit="USD_per_share")),))
    result = build_category_intelligence(categories(), intelligence([event]))["earnings"]
    assert result.important_metrics[0].actual == "$2.02"
    assert result.important_metrics[0].expected is None and result.important_metrics[0].indicator is None
    assert not result.positive_drivers and not result.negative_drivers
    assert result.important_metrics[0].sources[0].url.endswith("aapl.htm")


def test_earnings_beat_miss_inline_and_margin_are_metric_specific():
    event_id = "earnings:AAPL:FY2026:Q3"
    metrics = (
        EventMeasurement(key="diluted_eps", label="EPS", actual_value=EventValue(amount=2.02, unit="USD_per_share"),
            expectation=expectation(event_id, "diluted_eps", 1.89, "USD_per_share"), expectation_status="available"),
        EventMeasurement(key="revenue", label="Revenue", actual_value=EventValue(amount=107, unit="USD_billion"),
            expectation=expectation(event_id, "revenue", 108, "USD_billion"), expectation_status="available"),
        EventMeasurement(key="adjusted_eps", label="Adjusted EPS", actual_value=EventValue(amount=1.895, unit="USD_per_share"),
            expectation=expectation(event_id, "adjusted_eps", 1.89, "USD_per_share"), expectation_status="available"),
        EventMeasurement(key="gross_margin", label="Gross Margin", actual_value=EventValue(amount=46.5, unit="percent"),
            previous_value=EventValue(amount=46, unit="percent")),
    )
    result = build_category_intelligence(categories(), intelligence([earnings_event(metrics)]))["earnings"]
    values = {row.key: row for row in result.important_metrics}
    assert values["diluted_eps"].indicator == "Beat" and values["diluted_eps"].result == "+6.9%"
    assert values["revenue"].indicator == "Miss" and values["adjusted_eps"].indicator == "In Line"
    assert values["gross_margin"].indicator == "Improved" and values["gross_margin"].result == "+0.5 pp"


def test_near_zero_expectation_has_no_percentage_but_keeps_deterministic_label():
    event_id = "earnings:AAPL:FY2026:Q3"
    metric = EventMeasurement(key="diluted_eps", label="EPS", actual_value=EventValue(amount=.02, unit="USD_per_share"),
        expectation=expectation(event_id, "diluted_eps", 0, "USD_per_share"), expectation_status="available")
    result = build_category_intelligence(categories(), intelligence([earnings_event((metric,))]))["earnings"].important_metrics[0]
    assert result.indicator == "Beat" and result.result is None


def test_guidance_direction_and_upcoming_event_do_not_create_fake_driver():
    released = earnings_event(guidance="lowered")
    upcoming = earnings_event(status="upcoming")
    result = build_category_intelligence(categories(), intelligence([released], [upcoming]))["earnings"]
    assert [row.label for row in result.negative_drivers] == ["Guidance lowered"]
    assert result.next_material_event.event_id == upcoming.event_id
    assert not any(row.related_event_id == upcoming.event_id for row in (*result.positive_drivers, *result.negative_drivers, *result.neutral_mixed_drivers))


def test_event_importance_and_insufficient_categories_are_serializable():
    high = earnings_event(status="upcoming")
    low = high.model_copy(update={"event_id": "other", "event_type": "other_event", "title": "Other"})
    events = intelligence(upcoming=[high, low])
    summaries = build_key_events(events)
    assert [row.importance for row in summaries] == ["high", "low"]
    result = build_category_intelligence(categories(), events)
    assert result["company"].availability == "insufficient_data"
    assert result["company"].model_dump(mode="json")["evidence_sufficiency"].startswith("Insufficient")


def test_generic_driver_direction_prioritization_and_omission_are_backend_owned():
    factors = [
        OutlookFactor(title="Positive driver", impact="Positive", description="Supported."),
        OutlookFactor(title="Negative driver", impact="Negative", description="Supported."),
        OutlookFactor(title="Neutral driver", impact="Mixed", description="Supported."),
        OutlookFactor(title="Second positive", impact="Very Positive", description="Supported."),
        OutlookFactor(title="Lower priority", impact="Mixed", description="Supported."),
    ]
    company = OutlookCategory(status="available", value=0, factors=factors, evidence_count=5,
                              summary="Five supported factors.")
    result = build_category_intelligence(categories(company), EventIntelligence())["earnings"]
    assert len(result.positive_drivers) == 1
    assert len(result.negative_drivers) == 1 and len(result.neutral_mixed_drivers) == 2
    assert result.omitted_driver_count == 1 and result.rating.value == "Mixed"
    assert "Second positive" not in {row.label for row in (*result.positive_drivers, *result.negative_drivers, *result.neutral_mixed_drivers)}
