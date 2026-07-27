import logging
from copy import deepcopy
from threading import RLock
from time import time

from .config import CACHE_TTL_SECONDS, DEFAULT_SCORING_PROFILE, SCORE_VERSION
from .metrics import calculate_metrics
from .profiles import (
    PROFILE_LABELS,
    PROFILE_VERSION,
    SectorProfile,
    normalize_sector,
    resolve_profile,
)
from .provider import fetch_financial_snapshot
from .scoring import score_financial_metrics

logger = logging.getLogger(__name__)
_cache = {}
_cache_lock = RLock()
UNSUPPORTED_TYPES = {
    "ETF", "MUTUALFUND", "INDEX", "CRYPTOCURRENCY", "PREFERRED_STOCK",
    "PREFERREDSTOCK", "CLOSED_END_FUND", "CLOSEDENDFUND",
}


def _profile_context(raw_sector):
    profile = normalize_sector(raw_sector)
    used_default = profile is SectorProfile.DEFAULT
    return {
        "sector": raw_sector,
        "sector_profile": profile.value,
        "sector_profile_label": PROFILE_LABELS[profile.value],
        "sector_source": "provider" if raw_sector else "unavailable",
        "used_default_profile": used_default,
        "profile_version": PROFILE_VERSION,
    }


def _unavailable(ticker, reason_code, message, provider="yfinance", raw_sector=None):
    expected_metrics = sum(
        len(category["metrics"]) for category in DEFAULT_SCORING_PROFILE.values()
    )
    return {
        "ticker": ticker,
        "status": "unavailable",
        "score": None,
        "label": "Unavailable",
        "coverage": {
            "percentage": 0, "ratio": 0, "weighted_coverage": 0,
            "metric_count_coverage": 0, "coverage_method": "weighted",
            "available_weight": 0, "supported_weight": 100,
            "configured_weight": 100, "total_weight": 100,
            "configured_metrics": expected_metrics, "supported_metrics": expected_metrics,
            "available_metrics": 0, "expected_metrics": expected_metrics,
            "missing_supported_metrics": expected_metrics, "unsupported_metrics": 0,
            "confidence": "none",
        },
        "configured_metrics": expected_metrics,
        "available_metrics": 0,
        "expected_metrics": expected_metrics,
        "supported_metrics": expected_metrics,
        "missing_supported_metrics": expected_metrics,
        "unsupported_metrics": 0,
        "reason_code": reason_code,
        "message": message,
        "categories": {},
        "provider": provider,
        **_profile_context(raw_sector),
    }


def analyze_financials(ticker, provider=fetch_financial_snapshot):
    symbol = str(ticker).strip().upper()
    now = time()
    with _cache_lock:
        cache_key = (symbol, SCORE_VERSION, PROFILE_VERSION)
        cached = _cache.get(cache_key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return deepcopy(cached[1])

    try:
        snapshot = provider(symbol)
        if (snapshot.instrument_type or "").upper() in UNSUPPORTED_TYPES:
            result = _unavailable(
                symbol, "unsupported_instrument_type",
                "Financial analysis is not available for this instrument.",
                snapshot.provider,
                snapshot.sector,
            )
        else:
            profile = normalize_sector(snapshot.sector)
            if profile is SectorProfile.DEFAULT and snapshot.sector:
                logger.info("Unknown financial sector %r for %s; using default profile", snapshot.sector, symbol)
            result = score_financial_metrics(calculate_metrics(snapshot), resolve_profile(profile))
            result.update({
                "ticker": symbol,
                "as_of": snapshot.as_of,
                "provider": snapshot.provider,
                **_profile_context(snapshot.sector),
            })
    except Exception:
        logger.exception("Financial analysis provider failed for %s", symbol)
        result = _unavailable(
            symbol, "provider_error",
            "Financial analysis is temporarily unavailable.",
        )

    with _cache_lock:
        _cache[cache_key] = (now, deepcopy(result))
    return result
