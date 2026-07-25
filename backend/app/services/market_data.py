import logging
import re
from time import perf_counter

import yfinance as yf
from yfinance.exceptions import YFRateLimitError


PRICE_HISTORY_TIMEOUT_SECONDS = 10
LOGGER = logging.getLogger("market_data")


class MarketDataError(RuntimeError):
    category = "provider_failure"
    retryable = True

    def __init__(self, ticker, message, *, cause=None):
        super().__init__(message)
        self.ticker = str(ticker).strip().upper()
        self.cause = cause


class MarketDataRateLimitError(MarketDataError):
    category = "rate_limit"


class MarketDataUnavailableError(MarketDataError):
    category = "temporary_provider_failure"


class InvalidTickerError(MarketDataError):
    category = "invalid_ticker"
    retryable = False
    invalid_ticker = True


VALID_TICKER_PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.^=-]{0,24}$")


def classify_market_data_error(error):
    return {
        "category": getattr(error, "category", "unexpected_error"),
        "retryable": bool(getattr(error, "retryable", False)),
        "invalid_ticker": bool(getattr(error, "invalid_ticker", False)),
    }


def _record_market_data_request(audit_context, ticker, period, interval, duration, data, error=None):
    if audit_context is None:
        return

    request_key = (str(ticker).strip().upper(), str(period), str(interval))
    request_keys = audit_context.setdefault("market_data_request_keys", set())
    request_count = audit_context.setdefault("market_data_requests", 0)
    duplicate_count = audit_context.setdefault("duplicate_market_data_requests", 0)
    request_details = audit_context.setdefault("market_data_request_details", [])

    request_count += 1
    if request_key in request_keys:
        duplicate_count += 1
    else:
        request_keys.add(request_key)

    audit_context["market_data_requests"] = request_count
    audit_context["duplicate_market_data_requests"] = duplicate_count
    audit_context["last_fetch_seconds"] = duration

    request_details.append({
        "symbol": request_key[0],
        "period": request_key[1],
        "interval": request_key[2],
        "duration_seconds": round(duration, 6),
        "row_count": int(len(data)) if data is not None else 0,
        "empty": bool(getattr(data, "empty", False)) if data is not None else True,
        "error": bool(error),
        "error_type": type(error).__name__ if error is not None else None,
    })

    stage_timings = audit_context.setdefault("stage_timings", {})
    stage_timings["market_data_fetching_seconds"] = stage_timings.get("market_data_fetching_seconds", 0.0) + duration


def get_price_history(ticker: str, period: str = "max", interval: str = "1d", audit_context=None):
    ticker = str(ticker).strip().upper()
    if not VALID_TICKER_PATTERN.fullmatch(ticker):
        raise InvalidTickerError(ticker, f"Ticker format is invalid: {ticker!r}")

    request_started_at = perf_counter()

    try:
        stock = yf.Ticker(ticker)

        data = stock.history(
            period=period,
            interval=interval,
            timeout=PRICE_HISTORY_TIMEOUT_SECONDS,
        )
    except YFRateLimitError as exc:
        _record_market_data_request(audit_context, ticker, period, interval, perf_counter() - request_started_at, None, error=exc)
        LOGGER.warning(
            "[MARKET_DATA_FAILURE] symbol=%s category=rate_limit retryable=true",
            ticker,
        )
        raise MarketDataRateLimitError(
            ticker,
            f"Market data provider rate limit reached for {str(ticker).strip().upper()}",
            cause=exc,
        ) from exc
    except Exception as exc:
        _record_market_data_request(audit_context, ticker, period, interval, perf_counter() - request_started_at, None, error=exc)
        LOGGER.warning(
            "[MARKET_DATA_FAILURE] symbol=%s category=temporary_provider_failure retryable=true error_type=%s",
            ticker,
            type(exc).__name__,
        )
        raise MarketDataUnavailableError(
            ticker,
            f"Market data is temporarily unavailable for {str(ticker).strip().upper()}",
            cause=exc,
        ) from exc

    duration = perf_counter() - request_started_at
    _record_market_data_request(audit_context, ticker, period, interval, duration, data)

    if data.empty:
        # Yahoo also returns empty frames for throttling, transport failures, and
        # malformed responses. An empty frame alone is not proof of invalidity.
        LOGGER.warning(
            "[MARKET_DATA_FAILURE] symbol=%s category=temporary_provider_failure retryable=true empty_response=true",
            ticker,
        )
        raise MarketDataUnavailableError(
            ticker,
            f"Market data provider returned no rows for {str(ticker).strip().upper()}",
        )

    return data
