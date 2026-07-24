# Scanner Performance Audit

## Summary

The scanner bottleneck is dominated by market-data fetching, not by the technical-analysis or scoring stages. In the measured runs, roughly 83% to 88% of total scan time was spent waiting on yfinance history requests.

## What changed

A lightweight, opt-in audit mode was added to the scanner pipeline so scan behavior and returned results remain unchanged by default while exposing timing diagnostics. The scanner now also supports bounded thread-based concurrency at the whole-symbol boundary, which keeps the existing analysis and scoring pipeline intact while parallelizing the network-bound work.

Relevant implementation points:

- [backend/app/services/scanner.py](backend/app/services/scanner.py): adds scan-level timing, audit summary generation, structured logging, bounded thread-pool execution, and deterministic post-processing.
- [backend/app/services/analyzer.py](backend/app/services/analyzer.py): records per-symbol timing for fetch, indicator, scoring, and setup generation stages.
- [backend/app/services/market_data.py](backend/app/services/market_data.py): records market-data fetch timings and request counts.
- [backend/app/main.py](backend/app/main.py): passes the audit flag and worker-count configuration through the API layer.

## Measurement evidence

### Small sample run

Configuration:
- Universe: S&P 500
- Symbols requested: 10
- Limit: 10

Observed timings:
- Total duration: 5.635137s
- Market-data fetching: 4.908891s
- Indicator calculation: 0.030467s
- Technical scoring: 0.000437s
- Trade-quality scoring: 0.000518s
- Trade-setup generation: 0.000108s
- Filtering and sorting: negligible

Interpretation:
- Market-data fetch time accounted for about 87% of the total runtime.
- The rest of the pipeline was effectively negligible in this run.

### Broader sample run

Configuration:
- Universe: S&P 500
- Symbols requested: 20
- Limit: 10

Observed timings:
- Total duration: 11.830267s
- Market-data fetching: 10.442169s
- Indicator calculation: 0.062262s
- Results returned: 4

Interpretation:
- Market-data fetch time accounted for about 88% of the total runtime.
- The analysis and filtering logic remained a small fraction of the total cost.

### Nasdaq sample run

Configuration:
- Universe: Nasdaq
- Symbols requested: 20
- Limit: 10

Observed timings:
- Total duration: 9.961215s
- Market-data fetching: 8.278369s
- Indicator calculation: 0.053422s
- Results returned: 0

Interpretation:
- Market-data fetch time accounted for about 83% of the total runtime.
- The Nasdaq run also surfaced a separate reliability issue: one symbol failed due to a data/value edge case in the analysis path.

## Concurrency implementation

- Concurrency boundary: whole-symbol analysis with the existing per-symbol pipeline preserved.
- Executor type: Python standard-library ThreadPoolExecutor.
- Default worker count: 8.
- Maximum worker count: 16.
- Thread-safety approach: each worker receives isolated symbol inputs and returns structured results that are merged back into the parent scan context after completion.
- Result determinism approach: the final filtering and sorting stage remains the same, with a deterministic symbol tie-breaker applied after the concurrent run so output ordering is stable.

## Main conclusion

The dominant cost is the sequential per-symbol market-data fetches. The current implementation spends most of its time waiting on external history downloads, while the rest of the pipeline is comparatively cheap.

Bounded concurrency materially reduces wall-clock time without changing the underlying scoring or filtering logic.

## Benchmark results

Measured on a fixed 25-symbol S&P 500 sample with audit mode enabled and the analysis cache cleared:

| Workers | Duration | Speedup vs 1 worker | Completed | Failed | Results |
|---:|---:|---:|---:|---:|---:|
| 1 | 14.224938s | 1.00× | 25 | 0 | 3 |
| 4 | 3.737837s | 3.81× | 25 | 0 | 4 |
| 8 | 2.758802s | 5.16× | 25 | 0 | 4 |
| 12 | 2.947869s | 4.82× | 25 | 0 | 4 |
| 16 | 2.682705s | 5.30× | 25 | 0 | 4 |

Additional validation on a 10-symbol Nasdaq sample:

| Workers | Duration | Completed | Failed | Results |
|---:|---:|---:|---:|---:|
| 1 | 7.714043s | 9 | 1 | 0 |
| 8 | 1.410713s | 9 | 1 | 0 |

## Selected default

Eight workers was selected as the production default because it delivered a large wall-clock reduction while keeping the scan behavior stable and avoiding the diminishing returns and increased contention seen with 12 or 16 workers in the live measurements.

## Remaining bottlenecks

After introducing bounded concurrency, the remaining bottleneck is still external market-data latency. The next likely improvements would be request reuse or caching, but those were intentionally left out of this task.

## Optimization candidates

1. Parallelize market-data fetches
   - Fetch multiple symbols concurrently instead of one-by-one.
   - This should reduce wall-clock time significantly without changing scoring logic.

2. Add caching and request reuse
   - Reuse recent history for repeated symbols or overlapping periods.
   - Keep the current audit instrumentation so cache hits remain visible.

3. Reduce the number of network calls per symbol
   - Prefer a single history request where possible.
   - Avoid redundant intraday refresh fetches unless they are truly needed.

4. Improve resilience for bad market-data responses
   - Skip or report problematic symbols more gracefully so a single bad ticker does not stall or distort a scan run.

## Verification notes

The instrumentation was validated by:
- running the dedicated audit regression test,
- running the backend unit suite,
- executing real scan samples in audit mode.
