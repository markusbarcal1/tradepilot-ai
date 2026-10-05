"""Ticker earnings schedules plus existing SEC interpretation, represented as ExternalEvent."""
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
import math
import re
from threading import RLock
from zoneinfo import ZoneInfo

import yfinance as yf

from app.models.outlook_event import (EarningsMetricIdentity, EventMeasurement, EventScope, EventSource,
    EventValue, ExpectationSnapshot, ExternalEvent, ExposureAssessment, RelevantEvent, EventIntelligence)
from app.models.outlook_reporting import ReportingIdentity, ReportingPeriodIdentity
from app.services.market_data import VALID_TICKER_PATTERN
from app.services.outlook_events import lifecycle, upcoming_order, with_expectations
from app.services.earnings_expectations import compare_measurement, current_upcoming_snapshot
from .transport import Cache

ET = ZoneInfo("America/New_York")
UPCOMING_DAYS = 45
RECENT_DAYS = 120
YAHOO_EARNINGS_URL = "https://finance.yahoo.com/calendar/earnings"


def _finite(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _calendar_rows(ticker):
    """Normalize yfinance's structured ticker calendar; estimates stay non-historical."""
    calendar = yf.Ticker(ticker).calendar
    if not isinstance(calendar, dict):
        return []
    dates = calendar.get("Earnings Date", [])
    dates = dates if isinstance(dates, (list, tuple)) else [dates]
    rows = []
    for value in dates[:2]:
        when = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
        if isinstance(when, datetime):
            if when.tzinfo is None:
                scheduled_at, scheduled_date = None, when.date()
            else:
                local = when.astimezone(ET)
                scheduled_date = local.date()
                scheduled_at = None if (local.hour, local.minute, local.second) == (0, 0, 0) else local
        elif isinstance(when, date):
            scheduled_at, scheduled_date = None, when
        else:
            continue
        rows.append({"scheduled_date": scheduled_date, "scheduled_at": scheduled_at,
            "certainty": "provider_reported", "eps_estimate": _finite(calendar.get("Earnings Average")),
            "revenue_estimate": _finite(calendar.get("Revenue Average")), "reported_eps": None})
    return rows


def _session(when):
    if when is None:
        return "unknown"
    local = when.astimezone(ET)
    if local.hour < 9 or (local.hour == 9 and local.minute < 30):
        return "before_market"
    if local.hour >= 16:
        return "after_market"
    return "during_market"


def schedule_event(ticker, issuer, row, retrieved_at, *, previous=None):
    day, when = row["scheduled_date"], row["scheduled_at"]
    if not isinstance(day, date) or (when and (when.tzinfo is None or when.utcoffset() is None)):
        raise ValueError("Invalid earnings schedule")
    source = EventSource(source="Yahoo Finance — Earnings Calendar", source_type="market_data",
        source_url=f"{YAHOO_EARNINGS_URL}?symbol={ticker}", retrieved_at=retrieved_at)
    history = previous.schedule_history if previous else ()
    if previous and (previous.scheduled_date != day or previous.scheduled_at != when):
        history = (*history, previous.provenance[0])[-8:]
    measurements = ()
    # Current calendar estimates are visible context only. They are not retained as
    # production expectations because Yahoo does not expose an immutable as-of snapshot.
    return ExternalEvent(event_id=f"earnings:{ticker}:next", event_type="earnings_release", category="earnings",
        ticker=ticker, issuer=issuer, title=f"{ticker} Earnings", summary="Provider-reported upcoming issuer earnings date.",
        scheduled_date=day, scheduled_at=when, scheduled_timezone="America/New_York" if when else None,
        schedule_certainty=row.get("certainty", "provider_reported"), market_session=_session(when), status="upcoming",
        measurements=measurements, provenance=(source,), schedule_history=history,
        scope=EventScope(entities=(issuer or ticker,)))


def _identity(record):
    try:
        identity = ReportingIdentity.model_validate(record.source_details.get("reporting_identity"))
    except Exception:
        return None
    periods = [p for p in identity.periods if p.ticker == record.ticker and p.fiscal_period != "FY"]
    return identity if identity.status == "authoritative" and len(periods) == 1 else None


def _event_value(numeric):
    metric = str(numeric.get("metric", "")).lower()
    if metric in ("gross_margin", "operating_margin"):
        return EventValue(amount=float(numeric["current_percent"]), unit="percent")
    value = _finite(numeric.get("current_value"))
    unit = numeric.get("unit")
    return EventValue(amount=value, unit=unit) if value is not None and unit else None


def released_events(ticker, issuer, records, now):
    """Group existing interpreted evidence by authoritative reporting identity."""
    groups = OrderedDict()
    for record in sorted((r for r in records if r.category == "earnings"), key=lambda r: r.published_at):
        identity = _identity(record)
        if identity:
            period = next(p for p in identity.periods if p.fiscal_period != "FY")
            groups.setdefault(period.key, {"period": period, "identity": identity, "records": []})["records"].append(record)
    # Guidance evidence intentionally carries no reporting identity because it does
    # not establish a fiscal result. Attach it only through the same SEC accession.
    for group in groups.values():
        accessions = {r.raw_provider_id for r in group["records"]}
        group["records"].extend(r for r in records if r.category == "earnings"
            and r.event_type in ("guidance_raise", "guidance_cut", "guidance_withdrawal")
            and r.raw_provider_id in accessions and r not in group["records"])
    events = []
    for key, group in groups.items():
        period, rows = group["period"], group["records"]
        # Prefer the issuer's filed earnings exhibit when both an exhibit and the
        # periodic filing repeat a value for the same fiscal result.
        rows = sorted(rows, key=lambda row: (
            0 if row.source_details.get("document_kind") == "earnings_exhibit" else 1,
            row.published_at,
            row.id,
        ))
        announced = min(row.published_at for row in rows)
        fiscal = f"FY{period.fiscal_year} {period.fiscal_period}"
        measurements, seen = [], set()
        guidance = "unavailable"
        sources = OrderedDict()
        for row in rows:
            source_label = f"{issuer or ticker} {fiscal} Earnings Release" if row.source_details.get("document_kind") == "earnings_exhibit" else f"{issuer or ticker} {fiscal} SEC Filing"
            sources[(source_label, str(row.source_url))] = EventSource(source=source_label, source_type=row.source_type,
                source_url=row.source_url, published_at=row.published_at, retrieved_at=row.observed_at)
            numeric = row.source_details.get("numeric", {})
            metric = str(numeric.get("metric", "")).lower().replace("revenues", "revenue")
            value = _event_value(numeric)
            if row.event_type == "earnings_result" and metric in ("revenue", "eps", "diluted_eps") and value:
                measurement_key = "revenue" if metric == "revenue" else "diluted_eps" if metric == "diluted_eps" else "eps"
                if measurement_key not in seen:
                    measurements.append(EventMeasurement(key=measurement_key,
                        label={"revenue": "Revenue", "eps": "EPS", "diluted_eps": "Diluted EPS"}[measurement_key],
                        actual_value=value, currency="USD",
                        metric_identity=(EarningsMetricIdentity(metric="revenue", accounting_basis="not_applicable",
                            share_basis="not_applicable", scope="total_company") if measurement_key == "revenue" else
                            EarningsMetricIdentity(metric="eps", accounting_basis="unknown",
                                share_basis="diluted" if measurement_key == "diluted_eps" else "unknown",
                                scope="total_company"))))
                    seen.add(measurement_key)
            elif row.event_type == "margin_change" and metric in ("gross_margin", "operating_margin") and value and metric not in seen:
                prior = _finite(numeric.get("prior_percent"))
                measurements.append(EventMeasurement(key=metric, label=metric.replace("_", " ").title(),
                    actual_value=value, previous_value=EventValue(amount=prior, unit="percent") if prior is not None else None))
                seen.add(metric)
            elif row.event_type in ("guidance_raise", "guidance_cut", "guidance_withdrawal"):
                guidance = {"guidance_raise": "raised", "guidance_cut": "lowered",
                            "guidance_withdrawal": "withdrawn"}[row.event_type]
        if not measurements and guidance == "unavailable":
            continue
        event = ExternalEvent(event_id=f"earnings:{key}", underlying_event_id=f"earnings:{key}",
            event_type="earnings_release", category="earnings", ticker=ticker, issuer=issuer,
            title=f"{ticker} Earnings", summary=f"Issuer results for {fiscal}.",
            announced_at=announced, scheduled_date=announced.astimezone(ET).date(), status="occurred",
            expires_at=announced + timedelta(days=RECENT_DAYS), reference_period=fiscal,
            reporting_identity=group["identity"], release_type="Earnings release",
            guidance_status=guidance, measurements=tuple(measurements), provenance=tuple(sources.values()),
            scope=EventScope(entities=(issuer or ticker,)))
        events.append(lifecycle(event, now))
    return events


def issuer_exposure(ticker, issuer):
    reason = f"This is {issuer or ticker}'s own earnings release, so relevance to {ticker} is direct."
    return ExposureAssessment(True, reason, None, "company_specific", "business", 1, 1)


class EarningsEventProvider:
    name = "earnings_events"
    event_intelligence_provider = True
    uses_placeholder_data = False

    def __init__(self, settings, sec_provider, metadata, classification_cache=None, calendar_loader=None,
                 expectations=None, clock=lambda: datetime.now(timezone.utc)):
        self.settings, self.sec, self.metadata, self.clock = settings, sec_provider, metadata, clock
        self.calendar_loader = calendar_loader or _calendar_rows
        self.calendar_cache = Cache(settings.outlook_failure_cache_ttl, capacity=128)
        self.classifications = classification_cache or Cache(settings.outlook_failure_cache_ttl)
        self.expectations = expectations
        self.history, self.schedule_history, self.lock = OrderedDict(), {}, RLock()
        self.calendar_reads = self.calendar_loads = 0
        self.unavailable_reason = None if settings.outlook_earnings_events_enabled else "disabled"

    def _calendar(self, ticker):
        self.calendar_loads += 1
        return self.calendar_loader(ticker)

    def _expectations(self, event, now):
        if self.expectations and hasattr(self.expectations, "observations"):
            measurements, history = [], []
            for measurement in event.measurements:
                try:
                    supplied = self.expectations.observations(
                        event.ticker, event.reporting_identity, measurement.key)
                    if not isinstance(supplied, list) or len(supplied) > 256:
                        raise ValueError("Invalid expectation response")
                    parsed = [row if isinstance(row, ExpectationSnapshot)
                              else ExpectationSnapshot.model_validate(row) for row in supplied]
                    if event.status == "upcoming":
                        selected = current_upcoming_snapshot(event, measurement, parsed)
                        measurements.append(measurement.model_copy(update={
                            "expectation": selected.model_copy(update={"temporal_status": "upcoming_current"}) if selected else None,
                            "expectation_status": "available" if selected else "unavailable"}))
                    else:
                        compared, _selection = compare_measurement(event, measurement, parsed)
                        measurements.append(compared)
                    history.extend(parsed)
                except ValueError:
                    measurements.append(measurement.model_copy(update={"expectation_status": "invalid"}))
                except Exception:
                    measurements.append(measurement.model_copy(update={"expectation_status": "error"}))
            ordered = tuple(sorted({row.snapshot_id: row for row in history}.values(),
                key=lambda row: (row.captured_at or datetime.min.replace(tzinfo=timezone.utc), row.snapshot_id))[-32:])
            return event.model_copy(update={"measurements": tuple(measurements),
                "expectation_history": ordered})
        supplied, failure = [], None
        if self.expectations:
            try:
                supplied = self.expectations.snapshots(event.event_id)
                if not isinstance(supplied, (list, tuple)) or len(supplied) > 32:
                    supplied, failure = [], "invalid"
            except Exception:
                failure = "error"
        with self.lock:
            history = self.history.setdefault(event.event_id, {})
            for snapshot in supplied:
                try:
                    snapshot = snapshot if isinstance(snapshot, ExpectationSnapshot) else ExpectationSnapshot.model_validate(snapshot)
                except Exception:
                    failure = "invalid"
                    continue
                if snapshot.event_id != event.event_id or (snapshot.snapshot_id in history and history[snapshot.snapshot_id] != snapshot):
                    failure = "invalid"
                    continue
                history[snapshot.snapshot_id] = snapshot
            kept = sorted(history.values(), key=lambda x: (
                x.observed_at or datetime.min.replace(tzinfo=timezone.utc), x.snapshot_id))[-32:]
        return with_expectations(event, kept, now, failure)

    def inspect(self, ticker):
        ticker = ticker.strip().upper()
        diagnostics = {"directional_evidence": False,
            "dedup": "ExternalEvent reuses SEC interpretation; it creates no additional OutlookEvidence.",
            "consensus_provider": "configured" if self.expectations else "not_configured",
            "calendar_source": "Yahoo Finance via yfinance", "calendar_certainty": "provider_reported_not_issuer_confirmed",
            "upcoming_horizon_days": UPCOMING_DAYS, "recent_horizon_days": RECENT_DAYS}
        def result(status, upcoming=(), recent=()):
            diagnostics.update(calendar_reads=self.calendar_reads, calendar_loads=self.calendar_loads,
                calendar_cache_hits=self.calendar_reads-self.calendar_loads)
            return {"intelligence": EventIntelligence(status=status, upcoming=tuple(upcoming), recent=tuple(recent)),
                    "evidence": [], "diagnostics": diagnostics}
        if self.unavailable_reason or not VALID_TICKER_PATTERN.fullmatch(ticker):
            return result(self.unavailable_reason or "invalid_symbol")
        now = self.clock()
        try:
            info = self.classifications.get(ticker, lambda: self.metadata(ticker), self.settings.outlook_classification_cache_ttl)
            issuer = info.get("shortName") or info.get("longName") or ticker
        except Exception:
            issuer = ticker
        exposure = issuer_exposure(ticker, issuer)
        upcoming, calendar_failure = [], False
        self.calendar_reads += 1
        try:
            rows = self.calendar_cache.get(ticker, lambda: self._calendar(ticker),
                self.settings.outlook_earnings_calendar_cache_ttl)
            future = [r for r in rows if now.astimezone(ET).date() <= r["scheduled_date"] <=
                      (now + timedelta(days=UPCOMING_DAYS)).astimezone(ET).date() and r.get("reported_eps") is None]
            if future:
                previous = self.schedule_history.get(ticker)
                event = schedule_event(ticker, issuer, min(future, key=lambda r: r["scheduled_date"]), now, previous=previous)
                self.schedule_history[ticker] = event
                upcoming.append(RelevantEvent(event=self._expectations(event, now), exposure=exposure))
        except Exception:
            calendar_failure = True
        try:
            records = self.sec.get_evidence(ticker)
            released = released_events(ticker, issuer, records, now)
        except Exception:
            records, released = [], []
            diagnostics["sec_status"] = "unavailable"
        else:
            diagnostics["sec_status"] = "available"
        released = sorted((e for e in released if e.status in ("occurred", "effective")),
                          key=lambda e: (e.announced_at, e.event_id), reverse=True)[:2]
        previous_schedule = self.schedule_history.get(ticker)
        if previous_schedule and released and abs((released[0].announced_at.astimezone(ET).date()
                                                   - previous_schedule.scheduled_date).days) <= 7:
            released[0] = released[0].model_copy(update={"event_id": previous_schedule.event_id,
                "scheduled_date": previous_schedule.scheduled_date, "scheduled_at": previous_schedule.scheduled_at,
                "scheduled_timezone": previous_schedule.scheduled_timezone,
                "schedule_certainty": previous_schedule.schedule_certainty,
                "market_session": previous_schedule.market_session,
                "schedule_history": previous_schedule.schedule_history,
                "provenance": (*released[0].provenance, *previous_schedule.provenance)})
        recent = [RelevantEvent(event=self._expectations(e, now), exposure=exposure) for e in released]
        diagnostics.update(schedule_status="unavailable" if calendar_failure else "available" if upcoming else "no_event_in_horizon",
            source_documents=sum(len(r.source_details.get("source_document_ids", [])) for r in records),
            reused_outlook_evidence=len([r for r in records if r.category == "earnings"]),
            duplicate_event_evidence=0, exposure={"relevance": "issuer_event", "reason": exposure.reason})
        status = "available" if upcoming or recent else "partial" if calendar_failure or diagnostics["sec_status"] == "unavailable" else "no_events"
        return result(status, upcoming, recent)
