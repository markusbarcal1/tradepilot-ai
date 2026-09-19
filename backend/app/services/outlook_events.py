"""Lifecycle, immutable expectations, explicit exposure, and the evidence boundary."""
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import re
from threading import RLock
from typing import Protocol

from app.models.outlook_event import (EventIntelligence, EventSurprise, EventValue, ExpectationSnapshot,
    ExposureAssessment, RelevantEvent)
from app.models.outlook_evidence import CompanyContext, ExposureLink, OutlookEvidence
from app.services.market_data import VALID_TICKER_PATTERN
from app.services.outlook_structured.fomc import ET, FomcSource, MAX_RECENT, MAX_UPCOMING
from app.services.outlook_structured.transport import Cache, ProviderUnavailable


class ExpectationProvider(Protocol):
    def snapshots(self, event_id: str) -> list[ExpectationSnapshot]: ...


def lifecycle(event, now):
    if event.expires_at and now >= event.expires_at:
        status = "expired"
    elif event.announced_at and event.announced_at <= now:
        effective = (event.effective_at and event.effective_at <= now) or (
            event.effective_date and event.effective_date <= now.astimezone(ET).date())
        status = "effective" if effective else "occurred"
    elif event.scheduled_date and event.scheduled_date < now.astimezone(ET).date():
        status = "expired"  # A missed schedule is never proof that a decision occurred.
    else:
        status = "upcoming"
    return event.model_copy(update={"status": status})


def with_expectations(event, snapshots, now, failure=None):
    """Use only information available before announcement, fresh at that cutoff."""
    cutoff = min(now, event.announced_at) if event.announced_at else now
    history = tuple(sorted(snapshots, key=lambda s: (s.observed_at, s.snapshot_id))[-32:])
    valid = [s for s in history if s.event_id == event.event_id
             and s.observed_at <= cutoff and s.provenance.published_at <= cutoff
             and s.provenance.retrieved_at <= cutoff
             and (event.announced_at is None or max(s.observed_at, s.provenance.published_at, s.provenance.retrieved_at) < event.announced_at)
             and s.expires_at > cutoff and cutoff - s.observed_at <= timedelta(hours=24)]
    expectation = valid[-1] if valid else None
    status = "available" if expectation else failure or ("stale" if history else "unavailable")
    surprise = EventSurprise()
    if expectation and event.announced_at and event.announced_at <= now:
        actual = event.change if expectation.metric == "change" else event.actual_value
        expected = expectation.expected_value
        if actual and expected and actual.unit == expected.unit:
            difference = None
            if actual.amount is not None and expected.amount is not None:
                difference = EventValue(amount=round(actual.amount - expected.amount, 8), unit=actual.unit)
            surprise = EventSurprise(status="as_expected" if actual == expected else "different_from_expected",
                difference=difference, expectation_snapshot_id=expectation.snapshot_id)
        elif actual:
            matches = [row for row in expectation.outcomes if row.outcome == actual]
            if len(matches) == 1:
                surprise = EventSurprise(status="probability_based", actual_outcome_probability=matches[0].probability,
                    expectation_snapshot_id=expectation.snapshot_id)
    return event.model_copy(update={"expectation": expectation, "expectation_history": history,
        "expected_value": expectation.expected_value if expectation else None,
        "expectation_status": status, "surprise": surprise})


US_EXCHANGES = frozenset({"NYQ", "NMS", "NGM", "NCM", "ASE", "PCX", "BTS", "NYSE", "NASDAQ"})
BANKS = frozenset({"banks - diversified", "banks - regional", "mortgage finance"})
REITS = frozenset({"reit - diversified", "reit - industrial", "reit - office", "reit - residential",
    "reit - retail", "reit - healthcare facilities", "reit - hotel & motel", "reit - specialty", "reit - mortgage"})


def fomc_exposure(context, info):
    if info.get("quoteType") != "EQUITY" or info.get("exchange") not in US_EXCHANGES:
        return ExposureAssessment(False, "A supported US-listed equity classification is unavailable.")
    industry = (context.industry or "").casefold().strip()
    reason, directness, confidence, materiality = None, "industry", .8, .6
    if industry in BANKS:
        reason = "The classified financial business is exposed to funding costs, asset yields and credit demand. Their net effect is uncertain."
    elif industry in REITS:
        reason = "The classified REIT business is exposed to financing costs and property valuation discount rates. Its stock reaction is uncertain."
    else:
        # Explicit present-tense business activity, not a ticker map, sector proxy,
        # a mention of crypto, or a claim about a customer's operations.
        description = context.business_description or ""
        crypto = re.search(r"\b(?:engages in|is engaged in|operates as|is a|operates) (?:the )?(?:bitcoin mining|bitcoin miner|bitcoin mining company)\b"
            r"|\bthe company is engaged in the operation of application-specific integrated circuit miners for the purpose of mining bitcoin\b", description, re.I)
        if crypto:
            sentence = re.split(r"[.!?]", description[:crypto.start()])[-1] + description[crypto.start():].split(".")[0]
            if not re.search(r"\b(?:not|no longer|formerly|plans|planned|may|could|customers?|clients?|competitors?|suppliers?|subsidiaries of other)\b", sentence, re.I):
                reason = "The company description explicitly identifies Bitcoin mining. Monetary policy can affect financial conditions and crypto risk-asset conditions relevant to that business; stock direction is uncertain."
                directness, confidence, materiality = "business", .8, .6
    if reason:
        return ExposureAssessment(True, reason,
            ExposureLink(kind="industry", description=reason, source_url=f"https://finance.yahoo.com/quote/{context.ticker}/profile/"),
            "company_specific", directness, confidence, materiality)
    reason = "US-listed equity: monetary policy provides broad financing and discount-rate context. No enhanced company-specific sensitivity or stock direction is established."
    return ExposureAssessment(True, reason,
        ExposureLink(kind="industry", description=reason, source_url=f"https://finance.yahoo.com/quote/{context.ticker}/profile/"),
        "broad", "broad", .6, .3)


def event_evidence(event, exposure, ticker):
    """FOMC V1 has no defensible directional mapping; preserve provenance only.

    Zero here is the legacy evidence sentinel, NOT a neutral assessment. The
    mandatory scoring_eligible=False prevents support and FRED double counting.
    """
    if not exposure.matched or event.status not in ("occurred", "effective") or not event.announced_at:
        return []
    source = event.provenance[0]
    return [OutlookEvidence(id=f"{event.event_id}:{ticker}", ticker=ticker, category="economic",
        event_type="monetary_policy", title=event.title, summary=exposure.reason,
        source=source.source, source_type=source.source_type, source_url=source.source_url,
        published_at=event.announced_at, observed_at=source.retrieved_at, expires_at=event.expires_at,
        impact=0, confidence=exposure.confidence, materiality=exposure.materiality,
        materiality_reason=exposure.reason, exposure_links=(exposure.link,) if exposure.link else (),
        scoring_eligible=False, source_quality="primary_authoritative", raw_provider="fomc",
        raw_provider_id=event.event_id, source_details={"external_event_id": event.event_id,
            "direction_status": "uncertain", "dedup_rule": "non_scoring_policy_context",
            "previous_value": event.previous_value.model_dump() if event.previous_value else None,
            "actual_value": event.actual_value.model_dump() if event.actual_value else None,
            "change": event.change.model_dump() if event.change else None})]


class FomcEventProvider:
    name = "fomc"
    event_intelligence_provider = True
    # A relevance-only event must not make a category connected, failed, or available.
    # Orchestration consumes this separate boundary before normal evidence providers.
    uses_placeholder_data = False

    def __init__(self, settings, source=None, metadata=None, classification_cache=None,
                 expectations=None, clock=lambda: datetime.now(timezone.utc)):
        from app.services.outlook_structured.industry import classification
        self.settings, self.clock = settings, clock
        self.source = source or FomcSource(settings, clock=clock)
        self.metadata = metadata or classification
        self.classifications = classification_cache or Cache(settings.outlook_failure_cache_ttl)
        self.expectations = expectations
        self.expectation_cache = Cache(settings.outlook_failure_cache_ttl, capacity=32)
        self.history, self.lock = OrderedDict(), RLock()
        self.classification_loads = 0
        self.unavailable_reason = None if settings.outlook_fomc_enabled else "disabled"

    def _classification(self, ticker):
        self.classification_loads += 1
        return self.metadata(ticker)

    def _expectations(self, event, now):
        failure = None
        with self.lock:
            history = self.history.setdefault(event.event_id, {})
            if self.expectations:
                try:
                    supplied = self.expectation_cache.get(event.event_id,
                        lambda: self.expectations.snapshots(event.event_id), 300)
                    if not isinstance(supplied, list) or len(supplied) > 32:
                        raise ValueError("Unbounded expectation response")
                    parsed = [ExpectationSnapshot.model_validate(value) for value in supplied]
                    if any(s.event_id != event.event_id or (s.snapshot_id in history and history[s.snapshot_id] != s) for s in parsed):
                        raise ValueError("Expectation identity conflict")
                    for item in parsed:
                        history[item.snapshot_id] = item
                except ValueError:
                    failure = "invalid"
                except Exception:
                    failure = "error"
            kept = sorted(history.values(), key=lambda s: (s.observed_at, s.snapshot_id))[-32:]
            self.history[event.event_id] = {s.snapshot_id: s for s in kept}
            self.history.move_to_end(event.event_id)
            while len(self.history) > 32:
                self.history.popitem(last=False)
            return with_expectations(event, kept, now, failure)

    def inspect(self, ticker):
        ticker = ticker.strip().upper()
        diagnostics = {"directional_evidence": False, "dedup": "FOMC provenance never contributes independent support; existing FRED evidence unchanged.",
            "probability_provider": "configured" if self.expectations else "not_configured",
            "cache_ttl_seconds": self.settings.outlook_fomc_cache_ttl,
            "classification_cache_ttl_seconds": self.settings.outlook_classification_cache_ttl,
            "failure_backoff_seconds": self.settings.outlook_failure_cache_ttl}
        def result(status, upcoming=(), recent=(), evidence=()):
            diagnostics.update({"source_requests": self.source.requests, "source_loads": self.source.loads,
                                "source_reads": self.source.reads, "source_cache_hits": self.source.reads - self.source.loads,
                                "classification_loads": self.classification_loads})
            return {"intelligence": EventIntelligence(status=status, upcoming=tuple(upcoming), recent=tuple(recent)),
                    "evidence": list(evidence), "diagnostics": diagnostics}
        if self.unavailable_reason or not VALID_TICKER_PATTERN.fullmatch(ticker):
            return result(self.unavailable_reason or "invalid_symbol")
        try:
            snapshot = self.source.get_events()
        except Exception:
            return result("temporarily_unavailable")
        diagnostics.update({key: value for key, value in snapshot.items() if key != "events"})
        try:
            info = self.classifications.get(ticker, lambda: self._classification(ticker), self.settings.outlook_classification_cache_ttl)
            if not isinstance(info, dict):
                raise ProviderUnavailable("missing_classification")
            context = CompanyContext(ticker=ticker, company_name=info.get("shortName"), country=info.get("country"),
                sector=info.get("sector"), industry=info.get("industry"), business_description=info.get("longBusinessSummary"))
            exposure = fomc_exposure(context, info)
        except Exception:
            return result("classification_unavailable")
        diagnostics["exposure"] = {"matched": exposure.matched, "relevance": exposure.relevance,
            "reason": exposure.reason, "industry": context.industry}
        if not exposure.matched:
            return result("no_supported_exposure")
        now = self.clock()
        events = [self._expectations(lifecycle(event, now), now) for event in snapshot["events"]]
        upcoming = sorted((e for e in events if e.status == "upcoming"), key=lambda e: (e.scheduled_date, e.event_id))[:MAX_UPCOMING]
        recent = sorted((e for e in events if e.status in ("occurred", "effective")), key=lambda e: (e.announced_at, e.event_id), reverse=True)[:MAX_RECENT]
        evidence = [item for event in recent for item in event_evidence(event, exposure, ticker)]
        return result("partial" if snapshot["excluded"] else "available",
            [RelevantEvent(event=e, exposure=exposure) for e in upcoming],
            [RelevantEvent(event=e, exposure=exposure) for e in recent], evidence)

