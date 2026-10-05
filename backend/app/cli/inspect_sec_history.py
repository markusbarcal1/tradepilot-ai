"""Offline-first diagnostics for bounded SEC historical normalization."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter

from app.config import Settings
from app.services.outlook_structured.sec_history import (
    SecHistoricalFinancialProvider, normalize_companyfacts,
)
from app.services.outlook_structured.transport import JsonClient, ProviderUnavailable

LIVE_CERTIFICATION_TICKERS = frozenset({"AAPL", "NVDA", "ABTC"})
LIVE_CERTIFICATION_ORDER = ("AAPL", "NVDA", "ABTC")
LIVE_CERTIFICATION_REQUEST_BUDGET = 9


class AggregateSecRequestClient:
    """Count attempted SEC client calls and refuse an aggregate overrun."""

    def __init__(self, delegate, limit=LIVE_CERTIFICATION_REQUEST_BUDGET):
        self.delegate, self.limit, self.attempts = delegate, limit, 0

    def get(self, url, **kwargs):
        if self.attempts >= self.limit:
            raise ProviderUnavailable("aggregate_sec_request_budget_exceeded")
        self.attempts += 1
        return self.delegate.get(url, **kwargs)


def _summary(snapshot):
    return {
        "schema_version": snapshot.schema_version,
        "ticker": snapshot.ticker,
        "issuer": snapshot.issuer,
        "cik": snapshot.cik,
        "status": snapshot.status,
        "accepted_periods": sorted({row.period_id for row in snapshot.observations
                                    if row.version_status == "current"}),
        "observations": [row.model_dump(mode="json") for row in snapshot.observations],
        "rejected": [row.model_dump(mode="json") for row in snapshot.rejected],
        "amendments": [row.model_dump(mode="json") for row in snapshot.observations
                       if row.version_status in ("superseded", "conflict")],
        "missing_periods": [row.model_dump(mode="json") for row in snapshot.missing_periods],
        "comparison_eligibility": [{"observation_id": row.observation_id,
            "eligible": row.comparison_eligible,
            "reasons": list(row.comparison_exclusion_reasons)} for row in snapshot.observations],
        "sources": [{"observation_id": row.observation_id, "accession": row.accession,
            "form": row.form, "filing_date": row.filing_date.isoformat(),
            "acceptance_time": row.acceptance_time.isoformat() if row.acceptance_time else None,
            "url": row.source_url} for row in snapshot.observations],
        "request_and_cache_statistics": snapshot.diagnostics.model_dump(mode="json"),
    }


def _run_live_certification(output_dir, settings=None, client=None):
    settings = settings or Settings(outlook_sec_history_enabled=True, outlook_http_attempts=1)
    if settings.outlook_sec_history_request_budget > 3 or settings.outlook_http_attempts != 1:
        raise RuntimeError("Live certification requires a three-request per-ticker budget and one HTTP attempt")
    aggregate = AggregateSecRequestClient(client or JsonClient(settings))
    manifest = {"authorized_tickers": list(LIVE_CERTIFICATION_ORDER),
        "aggregate_request_budget": LIVE_CERTIFICATION_REQUEST_BUDGET, "results": []}
    output_dir.mkdir(parents=True, exist_ok=True)
    for symbol in LIVE_CERTIFICATION_ORDER:
        before = aggregate.attempts
        started = perf_counter()
        try:
            snapshot = SecHistoricalFinancialProvider(settings, aggregate).get_history(symbol)
            result = _summary(snapshot)
            status, failure = snapshot.status, None
        except Exception as error:
            result = {"schema_version": "1", "ticker": symbol, "status": "retrieval_failure",
                "observations": [], "rejected": [], "missing_periods": [],
                "comparison_eligibility": [], "sources": []}
            status, failure = "retrieval_failure", type(error).__name__
        elapsed = round(perf_counter() - started, 3)
        attempts = aggregate.attempts - before
        result["certification_execution"] = {"http_attempts": attempts,
            "aggregate_http_attempts_after_ticker": aggregate.attempts,
            "elapsed_seconds": elapsed, "failure_type": failure}
        path = output_dir / f"phase6b5c2a2-{symbol.lower()}.json"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest["results"].append({"ticker": symbol, "status": status,
            "http_attempts": attempts, "elapsed_seconds": elapsed, "artifact": str(path)})
    manifest["actual_http_attempts"] = aggregate.attempts
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect internal SEC historical normalization")
    parser.add_argument("--fixture", type=Path,
        help="Offline JSON containing ticker, retrieved_at, companyfacts and submissions")
    parser.add_argument("--ticker", help="Ticker override for fixture or explicit live diagnostic")
    parser.add_argument("--live", action="store_true",
        help="Explicitly allow official SEC requests; never enabled by default")
    parser.add_argument("--output", type=Path,
        help="Optional bounded JSON diagnostic artifact path")
    parser.add_argument("--live-certification-output-dir", type=Path,
        help="Run the hard-coded three-ticker certification once under one aggregate request budget")
    args = parser.parse_args(argv)
    if args.live_certification_output_dir:
        if args.fixture or args.ticker or args.live or args.output:
            parser.error("The aggregate live certification mode cannot be combined with other inputs")
        rendered = json.dumps(_run_live_certification(args.live_certification_output_dir),
            indent=2, sort_keys=True)
        print(rendered)
        return 0
    if args.fixture:
        payload = json.loads(args.fixture.read_text(encoding="utf-8"))
        retrieved_at = datetime.fromisoformat(payload.get("retrieved_at", "").replace("Z", "+00:00"))
        snapshot = normalize_companyfacts(payload["companyfacts"], payload.get("submissions", {}),
            args.ticker or payload["ticker"], retrieved_at)
    elif args.live and args.ticker:
        symbol = args.ticker.strip().upper()
        if symbol not in LIVE_CERTIFICATION_TICKERS:
            parser.error("Live certification is restricted to AAPL, NVDA and ABTC")
        settings = Settings(outlook_sec_history_enabled=True)
        snapshot = SecHistoricalFinancialProvider(settings).get_history(symbol)
    else:
        parser.error("Provide --fixture for offline diagnostics, or both --live and --ticker explicitly")
    rendered = json.dumps(_summary(snapshot), indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
