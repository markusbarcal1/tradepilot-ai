import csv
import logging
import os
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO
from time import perf_counter, time
from urllib.request import urlopen

from app.services.analyzer import analyze_ticker, analyze_tickers
from app.services.eligibility import ScannerEligibilityConfig


DEFAULT_UNIVERSE = "sp500"
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
NASDAQ_UNIVERSE_CACHE_SECONDS = 12 * 60 * 60
_nasdaq_universe_cache = {
    "expires_at": 0,
    "symbols": [],
}

SP500_UNIVERSE = [
    "MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A",
    "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL",
    "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG",
    "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO",
    "AAPL", "AMAT", "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG",
    "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR",
    "BALL", "BAC", "BAX", "BDX", "BRK-B", "BBY", "TECH", "BIIB", "BLK",
    "BX", "XYZ", "BNY", "BA", "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO",
    "BF-B", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CPT", "COF", "CAH",
    "CCL", "CARR", "CVNA", "CASY", "CAT", "CBOE", "CBRE", "CDW", "COR",
    "CNC", "CNP", "CF", "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD",
    "CIEN", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME", "CMS",
    "KO", "CTSH", "COHR", "COIN", "CL", "CMCSA", "FIX", "CAG", "COP",
    "ED", "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA", "CSGP",
    "COST", "CRH", "CRWD", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI",
    "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN", "DXCM", "FANG",
    "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI", "DTE",
    "DUK", "DD", "ETN", "EBAY", "SATS", "ECL", "EIX", "EW", "EA", "ELV",
    "EME", "EMR", "ETR", "EOG", "EQT", "EFX", "EQIX", "EQR", "ERIE",
    "ESS", "EL", "EG", "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD", "EXR",
    "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FDXF", "FIS",
    "FITB", "FSLR", "FE", "FISV", "FLEX", "F", "FTNT", "FTV", "FOXA",
    "FOX", "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC",
    "GD", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL",
    "HIG", "HAS", "HCA", "DOC", "HSIC", "HSY", "HPE", "HLT", "HD", "HON",
    "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM",
    "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "IBKR", "ICE",
    "IFF", "IP", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT",
    "JBL", "JKHY", "J", "JNJ", "JCI", "JPM", "KVUE", "KDP", "KEY", "KEYS",
    "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC", "KR", "LHX", "LH", "LRCX",
    "LVS", "LDOS", "LEN", "LII", "LLY", "LIN", "LYV", "LMT", "L", "LOW",
    "LULU", "LITE", "LYB", "MTB", "MPC", "MAR", "MRSH", "MLM", "MRVL",
    "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK", "META", "MET", "MTD",
    "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP", "MDLZ", "MPWR",
    "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX",
    "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS",
    "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY",
    "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR",
    "PANW", "PSKY", "PH", "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG",
    "PM", "PSX", "PNW", "PNC", "PPG", "PPL", "PFG", "PG", "PGR", "PLD",
    "PRU", "PEG", "PTC", "PSA", "PHM", "PWR", "QCOM", "DGX", "Q", "RL",
    "RJF", "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD",
    "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SNDK", "SBAC",
    "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SW", "SNA",
    "SOLV", "SO", "LUV", "SWK", "SBUX", "STT", "STLD", "STE", "SYK",
    "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW", "TTWO", "TPR", "TRGP",
    "TGT", "TEL", "TDY", "TER", "TSLA", "TXN", "TPL", "TXT", "TMO", "TJX",
    "TKO", "TTD", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN",
    "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS",
    "VLO", "VEEV", "VTR", "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VRT",
    "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW", "WAB", "WMT", "DIS",
    "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WY", "WSM",
    "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM", "ZBRA", "ZBH",
    "ZTS",
]

SCAN_UNIVERSES = {
    "sp500": SP500_UNIVERSE,
}

LOGGER = logging.getLogger("scanner.audit")
if not LOGGER.handlers:
    logging.basicConfig(level=logging.INFO)
SCANNER_AUDIT_ENABLED_ENV = "SCANNER_AUDIT"
SCANNER_MAX_WORKERS_ENV = "SCANNER_MAX_WORKERS"
DEFAULT_SCANNER_MAX_WORKERS = 8
MIN_SCANNER_MAX_WORKERS = 1
MAX_SCANNER_MAX_WORKERS = 16


def _is_scannable_nasdaq_listing(row):
    symbol = row.get("Symbol", "").strip()
    security_name = row.get("Security Name", "").lower()

    if not symbol or symbol.startswith("File Creation Time"):
        return False

    if row.get("Test Issue", "").strip().upper() != "N":
        return False

    if row.get("ETF", "").strip().upper() == "Y":
        return False

    excluded_terms = (
        " warrant",
        " warrants",
        " right",
        " rights",
        " unit",
        " units",
        " preferred",
        " preference",
        " senior note",
        " notes due",
        " bond",
        " debenture",
    )

    return not any(term in security_name for term in excluded_terms)


def get_nasdaq_universe():
    if (
        _nasdaq_universe_cache["symbols"]
        and _nasdaq_universe_cache["expires_at"] > time()
    ):
        return _nasdaq_universe_cache["symbols"]

    try:
        with urlopen(NASDAQ_LISTED_URL, timeout=20) as response:
            data = response.read().decode("utf-8")
    except Exception as e:
        raise ValueError(f"Unable to load Nasdaq universe: {e}")

    symbols = []
    reader = csv.DictReader(StringIO(data), delimiter="|")

    for row in reader:
        if _is_scannable_nasdaq_listing(row):
            symbols.append(row["Symbol"].strip().upper().replace(".", "-"))

    _nasdaq_universe_cache["symbols"] = symbols
    _nasdaq_universe_cache["expires_at"] = time() + NASDAQ_UNIVERSE_CACHE_SECONDS

    return symbols


def get_scan_universe(universe: str):
    universe_key = universe.strip().lower()

    if universe_key == "nasdaq":
        return universe_key, get_nasdaq_universe()

    if universe_key not in SCAN_UNIVERSES:
        available = ", ".join(sorted([*SCAN_UNIVERSES.keys(), "nasdaq"]))
        raise ValueError(f"Unknown scanner universe '{universe}'. Available universes: {available}")

    return universe_key, SCAN_UNIVERSES[universe_key]


def get_safe_max_symbols(max_symbols: int | None, universe_size: int):
    if max_symbols is None:
        return universe_size

    if max_symbols < 1:
        return 1

    return min(max_symbols, universe_size)


def _build_scan_results(analyses, stage_timings=None):
    results = []

    filtering_start = perf_counter()
    for analysis in analyses:
        try:
            trade_quality_score_data = (
                analysis.get("trade_quality_score")
                or analysis.get("entry_score", {})
            )
            technical_score_data = (
                analysis.get("technical_score")
                or analysis.get("trend_score", {})
            )
            trade_setup = analysis.get("trade_setup", {})
            support_zone = analysis.get("support_zone") or {}
            resistance_zone = analysis.get("resistance_zone") or {}

            trade_quality_score = trade_quality_score_data.get("score", 0)
            technical_score = technical_score_data.get("score", 0)

            setup_type = trade_setup.get("setup_type")
            setup_bias = trade_setup.get("setup_bias")
            setup_quality = trade_setup.get("quality")

            # Scanner v1: bullish long setups only
            if setup_bias != "Bullish":
                continue

            if setup_type == "No Clear Setup":
                continue

            if setup_quality == "Unfavorable":
                continue

            results.append({
                "ticker": analysis.get("ticker"),
                "price": analysis.get("price"),

                "trade_quality_score": trade_quality_score,
                "trade_quality_grade": trade_quality_score_data.get("grade"),
                # Deprecated compatibility aliases for older scanner clients.
                "entry_score": trade_quality_score,
                "entry_grade": trade_quality_score_data.get("grade"),
                "technical_score": technical_score,
                "technical_grade": technical_score_data.get("grade"),
                # Deprecated compatibility aliases for older scanner clients.
                "trend_score": technical_score,
                "trend_grade": technical_score_data.get("grade"),

                "setup_type": setup_type,
                "setup_bias": setup_bias,
                "setup_quality": setup_quality,

                "entry": trade_setup.get("entry"),
                "stop": trade_setup.get("stop"),
                "target": trade_setup.get("target"),
                "risk_reward": trade_setup.get("risk_reward"),
                "risk_pct": trade_setup.get("risk_pct"),
                "reward_pct": trade_setup.get("reward_pct"),

                "rsi": analysis.get("rsi"),
                "rvol": analysis.get("rvol"),

                "support": support_zone.get("display", "N/A"),
                "resistance": resistance_zone.get("display", "N/A"),

                "notes": trade_setup.get("notes", []),
            })

        except Exception as e:
            print(f"Scanner failed for {analysis.get('ticker')}: {e}")

    if stage_timings is not None:
        stage_timings["filtering_seconds"] = perf_counter() - filtering_start

    sorting_start = perf_counter()
    results.sort(
        key=lambda stock: (
            -(stock["trade_quality_score"] or 0),
            -(stock["technical_score"] or 0),
            str(stock.get("ticker") or "")
        )
    )
    if stage_timings is not None:
        stage_timings["sorting_seconds"] = perf_counter() - sorting_start

    return results


def _build_scan_response(
    period,
    interval,
    universe_key,
    symbols_to_scan,
    safe_max_symbols,
    limit,
    results,
    errors=None,
    audit=None,
    stage_timings=None,
):
    errors = errors or []

    serialization_start = perf_counter()
    response = {
        "period": period,
        "interval": interval,
        "universe": universe_key,
        "scanned_count": len(symbols_to_scan),
        "max_symbols": safe_max_symbols,
        "mode": "bullish",
        "error_count": len(errors),
        "errors": errors,
        "count": len(results[:limit]),
        "results": results[:limit]
    }

    if audit is not None:
        response["audit"] = audit

    if stage_timings is not None:
        stage_timings["serialization_seconds"] = perf_counter() - serialization_start

    return response


def _is_audit_enabled(explicit=None):
    if explicit is not None:
        return bool(explicit)

    raw = os.getenv(SCANNER_AUDIT_ENABLED_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _normalize_reason(reason):
    if not reason:
        return "unknown"

    reason = str(reason).strip().lower().replace(" ", "_")
    if not reason:
        return "unknown"

    return reason


def _resolve_worker_count(max_workers=None):
    if max_workers is None:
        raw = os.getenv(SCANNER_MAX_WORKERS_ENV, "").strip()
        if not raw:
            return DEFAULT_SCANNER_MAX_WORKERS
        max_workers = raw

    if isinstance(max_workers, bool):
        return DEFAULT_SCANNER_MAX_WORKERS

    if isinstance(max_workers, str):
        stripped = max_workers.strip()
        if not stripped:
            return DEFAULT_SCANNER_MAX_WORKERS
        try:
            max_workers = int(stripped)
        except ValueError:
            return DEFAULT_SCANNER_MAX_WORKERS

    try:
        resolved = int(max_workers)
    except (TypeError, ValueError):
        return DEFAULT_SCANNER_MAX_WORKERS

    if resolved < MIN_SCANNER_MAX_WORKERS:
        return MIN_SCANNER_MAX_WORKERS

    if resolved > MAX_SCANNER_MAX_WORKERS:
        return MAX_SCANNER_MAX_WORKERS

    return resolved


def _create_audit_context():
    return {
        "stage_timings": {},
        "symbol_records": [],
        "market_data_request_keys": set(),
        "market_data_requests": 0,
        "duplicate_market_data_requests": 0,
        "market_data_request_details": [],
        "last_fetch_seconds": None,
    }


def _merge_audit_context(target, source):
    if target is None or source is None:
        return

    target_stage_timings = target.setdefault("stage_timings", {})
    source_stage_timings = source.get("stage_timings", {})
    for key, value in source_stage_timings.items():
        target_stage_timings[key] = target_stage_timings.get(key, 0.0) + float(value or 0.0)

    target_symbol_records = target.setdefault("symbol_records", [])
    target_symbol_records.extend(source.get("symbol_records", []))

    target.setdefault("market_data_request_keys", set()).update(source.get("market_data_request_keys", set()))
    target["market_data_requests"] = target.get("market_data_requests", 0) + int(source.get("market_data_requests", 0))
    target["duplicate_market_data_requests"] = target.get("duplicate_market_data_requests", 0) + int(source.get("duplicate_market_data_requests", 0))
    target.setdefault("market_data_request_details", []).extend(source.get("market_data_request_details", []))

    if source.get("last_fetch_seconds") is not None:
        target["last_fetch_seconds"] = source.get("last_fetch_seconds")


def _resolve_eligibility_config(eligibility=None):
    if eligibility is None:
        return None

    if isinstance(eligibility, ScannerEligibilityConfig):
        return eligibility

    if isinstance(eligibility, dict):
        return ScannerEligibilityConfig.from_dict(eligibility)

    return ScannerEligibilityConfig.from_dict({})


def _build_eligibility_summary(symbols_to_scan, eligibility_config, eligibility_records):
    if eligibility_config is None or not eligibility_config.enabled:
        return {
            "enabled": False,
            "symbols_checked": len(symbols_to_scan),
            "symbols_eligible": 0,
            "symbols_excluded": 0,
            "reason_counts": {},
        }

    reason_counts = {}
    for record in eligibility_records:
        reason_code = (record or {}).get("reason_code") or "eligible"
        reason_counts[reason_code] = reason_counts.get(reason_code, 0) + 1

    excluded = [record for record in eligibility_records if isinstance(record, dict) and not record.get("eligible", True)]

    return {
        "enabled": True,
        "symbols_checked": len(symbols_to_scan),
        "symbols_eligible": len(symbols_to_scan) - len(excluded),
        "symbols_excluded": len(excluded),
        "reason_counts": reason_counts,
    }


def _process_symbol(symbol, period, interval, audit_context=None, eligibility_config=None):
    clean_symbol = str(symbol).strip().upper()
    if not clean_symbol:
        return {
            "symbol": clean_symbol,
            "analysis": None,
            "error": None,
            "audit_context": None,
        }

    local_audit_context = _create_audit_context() if audit_context is not None else None

    try:
        try:
            analysis = analyze_ticker(
                clean_symbol,
                period,
                interval,
                audit_context=local_audit_context,
                eligibility_config=eligibility_config,
            )
        except TypeError:
            analysis = analyze_ticker(clean_symbol, period, interval, audit_context=local_audit_context)
        return {
            "symbol": clean_symbol,
            "analysis": analysis,
            "error": None,
            "audit_context": local_audit_context,
        }
    except Exception as exc:
        if local_audit_context is not None:
            from app.services.analyzer import _record_symbol_result

            existing_symbols = {str(record.get("symbol", "")).strip().upper() for record in local_audit_context.get("symbol_records", [])}
            if clean_symbol not in existing_symbols:
                _record_symbol_result(local_audit_context, clean_symbol, "failed", stage="market_data_fetch", reason="market_data_error")

        return {
            "symbol": clean_symbol,
            "analysis": None,
            "error": {"ticker": clean_symbol, "detail": str(exc)},
            "audit_context": local_audit_context,
        }


def _invoke_analyze_tickers(symbols, period, interval, audit_context=None, max_workers=None, eligibility_config=None):
    worker_count = _resolve_worker_count(max_workers)

    if worker_count <= 1:
        if audit_context is None:
            try:
                return analyze_tickers(symbols, period, interval, eligibility_config=eligibility_config)
            except TypeError:
                return analyze_tickers(symbols, period, interval)

        try:
            return analyze_tickers(symbols, period, interval, audit_context=audit_context, eligibility_config=eligibility_config)
        except TypeError:
            try:
                return analyze_tickers(symbols, period, interval, audit_context=audit_context)
            except TypeError:
                return analyze_tickers(symbols, period, interval)

    if not symbols:
        return {
            "period": period,
            "interval": interval,
            "count": 0,
            "results": [],
            "errors": [],
        }

    results = []
    errors = []
    eligibility_records = []

    try:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_symbol = {
                executor.submit(_process_symbol, symbol, period, interval, audit_context=audit_context, eligibility_config=eligibility_config): symbol
                for symbol in symbols
            }

            for future in as_completed(future_to_symbol):
                item = future.result()
                analysis = item.get("analysis")
                if analysis is not None:
                    if isinstance(analysis, dict) and isinstance(analysis.get("eligibility"), dict) and not analysis.get("eligibility", {}).get("eligible", True):
                        eligibility_records.append(analysis.get("eligibility"))
                    else:
                        results.append(analysis)
                if item.get("error") is not None:
                    errors.append(item["error"])
                if audit_context is not None:
                    _merge_audit_context(audit_context, item.get("audit_context"))
    except Exception as exc:
        LOGGER.warning("Concurrent execution unavailable; falling back to 1 worker: %s", exc)
        if audit_context is None:
            try:
                return analyze_tickers(symbols, period, interval, eligibility_config=eligibility_config)
            except TypeError:
                return analyze_tickers(symbols, period, interval)

        try:
            return analyze_tickers(symbols, period, interval, audit_context=audit_context, eligibility_config=eligibility_config)
        except TypeError:
            try:
                return analyze_tickers(symbols, period, interval, audit_context=audit_context)
            except TypeError:
                return analyze_tickers(symbols, period, interval)

    return {
        "period": period,
        "interval": interval,
        "count": len(results),
        "results": results,
        "errors": errors,
        "eligibility_records": eligibility_records,
    }


def _materialize_audit_symbol_records(symbol_records, symbols_to_scan, analyses, errors):
    seen_symbols = {
        str(record.get("symbol", "")).strip().upper()
        for record in symbol_records
        if str(record.get("symbol", "")).strip()
    }

    for analysis in analyses:
        symbol = str(analysis.get("ticker") or "").strip().upper()
        if not symbol or symbol in seen_symbols:
            continue

        symbol_records.append({
            "symbol": symbol,
            "status": "completed",
            "reason": None,
            "total_seconds": 0.0,
        })
        seen_symbols.add(symbol)

    for error in errors:
        symbol = str(error.get("ticker") or "").strip().upper()
        if not symbol or symbol in seen_symbols:
            continue

        symbol_records.append({
            "symbol": symbol,
            "status": "failed",
            "stage": "market_data_fetch",
            "reason": "market_data_error",
            "total_seconds": 0.0,
        })
        seen_symbols.add(symbol)

    for symbol in symbols_to_scan:
        symbol_key = str(symbol).strip().upper()
        if symbol_key and symbol_key not in seen_symbols:
            symbol_records.append({
                "symbol": symbol_key,
                "status": "skipped",
                "reason": "insufficient_history",
                "total_seconds": 0.0,
            })


def _summarize_audit(symbol_records, stage_timings, total_duration, universe_key, period, interval, symbols_to_scan, safe_max_symbols, limit, results, errors, eligibility_summary=None):
    completed = [record for record in symbol_records if record.get("status") == "completed"]
    failed = [record for record in symbol_records if record.get("status") == "failed"]
    skipped = [record for record in symbol_records if record.get("status") == "skipped"]

    durations = [record.get("total_seconds", 0.0) for record in symbol_records if isinstance(record.get("total_seconds"), (int, float))]

    def _stats(values):
        if not values:
            return {
                "average": 0.0,
                "median": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "maximum": 0.0,
            }

        ordered = sorted(values)
        count = len(ordered)
        average = sum(ordered) / count
        median = statistics.median(ordered)
        p90_index = max(0, min(count - 1, int(round(count * 0.9)) - 1))
        p95_index = max(0, min(count - 1, int(round(count * 0.95)) - 1))
        return {
            "average": round(average, 6),
            "median": round(median, 6),
            "p90": round(ordered[p90_index], 6),
            "p95": round(ordered[p95_index], 6),
            "maximum": round(ordered[-1], 6),
        }

    duration_stats = _stats(durations)
    failure_reasons = {}
    skip_reasons = {}

    for record in failed:
        reason = _normalize_reason(record.get("reason") or record.get("error_type") or record.get("stage") or "unexpected_exception")
        failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

    for record in skipped:
        reason = _normalize_reason(record.get("reason") or "skipped")
        skip_reasons[reason] = skip_reasons.get(reason, 0) + 1

    slowest_symbols = sorted(
        symbol_records,
        key=lambda record: float(record.get("total_seconds", 0.0) or 0.0),
        reverse=True,
    )[:10]

    slowest_fetches = sorted(
        [record for record in symbol_records if record.get("fetch_seconds") is not None],
        key=lambda record: float(record.get("fetch_seconds", 0.0) or 0.0),
        reverse=True,
    )[:10]

    slowest_analysis = sorted(
        [record for record in symbol_records if record.get("analysis_seconds") is not None],
        key=lambda record: float(record.get("analysis_seconds", 0.0) or 0.0),
        reverse=True,
    )[:10]

    audit = {
        "universe": universe_key,
        "timeframe": interval,
        "symbols_requested": len(symbols_to_scan),
        "symbols_completed": len(completed),
        "symbols_failed": len(failed),
        "symbols_skipped": len(skipped),
        "results_returned": len(results),
        "total_duration_seconds": round(total_duration, 6),
        "timing": {
            "universe_loading_seconds": round(stage_timings.get("universe_loading_seconds", 0.0), 6),
            "market_data_fetching_seconds": round(stage_timings.get("market_data_fetching_seconds", 0.0), 6),
            "indicator_calculation_seconds": round(stage_timings.get("indicator_calculation_seconds", 0.0), 6),
            "technical_scoring_seconds": round(stage_timings.get("technical_scoring_seconds", 0.0), 6),
            "trade_quality_scoring_seconds": round(stage_timings.get("trade_quality_scoring_seconds", 0.0), 6),
            "trade_setup_generation_seconds": round(stage_timings.get("trade_setup_generation_seconds", 0.0), 6),
            "filtering_seconds": round(stage_timings.get("filtering_seconds", 0.0), 6),
            "sorting_seconds": round(stage_timings.get("sorting_seconds", 0.0), 6),
            "serialization_seconds": round(stage_timings.get("serialization_seconds", 0.0), 6),
            "total_duration_seconds": round(total_duration, 6),
        },
        "symbols": symbol_records,
        "slowest_symbols": [
            {
                "symbol": record.get("symbol"),
                "total_seconds": round(float(record.get("total_seconds", 0.0) or 0.0), 6),
            }
            for record in slowest_symbols
        ],
        "slowest_market_data_fetches": [
            {
                "symbol": record.get("symbol"),
                "fetch_seconds": round(float(record.get("fetch_seconds", 0.0) or 0.0), 6),
            }
            for record in slowest_fetches
        ],
        "slowest_analysis_operations": [
            {
                "symbol": record.get("symbol"),
                "analysis_seconds": round(float(record.get("analysis_seconds", 0.0) or 0.0), 6),
            }
            for record in slowest_analysis
        ],
        "duration_stats": duration_stats,
        "failure_reasons": failure_reasons,
        "skip_reasons": skip_reasons,
        "total_market_data_requests": stage_timings.get("total_market_data_requests", 0),
        "unique_market_data_requests": stage_timings.get("unique_market_data_requests", 0),
        "duplicate_market_data_requests": stage_timings.get("duplicate_market_data_requests", 0),
        "execution_model": "thread_pool" if stage_timings.get("execution_model") == "thread_pool" else "sequential",
        "worker_count": int(stage_timings.get("worker_count", 1)),
        "maximum_in_flight_symbols": int(stage_timings.get("worker_count", 1)),
        "refresh_interaction": {
            "dashboard_refreshes_during_scan": False,
            "same_symbol_requests_during_scan": False,
            "scan_endpoint_overlap_possible": True,
            "scan_button_disabled_during_active_scan": False,
            "refresh_timer_initiates_scan": False,
            "concurrent_requests_possible": True,
        },
        "market_data_method": "yfinance.Ticker.history",
        "market_data_calls_per_symbol": 1,
        "audit_mode": True,
    }

    if eligibility_summary is not None:
        audit["eligibility"] = eligibility_summary

    return audit


def _log_audit_summary(audit):
    LOGGER.info(
        "[SCANNER_SUMMARY] universe=%s timeframe=%s execution_model=%s workers=%s requested=%s completed=%s failed=%s skipped=%s results=%s duration=%.6fs",
        audit.get("universe"),
        audit.get("timeframe"),
        audit.get("execution_model"),
        audit.get("worker_count"),
        audit.get("symbols_requested"),
        audit.get("symbols_completed"),
        audit.get("symbols_failed"),
        audit.get("symbols_skipped"),
        audit.get("results_returned"),
        audit.get("total_duration_seconds"),
    )

    for entry in audit.get("slowest_symbols", [])[:5]:
        LOGGER.info("[SCANNER_SYMBOL] symbol=%s total=%.6fs", entry.get("symbol"), entry.get("total_seconds", 0.0))


def scan_market(
    period: str = "1y",
    interval: str = "1d",
    limit: int = 10,
    universe: str = DEFAULT_UNIVERSE,
    max_symbols: int | None = None,
    audit: bool | None = None,
    max_workers: int | None = None,
    eligibility: dict | None = None,
):
    scan_start = perf_counter()
    stage_timings = {
        "universe_loading_seconds": 0.0,
        "market_data_fetching_seconds": 0.0,
        "indicator_calculation_seconds": 0.0,
        "technical_scoring_seconds": 0.0,
        "trade_quality_scoring_seconds": 0.0,
        "trade_setup_generation_seconds": 0.0,
        "filtering_seconds": 0.0,
        "sorting_seconds": 0.0,
        "serialization_seconds": 0.0,
        "total_market_data_requests": 0,
        "unique_market_data_requests": 0,
        "duplicate_market_data_requests": 0,
        "execution_model": "sequential",
        "worker_count": 1,
    }
    audit_context = None

    universe_start = perf_counter()
    universe_key, symbols = get_scan_universe(universe)
    stage_timings["universe_loading_seconds"] = perf_counter() - universe_start

    safe_max_symbols = get_safe_max_symbols(max_symbols, len(symbols))
    symbols_to_scan = symbols[:safe_max_symbols]

    worker_count = _resolve_worker_count(max_workers)
    stage_timings["worker_count"] = worker_count
    stage_timings["execution_model"] = "thread_pool" if worker_count > 1 else "sequential"

    eligibility_config = _resolve_eligibility_config(eligibility)

    audit_enabled = _is_audit_enabled(audit)
    if audit_enabled:
        audit_context = _create_audit_context()
        audit_context["stage_timings"] = stage_timings
    else:
        audit_context = None

    batch = _invoke_analyze_tickers(
        symbols_to_scan,
        period,
        interval,
        audit_context=audit_context,
        max_workers=worker_count,
        eligibility_config=eligibility_config,
    )
    errors = batch.get("errors", [])
    eligibility_records = batch.get("eligibility_records", [])

    for error in errors:
        print(f"Scanner failed for {error['ticker']}: {error['detail']}")

    results = _build_scan_results(batch.get("results", []), stage_timings=stage_timings)

    if audit_enabled:
        stage_timings.update(audit_context.get("stage_timings", {}))
        stage_timings["total_market_data_requests"] = audit_context.get("market_data_requests", 0)
        stage_timings["unique_market_data_requests"] = len(audit_context.get("market_data_request_keys", set()))
        stage_timings["duplicate_market_data_requests"] = audit_context.get("duplicate_market_data_requests", 0)
        stage_timings["execution_model"] = "thread_pool" if worker_count > 1 else "sequential"
        stage_timings["worker_count"] = worker_count

        symbol_records = audit_context.get("symbol_records", [])
        _materialize_audit_symbol_records(symbol_records, symbols_to_scan, batch.get("results", []), errors)

        audit_summary = _summarize_audit(
            symbol_records,
            stage_timings,
            perf_counter() - scan_start,
            universe_key,
            period,
            interval,
            symbols_to_scan,
            safe_max_symbols,
            limit,
            results,
            errors,
            eligibility_summary=_build_eligibility_summary(symbols_to_scan, eligibility_config, eligibility_records),
        )
        _log_audit_summary(audit_summary)
    else:
        audit_summary = None

    return _build_scan_response(
        period,
        interval,
        universe_key,
        symbols_to_scan,
        safe_max_symbols,
        limit,
        results,
        errors,
        audit_summary,
        stage_timings,
    )


def stream_scan_market(
    period: str = "1y",
    interval: str = "1d",
    limit: int = 10,
    universe: str = DEFAULT_UNIVERSE,
    max_symbols: int | None = None,
    audit: bool | None = None,
    max_workers: int | None = None,
    eligibility: dict | None = None,
):
    analyses = []
    errors = []
    universe_key, symbols = get_scan_universe(universe)
    safe_max_symbols = get_safe_max_symbols(max_symbols, len(symbols))
    symbols_to_scan = symbols[:safe_max_symbols]
    total = len(symbols_to_scan)
    audit_context = None
    audit_enabled = _is_audit_enabled(audit)
    worker_count = _resolve_worker_count(max_workers)
    eligibility_config = _resolve_eligibility_config(eligibility)

    if audit_enabled:
        audit_context = _create_audit_context()

    yield {
        "event": "start",
        "data": {
            "period": period,
            "interval": interval,
            "universe": universe_key,
            "scanned": 0,
            "total": total,
            "max_symbols": safe_max_symbols,
        },
    }

    if worker_count <= 1:
        for index, symbol in enumerate(symbols_to_scan, start=1):
            clean_symbol = str(symbol).strip().upper()

            if clean_symbol:
                try:
                    analyses.append(analyze_ticker(clean_symbol, period, interval, audit_context=audit_context))
                except Exception as e:
                    print(f"Scanner failed for {clean_symbol}: {e}")
                    errors.append({
                        "ticker": clean_symbol,
                        "detail": str(e),
                    })

            yield {
                "event": "progress",
                "data": {
                    "scanned": index,
                    "total": total,
                    "symbol": clean_symbol,
                    "failed": len(errors),
                },
            }
    else:
        try:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                future_to_symbol = {
                    executor.submit(_process_symbol, symbol, period, interval, audit_context=audit_context, eligibility_config=eligibility_config): symbol
                    for symbol in symbols_to_scan
                }

                for future in as_completed(future_to_symbol):
                    item = future.result()
                    if item.get("analysis") is not None:
                        analyses.append(item["analysis"])
                    if item.get("error") is not None:
                        errors.append(item["error"])
                    if audit_context is not None:
                        _merge_audit_context(audit_context, item.get("audit_context"))

                    yield {
                        "event": "progress",
                        "data": {
                            "scanned": len(analyses) + len(errors),
                            "total": total,
                            "symbol": item.get("symbol"),
                            "failed": len(errors),
                        },
                    }
        except Exception as exc:
            LOGGER.warning("Concurrent execution unavailable for streaming scan; falling back to 1 worker: %s", exc)
            for index, symbol in enumerate(symbols_to_scan, start=1):
                clean_symbol = str(symbol).strip().upper()
                if clean_symbol:
                    try:
                        analyses.append(analyze_ticker(clean_symbol, period, interval, audit_context=audit_context, eligibility_config=eligibility_config))
                    except Exception as e:
                        print(f"Scanner failed for {clean_symbol}: {e}")
                        errors.append({
                            "ticker": clean_symbol,
                            "detail": str(e),
                        })

                yield {
                    "event": "progress",
                    "data": {
                        "scanned": index,
                        "total": total,
                        "symbol": clean_symbol,
                        "failed": len(errors),
                    },
                }

    results = _build_scan_results(analyses, stage_timings=audit_context.get("stage_timings") if audit_context is not None else None)
    audit_summary = None

    if audit_enabled:
        stage_timings = audit_context.get("stage_timings", {})
        stage_timings["total_market_data_requests"] = audit_context.get("market_data_requests", 0)
        stage_timings["unique_market_data_requests"] = len(audit_context.get("market_data_request_keys", set()))
        stage_timings["duplicate_market_data_requests"] = audit_context.get("duplicate_market_data_requests", 0)
        audit_summary = _summarize_audit(
            audit_context.get("symbol_records", []),
            stage_timings,
            0.0,
            universe_key,
            period,
            interval,
            symbols_to_scan,
            safe_max_symbols,
            limit,
            results,
            errors,
        )
        _log_audit_summary(audit_summary)

    yield {
        "event": "complete",
        "data": _build_scan_response(
            period,
            interval,
            universe_key,
            symbols_to_scan,
            safe_max_symbols,
            limit,
            results,
            errors,
            audit_summary,
            audit_context.get("stage_timings") if audit_context is not None else None,
        ),
    }
