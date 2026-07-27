import logging
from copy import deepcopy
from threading import RLock
from time import time

from .config import CACHE_TTL_SECONDS, DEFAULT_SCORING_PROFILE
from .metrics import calculate_metrics
from .provider import fetch_financial_snapshot
from .scoring import score_financial_metrics

logger = logging.getLogger(__name__)
_cache = {}
_cache_lock = RLock()
UNSUPPORTED_TYPES = {"ETF", "MUTUALFUND", "INDEX", "CRYPTOCURRENCY"}


def _unavailable(ticker, reason_code, message, provider="yfinance"):
    expected_metrics = sum(
        len(category["metrics"]) for category in DEFAULT_SCORING_PROFILE.values()
    )
    return {
        "ticker": ticker,
        "status": "unavailable",
        "score": None,
        "label": "Unavailable",
        "coverage": {
            "percentage": 0, "ratio": 0, "available_weight": 0, "total_weight": 100,
            "available_metrics": 0, "expected_metrics": expected_metrics, "confidence": "none",
        },
        "available_metrics": 0,
        "expected_metrics": expected_metrics,
        "reason_code": reason_code,
        "message": message,
        "categories": {},
        "provider": provider,
    }


def analyze_financials(ticker, provider=fetch_financial_snapshot):
    symbol = str(ticker).strip().upper()
    now = time()
    with _cache_lock:
        cached = _cache.get(symbol)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return deepcopy(cached[1])

    try:
        snapshot = provider(symbol)
        if (snapshot.instrument_type or "").upper() in UNSUPPORTED_TYPES:
            result = _unavailable(
                symbol, "unsupported_instrument_type",
                "Financial analysis is not available for this instrument.",
                snapshot.provider,
            )
        else:
            result = score_financial_metrics(calculate_metrics(snapshot))
            result.update({
                "ticker": symbol,
                "as_of": snapshot.as_of,
                "provider": snapshot.provider,
            })
    except Exception:
        logger.exception("Financial analysis provider failed for %s", symbol)
        result = _unavailable(
            symbol, "provider_error",
            "Financial analysis is temporarily unavailable.",
        )

    with _cache_lock:
        _cache[symbol] = (now, deepcopy(result))
    return result
