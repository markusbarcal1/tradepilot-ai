"""Valuation analysis orchestration, profile selection, caching, and serialization."""

import logging
from copy import deepcopy
from threading import RLock
from time import time

from .config import CACHE_TTL_SECONDS, VALUATION_PROFILE_VERSION, VALUATION_SCORING_VERSION
from .metrics import calculate_valuation_metrics, currency_consistency, valid_number
from .profiles import PROFILE_LABELS, SectorProfile, normalize_sector, resolve_valuation_profile
from .provider import fetch_valuation_snapshot
from .scoring import score_valuation_metrics

logger = logging.getLogger(__name__)
_cache = {}
_cache_lock = RLock()
UNSUPPORTED_TYPES = {
    "ETF", "MUTUALFUND", "INDEX", "CRYPTOCURRENCY",
    "PREFERRED_STOCK", "PREFERREDSTOCK", "CLOSED_END_FUND", "CLOSEDENDFUND",
}


def _context(snapshot):
    profile = normalize_sector(snapshot.sector)
    return profile, {
        "sector": snapshot.sector,
        "sector_profile": profile.value,
        "sector_profile_label": PROFILE_LABELS[profile.value],
        "used_default_profile": profile is SectorProfile.DEFAULT,
        "profile_version": VALUATION_PROFILE_VERSION,
    }


def _empty_coverage():
    return {
        "configured_metrics": 8, "supported_metrics": 8, "available_metrics": 0,
        "missing_supported_metrics": 8, "unsupported_metrics": 0,
        "available_weight": 0, "supported_weight": 100, "configured_weight": 100,
        "weighted_coverage": 0, "metric_count_coverage": 0,
        "percentage": 0, "ratio": 0, "coverage_method": "weighted",
    }


def _unavailable(symbol, reason_code, message, snapshot=None):
    coverage = _empty_coverage()
    result = {
        "symbol": symbol, "ticker": symbol, "score": None,
        "status": "unsupported" if reason_code == "unsupported_instrument_type" else "unavailable",
        "status_label": "Unsupported" if reason_code == "unsupported_instrument_type" else "Unavailable",
        "availability": "unavailable", "reason_code": reason_code, "message": message,
        "coverage": coverage, "categories": {},
        "configured_metrics": 8, "supported_metrics": 8, "available_metrics": 0,
        "missing_supported_metrics": 8, "unsupported_metrics": 0,
        "scoring_version": VALUATION_SCORING_VERSION,
        "profile_version": VALUATION_PROFILE_VERSION,
        "provider": snapshot.provider if snapshot else "yfinance",
    }
    if snapshot:
        _, context = _context(snapshot)
        result.update(context)
        result.update({
            "as_of": snapshot.as_of, "currency": snapshot.currency,
            "financial_currency": snapshot.financial_currency,
            "currency_consistent": currency_consistency(
                snapshot.currency, snapshot.financial_currency
            ),
            "current_price": valid_number(snapshot.values.get("current_price")),
            "price_source": snapshot.price_source, "price_as_of": snapshot.price_as_of,
            "price_is_fallback": snapshot.price_is_fallback,
        })
    return result


def analyze_valuation(ticker, provider=fetch_valuation_snapshot):
    symbol = str(ticker).strip().upper()
    cache_key = (
        symbol, VALUATION_SCORING_VERSION, VALUATION_PROFILE_VERSION,
        getattr(provider, "__name__", provider.__class__.__name__),
    )
    now = time()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return deepcopy(cached[1])

    try:
        snapshot = provider(symbol)
        if (snapshot.instrument_type or "").upper() in UNSUPPORTED_TYPES:
            result = _unavailable(
                symbol, "unsupported_instrument_type",
                "Relative company valuation is not supported for this instrument.",
                snapshot,
            )
        else:
            profile, context = _context(snapshot)
            if profile is SectorProfile.DEFAULT and snapshot.sector:
                logger.info("Unknown valuation sector %r for %s; using default", snapshot.sector, symbol)
            result = score_valuation_metrics(
                calculate_valuation_metrics(snapshot),
                resolve_valuation_profile(profile),
            )
            result.update({
                "symbol": symbol, "ticker": symbol, **context,
                "as_of": snapshot.as_of, "provider": snapshot.provider,
                "currency": snapshot.currency,
                "financial_currency": snapshot.financial_currency,
                "currency_consistent": currency_consistency(
                    snapshot.currency, snapshot.financial_currency
                ),
                "current_price": valid_number(snapshot.values.get("current_price")),
                "market_cap": valid_number(snapshot.values.get("market_cap")),
                "enterprise_value": valid_number(snapshot.values.get("enterprise_value")),
                "price_source": snapshot.price_source,
                "price_as_of": snapshot.price_as_of,
                "price_is_fallback": snapshot.price_is_fallback,
            })
    except Exception:
        logger.exception("Valuation analysis provider failed for %s", symbol)
        result = _unavailable(
            symbol, "provider_error", "Valuation analysis is temporarily unavailable."
        )

    with _cache_lock:
        _cache[cache_key] = (now, deepcopy(result))
    return result
