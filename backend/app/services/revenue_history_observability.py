"""Bounded server logging for normal Analyze revenue-history invocations."""
import json
import logging
import re
from time import monotonic


LOGGER = logging.getLogger(__name__)
EVENT_NAME = "revenue_history_snapshot"
_TICKER = re.compile(r"[A-Z0-9][A-Z0-9.-]{0,15}")
_CODE = re.compile(r"[a-z0-9_]{1,64}")


def _ticker(value):
    normalized = str(value).strip().upper()
    return normalized if _TICKER.fullmatch(normalized) else "INVALID"


def _reason(result):
    reasons = getattr(result, "reasons", ()) or ()
    candidate = reasons[0] if reasons else None
    if candidate is None and getattr(result, "state", None) == "available":
        candidate = "available"
    if candidate is None:
        candidate = getattr(result, "q4_skip_reason", None) or "none"
    return candidate if isinstance(candidate, str) and _CODE.fullmatch(candidate) else "unavailable_reason"


def _fields(result, settings, elapsed_ms):
    accounting = getattr(result, "request_accounting", None)
    documents = getattr(accounting, "document_accounting", None)
    historical_logical = getattr(accounting, "historical_logical_requests", None)
    historical_attempts = getattr(accounting, "historical_http_attempts", None)
    document_logical = getattr(documents, "logical_documents_requested", None)
    document_attempts = getattr(documents, "http_attempts_charged", None)
    success_hits = getattr(documents, "cache_success_hits", None)
    failure_hits = getattr(documents, "cache_failure_hits", None)
    document_hits = (success_hits + failure_hits
        if isinstance(success_hits, int) and isinstance(failure_hits, int) else None)
    projection = getattr(result, "projection", None)
    total_attempts = getattr(accounting, "total_sec_http_attempts", None)
    total_logical = (historical_logical + document_logical
        if isinstance(historical_logical, int) and isinstance(document_logical, int)
        else historical_logical if isinstance(historical_logical, int) and documents is None else None)
    return {
        "event": EVENT_NAME,
        "ticker": _ticker(getattr(result, "ticker", "")),
        "master_enabled": bool(settings.outlook_historical_revenue_enabled),
        "q4_enabled": bool(settings.outlook_historical_revenue_q4_derivation_enabled),
        "snapshot_state": getattr(result, "state", None),
        "reason_code": _reason(result),
        "q4_considered": bool(getattr(result, "q4_considered", False)),
        "q4_attempted": bool(getattr(result, "q4_attempted", False)),
        "target_fy": getattr(result, "target_fiscal_year", None),
        "acquisition_cache_state": getattr(accounting, "acquisition_cache_state", None),
        "document_cache_hits": document_hits,
        "document_misses_or_attempted": document_attempts,
        "document_failures": getattr(documents, "failures", None),
        "historical_logical_requests": historical_logical,
        "historical_http_attempts": historical_attempts,
        "document_logical_requests": document_logical,
        "document_http_attempts": document_attempts,
        "total_logical_requests": total_logical,
        "total_http_attempts": total_attempts,
        "projection_state": getattr(projection, "state", None),
        "elapsed_ms": max(0, round(elapsed_ms)),
    }


def _emit(level, fields):
    try:
        LOGGER.log(level, json.dumps(fields, sort_keys=True, separators=(",", ":")),
            extra={"revenue_history_event": fields})
    except Exception:
        # Operational telemetry must never change a valid Analyze outcome.
        return


def observe_revenue_snapshot(service, ticker, settings, *, clock=monotonic):
    """Invoke once, log one completion or bounded error event, and preserve behavior."""
    started = clock()
    try:
        result = service.get_snapshot(ticker)
    except Exception as exc:
        fields = {
            "event": EVENT_NAME,
            "ticker": _ticker(ticker),
            "master_enabled": bool(settings.outlook_historical_revenue_enabled),
            "q4_enabled": bool(settings.outlook_historical_revenue_q4_derivation_enabled),
            "outcome": "unexpected_exception",
            "elapsed_ms": max(0, round((clock() - started) * 1000)),
            "exception_type": type(exc).__name__,
        }
        _emit(logging.ERROR, fields)
        raise
    fields = _fields(result, settings, (clock() - started) * 1000)
    _emit(logging.INFO, fields)
    return result
