"""Presentation-only assembly from one deterministic Outlook snapshot."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Iterable

from app.models.outlook import OutlookResponse
from app.models.outlook_ai import AIOutlookResponse, OutlookContextPacket
from app.models.outlook_event import EventSource, ExternalEvent
from app.models.outlook_evidence import OutlookEvidence
from app.models.outlook_reporting import ReportingIdentity
from app.models.outlook_research import (EconomicResearch, EarningsResearch, EventResearch,
    IndustryHistory, IndustryHistoryCoverage, IndustryHistoryPoint, IndustryHistoryWindow,
    IndustryResearch, MarketBenchmark, MarketResearch, MarketVolatility, ResearchBenchmark,
    ResearchBreadth, ResearchCatalyst, ResearchComparison, ResearchEvent, ResearchMetric,
    ResearchPresentation, ResearchSeries, ResearchSeriesPoint, ResearchSource,
    RevenueHistoryGrowth, RevenueHistoryPoint, RevenueHistoryResearch)
from app.models.outlook_revenue_research import RevenueResearchProjectionResult


def _pid(kind: str, identity: str) -> str:
    return f"{kind}-{sha256(identity.encode()).hexdigest()[:12]}"


class _Sources:
    def __init__(self):
        self.rows: dict[tuple[str, str], ResearchSource] = {}

    def evidence(self, row: OutlookEvidence) -> str | None:
        if not row.source_url:
            return None
        return self.add(str(row.source_url), row.source, row.title, row.source_type.value,
                        row.published_at.date())

    def event(self, row: EventSource) -> str:
        return self.add(str(row.source_url), row.source, row.source, row.source_type.value,
                        row.published_at.date() if row.published_at else None)

    def add(self, url, name, title, source_type, day):
        key = (url, title or name)
        if key not in self.rows:
            self.rows[key] = ResearchSource(id=_pid("source", "|".join(key)), name=name,
                title=title, url=url, source_type=source_type, date=day)
        return self.rows[key].id

    def ids_for_evidence(self, row):
        value = self.evidence(row)
        return (value,) if value else ()

    def ids_for_event(self, row):
        return tuple(dict.fromkeys(self.event(source) for source in row.provenance))


def _number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _direction(row: OutlookEvidence):
    if not row.scoring_eligible or row.impact == 0:
        return "informational"
    return "positive" if row.impact > 0 else "negative"


def _event(row: ExternalEvent, sources: _Sources, *, summary=None, qualifier=None):
    details = {}
    if row.reporting_identity and row.reporting_identity.status == "authoritative":
        period = row.reporting_identity.periods[0]
        details.update(fiscal_year=period.fiscal_year, fiscal_period=period.fiscal_period,
                       period_end=period.period_end.isoformat() if period.period_end else None)
    return ResearchEvent(id=_pid("event", row.event_id), category=row.category,
        event_type=row.event_type, title=row.title, summary=summary or row.summary,
        date=row.scheduled_date or (row.announced_at.date() if row.announced_at else row.effective_date),
        scheduled_at=row.scheduled_at, timezone=row.scheduled_timezone,
        market_session=row.market_session, schedule_certainty=row.schedule_certainty,
        reference_period=row.reference_period, details=details,
        source_ids=sources.ids_for_event(row), qualifier=qualifier)


def _earnings(outlook, sources):
    recent = [row.event for row in outlook.event_intelligence.recent if row.event.category == "earnings"]
    upcoming = [row.event for row in outlook.event_intelligence.upcoming if row.event.category == "earnings"]
    latest = recent[0] if recent else None
    evidence = [row for row in outlook.categories["earnings"].evidence if row.scoring_eligible]
    fiscal_year = fiscal_period = period_end = None
    if latest and latest.reporting_identity and latest.reporting_identity.status == "authoritative":
        period = latest.reporting_identity.periods[0]
        fiscal_year, fiscal_period, period_end = period.fiscal_year, period.fiscal_period, period.period_end
    metrics = []
    supported = {"revenue", "diluted_eps", "gross_margin", "operating_margin"}
    latest_period_key = (latest.reporting_identity.periods[0].key if latest and
        latest.reporting_identity and latest.reporting_identity.status == "authoritative" else None)

    def matching_evidence(measurement):
        matches = []
        for row in evidence:
            numeric = row.source_details.get("numeric")
            if not isinstance(numeric, dict):
                continue
            metric = str(numeric.get("metric") or "").lower().replace("revenues", "revenue")
            if metric != measurement.key:
                continue
            try:
                identity = ReportingIdentity.model_validate(row.source_details.get("reporting_identity"))
                period = next(p for p in identity.periods if p.fiscal_period != "FY")
            except Exception:
                continue
            if identity.status != "authoritative" or period.key != latest_period_key:
                continue
            current = numeric.get("current_percent") if measurement.key.endswith("_margin") else numeric.get("current_value")
            unit = "percent" if measurement.key.endswith("_margin") else numeric.get("unit")
            if _number(current) == measurement.actual_value.amount and unit == measurement.actual_value.unit:
                matches.append(row)
        return matches

    if latest:
        for measurement in latest.measurements:
            actual = measurement.actual_value
            if measurement.key not in supported or not actual or actual.amount is None:
                continue
            previous = measurement.previous_value.amount if measurement.previous_value and measurement.previous_value.amount is not None else None
            change = actual.amount - previous if previous is not None and measurement.previous_value.unit == actual.unit else None
            accepted = matching_evidence(measurement)
            ids = tuple(dict.fromkeys((*sources.ids_for_event(latest),
                *(source for row in accepted for source in sources.ids_for_evidence(row)))))
            comparison = next((row.source_details.get("numeric", {}) for row in accepted
                if row.source_details.get("numeric", {}).get("comparison") == "year_over_year"), {})
            exact_comparison = (previous is not None and change is not None
                and comparison.get("comparison") == "year_over_year"
                and _number(comparison.get("prior_percent")) == previous)
            metrics.append(ResearchMetric(id=_pid("metric", f"{latest.event_id}:{measurement.key}"),
                label=measurement.label, value=actual.amount, unit=actual.unit,
                previous_value=previous if exact_comparison else None,
                change=change if exact_comparison else None,
                change_unit="percentage_points" if exact_comparison else None,
                observation_date=latest.announced_at.date() if latest.announced_at else latest.scheduled_date,
                comparison_date=None, period=latest.reference_period,
                comparison_label="Year over year" if exact_comparison else None,
                comparison_type="year_over_year" if exact_comparison else None,
                comparison_basis="exact_values" if exact_comparison else None,
                comparison_period=str(comparison.get("prior_period")) if exact_comparison and comparison.get("prior_period") else None,
                source_ids=ids,
                qualifier="Primary-source reported result; no consensus or forecast is implied."))
    for row in evidence:
        numeric = row.source_details.get("numeric")
        if not isinstance(numeric, dict):
            continue
        metric_name = str(numeric.get("metric") or "").lower().replace("earnings per share", "diluted_eps").replace(" ", "_")
        change_percent = _number(numeric.get("change_percent"))
        if change_percent is None:
            continue
        target = next((m for m in metrics if
                       (metric_name == "revenue" and m.label.lower() == "revenue") or
                       (metric_name == "diluted_eps" and m.label.lower() == "diluted eps")), None)
        try:
            identity = ReportingIdentity.model_validate(row.source_details.get("reporting_identity"))
            row_period = next(p for p in identity.periods if p.fiscal_period != "FY")
        except Exception:
            identity = None
            row_period = None
        current = _number(numeric.get("current_value"))
        unit_matches = numeric.get("unit") == target.unit if target else False
        if (target and identity and identity.status == "authoritative" and row_period.key == latest_period_key
                and current == target.value and unit_matches and numeric.get("comparison") == "year_over_year"):
            metrics[metrics.index(target)] = target.model_copy(update={
                "change": change_percent, "change_unit": "percent",
                "comparison_label": "Reported year over year",
                "comparison_type": "year_over_year", "comparison_basis": "reported_change_only",
                "source_ids": tuple(dict.fromkeys((*target.source_ids, *sources.ids_for_evidence(row))))})
    priority = {"Revenue": 0, "Diluted EPS": 1, "Gross Margin": 2, "Operating Margin": 3}
    metrics.sort(key=lambda row: priority.get(row.label, 99))
    guidance = tuple(ResearchEvent(id=_pid("event", row.id), category="earnings",
        event_type=row.event_type.value, title=row.title, summary=row.summary,
        date=row.published_at.date(), direction=_direction(row),
        details={k: v for k, v in (row.source_details.get("numeric") or {}).items()
                 if isinstance(v, (str, int, float, bool))},
        source_ids=sources.ids_for_evidence(row)) for row in evidence if row.event_type.value.startswith("guidance_"))
    return EarningsResearch(fiscal_year=fiscal_year, fiscal_period=fiscal_period,
        period_end=period_end, release_date=latest.announced_at.date() if latest and latest.announced_at else None,
        metrics=tuple(metrics), guidance=guidance,
        next_event=_event(upcoming[0], sources) if upcoming else None)


def _industry(outlook, sources):
    rows = [row for row in outlook.categories["industry"].evidence if row.scoring_eligible]
    detail = next((row.source_details for row in rows if row.event_type.value == "industry_other"),
                  rows[0].source_details if rows else {})
    group = next((row.source_details for row in rows if row.event_type.value == "sector_performance"), {})
    source_ids = tuple(dict.fromkeys(source for row in rows for source in sources.ids_for_evidence(row)))
    comparisons = []
    for window in (21, 63):
        company, benchmark, relative = (_number(detail.get(f"company_return_{window}")),
            _number(detail.get(f"benchmark_return_{window}")), _number(detail.get(f"relative_return_{window}")))
        if None not in (company, benchmark, relative):
            comparisons.append(ResearchComparison(window_sessions=window, company_return=company,
                benchmark_return=benchmark, relative_difference=relative))
    breadth = None
    if detail.get("benchmark_type") == "industry_etf" and group.get("breadth_state") not in (None, "unavailable"):
        positive, above = _number(group.get("positive_return_breadth")), _number(group.get("above_sma50_breadth"))
        if positive is not None and above is not None:
            breadth = ResearchBreadth(state=str(group["breadth_state"]),
                configured_count=int(group.get("configured_peer_count") or 0),
                valid_count=int(group.get("valid_peer_count") or 0),
                positive_return_participation=positive, above_sma50_participation=above,
                median_return_21=_number(group.get("median_peer_return_21")),
                constituent_sample=tuple(str(x) for x in group.get("peer_sample", []) if isinstance(x, str)))
    symbol = detail.get("benchmark_symbol") or group.get("benchmark_symbol")
    history = None
    raw_history = detail.get("history")
    if isinstance(raw_history, dict) and raw_history.get("ticker") == outlook.ticker and symbol:
        raw_benchmark = raw_history.get("benchmark") if isinstance(raw_history.get("benchmark"), dict) else {}
        raw_windows = raw_history.get("windows") if isinstance(raw_history.get("windows"), dict) else {}
        coverage = raw_history.get("coverage") if isinstance(raw_history.get("coverage"), dict) else {}
        if raw_benchmark.get("symbol") == symbol:
            windows = []
            for label in ("1M", "3M", "6M"):
                raw_points = raw_windows.get(label)
                if not isinstance(raw_points, list):
                    continue
                points = tuple(IndustryHistoryPoint.model_validate(point) for point in raw_points)
                windows.append(IndustryHistoryWindow(label=label, session_count=len(points), points=points))
            if windows:
                history = IndustryHistory(schema_version=raw_history.get("schema_version", "1"),
                    snapshot_id=raw_history["snapshot_id"], ticker=raw_history["ticker"],
                    as_of=raw_history["as_of"], series_start=raw_history["series_start"],
                    series_end=raw_history["series_end"],
                    price_adjustment_basis=raw_history["price_adjustment_basis"], currency=raw_history["currency"],
                    benchmark=ResearchBenchmark(symbol=str(raw_benchmark["symbol"]),
                        name=raw_benchmark.get("name"), benchmark_type=raw_benchmark.get("benchmark_type")),
                    classification_quality=raw_benchmark["classification_quality"],
                    fallback_reason=raw_benchmark.get("fallback_reason"),
                    taxonomy_version=raw_benchmark["taxonomy_version"], mapping_version=raw_benchmark["mapping_version"],
                    available_windows=tuple(window.label for window in windows), windows=tuple(windows),
                    coverage=IndustryHistoryCoverage.model_validate(coverage), source_ids=source_ids,
                    qualifier=str(raw_history["qualifier"]))
    return IndustryResearch(raw_sector=detail.get("raw_sector"), raw_industry=detail.get("raw_industry"),
        normalized_industry=detail.get("normalized_industry"), industry_name=detail.get("industry_name"),
        classification_quality=detail.get("classification_quality"), fallback_reason=detail.get("fallback_reason"),
        taxonomy_version=detail.get("taxonomy_version"),
        benchmark=ResearchBenchmark(symbol=str(symbol), name=detail.get("benchmark_name"),
            benchmark_type=detail.get("benchmark_type")) if symbol else None,
        relative_state=detail.get("relative_performance_state"), comparisons=tuple(comparisons),
        breadth=breadth, history=history, source_ids=source_ids)


def _economic(outlook, sources):
    trends, series = [], []
    for row in outlook.categories["economic"].evidence:
        details = row.source_details
        if row.raw_provider != "fred":
            continue
        current, previous, change = map(_number, (details.get("current_measure"), details.get("previous_measure"), details.get("change")))
        if None in (current, previous, change):
            continue
        ids = sources.ids_for_evidence(row)
        trends.append(ResearchMetric(id=_pid("metric", row.id), label=str(details.get("series_title") or row.title),
            value=current, unit="percent", previous_value=previous, change=change,
            change_unit="percentage_points", observation_date=_date(details.get("observation_date")),
            comparison_date=_date(details.get("comparison_date")), source_ids=ids,
            qualifier="Latest available FRED vintage."))
        points = tuple(ResearchSeriesPoint(date=day, value=float(point["value"]))
            for point in details.get("observations_used", []) if isinstance(point, dict)
            and (day := _date(point.get("date"))) and _number(point.get("value")) is not None)
        if len(points) >= 6:
            series.append(ResearchSeries(id=_pid("series", row.id), label=row.title,
                unit="percent", points=points, source_ids=ids,
                qualifier="Latest-vintage observations; not point-in-time reconstruction."))
    releases = []
    for relevant in outlook.event_intelligence.recent:
        event = relevant.event
        if event.category != "economic" or not event.measurements:
            continue
        values = {m.key: f"{m.actual_value.amount:g} {m.actual_value.unit}" for m in event.measurements
                  if m.actual_value and m.actual_value.amount is not None}
        releases.append(_event(event, sources).model_copy(update={"details": values}))
    return EconomicResearch(trends=tuple(trends), releases=tuple(releases), series=tuple(series))


def _date(value):
    from datetime import date
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def _market(outlook, sources):
    from app.models.outlook_research import MarketHistory, MarketHistoryWindow, VixHistoryPoint
    benchmarks, volatility, raw_history = [], None, None
    for row in outlook.categories["market"].evidence:
        ids = sources.ids_for_evidence(row)
        if raw_history is None and isinstance(row.source_details.get("history"), dict):
            raw_history = row.source_details["history"]
        if row.event_type.value == "broad_market_trend":
            for item in row.source_details.get("benchmarks", []):
                if not isinstance(item, dict):
                    continue
                close, sma, prior = map(_number, (item.get("price"), item.get("sma50"), item.get("sma50_five_sessions_ago")))
                day = _date(str(item.get("published", ""))[:10])
                if None in (close, sma, prior) or not day:
                    continue
                direction = int(item.get("direction") or 0)
                benchmarks.append(MarketBenchmark(symbol=str(item.get("symbol")), close=close, sma50=sma,
                    prior_sma50=prior, trend="above_rising" if direction > 0 else "below_falling" if direction < 0 else "mixed",
                    observation_date=day, source_ids=ids))
        elif row.event_type.value == "volatility":
            close = _number(row.source_details.get("close"))
            if close is not None:
                volatility = MarketVolatility(symbol=str(row.source_details.get("symbol") or "^VIX"), close=close,
                    regime="elevated" if close >= 25 else "low" if close < 15 else "normal",
                    observation_date=row.published_at.date(), source_ids=ids)
    history = None
    if raw_history:
        equity = raw_history.get("equity") or {}
        windows = tuple(MarketHistoryWindow(label=label, session_count=len(points), points=tuple(points))
            for label, points in (equity.get("windows") or {}).items())
        vix = raw_history.get("vix") or {}
        thresholds = raw_history.get("vix_thresholds") or {}
        if windows or vix.get("points"):
            history = MarketHistory(schema_version=raw_history["schema_version"],
                snapshot_id=raw_history["snapshot_id"], as_of=raw_history["as_of"],
                price_adjustment_basis=raw_history["price_adjustment_basis"], windows=windows,
                equity_coverage=equity.get("coverage"),
                vix_points=tuple(VixHistoryPoint.model_validate(point) for point in vix.get("points", [])),
                vix_threshold_low=float(thresholds.get("low_below", 15)),
                vix_threshold_high=float(thresholds.get("elevated_at_or_above", 25)),
                qualifier=str(raw_history.get("qualifier") or ""))
    return MarketResearch(benchmarks=tuple(benchmarks), volatility=volatility, history=history)


def _evidence_events(rows: Iterable[OutlookEvidence], category, sources, empty_message):
    events = []
    for row in rows:
        if not row.scoring_eligible:
            continue
        details = row.source_details
        structured = details.get("structured") if isinstance(details.get("structured"), dict) else {}
        safe = {str(k): v for k, v in structured.items() if isinstance(v, (str, int, float, bool, type(None)))}
        for key in ("form", "filing_date", "event_date", "items", "publication_title", "document_number",
                    "effective_at", "review_expires_at", "policy_change", "product_group", "exposure_reason"):
            value = details.get(key)
            if isinstance(value, (str, int, float, bool, type(None))):
                safe[key] = value
        countries = details.get("countries")
        if isinstance(countries, list) and all(isinstance(x, str) for x in countries):
            safe["geography"] = ", ".join(countries)
        qualifier = ("Industry relevance does not establish product qualification, customer exposure, revenue exposure, or exact financial impact."
                     if category == "geopolitical" else None)
        events.append(ResearchEvent(id=_pid("event", row.id), category=category,
            event_type=row.event_type.value, title=row.title, summary=row.summary,
            date=_date(details.get("event_date")) or row.published_at.date(), direction=_direction(row),
            details=safe, source_ids=sources.ids_for_evidence(row), qualifier=qualifier))
    events.sort(key=lambda item: (item.date is not None, item.date), reverse=True)
    return EventResearch(events=tuple(events), empty_message=empty_message)


def _revenue_history(projection: RevenueResearchProjectionResult | None):
    """Map reviewed projection fields only; never calculate financial values here."""
    if projection is None:
        return RevenueHistoryResearch(availability="unavailable",
            reasons=("revenue_projection_not_supplied",))
    if projection.state != "available" or projection.summary is None:
        availability = "conflict" if projection.state == "conflict" else (
            "insufficient_data" if "research_eligible_series_required" in projection.reasons
            else "unavailable")
        return RevenueHistoryResearch(availability=availability,
            policy=projection.projection_policy, reasons=projection.reasons)
    points = tuple(RevenueHistoryPoint(fiscal_year=row.fiscal_year,
        fiscal_quarter=row.fiscal_quarter, display_label=row.display_label,
        period_start=row.period_start, period_end=row.period_end,
        duration_days=row.duration_days, exact_revenue=row.exact_revenue,
        revenue_billions=row.revenue_billions, currency=row.currency,
        source_kind=row.source_kind, derived=row.derived,
        source_policy=row.source_policy, evidence_identity=row.evidence_identity,
        derivation_policy=row.derivation_policy,
        derivation_formula_identity=("FY-minus-Q1-minus-Q2-minus-Q3"
            if row.derived and row.derivation_policy == "revenue-q4-derivation-1" else None),
        reconciliation_policy=row.reconciliation_policy,
        qoq=RevenueHistoryGrowth.model_validate(row.qoq.model_dump()),
        yoy=RevenueHistoryGrowth.model_validate(row.yoy.model_dump()))
        for row in projection.points)
    summary = projection.summary
    return RevenueHistoryResearch(availability="available",
        policy=projection.projection_policy,
        observation_count=summary.observation_count,
        directly_reported_count=summary.directly_reported_count,
        derived_count=summary.derived_count,
        earliest_quarter=summary.earliest_quarter,
        latest_quarter=summary.latest_quarter,
        latest_exact_revenue=summary.latest_exact_revenue,
        latest_qoq_growth_pct=summary.latest_qoq_growth_pct,
        latest_yoy_growth_pct=summary.latest_yoy_growth_pct,
        qoq_comparison_count=summary.available_qoq_comparisons,
        yoy_comparison_count=summary.available_yoy_comparisons,
        points=points)


def build_research_presentation(outlook: OutlookResponse, packet: OutlookContextPacket,
                                analysis: AIOutlookResponse, *, as_of=None,
                                revenue_projection: RevenueResearchProjectionResult | None = None):
    """Assemble bounded display data; never changes intelligence or parses AI prose."""
    sources = _Sources()
    earnings = _earnings(outlook, sources)
    industry = _industry(outlook, sources)
    economic = _economic(outlook, sources)
    market = _market(outlook, sources)
    company = _evidence_events(outlook.categories["company"].evidence, "company", sources,
        "No qualifying material company developments were identified in the current research window.")
    geopolitical = _evidence_events(outlook.categories["geopolitical"].evidence, "geopolitical", sources,
        "No qualifying issuer-relevant geopolitical developments were identified in the current research window.")
    event_map = {row.event.event_id: row.event for row in (*outlook.event_intelligence.upcoming, *outlook.event_intelligence.recent)}
    allowed = {row.event_id for row in packet.upcoming_events}
    catalysts = []
    for watch in analysis.what_to_watch:
        event = event_map.get(watch.event_id)
        if event and watch.event_id in allowed:
            base = _event(event, sources)
            catalysts.append(ResearchCatalyst(**base.model_dump(), reason=watch.reason))
    return ResearchPresentation(as_of=as_of or datetime.now(timezone.utc), ticker=outlook.ticker,
        earnings=earnings, industry=industry, economic=economic, market=market,
        company=company, geopolitical=geopolitical,
        revenue_history=_revenue_history(revenue_projection), what_to_watch=tuple(catalysts),
        sources=tuple(sorted(sources.rows.values(), key=lambda row: row.id)))
