"""Bounded, versioned industry context with explicit sector fallback."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
from statistics import median

import pandas as pd
import yfinance as yf

from app.models.outlook_evidence import OutlookEvidence
from app.services.market_data import VALID_TICKER_PATTERN
from .history import OutlookHistory
from .market import completed_history
from .transport import Cache, ProviderUnavailable

INDUSTRY_TAXONOMY_VERSION = "1"
BENCHMARK_MAPPING_VERSION = "1"
BENCHMARKS = {
    "technology": "XLK", "financial services": "XLF", "energy": "XLE",
    "healthcare": "XLV", "industrials": "XLI", "consumer cyclical": "XLY",
    "consumer defensive": "XLP", "utilities": "XLU", "basic materials": "XLB",
    "real estate": "XLRE", "communication services": "XLC",
}
INDUSTRY_ALIASES = {
    "semiconductors": ("semiconductors", "Semiconductors"),
    "semiconductor equipment & materials": ("semiconductor_equipment", "Semiconductor Equipment & Materials"),
    "software - infrastructure": ("software_infrastructure", "Software - Infrastructure"),
    "software - application": ("software_application", "Software - Application"),
    "banks - diversified": ("banks_diversified", "Banks - Diversified"),
    "banks - regional": ("banks_regional", "Banks - Regional"),
    "biotechnology": ("biotechnology", "Biotechnology"),
    "drug manufacturers - general": ("pharmaceuticals", "Drug Manufacturers - General"),
    "aerospace & defense": ("aerospace_defense", "Aerospace & Defense"),
    "oil & gas integrated": ("integrated_oil_gas", "Oil & Gas Integrated"),
    "auto manufacturers": ("auto_manufacturers", "Auto Manufacturers"),
    "discount stores": ("discount_stores", "Discount Stores"),
    "consumer electronics": ("consumer_electronics", "Consumer Electronics"),
    "internet content & information": ("internet_content_information", "Internet Content & Information"),
    "computer hardware": ("computer_hardware", "Computer Hardware"),
}
INDUSTRY_BENCHMARKS = {
    "semiconductors": ("SOXX", "iShares Semiconductor ETF"),
    "semiconductor_equipment": ("SOXX", "iShares Semiconductor ETF"),
    "software_infrastructure": ("IGV", "iShares Expanded Tech-Software Sector ETF"),
    "software_application": ("IGV", "iShares Expanded Tech-Software Sector ETF"),
    "banks_diversified": ("KBE", "SPDR S&P Bank ETF"),
    "banks_regional": ("KRE", "SPDR S&P Regional Banking ETF"),
    "biotechnology": ("XBI", "SPDR S&P Biotech ETF"),
    "pharmaceuticals": ("IHE", "iShares U.S. Pharmaceuticals ETF"),
    "aerospace_defense": ("ITA", "iShares U.S. Aerospace & Defense ETF"),
    "integrated_oil_gas": ("XLE", "Energy Select Sector SPDR Fund"),
}
PEER_LIMIT, MIN_PEERS, HOLDINGS_TTL = 10, 5, 86400
HISTORY_MAX_POINTS = 128
HISTORY_WINDOWS = (("1M", 22), ("3M", 64), ("6M", None))
HISTORY_MIN_SIX_MONTH_POINTS = 100
PRICE_ADJUSTMENT_BASIS = "yahoo_auto_adjust_true"


def classification(ticker):
    info = yf.Ticker(ticker).get_info()
    return {key: info.get(key) for key in
            ("sector", "industry", "quoteType", "exchange", "country", "shortName", "longBusinessSummary")}


def holdings(symbol):
    frame = yf.Ticker(symbol).funds_data.top_holdings
    if frame is None or frame.empty or "Holding Percent" not in frame:
        raise ProviderUnavailable("holdings_unavailable")
    rows = [(str(s).strip().upper(), float(w)) for s, w in frame["Holding Percent"].items()
            if pd.notna(w) and isfinite(float(w)) and float(w) > 0]
    return [s for s, _ in sorted(rows, key=lambda row: (-row[1], row[0]))
            if VALID_TICKER_PATTERN.fullmatch(s)][:PEER_LIMIT + 1]


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


def relative_state(short, long):
    signs = direction(short, .03), direction(long, .05)
    if signs == (1, 1):
        return "strongly_outperforming" if short > .08 and long > .12 else "outperforming"
    if signs == (-1, -1):
        return "strongly_underperforming" if short < -.08 and long < -.12 else "underperforming"
    return "roughly_in_line" if signs == (0, 0) else "mixed"


def _window_points(rows):
    company_base, benchmark_base = rows[0][1], rows[0][2]
    return [{"date": str(day),
             "company_cumulative_return": 100 * (company / company_base - 1),
             "benchmark_cumulative_return": 100 * (benchmark / benchmark_base - 1),
             "relative_performance": 100 * ((company / company_base) - (benchmark / benchmark_base))}
            for day, company, benchmark in rows]


def historical_projection(ticker, benchmark, benchmark_name, benchmark_type, quality, fallback_reason,
                          taxonomy_version, mapping_version, target, group, observed_at):
    """Bounded immutable-ready projection from accepted frames; never retrieves data."""
    company_frame, company_published = target
    benchmark_frame, benchmark_published = group
    company_dates = {day for day in company_frame.index
        if isfinite(float(company_frame.at[day, "Close"])) and float(company_frame.at[day, "Close"]) > 0}
    benchmark_dates = {day for day in benchmark_frame.index
        if isfinite(float(benchmark_frame.at[day, "Close"])) and float(benchmark_frame.at[day, "Close"]) > 0}
    common_dates = sorted(company_dates & benchmark_dates)[-HISTORY_MAX_POINTS:]
    rows = [(day, float(company_frame.at[day, "Close"]), float(benchmark_frame.at[day, "Close"]))
            for day in common_dates]
    if len(rows) < 2:
        return None
    windows = {}
    for label, point_count in HISTORY_WINDOWS:
        if label == "6M":
            selected = rows if len(rows) >= HISTORY_MIN_SIX_MONTH_POINTS else []
        else:
            selected = rows[-point_count:] if len(rows) >= point_count else []
        if selected:
            windows[label] = _window_points(selected)
    if not windows:
        return None
    start, end = rows[0][0], rows[-1][0]
    identity = {"ticker": ticker, "benchmark": benchmark, "start": str(start), "end": str(end),
        "basis": PRICE_ADJUSTMENT_BASIS,
        "observations": [[str(day), company, group_value] for day, company, group_value in rows],
        "windows": {key: len(value) for key, value in windows.items()}}
    snapshot_id = sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
    bounded_company_dates = {day for day in company_dates if start <= day <= end}
    bounded_benchmark_dates = {day for day in benchmark_dates if start <= day <= end}
    return {"schema_version": "1", "snapshot_id": snapshot_id, "ticker": ticker,
        "as_of": observed_at.isoformat(), "series_start": str(start), "series_end": str(end),
        "price_adjustment_basis": PRICE_ADJUSTMENT_BASIS, "currency": "USD",
        "benchmark": {"symbol": benchmark, "name": benchmark_name, "benchmark_type": benchmark_type,
            "classification_quality": quality, "fallback_reason": fallback_reason,
            "taxonomy_version": taxonomy_version, "mapping_version": mapping_version},
        "available_windows": list(windows), "windows": windows,
        "coverage": {"common_session_count": len(rows),
            "company_missing_session_count": len(bounded_benchmark_dates - bounded_company_dates),
            "benchmark_missing_session_count": len(bounded_company_dates - bounded_benchmark_dates),
            "has_gaps": bounded_company_dates != bounded_benchmark_dates,
            "company_last_session": str(company_published.date()),
            "benchmark_last_session": str(benchmark_published.date())},
        "units": {"cumulative_return": "percentage_points", "relative_performance": "percentage_points"},
        "qualifier": "Adjusted-price return from Yahoo Close with auto-adjust enabled; TradePilot does not independently reconstruct or verify a dividend-reinvested total-return index."}


class IndustryEvidenceProvider:
    name, categories, uses_placeholder_data = "industry", ("industry",), False

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
        if not isinstance(value, dict) or not (value.get("sector") or value.get("industry")):
            raise ProviderUnavailable("missing_classification")
        return value

    def _members(self, symbol):
        values = list(dict.fromkeys(str(s).strip().upper() for s in self.peers(symbol)))
        values = [s for s in values if VALID_TICKER_PATTERN.fullmatch(s)]
        if not values:
            raise ProviderUnavailable("missing_peers")
        return values[:PEER_LIMIT + 1]

    def _history(self, symbol, now):
        result = completed_history(self.history(symbol, "6mo", "1d"), now)
        if result is None:
            return None
        frame, published = result
        frame = frame.copy()
        frame.index = pd.Index([stamp.date() for stamp in frame.index])
        if frame.index.has_duplicates or len(frame) < 64 or (frame.index[-1] - frame.index[-64]).days > 105:
            return None
        return frame, published

    def get_evidence(self, ticker):
        return self.inspect(ticker)["evidence"]

    def inspect(self, ticker):
        ticker = ticker.strip().upper()
        if self.unavailable_reason or not VALID_TICKER_PATTERN.fullmatch(ticker):
            return {"status": self.unavailable_reason or "invalid_symbol", "evidence": []}
        return self.calculations.get(ticker, lambda: self._load(ticker), self.settings.outlook_industry_cache_ttl)

    def _resolve(self, context):
        raw = str(context.get("industry") or "").strip()
        normalized = INDUSTRY_ALIASES.get(raw.casefold())
        sector = BENCHMARKS.get(str(context.get("sector") or "").strip().casefold())
        precise = INDUSTRY_BENCHMARKS.get(normalized[0]) if normalized else None
        if precise:
            return normalized, precise, "industry_etf", "exact_industry", None
        if sector:
            return normalized or (None, None), (sector, f"{context.get('sector')} sector ETF"), "sector_etf", "sector_fallback", "unsupported_industry" if raw else "missing_industry"
        return normalized or (None, None), (None, None), None, "unknown", "missing_sector_benchmark"

    def _load(self, ticker):
        now = self.clock()
        context = self.classifications.get(ticker, lambda: self._classification(ticker),
                                           self.settings.outlook_classification_cache_ttl)
        normalized, configured, benchmark_type, quality, fallback_reason = self._resolve(context)
        benchmark, benchmark_name = configured
        diagnostic = {"raw_sector": context.get("sector"), "raw_industry": context.get("industry"),
            "normalized_industry": normalized[0], "industry_name": normalized[1],
            "taxonomy_version": INDUSTRY_TAXONOMY_VERSION, "classification_quality": quality,
            "benchmark_symbol": benchmark, "benchmark_name": benchmark_name, "benchmark_type": benchmark_type,
            "mapping_version": BENCHMARK_MAPPING_VERSION, "fallback_reason": fallback_reason,
            "company_return_21": None, "company_return_63": None, "benchmark_return_21": None,
            "benchmark_return_63": None, "relative_return_21": None, "relative_return_63": None,
            "relative_performance_state": "unavailable", "configured_peer_count": 0,
            "valid_peer_count": 0, "peer_sample": [], "breadth_state": "unavailable",
            "industry_health_state": "unavailable", "evidence": []}
        if context.get("quoteType") != "EQUITY" or context.get("exchange") not in {"NMS", "NYQ", "NGM", "NCM", "ASE", "BTS"}:
            return {**diagnostic, "status": "unsupported_instrument"}
        if not benchmark:
            return {**diagnostic, "status": "unsupported_sector"}
        common = {"classification_source": "Yahoo Finance structured quote metadata",
            "raw_sector": context.get("sector"), "raw_industry": context.get("industry"),
            "normalized_industry": normalized[0], "industry_name": normalized[1],
            "taxonomy_version": INDUSTRY_TAXONOMY_VERSION, "classification_quality": quality,
            "benchmark_symbol": benchmark, "benchmark_name": benchmark_name, "benchmark_type": benchmark_type,
            "mapping_version": BENCHMARK_MAPPING_VERSION, "fallback_reason": fallback_reason,
            "market_benchmark": "SPY", "windows_sessions": [21, 63], "observation_time": now.isoformat()}
        try:
            group = self._history(benchmark, now)
        except Exception:
            group = None
        if group is None and benchmark_type == "industry_etf":
            sector = BENCHMARKS.get(str(context.get("sector") or "").strip().casefold())
            if sector:
                benchmark, benchmark_name, benchmark_type, quality = sector, f"{context.get('sector')} sector ETF", "sector_etf", "sector_fallback"
                fallback_reason = "industry_benchmark_history_unavailable"
                common.update(benchmark_symbol=benchmark, benchmark_name=benchmark_name, benchmark_type=benchmark_type,
                              classification_quality=quality, fallback_reason=fallback_reason)
                diagnostic.update(benchmark_symbol=benchmark, benchmark_name=benchmark_name, benchmark_type=benchmark_type,
                                  classification_quality=quality, fallback_reason=fallback_reason)
                group = self._history(benchmark, now)
        if group is None:
            raise ProviderUnavailable("insufficient_benchmark_history")
        frame, published = group
        dates, gm = frame.index[-64:], metrics(frame.iloc[-64:])
        trend = consensus([direction(gm["return_21"], .01), direction(gm["return_63"], .03),
                           1 if gm["above_sma50"] else -1 if gm["below_sma50"] else 0])
        health = "positive" if trend > 0 else "negative" if trend < 0 else "mixed"
        diagnostic.update(benchmark_return_21=gm["return_21"], benchmark_return_63=gm["return_63"], industry_health_state=health)
        scope = normalized[1] if benchmark_type == "industry_etf" else f"{context.get('sector')} sector fallback"
        summary = (f"{scope} health is {health}. {benchmark} returned {gm['return_21']:.1%} / {gm['return_63']:.1%} "
                   f"over 21 / 63 sessions and is {'above' if gm['above_sma50'] else 'below'} its 50-session average.")
        results = [self._evidence(ticker, "sector_performance", "Industry benchmark health", summary, published, now,
            trend, .9, .8 if trend else .5, {**common, **gm, "industry_health_state": health,
            "trend_direction": trend, "window_start": str(dates[0]), "window_end": str(dates[-1])})]
        try:
            target = self._history(ticker, now)
        except Exception:
            target = None
        if target is not None and all(date in target[0].index for date in dates):
            cm = metrics(target[0].loc[dates])
            rel21, rel63 = cm["return_21"] - gm["return_21"], cm["return_63"] - gm["return_63"]
            state = relative_state(rel21, rel63)
            impact = 1 if state.endswith("outperforming") else -1 if state.endswith("underperforming") else 0
            diagnostic.update(company_return_21=cm["return_21"], company_return_63=cm["return_63"],
                              relative_return_21=rel21, relative_return_63=rel63, relative_performance_state=state)
            summary = (f"{ticker} is {state.replace('_', ' ')} versus {benchmark}: company returns {cm['return_21']:.1%} / "
                       f"{cm['return_63']:.1%}, benchmark returns {gm['return_21']:.1%} / {gm['return_63']:.1%}, "
                       f"relative {rel21 * 100:+.1f} / {rel63 * 100:+.1f} percentage points over 21 / 63 sessions.")
            results.append(self._evidence(ticker, "industry_other", "Company relative industry performance", summary,
                published, now, impact, .9, .8 if impact else .5, {**common,
                "company_return_21": cm["return_21"], "company_return_63": cm["return_63"],
                "benchmark_return_21": gm["return_21"], "benchmark_return_63": gm["return_63"],
                "relative_return_21": rel21, "relative_return_63": rel63, "relative_performance_state": state,
                "window_start": str(dates[0]), "window_end": str(dates[-1])}))
            history = historical_projection(ticker, benchmark, benchmark_name, benchmark_type, quality,
                fallback_reason, INDUSTRY_TAXONOMY_VERSION, BENCHMARK_MAPPING_VERSION, target, group, now)
            diagnostic["history"] = history
            if history is not None:
                results[-1].source_details["history"] = history
        if benchmark_type == "industry_etf":
            try:
                members = self.memberships.get(benchmark, lambda: self._members(benchmark), HOLDINGS_TTL)
            except Exception:
                members = []
            sample = [s for s in members if s not in {ticker, benchmark, "SPY"}][:PEER_LIMIT]
            rows = []
            for symbol in sample:
                try:
                    peer = self._history(symbol, now)
                    if peer is not None and all(date in peer[0].index for date in dates):
                        rows.append({"symbol": symbol, **metrics(peer[0].loc[dates])})
                except Exception:
                    continue
            diagnostic.update(configured_peer_count=len(sample), valid_peer_count=len(rows), peer_sample=sample)
            if len(rows) >= MIN_PEERS:
                positive = sum(r["return_21"] > 0 for r in rows) / len(rows)
                above = sum(r["above_sma50"] for r in rows) / len(rows)
                negative = sum(r["return_21"] < 0 for r in rows) / len(rows)
                below = sum(r["below_sma50"] for r in rows) / len(rows)
                breadth = "positive" if min(positive, above) >= 2/3 else "negative" if min(negative, below) >= 2/3 else "mixed"
                med = median(r["return_21"] for r in rows)
                diagnostic.update(breadth_state=breadth, positive_return_breadth=positive,
                                  above_sma50_breadth=above, median_peer_return_21=med)
                results[0].source_details.update(peer_sample=sample, configured_peer_count=len(sample),
                    valid_peer_count=len(rows), positive_return_breadth=positive, above_sma50_breadth=above,
                    median_peer_return_21=med, breadth_state=breadth)
        diagnostic.update(evidence=results, status="available" if len(results) >= 2 else "partial" if results else "insufficient_data")
        return diagnostic

    def _evidence(self, ticker, event, title, summary, published, observed, impact, confidence, materiality, details):
        identity = f"{details['benchmark_symbol']}:{event}:{published.date()}:{BENCHMARK_MAPPING_VERSION}"
        return OutlookEvidence(id=f"industry:{ticker}:{identity}", ticker=ticker, category="industry",
            event_type=event, title=title, summary=summary, source="Yahoo Finance industry market data",
            source_type="market_data", source_url=f"https://finance.yahoo.com/quote/{details['benchmark_symbol']}/",
            published_at=published, observed_at=observed, expires_at=published + timedelta(days=7),
            impact=impact, confidence=confidence, materiality=materiality,
            materiality_reason="Sustained group condition." if impact else "Mixed or immaterial group condition.",
            raw_provider="industry", raw_provider_id=identity, source_details=details)
