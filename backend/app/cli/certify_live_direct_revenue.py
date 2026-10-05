"""One-shot bounded live certification for direct revenue history (AAPL, NVDA only)."""
from __future__ import annotations

import json
from urllib.error import HTTPError

from app.config import settings
from app.services import revenue_history_runtime
from app.services.outlook_structured import transport


TICKERS = ("AAPL", "NVDA")
GLOBAL_LIMIT = 6
TICKER_LIMIT = 3


def _resource_type(url):
    if url.endswith("/files/company_tickers.json"):
        return "ticker_cik_mapping"
    if "/api/xbrl/companyfacts/" in url:
        return "company_facts"
    if "/submissions/" in url:
        return "submissions_recent"
    raise RuntimeError("unauthorized_sec_resource")


def _summarize_acquisition(value):
    history = value.snapshot
    revenue = [row for row in history.observations if row.metric == "revenue"]
    latest = max(revenue, key=lambda row: (row.fiscal_year, row.fiscal_quarter), default=None)
    submissions = value.submissions
    return {
        "normalized_ticker": history.ticker,
        "issuer": history.issuer,
        "cik": history.cik,
        "acquisition_policy": value.acquisition_policy,
        "historical_snapshot_schema": history.schema_version,
        "acquisition_evidence_fingerprint": value.evidence_fingerprint,
        "cache_state": value.cache_state,
        "logical_requests": value.logical_requests,
        "http_attempts": value.http_attempts,
        "accepted_revenue_observation_count": len(revenue),
        "accepted_total_observation_count": history.diagnostics.accepted_observation_count,
        "rejected_fact_count": history.diagnostics.rejected_fact_count,
        "missing_fiscal_periods": [row.model_dump(mode="json") for row in history.missing_periods],
        "conflict_observation_count": sum(row.version_status == "conflict" for row in revenue),
        "latest": None if latest is None else {
            "fiscal_identity": f"FY{latest.fiscal_year} {latest.fiscal_quarter}",
            "exact_revenue": str(latest.normalized_value),
            "concept": latest.original_concept,
            "unit": latest.original_unit,
            "currency": latest.currency,
            "form": latest.form,
            "accession": latest.accession,
            "source_url": latest.source_url,
        },
        "submissions": None if submissions is None else {
            "typed_row_count": len(submissions.rows),
            "malformed_row_count": None,
            "issuer_identity_validated": submissions.issuer == history.issuer,
            "cik_identity_validated": submissions.cik == history.cik,
            "recent_10k_10q_report_periods": sorted({str(row.report_period_end)
                for row in submissions.rows if row.form in {"10-K", "10-K/A", "10-Q", "10-Q/A"}
                and row.report_period_end is not None}, reverse=True)[:16],
        },
    }


def _summarize_snapshot(value):
    series, projection = value.series, value.projection
    documents = value.request_accounting.document_accounting
    return {
        "snapshot_policy": value.snapshot_policy,
        "state": value.state,
        "reasons": list(value.reasons),
        "q4_considered": value.q4_considered,
        "q4_attempted": value.q4_attempted,
        "q4_skip_reason": value.q4_skip_reason,
        "series_state": None if series is None else series.state,
        "series_research_eligible": None if series is None else series.research_eligible,
        "series_observation_count": None if series is None else series.observation_count,
        "series_missing_periods": [] if series is None else list(series.missing_periods),
        "series_conflicts": [] if series is None else list(series.conflicts),
        "projection_state": None if projection is None else projection.state,
        "projection_point_count": 0 if projection is None else len(projection.points),
        "qoq_count": 0 if projection is None or projection.summary is None
            else projection.summary.available_qoq_comparisons,
        "yoy_count": 0 if projection is None or projection.summary is None
            else projection.summary.available_yoy_comparisons,
        "filing_document_http_attempts": 0 if documents is None else documents.http_attempts_charged,
        "request_accounting": value.request_accounting.model_dump(mode="json"),
    }


def main():
    original = {
        "master": settings.outlook_historical_revenue_enabled,
        "q4": settings.outlook_historical_revenue_q4_derivation_enabled,
        "attempts": settings.outlook_http_attempts,
    }
    original_urlopen = transport.urlopen
    requests = []
    active_ticker = [None]

    def observed_urlopen(request, *args, **kwargs):
        ticker = active_ticker[0]
        resource = _resource_type(request.full_url)
        ticker_count = sum(row["ticker"] == ticker for row in requests)
        if ticker not in TICKERS or len(requests) >= GLOBAL_LIMIT or ticker_count >= TICKER_LIMIT:
            raise RuntimeError("authorization_budget_exceeded_before_request")
        record = {"ordinal": len(requests) + 1, "ticker": ticker, "resource_type": resource,
            "status": None, "attempt": 1}
        requests.append(record)
        try:
            response = original_urlopen(request, *args, **kwargs)
            record["status"] = getattr(response, "status", None)
            return response
        except HTTPError as exc:
            record["status"] = exc.code
            raise

    output = {"authorization": {"global_limit": GLOBAL_LIMIT, "per_ticker_limit": TICKER_LIMIT},
        "tickers": {}, "requests": requests}
    try:
        settings.outlook_historical_revenue_enabled = True
        settings.outlook_historical_revenue_q4_derivation_enabled = False
        settings.outlook_http_attempts = 1
        revenue_history_runtime.get_revenue_history_snapshot_service.cache_clear()
        service = revenue_history_runtime.get_revenue_history_snapshot_service()
        provider = service.acquire_history.__self__
        output["cache_before"] = {
            "ticker_mapping_warm": bool(provider.mapping_cache.entries),
            "AAPL_acquisition_bundle_warm": "AAPL" in provider.history_cache.entries,
            "NVDA_acquisition_bundle_warm": "NVDA" in provider.history_cache.entries,
        }
        transport.urlopen = observed_urlopen
        for ticker in TICKERS:
            active_ticker[0] = ticker
            before = len(requests)
            row = {"maximum_global_budget_remaining_before": GLOBAL_LIMIT - before,
                "maximum_ticker_budget_remaining_before": TICKER_LIMIT}
            try:
                first = service.acquire_history(ticker)
                after_first = len(requests)
                repeat = service.acquire_history(ticker)
                after_repeat = len(requests)
                snapshot = service.get_snapshot(ticker)
                row.update({"acquisition": _summarize_acquisition(first),
                    "warm_repeat": {
                        "additional_http_attempts": after_repeat - after_first,
                        "same_fingerprint": repeat.evidence_fingerprint == first.evidence_fingerprint,
                        "cache_state": repeat.cache_state,
                    },
                    "snapshot": _summarize_snapshot(snapshot),
                    "unexpected_exception": None})
            except Exception as exc:
                row["unexpected_exception"] = type(exc).__name__
                try:
                    snapshot = service.get_snapshot(ticker)
                    row["snapshot"] = _summarize_snapshot(snapshot)
                except Exception as snapshot_exc:
                    row["snapshot_exception"] = type(snapshot_exc).__name__
            row["observed_http_attempts"] = len(requests) - before
            output["tickers"][ticker] = row
        output["global_http_attempts"] = len(requests)
        output["limits_respected"] = (len(requests) <= GLOBAL_LIMIT and all(
            sum(row["ticker"] == ticker for row in requests) <= TICKER_LIMIT for ticker in TICKERS))
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
    finally:
        transport.urlopen = original_urlopen
        settings.outlook_historical_revenue_enabled = original["master"]
        settings.outlook_historical_revenue_q4_derivation_enabled = original["q4"]
        settings.outlook_http_attempts = original["attempts"]
        revenue_history_runtime.get_revenue_history_snapshot_service.cache_clear()


if __name__ == "__main__":
    main()
