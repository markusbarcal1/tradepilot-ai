"""Deterministic decision presentation derived from existing Outlook inputs."""
from datetime import datetime

from app.models.outlook import (CategoryDriver, CategoryIntelligence, IntelligenceMetric,
    IntelligenceSource, MaterialEventSummary, OutlookCategory)
from app.models.outlook_event import EventIntelligence, EventMeasurement, EventValue, ExternalEvent
from app.models.outlook_taxonomy import CATEGORY_TITLES, CategoryKey

DRIVER_LIMIT = 4
EVENT_IMPORTANCE = {
    "earnings_release": "high", "fomc_rate_decision": "high", "macro_cpi": "high",
    "macro_pce": "high", "macro_employment": "high", "macro_gdp": "medium",
}


def _source(item):
    return IntelligenceSource(evidence_id=getattr(item, "id", None), name=getattr(item, "source", None) or item.title,
        url=str(item.source_url) if getattr(item, "source_url", None) else None,
        published_at=item.published_at.isoformat() if getattr(item, "published_at", None) else None)


def _event_sources(event):
    return tuple(IntelligenceSource(name=row.source, url=str(row.source_url),
        published_at=row.published_at.isoformat() if row.published_at else None) for row in event.provenance)


def _importance(materiality):
    return "high" if materiality >= .75 else "medium" if materiality >= .5 else "low"


def _value(value: EventValue | None):
    if not value:
        return None
    if value.amount is None:
        if value.lower is not None:
            return f"{value.lower:g}–{value.upper:g} {value.unit}"
        return value.text
    amount = value.amount
    if value.unit == "USD_per_share":
        return f"${amount:.2f}"
    if value.unit == "USD_billion":
        return f"${amount:g}B"
    if value.unit == "USD_million":
        return f"${amount:g}M"
    if value.unit == "percent":
        return f"{amount:g}%"
    return f"{amount:g} {value.unit}"


def _expectation_indicator(measurement: EventMeasurement):
    actual = measurement.actual_value
    expected = measurement.expectation.expected_value if measurement.expectation else None
    if measurement.expectation_status != "available" or not actual or not expected:
        return None, None
    if measurement.surprise.comparison_result != "unavailable":
        indicator = {"beat": "Beat", "miss": "Miss",
                     "approximately_in_line": "In Line"}[measurement.surprise.comparison_result]
        percent = measurement.surprise.percent_difference
        return indicator, f"{percent:+.1f}%" if percent is not None else None
    if actual.unit != expected.unit or actual.amount is None or expected.amount is None:
        return None, None
    delta = actual.amount - expected.amount
    # A 0.5% relative band suppresses microscopic differences. EPS also uses a
    # one-cent absolute floor. Near-zero expectations cannot support a percent result.
    tolerance = max(abs(expected.amount) * .005, .01 if actual.unit == "USD_per_share" else 1e-6)
    indicator = "In Line" if abs(delta) <= tolerance else "Beat" if delta > 0 else "Miss"
    result = None if abs(expected.amount) < 1e-6 else f"{delta / abs(expected.amount) * 100:+.1f}%"
    return indicator, result


def _metric(measurement, sources):
    indicator, result = _expectation_indicator(measurement)
    previous = _value(measurement.previous_value)
    if indicator is None and measurement.actual_value and measurement.previous_value:
        current, prior = measurement.actual_value.amount, measurement.previous_value.amount
        if current is not None and prior is not None and measurement.actual_value.unit == measurement.previous_value.unit:
            change = current - prior
            tolerance = .1 if measurement.actual_value.unit == "percent" else 1e-6
            indicator = "Unchanged" if abs(change) < tolerance else "Improved" if change > 0 else "Declined"
            suffix = " pp" if measurement.actual_value.unit == "percent" else f" {measurement.actual_value.unit}"
            result = f"{change:+.1f}{suffix}"
    return IntelligenceMetric(key=measurement.key, label=measurement.label,
        actual=_value(measurement.actual_value),
        expected=_value(measurement.expectation.expected_value) if measurement.expectation_status == "available" and measurement.expectation else None,
        previous=previous, result=result, indicator=indicator,
        comparison_status=measurement.expectation_status, sources=sources)


def event_importance(event):
    return EVENT_IMPORTANCE.get(event.event_type, "low")


def _event_summary(event):
    timing = event.market_session.replace("_", " ").title() if event.market_session else None
    certainty = event.schedule_certainty.replace("_", " ").title() if event.schedule_certainty else None
    return MaterialEventSummary(event_id=event.event_id, title=event.title, status=event.status,
        event_date=event.scheduled_date or (event.announced_at.date() if event.announced_at else None),
        importance=event_importance(event), timing=timing, certainty=certainty)


def build_key_events(events: EventIntelligence):
    """Bounded upcoming list; importance comes only from the controlled mapping."""
    return tuple(_event_summary(row.event) for row in events.upcoming[:4])


def _category_events(category, intelligence):
    def belongs(event):
        if category == "earnings": return event.category == "earnings"
        if category == "economic": return event.category == "economic"
        return event.category == category
    upcoming = [row.event for row in intelligence.upcoming if belongs(row.event)]
    recent = [row.event for row in intelligence.recent if belongs(row.event)]
    return recent, upcoming


def _earnings(category, intelligence):
    recent, upcoming = _category_events("earnings", intelligence)
    latest = recent[0] if recent else None
    metrics = tuple(_metric(row, _event_sources(latest)) for row in latest.measurements) if latest else ()
    drivers = []
    if latest:
        for metric in metrics:
            if metric.indicator:
                direction = "positive" if metric.indicator in ("Beat", "Improved") else "negative" if metric.indicator in ("Miss", "Declined") else "neutral"
                drivers.append(CategoryDriver(label=f"{metric.label} {metric.indicator.lower()}", direction=direction,
                    importance="high" if metric.key in ("revenue", "eps", "diluted_eps") else "medium",
                    value=metric.actual, change=metric.result, sources=metric.sources, related_event_id=latest.event_id))
        guidance = latest.guidance_status
        if guidance and guidance != "unavailable":
            direction = "positive" if guidance == "raised" else "negative" if guidance in ("lowered", "withdrawn") else "neutral" if guidance in ("maintained", "new") else "mixed"
            drivers.append(CategoryDriver(label=f"Guidance {guidance}", direction=direction, importance="high",
                sources=_event_sources(latest), related_event_id=latest.event_id))
    return metrics, drivers, latest, upcoming[0] if upcoming else None


def build_category_intelligence(categories: dict[CategoryKey, OutlookCategory],
                                events: EventIntelligence) -> dict[CategoryKey, CategoryIntelligence]:
    result = {}
    for key in CATEGORY_TITLES:
        category = categories[key]
        evidence = {item.id: item for item in category.evidence}
        drivers = []
        for factor in category.factors:
            records = [evidence[item] for item in factor.evidence_ids if item in evidence]
            materiality = max((item.materiality for item in records), default=0)
            direction = "positive" if factor.impact.value.endswith("Positive") else "negative" if factor.impact.value.endswith("Negative") else "mixed"
            drivers.append(CategoryDriver(label=factor.title, direction=direction,
                importance=_importance(materiality), sources=tuple(_source(item) for item in records)))
        recent, upcoming = _category_events(key, events)
        metrics = ()
        if key == "earnings":
            metrics, earnings_drivers, latest, next_event = _earnings(category, events)
            # Metric drivers explain measurements; factor drivers retain the rating link.
            drivers = earnings_drivers + drivers
        else:
            latest, next_event = (recent[0] if recent else None), (upcoming[0] if upcoming else None)
        direction_order = {"high": 0, "medium": 1, "low": 2, None: 3}
        drivers.sort(key=lambda row: (direction_order[row.importance], row.label, row.related_event_id or ""))
        selected, omitted = drivers[:DRIVER_LIMIT], max(0, len(drivers) - DRIVER_LIMIT)
        grouped = {direction: tuple(row for row in selected if row.direction == direction)
                   for direction in ("positive", "negative", "neutral", "mixed")}
        sufficiency = (f"{category.evidence_count or 0} qualifying events; current support threshold met."
            if category.status == "available" else category.summary)
        sources = tuple(dict.fromkeys(_source(item).model_dump_json() for item in category.evidence))
        sources = tuple(IntelligenceSource.model_validate_json(item) for item in sources)
        summary = (f"{CATEGORY_TITLES[key]} outlook is {category.label.value.lower()}."
                   if category.status == "available" and category.label else
                   "More independent evidence is required." if category.status == "insufficient_data" else
                   "Reviewed evidence is not material to this company." if category.status == "not_material" else
                   "Decision context is temporarily unavailable." if category.status == "error" else
                   "Decision context is not currently available.")
        result[key] = CategoryIntelligence(category=key, rating=category.label,
            availability=category.status, summary=summary,
            positive_drivers=grouped["positive"], negative_drivers=grouped["negative"],
            neutral_mixed_drivers=(*grouped["neutral"], *grouped["mixed"]),
            important_metrics=metrics, latest_material_event=_event_summary(latest) if latest else None,
            next_material_event=_event_summary(next_event) if next_event else None,
            sources=sources, evidence_sufficiency=sufficiency, omitted_driver_count=omitted)
    return result
