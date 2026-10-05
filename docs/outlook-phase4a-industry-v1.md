# Outlook Phase 4A: Industry intelligence V1

Industry now supplies deterministic market-derived sector context through the existing evidence pipeline. No final Outlook labels originate in the provider. No other category/scoring calibration, production environment file, database, authentication, or UI design changed. No paid/model dependencies were added.

## Definition and boundary

Industry measures the sector environment around a company: absolute sector trend, performance relative to SPY, and breadth among a bounded sector peer sample. Market retains SPY/QQQ trend and VIX regime. A SPY return alone is never Industry evidence. This is market-derived sector context, not a claim about industry fundamentals, news sentiment, demand, or the company's own performance.

## Classification and benchmarks

Existing financial/valuation adapters already use `yfinance.Ticker.info` for sector and industry, but also fetch statements. Industry reads only structured `get_info()` metadata and caches it independently to avoid fetching statements or changing those adapters. The scanner universe contains symbols without sector membership; classifying it on demand would require scanner-scale requests. No production ticker-to-sector reference table is used.

V1 supports Yahoo `EQUITY` instruments on NMS, NYQ, NGM, NCM, ASE, BTS exchanges. Sector and industry text are retained as supplied. Missing industry does not prevent sector context; unsupported instruments/sectors produce no invented benchmark. Country is retained for diagnostics; U.S.-listed foreign issuers can receive a U.S. sector proxy, which may be a weaker economic match.

The mapping uses the eleven [State Street Select Sector ETFs](https://www.ssga.com/us/en/individual/capabilities/equities/sector-investing/select-sector-etfs), each representing its corresponding S&P 500 sector. These are broad U.S. large-cap proxies, not exact narrow-industry indexes.

| Yahoo sector | Benchmark | Proxy rationale |
|---|---|---|
| Technology | XLK | S&P 500 technology |
| Financial Services | XLF | S&P 500 financials |
| Energy | XLE | S&P 500 energy |
| Healthcare | XLV | S&P 500 health care |
| Industrials | XLI | S&P 500 industrials |
| Consumer Cyclical | XLY | S&P 500 consumer discretionary |
| Consumer Defensive | XLP | S&P 500 consumer staples |
| Utilities | XLU | S&P 500 utilities |
| Basic Materials | XLB | S&P 500 materials |
| Real Estate | XLRE | S&P 500 real estate |
| Communication Services | XLC | S&P 500 communication services |

## Exact calculations and event semantics

Use the existing `get_price_history(symbol, "6mo", "1d")` path and its Yahoo-adjusted closes. Only completed U.S. sessions are eligible, using the existing Market helper (16:00 America/New_York; conservative on early-close days). Require 64 valid positive finite observations, no duplicate dates, latest history within the existing Market stale limit (5 days), and at most 105 calendar days spanning the final 64 bars. SPY and peers must cover every sector assessment date. No mismatched endpoints or synthetic price filling.

* Returns: `close[-1] / close[-22] - 1` and `close[-1] / close[-64] - 1`, approximately one and three months (21/63 sessions).
* Trend: positive only when 21-session return exceeds +1%, 63-session return exceeds +3%, and last close exceeds SMA50. Negative uses strictly symmetric -1%/-3% and below SMA50. Otherwise mixed.
* Relative strength: sector return minus SPY return for identical dates. Positive requires greater than +1 percentage point at 21 sessions and +2 points at 63; negative requires less than -1/-2 points. Otherwise mixed.
* Combined sector performance impact: +1 only if trend and relative strength are both positive; -1 only if both negative; otherwise 0. Opposing or inconsistent horizons do not generate extra votes.

Added event types are `sector_performance` and `industry_peer_breadth`. Existing `structural_trend` was not reused for short-term price behavior. Four sector measurements are stored in one performance record; two breadth measurements in one breadth record. Each becomes one ordinary event/factor through existing aggregation, with all measurement dimensions in provenance and the human-readable summary. No changes to earnings-release factor identities or Phase 3C evaluation semantics. Duplicate copies retain two events, not additional votes.

## Peer methodology

Use [yfinance structured ETF top holdings](https://ranaroussi.github.io/yfinance/reference/yfinance.ticker_tickers.html) (`funds_data.top_holdings`), not scraping. Sort by reported holding weight descending, symbol ascending for ties, retain up to ten valid unique symbols, exclude target/benchmark/SPY, then choose at most six. Fetch sequentially through the shared history cache. No per-peer company metadata lookup, replacement fan-out, or recursive requests.

At least four peers with matching 64-session histories are required. Compute equal-weight percentages with positive 21-session returns and above SMA50. Positive impact requires both proportions >= 2/3. Negative requires both negative-return and below-SMA50 proportions >= 2/3. Exact zero returns and ties to SMA50 are neither positive nor negative. Other distributions have impact 0. This ensures sign symmetry including ties.

The target never contributes to breadth. Peers are explicitly described as a sector ETF top-holdings sample, not a complete narrow industry. For example, TSLA's V1 sample contains consumer discretionary businesses rather than only auto manufacturers. ETF absolute performance can still include the target as a constituent. ETF and breadth are related views of one sector, not statistically independent experiments; they are two distinct event families under the unchanged existing support gate.

## Impact, reliability, materiality, freshness

Only -1/0/+1 are emitted; V1 does not claim extreme +/-2 evidence. Fixed thresholds are intentionally simple deadbands, not fitted to live labels.

Performance confidence is 0.90 with both complete aligned histories. Breadth confidence is 0.85 when all selected peers are usable and 0.65 for partial coverage of at least four; fewer than four produces no breadth event. Confidence never varies with return magnitude.

Materiality is 0.80 for sustained directional conditions, 0.50 for mixed/limited directional conditions. Mixed observations are genuine measured evidence with lower directional materiality, not fabricated neutral placeholders. Existing freshness/confidence/materiality and minimum-two-event/minimum-0.75-support gates still decide availability. A one-sided or old/weak observation can remain insufficient. Overall weights/thresholds are unchanged.

Both new events have a five-day half-life, seven-day maximum age, and explicit expiration seven days after the completed sector session. Re-fetching cannot refresh an old event's publication date. Weekends still decay. No Earnings freshness changes.

## Caches, configuration, and load

All caches use the existing process-local bounded `Cache`: single-flight locking, deep copies, failure backoff, LRU eviction. Industry calculation locking bounds concurrent Industry requests to one loader per process; histories load sequentially. Multiple backend processes have separate caches.

| Cache/config | Default | Scope |
|---|---:|---|
| `OUTLOOK_INDUSTRY_ENABLED` | true | Provider enablement |
| `OUTLOOK_CLASSIFICATION_CACHE_TTL` | 604800 seconds (7 days) | Per ticker metadata, 256 entries |
| ETF holdings | 86400 seconds (1 day) | Per benchmark, 16 entries |
| `OUTLOOK_INDUSTRY_CACHE_TTL` | 1800 seconds (30 minutes) | Per target calculated evidence/diagnostics, 256 entries |
| `OUTLOOK_MARKET_CACHE_TTL` | existing 900 seconds | Shared raw history, symbol/period/interval, 128 entries |
| `OUTLOOK_FAILURE_CACHE_TTL` | existing 60 seconds | Failed loader backoff |

The new Outlook-only history adapter wraps the existing service and is injected into both configured Market and Industry providers. It does not change Market calculation rules or chart/scanner request paths. SPY is reused safely and returned frames are copies. Classification remains cached after calculation expiry. Partial results are retained for the calculation TTL; missing subcomponents retry on the next calculation refresh, while complete loader failures retry after failure TTL. This favors bounded load over rapid recovery of partial coverage.

Cold Industry request bound: one metadata loader + one holdings loader + eight histories (sector, SPY, six peers). If Market has loaded SPY, Industry adds at most seven histories. Warm Industry request: zero source loader calls. A same-sector target generally needs its own metadata and at most the changed excluded peer history. Counts refer to service/yfinance calls, not HTTP packets: yfinance may internally issue multiple HTTP requests for metadata or session setup. Histories retain the existing ten-second timeout; metadata/holdings use library timeouts. No global yfinance settings are changed.

## Failure handling and diagnostics

Missing classification or transport failure is cached and isolated by existing provider orchestration (`error`, null label). Unsupported sector/instrument produces `no_evidence` / `insufficient_data`. Insufficient sector history fails closed. Missing SPY preserves breadth only; missing/insufficient peers preserves performance only; neither alone meets the unchanged two-event gate. Partial coverage lowers confidence. A failure does not become negative evidence and cannot suppress unrelated categories or cache keys.

Evidence retains raw sector/industry, classification source, benchmark/SPY, 21/63-session windows and endpoints, observation/publication times, constituent sample/coverage, and raw measured values. Source links navigate to the actual Yahoo benchmark quote pages.

`python -m app.cli.inspect_outlook TICKER` now prints Industry diagnostics, classification, benchmark comparison, peer coverage/sample, evidence summaries, supported event count, label, and existing availability gates. `--json` adds `industry_diagnostics` alongside normalized evidence. The diagnostic read reuses the calculation cache. A live XOM CLI check confirmed Positive Industry, 6/6 peers, two supported events, and 3/6 categories available. Offline replay remains network-free and has no live Industry diagnostic lookup.

## UI behavior

No component or CSS changes. Existing Industry label, summary, factors, sources and available-category count populate automatically. Native collapsed details behavior is preserved. Frontend rendering fixtures verify the populated Industry card, expanded content markup, links, and category count; backend authenticated HTTP fixture verifies the serialized card contract. This is automated rendered-markup/API verification, not an interactive authenticated browser certification.

## Live validation, 2026-09-18

Read-only configured-provider validation completed around 16:21 UTC using completed 2026-09-17 sessions. Initial sandbox execution could not access network/Yahoo cache; the authorized execution with network access succeeded. The [complete machine-readable capture](outlook-phase4a-live-validation.json) includes exact measurements, source provenance, factors, status, summary, and timings.

All five: Industry available with two qualifying events, peer coverage 6/6, categories **2 -> 3**, and zero cached Industry data calls. The before count excludes Industry from the same snapshot; it is not a separate earlier-time market observation.

| Ticker | Sector / industry | ETF | Label | Sector 21 / 63 return | Relative to SPY, pp | Positive-return / above-SMA50 breadth |
|---|---|---|---|---|---|---|
| AAPL | Technology / Consumer Electronics | XLK | Mixed | +1.3% / +1.3% | +1.9 / -1.8 | 67% / 83% |
| NVDA | Technology / Semiconductors | XLK | Mixed | +1.3% / +1.3% | +1.9 / -1.8 | 83% / 83% |
| TSLA | Consumer Cyclical / Auto Manufacturers | XLY | Negative | -4.3% / -3.4% | -3.6 / -6.5 | 0% / 0% |
| JPM | Financial Services / Banks - Diversified | XLF | Mixed | -3.4% / +3.7% | -2.8 / +0.6 | 33% / 50% |
| XOM | Energy / Oil & Gas Integrated | XLE | Positive | +1.3% / +18.8% | +1.9 / +15.6 | 83% / 100% |

Samples:

* AAPL: NVDA, MSFT, AVGO, MU, AMD, INTC.
* NVDA: AAPL, MSFT, AVGO, MU, AMD, INTC.
* TSLA: AMZN, HD, MCD, BKNG, TJX, SBUX.
* JPM: BRK-B, V, MA, BAC, GS, WFC.
* XOM: CVX, COP, MPC, PSX, VLO, SLB.

AAPL/NVDA show mixed sector horizons and broad peer strength. TSLA shows weakening/underperforming sector and broad weakness. JPM shows mixed sector and breadth. XOM shows strengthening/outperforming sector and broad strength. Labels follow the existing weighted aggregation, not subjective expectations. Existing category summaries report two supporting events; human-readable sector explanations appear in the supporting factors.

Full Outlook cold/mixed-cache request times were 16.15s, 4.94s, 5.76s, 5.45s, 3.63s respectively (include SEC/FRED/Market). History loader calls across that sequence were 10, 1, 7, 7, 7; the first includes Market's SPY/QQQ/VIX. Each used one classification lookup; holdings calls were 1, 0, 1, 1, 1. Cached Industry assessment took approximately 0.34-0.61ms and zero data calls. These are local observations, not hosting performance guarantees.

## Validation and files

Offline tests cover positive/negative/flat sector conditions, mixed/opposed horizons, strong/weak/mixed peers, target exclusion, partial/no peers, missing classification/benchmark, provider failure/backoff, insufficient/stale history, correlated duplicates, history sharing, cache expiry/deep copies, concurrent single-flight, and authenticated HTTP contract. No automated test requires live providers.

Validation results: 18 new Industry tests passed; full backend 606 passed, 46 skipped, 148 subtests; original/reporting evaluation corpora 40 cases, 65 replays, 535 checks passed, zero failures. Frontend tests, lint, build passed. Existing FastAPI lifespan deprecation and large-bundle build warnings remain. Whitespace review passed.

Changed files:

* `backend/app/services/outlook_structured/industry.py`: provider, mapping, metrics, bounded peers, caches.
* `backend/app/services/outlook_structured/history.py`: shared Outlook history cache.
* `backend/app/services/outlook_structured/__init__.py`: production registration/injection.
* `backend/app/config.py`: three Industry settings.
* `backend/app/models/outlook_taxonomy.py`: two event types.
* `backend/app/services/outlook_policy.py`: freshness for those events only.
* `backend/app/cli/inspect_outlook.py`: operator diagnostics.
* `backend/tests/test_outlook_industry.py`: offline coverage.
* `frontend/tests/outlook.mjs`: populated Industry rendering contract.
* This document and `docs/outlook-phase4a-live-validation.json`: methodology/results.

## Limitations and future work

This is a concentrated large-cap sector sample, not a representative whole-industry survey. Holdings metadata may lag and has no asserted effective date; observation time is retrieval time. No archival point-in-time classification/membership guarantee is made. Free Yahoo availability/rate limits remain external risks, and a cold request can take seconds. Process-local caches are not shared with financial/valuation metadata adapters or across workers. Small-cap/niche/foreign businesses can differ considerably from their U.S. sector proxy. The two event families remain economically correlated; no statistical independence claim is intended.

V2 opportunities: a reliable structured industry-membership source with bounded sampling; narrower industry benchmarks where defensible; concentration/coverage diagnostics; optional shared persistent caching if deployment scale warrants it; explicit point-in-time constituent data for historical replay. Broader news/regulatory/commodity intelligence needs separately scoped work.
