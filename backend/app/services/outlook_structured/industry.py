"""Bounded sector context from structured Yahoo metadata and existing price history."""
from datetime import datetime, timedelta, timezone
from math import isfinite

import pandas as pd
import yfinance as yf

from app.models.outlook_evidence import OutlookEvidence
from app.services.market_data import VALID_TICKER_PATTERN
from .history import OutlookHistory
from .market import completed_history
from .transport import Cache, ProviderUnavailable

# Yahoo sector names -> S&P 500 Select Sector proxies. Never infer from industry text.
BENCHMARKS = {
    "technology": "XLK", "financial services": "XLF", "energy": "XLE",
    "healthcare": "XLV", "industrials": "XLI", "consumer cyclical": "XLY",
    "consumer defensive": "XLP", "utilities": "XLU", "basic materials": "XLB",
    "real estate": "XLRE", "communication services": "XLC",
}
PEER_LIMIT = 6
MIN_PEERS = 4
HOLDINGS_TTL = 86400


def classification(ticker):
    info = yf.Ticker(ticker).get_info()
    return {key: info.get(key) for key in ("sector", "industry", "quoteType", "exchange", "country")}


def holdings(symbol):
    frame = yf.Ticker(symbol).funds_data.top_holdings
    if frame is None or frame.empty or "Holding Percent" not in frame:
        raise ProviderUnavailable("holdings_unavailable")
    # Stable rank, independent of upstream row order; only structured holding symbols.
    rows = [(str(s).strip().upper(), float(w)) for s, w in frame["Holding Percent"].items()
            if pd.notna(w) and isfinite(float(w)) and float(w) > 0]
    return [s for s, _ in sorted(rows, key=lambda row: (-row[1], row[0]))
            if VALID_TICKER_PATTERN.fullmatch(s)][:10]


def direction(value, deadband):
    return 1 if value > deadband else -1 if value < -deadband else 0


def consensus(values):
    return values[0] if values and all(v == values[0] for v in values) else 0


def metrics(frame):
    close = frame.Close
    return {"return_21": float(close.iloc[-1] / close.iloc[-22] - 1),
            "return_63": float(close.iloc[-1] / close.iloc[-64] - 1),
            "above_sma50": bool(close.iloc[-1] > close.iloc[-50:].mean()),
            "below_sma50": bool(close.iloc[-1] < close.iloc[-50:].mean())}


class IndustryEvidenceProvider:
    name = "industry"
    categories = ("industry",)
    uses_placeholder_data = False

    def __init__(self, settings, history=None, metadata=None, peers=None,
                 clock=lambda: datetime.now(timezone.utc)):
        self.settings, self.clock = settings, clock
        self.history = history or OutlookHistory(settings)
        self.metadata, self.peers = metadata or classification, peers or holdings
        self.classifications = Cache(settings.outlook_failure_cache_ttl)
        self.memberships = Cache(settings.outlook_failure_cache_ttl, capacity=16)
        self.calculations = Cache(settings.outlook_failure_cache_ttl)
        self.unavailable_reason = None if settings.outlook_industry_enabled else "disabled"

    def _classification(self, ticker):
        value = self.metadata(ticker)
        if not isinstance(value, dict) or not value.get("sector"):
            raise ProviderUnavailable("missing_classification")
        return value

    def _members(self, symbol):
        values = list(dict.fromkeys(str(s).strip().upper() for s in self.peers(symbol)))
        values = [s for s in values if VALID_TICKER_PATTERN.fullmatch(s)]
        if not values:
            raise ProviderUnavailable("missing_peers")
        return values[:10]

    def _history(self, symbol, now):
        result = completed_history(self.history(symbol, "6mo", "1d"), now)
        if result is None:
            return None
        frame, published = result
        frame = frame.copy()
        frame.index = pd.Index([stamp.date() for stamp in frame.index])
        if frame.index.has_duplicates or len(frame) < 64:
            return None
        # Reject gappy series rather than silently treating old bars as recent sessions.
        if (frame.index[-1] - frame.index[-64]).days > 105:
            return None
        return frame, published

    def get_evidence(self, ticker):
        return self.inspect(ticker)["evidence"]

    def inspect(self, ticker):
        ticker = ticker.strip().upper()
        if self.unavailable_reason or not VALID_TICKER_PATTERN.fullmatch(ticker):
            return {"status": self.unavailable_reason or "invalid_symbol", "evidence": []}
        return self.calculations.get(ticker, lambda: self._load(ticker), self.settings.outlook_industry_cache_ttl)

    def _load(self, ticker):
        now = self.clock()
        context = self.classifications.get(ticker, lambda: self._classification(ticker),
                                           self.settings.outlook_classification_cache_ttl)
        benchmark = BENCHMARKS.get(str(context.get("sector", "")).strip().casefold())
        diagnostic = {"classification": context, "benchmark": benchmark, "market_benchmark": "SPY",
                      "peer_sample": [], "peer_coverage": 0, "evidence": []}
        if context.get("quoteType") != "EQUITY" or context.get("exchange") not in {"NMS", "NYQ", "NGM", "NCM", "ASE", "BTS"}:
            return {**diagnostic, "status": "unsupported_instrument"}
        if not benchmark:
            return {**diagnostic, "status": "unsupported_sector"}
        details = {"classification_source": "Yahoo Finance structured quote metadata", **context,
                   "benchmark": benchmark, "market_benchmark": "SPY", "windows_sessions": [21, 63],
                   "peer_scope": "sector ETF top-holdings sample, excluding target",
                   "observation_time": now.isoformat()}
        results = []
        sector = self._history(benchmark, now)
        if sector is None:
            raise ProviderUnavailable("insufficient_sector_history")
        frame, published = sector
        try:
            market = self._history("SPY", now)
        except Exception:
            market = None
        if market is not None:
            market_frame, _ = market
            # Identical session endpoints and observations for both return windows.
            dates = frame.index[-64:]
            if all(date in market_frame.index for date in dates):
                sm, mm = metrics(frame.loc[dates]), metrics(market_frame.loc[dates])
                relative = {f"relative_{n}": sm[f"return_{n}"] - mm[f"return_{n}"] for n in (21, 63)}
                trend = consensus([direction(sm["return_21"], .01), direction(sm["return_63"], .03),
                                   1 if sm["above_sma50"] else -1 if sm["below_sma50"] else 0])
                strength = consensus([direction(relative["relative_21"], .01), direction(relative["relative_63"], .02)])
                impact = consensus([trend, strength])
                # One combined event: inconsistent absolute/relative signals remain mixed.
                materiality = .8 if impact else .5
                trend_text = "strengthening" if trend > 0 else "weakening" if trend < 0 else "mixed"
                relative_text = "outperforming" if strength > 0 else "underperforming" if strength < 0 else "tracking or mixed against"
                summary = (f"{context['sector']} sector trend is {trend_text}, {relative_text} the broader market. "
                    f"{benchmark} returned {sm['return_21']:.1%} / {sm['return_63']:.1%} over 21 / 63 sessions; "
                    f"relative to SPY: {relative['relative_21'] * 100:+.1f} / {relative['relative_63'] * 100:+.1f} percentage points.")
                results.append(self._evidence(ticker, "sector_performance", "Sector trend and relative strength",
                    summary, published, now, impact, .9, materiality,
                    {**details, **sm, **relative, "trend_direction": trend, "relative_direction": strength,
                     "window_start": str(dates[0]), "window_end": str(dates[-1])}))
        try:
            members = self.memberships.get(benchmark, lambda: self._members(benchmark), HOLDINGS_TTL)
        except Exception:
            members = []
        sample = [s for s in members if s not in {ticker, benchmark, "SPY"}][:PEER_LIMIT]
        rows = []
        for symbol in sample:
            try:
                peer = self._history(symbol, now)
                dates = frame.index[-64:]
                if peer is not None and all(date in peer[0].index for date in dates):
                    rows.append({"symbol": symbol, **metrics(peer[0].loc[dates])})
            except Exception:
                continue
        diagnostic.update(peer_sample=sample, peer_coverage=len(rows))
        if len(rows) >= MIN_PEERS:
            positive = sum(r["return_21"] > 0 for r in rows) / len(rows)
            negative = sum(r["return_21"] < 0 for r in rows) / len(rows)
            above = sum(r["above_sma50"] for r in rows) / len(rows)
            below = sum(r["below_sma50"] for r in rows) / len(rows)
            impact = 1 if min(positive, above) >= 2/3 else -1 if min(negative, below) >= 2/3 else 0
            confidence = .85 if len(rows) == len(sample) else .65
            state = "broad strength" if impact > 0 else "broad weakness" if impact < 0 else "mixed performance"
            summary = (f"The {context['sector']} sector peer sample shows {state}: {positive:.0%} have positive "
                       f"21-session returns and {above:.0%} are above their 50-session average. "
                       f"Coverage {len(rows)}/{len(sample)}; {ticker} excluded. This is a sector sample, not industry-wide breadth.")
            results.append(self._evidence(ticker, "industry_peer_breadth", "Sector peer breadth", summary,
                published, now, impact, confidence, .8 if impact else .5,
                {**details, "peer_sample": sample, "peer_coverage": len(rows), "peers": rows,
                 "positive_return_breadth": positive, "above_sma50_breadth": above,
                 "window_start": str(frame.index[-64]), "window_end": str(frame.index[-1])}))
        return {**diagnostic, "status": "available" if len(results) == 2 else "partial" if results else "insufficient_data",
                "evidence": results}

    def _evidence(self, ticker, event, title, summary, published, observed, impact, confidence, materiality, details):
        identity = f"{details['benchmark']}:{event}:{published.date()}"
        return OutlookEvidence(id=f"industry:{ticker}:{identity}", ticker=ticker, category="industry",
            event_type=event, title=title, summary=summary, source="Yahoo Finance sector market data",
            source_type="market_data", source_url=f"https://finance.yahoo.com/quote/{details['benchmark']}/",
            published_at=published, observed_at=observed, expires_at=published + timedelta(days=7),
            impact=impact, confidence=confidence, materiality=materiality,
            materiality_reason="Sustained sector condition." if impact else "Mixed or limited directional sector condition.",
            raw_provider="industry", raw_provider_id=identity, source_details=details)
