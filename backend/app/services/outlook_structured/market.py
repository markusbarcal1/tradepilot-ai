"""Shared market-wide context using the existing history service and SMA helper."""
from datetime import datetime, timezone
import logging
from zoneinfo import ZoneInfo

import pandas as pd

from app.models.outlook_evidence import OutlookEvidence
from app.services.market_data import get_price_history
from app.services.indicators import calculate_sma
from .policy import (MARKET_SYMBOLS, MARKET_SMA_WINDOW, MARKET_SLOPE_BARS, MARKET_STALE_DAYS,
                     VIX_HIGH, VIX_LOW, MARKET_CONFIDENCE, MARKET_MATERIALITY)
from .transport import Cache, ProviderUnavailable

LOGGER = logging.getLogger(__name__)
NY = ZoneInfo("America/New_York")


def completed_history(frame, now):
    frame = frame.copy()
    frame["Close"] = pd.to_numeric(frame["Close"], errors="coerce")
    frame = frame[frame["Close"].notna() & (frame["Close"] > 0) & (frame["Close"] < float("inf"))].sort_index()
    # Only completed US sessions. Intraday/partial bars do not become a new daily event.
    closes = [datetime(index.year, index.month, index.day, 16, tzinfo=NY) for index in frame.index]
    frame = frame[[close <= now for close in closes]]
    if frame.empty:
        return None
    last = frame.index[-1]
    published = datetime(last.year, last.month, last.day, 16, tzinfo=NY)
    if (now - published).total_seconds() > MARKET_STALE_DAYS * 86400:
        return None
    return frame, published


class MarketEvidenceProvider:
    name = "market"
    categories = ("market",)
    uses_placeholder_data = False

    def __init__(self, settings, history=None, clock=lambda: datetime.now(timezone.utc)):
        self.settings, self.clock = settings, clock
        self.history = history or get_price_history
        self.cache = Cache(settings.outlook_failure_cache_ttl)
        self.unavailable_reason = "disabled" if not settings.outlook_market_enabled else None

    def _load(self):
        snapshots = {}
        failures = 0
        for symbol in MARKET_SYMBOLS:
            try:
                frame = self.history(symbol, "6mo", "1d")
                result = completed_history(frame, self.clock())
                if result is not None:
                    snapshots[symbol] = result
            except Exception as error:
                failures += 1
                LOGGER.warning("outlook_market_unavailable symbol=%s kind=%s", symbol, type(error).__name__)
        if failures == len(MARKET_SYMBOLS):
            raise ProviderUnavailable("market_unavailable")
        return snapshots, self.clock()

    def get_evidence(self, ticker):
        ticker = ticker.strip().upper()
        if self.unavailable_reason:
            return []
        snapshots, fetched = self.cache.get("shared", self._load, self.settings.outlook_market_cache_ttl)
        results, trends = [], []
        for symbol in ("SPY", "QQQ"):
            if symbol not in snapshots:
                continue
            frame, published = snapshots[symbol]
            if len(frame) < MARKET_SMA_WINDOW + MARKET_SLOPE_BARS:
                continue
            sma = calculate_sma(frame, MARKET_SMA_WINDOW)
            price, average, previous = float(frame.Close.iloc[-1]), float(sma.iloc[-1]), float(sma.iloc[-1-MARKET_SLOPE_BARS])
            direction = 1 if price > average > previous else -1 if price < average < previous else 0
            trends.append({"symbol": symbol, "price": price, "sma50": average,
                           "sma50_five_sessions_ago": previous, "direction": direction, "published": published})
        if trends:
            impact = 1 if all(row["direction"] == 1 for row in trends) else -1 if all(row["direction"] == -1 for row in trends) else 0
            published = min(row["published"] for row in trends)
            identity = f"broad_trend:{published.date()}"
            summary = "; ".join(f"{row['symbol']} close {row['price']:.2f}, SMA50 {row['sma50']:.2f}, prior SMA50 {row['sma50_five_sessions_ago']:.2f}" for row in trends)
            results.append(self._evidence(ticker, identity, "broad_market_trend", "Broad equity-market trend",
                summary + (". One benchmark is unavailable." if len(trends) < 2 else ". Benchmarks form one combined trend event."),
                published, fetched, impact, MARKET_CONFIDENCE if len(trends) == 2 else 0.7,
                {"benchmarks": [{**row, "published": row["published"].isoformat()} for row in trends]},
                "https://finance.yahoo.com/quote/SPY/" if len(trends) == 2 or trends[0]["symbol"] == "SPY" else "https://finance.yahoo.com/quote/QQQ/"))
        if "^VIX" in snapshots:
            frame, published = snapshots["^VIX"]
            value = float(frame.Close.iloc[-1])
            impact = -1 if value >= VIX_HIGH else 1 if value < VIX_LOW else 0
            regime = "elevated" if impact < 0 else "low" if impact > 0 else "normal"
            results.append(self._evidence(ticker, f"volatility:{published.date()}", "volatility", "Market volatility regime",
                f"VIX closed at {value:.2f}: {regime} regime (low below {VIX_LOW}, elevated at {VIX_HIGH} or higher).",
                published, fetched, impact, MARKET_CONFIDENCE, {"symbol": "^VIX", "close": value},
                "https://finance.yahoo.com/quote/%5EVIX/"))
        return results

    def _evidence(self, ticker, identity, event, title, summary, published, fetched, impact, confidence, details, url):
        return OutlookEvidence(id=f"market:{ticker}:{identity}", ticker=ticker, category="market", event_type=event,
            title=title, summary=summary, source="Market Data (existing Yahoo history service)", source_type="market_data",
            source_url=url, published_at=published, observed_at=fetched, impact=impact, confidence=confidence,
            materiality=MARKET_MATERIALITY, materiality_reason="Shared broad-equity context; not the ticker's Technical Score.",
            raw_provider="market", raw_provider_id=identity, source_details=details)
