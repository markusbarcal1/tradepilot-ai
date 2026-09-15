"""Curated official FRED observations; deterministic changes, never narrative sentiment."""
from datetime import datetime, timezone
import logging
import math
from zoneinfo import ZoneInfo

from app.models.outlook_evidence import OutlookEvidence
from .policy import MACRO_SERIES, MACRO_CONFIDENCE, MACRO_MATERIALITY
from .transport import Cache, JsonClient, ProviderUnavailable

LOGGER = logging.getLogger(__name__)


def observations(payload):
    result = {}
    for row in payload.get("observations", []):
        try:
            date = datetime.fromisoformat(row["date"]).date()
            value = float(row["value"])
            if math.isfinite(value):
                result[date] = value
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(result.items())


def macro_change(spec, rows):
    needed = spec.comparison + (12 if spec.method == "yoy_change" else 0)
    if len(rows) <= needed:
        return None
    current, previous = rows[-1][1], rows[-1-spec.comparison][1]
    if spec.method == "yoy_change":
        base, prior_base = rows[-13][1], rows[-13-spec.comparison][1]
        if base <= 0 or prior_base <= 0:
            return None
        current, previous = 100 * (current / base - 1), 100 * (previous / prior_base - 1)
    change = current - previous
    impact = spec.higher_impact if change >= spec.threshold else -spec.higher_impact if change <= -spec.threshold else 0
    return impact, current, previous, change


class FredEvidenceProvider:
    name = "fred"
    categories = ("economic",)
    uses_placeholder_data = False

    def __init__(self, settings, client=None, clock=lambda: datetime.now(timezone.utc)):
        self.settings, self.clock = settings, clock
        self.client = client or JsonClient(settings)
        self.cache = Cache(settings.outlook_failure_cache_ttl)
        self.unavailable_reason = ("disabled" if not settings.outlook_fred_enabled else
            "missing_configuration" if not settings.fred_api_key.get_secret_value().strip() else None)

    def get_evidence(self, ticker):
        ticker = ticker.strip().upper()
        if self.unavailable_reason:
            return []
        results = []
        for spec in MACRO_SERIES:
            def load():
                params = {"api_key": self.settings.fred_api_key.get_secret_value(), "file_type": "json", "series_id": spec.id}
                metadata = self.client.get("https://api.stlouisfed.org/fred/series", provider="fred", params=params)
                payload = self.client.get("https://api.stlouisfed.org/fred/series/observations", provider="fred",
                    params={**params, "sort_order": "desc", "limit": 20})
                return metadata, payload, self.clock()
            try:
                metadata, payload, fetched = self.cache.get(spec.id, load, self.settings.outlook_economic_cache_ttl)
            except ProviderUnavailable:
                LOGGER.warning("outlook_fred_unavailable series=%s", spec.id)
                if not results:
                    raise
                break  # Stop a timeout/rate-limit cascade; keep already usable observations.
            rows = [(date, value) for date, value in observations(payload) if date <= fetched.date()]
            reported_dates = []
            for row in payload.get("observations", []):
                try:
                    date = datetime.fromisoformat(row["date"]).date()
                    if date <= fetched.date():
                        reported_dates.append(date)
                except (ValueError, KeyError, TypeError):
                    continue
            if reported_dates and (not rows or rows[-1][0] != max(reported_dates)):
                continue  # A missing latest value is not replaced by an older, freshly released signal.
            # Require contiguous reporting periods, not comparisons across silently missing months.
            if not rows or (self.clock().date() - rows[-1][0]).days > spec.max_age_days:
                continue
            expected_months = 3 if spec.id == "A191RL1Q225SBEA" else 1
            required = spec.comparison + (12 if spec.method == "yoy_change" else 0)
            tail = rows[-required-1:]
            if any((b[0].year-a[0].year)*12+b[0].month-a[0].month != expected_months for a,b in zip(tail, tail[1:])):
                continue
            change = macro_change(spec, rows)
            if change is None:
                continue
            try:
                details = metadata["seriess"][0]
                published = datetime.fromisoformat(details["last_updated"])
                if published.tzinfo is None:
                    published = published.replace(tzinfo=ZoneInfo("America/Chicago"))
                if published > fetched:
                    continue
            except (KeyError, IndexError, ValueError, TypeError):
                continue
            impact, current, previous, delta = change
            identity = f"{spec.id}:{rows[-1][0]}"
            results.append(OutlookEvidence(id=f"fred:{ticker}:{identity}", ticker=ticker, category="economic",
                event_type=spec.event, title=f"{spec.title} trend",
                summary=f"{spec.title}: {current:.2f} versus {previous:.2f} in the comparison period; change {delta:+.2f} percentage points. " +
                    ("Comparison uses year-over-year inflation rates." if spec.method == "yoy_change" else "Structured change, not a forecast."),
                source="Federal Reserve Bank of St. Louis (FRED)", source_type="economic_data",
                source_url=f"https://fred.stlouisfed.org/series/{spec.id}", published_at=published,
                observed_at=fetched, impact=impact, confidence=MACRO_CONFIDENCE, materiality=MACRO_MATERIALITY,
                materiality_reason="Conservative broad-equity macro baseline; no company-specific sensitivity inferred.",
                raw_provider="fred", raw_provider_id=identity, source_details={"series_id": spec.id,
                    "series_title": details.get("title", spec.title), "observation_date": str(rows[-1][0]),
                    "observation_value": rows[-1][1], "comparison_date": str(rows[-1-spec.comparison][0]),
                    "comparison_value": rows[-1-spec.comparison][1], "current_measure": current,
                    "previous_measure": previous, "change": delta, "method": spec.method,
                    "observations_used": [{"date": str(date), "value": value} for date,value in tail],
                    "publication_basis": "FRED series last_updated (latest-vintage proxy)",
                    "realtime_start": payload.get("realtime_start")}))
        return results
