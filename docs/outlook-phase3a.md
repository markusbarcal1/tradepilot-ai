# Outlook Phase 3A — Structured Evidence Providers

Follow-on implementation: [Phase 3B free intelligence foundation](outlook-phase3b.md). The status and validation below describe Phase 3A's original delivery.

## Status

Real SEC, FRED and existing-market-data adapters are implemented. All three are individually configurable. **LIVE STRUCTURED EVIDENCE** means an enabled adapter returned usable observations; it does not mean all six categories are available. The production route no longer uses the Phase 2 placeholder by default.

At implementation verification, Market was enabled and successfully returned two supported events for AAPL, with a Mixed Market assessment and 1 of 6 categories available. SEC identification and FRED credentials were absent in the local environment, so those adapters reported `missing_configuration`; they were tested with mocked official response shapes, not certified live. No real environment file, credentials, deployment, database, auth behavior, scanner, existing scores, portfolio, or watchlist design was changed.

Earnings, Industry and Geopolitical remain **NOT YET CONNECTED**, with null classifications. Optional earnings was deferred: `financial_analysis/provider.py` reads financial statements and company info but does not already fetch calendar/earnings-date/estimate-revision feeds. Adding those would create extra Yahoo calls. Breadth is also deferred; existing index history is not constituent breadth data.

## Architecture and API

`configured_providers()` constructs one SEC, FRED and Market adapter per backend process. They return `list[OutlookEvidence]`, never category/overall labels. Every item passes through Phase 2 validation, ticker/provider/category isolation, deduplication, freshness, materiality and minimum-evidence gates. A live assessment uses completion time after fetching; explicit fixture times still support deterministic replay.

`GET /outlook/{ticker}` remains authenticated with the existing response model. Additions:

- Response metadata version `1.2` and `metadata.provider_status` (`available`, `no_evidence`, `error`, `disabled`, `missing_configuration`, or fixture-only `placeholder`). Provider `available` means observations were returned, not necessarily sufficient directional evidence.
- Computed `available_categories` counts supported category assessments, not enabled providers.
- Evidence `source_details` retains structured source-specific provenance.
- Evidence `scoring_eligible=false` retains ambiguous/routine events without allowing them to establish an artificial Mixed assessment.

Failures affect only a provider's declared category. A failing SEC source does not erase Economic/Market evidence or mark Industry as failed. If all configured sources fail, overall state is error; if all are disabled or unconfigured, the honest disconnected placeholder remains. If observations exist but fail support requirements, categories remain insufficient. Partial Outlook is valid.

The collapsed card shows “N of 6 Outlook categories available” for connected responses. Expanded factors link their evidence IDs to source attribution. No progress bar, numeric confidence display, or UI redesign was introduced.

## SEC

Official endpoints:

- `https://www.sec.gov/files/company_tickers.json`: cached ticker-to-CIK dictionary, uppercase matching with dot/dash share-class normalization.
- `https://data.sec.gov/submissions/CIK##########.json`: recent structured submission arrays.

See [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [developer/fair-access guidance](https://www.sec.gov/about/developer-resources), and [Form 8-K item definitions](https://www.sec.gov/files/form8-k.pdf).

The adapter consumes 8-K, 10-Q and 10-K only, up to 200 supported filings within 180 days. It does not fetch filing prose, HTML, archives, XBRL financial facts, every form, or 6-K. Missing CIK, unsupported foreign forms and empty recent histories return no evidence without failing other providers. Filings without recognized items remain provenance-only. Amendments are not interpreted as independent directional events in this phase.

| 8-K item | Existing event type | Impact / scoring |
| --- | --- | --- |
| 1.03 bankruptcy/receivership | restructuring | -2; eligible |
| 1.05 material cybersecurity incident | cybersecurity_event | -1; eligible |
| 5.02 officer/director changes | management_change | 0; provenance only |
| 2.01 acquisition/disposition | acquisition | 0; provenance only; no inferred acquisition benefit |
| 1.01 definitive agreement | corporate_other | 0; provenance only; no duplicate taxonomy introduced |
| 3.02 equity issuance | capital_raise | 0; provenance only |
| 2.05 exit/disposal costs | restructuring | 0; provenance only |
| Other items, routine 10-Q/10-K | corporate_other | 0; provenance only |

Each accession becomes one evidence item, avoiding multiple votes for the same filing. If several recognized items appear, the strongest mapped adverse event is selected and all item numbers retained. Event presence is not parsed for subtler circumstances; the negative rules are limited and provisional. Company Outlook may often remain insufficient because Phase 2 still requires two independent supported events. This is preferable to declaring a company neutral from routine filing activity.

Provenance includes SEC source, CIK, accession, form, filing date, report/event date when present, item numbers, document link, publication/acceptance time, fetched time and provider identity. Share-class aliases preserve the caller's normalized ticker in evidence. No CIK or foreign issuer coverage is fabricated.

Centralized event freshness overrides: cybersecurity half-life 30 days / maximum 120; restructuring 45/180; management changes 14/60 (provenance-only at present). Other Phase 2 rules still apply.

Requests require a real operator-identifying `OUTLOOK_SEC_USER_AGENT`, including contact email. Do not invent an identity. A single process-wide SEC rate gate spaces starts at least one second apart, including retries. 403 and 429 are not retried. SEC guidance limits access across machines, not per process: this implementation is intentionally process-local. **For multiple workers/replicas sharing an egress identity, increase the interval at least in proportion to worker count (for example, 4 seconds for 4 workers), or deploy a shared limiter before scaling.** Other SEC workloads must be included in that budget. No claim of a distributed rate limiter is made.

## FRED / Economic

Uses the official [series metadata API](https://fred.stlouisfed.org/docs/api/fred/series.html) and [series observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html). Set a server-side key obtained through the [FRED API key process](https://fred.stlouisfed.org/docs/api/api_key.html). The key is a Pydantic `SecretStr`, never returned to the frontend, source URLs, CLI output, or normal logs.

Each of five cached inputs requests metadata plus at most 20 recent observations. Raw macro snapshots are shared across tickers/users. The basket is centralized in `outlook_structured/policy.py`:

| Series | Purpose and comparison | Directional rule |
| --- | --- | --- |
| [FEDFUNDS](https://fred.stlouisfed.org/series/FEDFUNDS) | Monthly effective policy rate; latest vs 3 months earlier | Increase >=0.25 percentage points: -1; decrease <=-0.25: +1; otherwise 0 |
| [CPIAUCSL](https://fred.stlouisfed.org/series/CPIAUCSL) | CPI level converted to YoY inflation, compared with YoY inflation 3 months earlier (16 observations) | Acceleration >=0.2 pp: -1; deceleration <=-0.2: +1; otherwise 0 |
| [UNRATE](https://fred.stlouisfed.org/series/UNRATE) | Monthly unemployment; latest vs 3 months earlier | Rise >=0.2 pp: -1; fall <=-0.2: +1; otherwise 0 |
| [A191RL1Q225SBEA](https://fred.stlouisfed.org/series/A191RL1Q225SBEA) | Annualized real GDP growth; latest quarter vs prior quarter | Acceleration >=0.5 pp: +1; deceleration <=-0.5: -1; otherwise 0 |
| [GS10](https://fred.stlouisfed.org/series/GS10) | Monthly 10-year Treasury yield; latest vs 3 months earlier | Increase >=0.25 pp: -1; decrease <=-0.25: +1; otherwise 0 |

These are limited broad-equity change rules, not absolute-level judgments or economic forecasts. Rate declines can accompany recession; lower yields can have mixed consequences. Policy rates and Treasury yields are correlated. Calibration of this small basket and company sensitivities remains a later task; no source is assigned an extreme +/-2 impact. Confidence is 0.9 for structured arithmetic and materiality is a conservative 0.6 baseline for every ticker. No unsupported sector sensitivity precision is invented.

Only contiguous reporting periods are compared. Missing/nonfinite latest values, gaps, insufficient history, future observations, or stale series do not create evidence. Observation-period age limits are 75 days for monthly series and 180 for GDP. Release timestamps use FRED series `last_updated`, separately retaining observation dates. This is a latest-vintage publication proxy, not an ALFRED point-in-time backtest guarantee. Revisions and releases are not treated as newly independent events: IDs use series + observation date.

Provenance includes series ID/title, latest and comparison dates/values, transformed measures, exact observations used, method, publication-basis note, realtime date where supplied, source link and fetched time. Cached data does not get a new publication or fetched timestamp when another ticker is requested. A timeout halts further requests in that FRED batch, preserving earlier usable series and preventing a repeated timeout cascade.

## Market

The adapter calls the existing `market_data.get_price_history` and `indicators.calculate_sma`, without creating another Yahoo client or modifying Technical Score. Three shared inputs: `SPY`, `QQQ`, `^VIX`, six months of daily bars. There are at most three history calls per successful cold snapshot, then zero additional calls for other tickers during the cache TTL.

- SPY/QQQ: compare completed close against SMA50 and SMA50 five sessions earlier. Above a rising SMA50 is +1; below a falling SMA50 is -1; otherwise 0. The two benchmarks combine into **one** broad-market trend event: aligned +1/-1 or mixed 0. This avoids treating correlated index trends as two independent events.
- VIX: below 15 is low volatility (+1); 15 to below 25 normal (0); >=25 elevated (-1). This is a separate volatility event.
- Only completed regular US sessions are used (16:00 America/New_York). Current intraday bars are excluded. Early-close sessions are conservatively treated as completed at 16:00. Invalid/nonpositive closes or latest bars older than five calendar days are unavailable.
- Confidence 0.95 and materiality 0.8; a single available benchmark reduces trend confidence to 0.7 and the explanation states the missing benchmark. If only one eligible event remains, Phase 2's minimum evidence rule still applies.
- Broad-market/volatility freshness half-life 5 days, maximum 7; the provider's five-day stale-input guard is stricter on refresh. No breadth or ticker-specific technical score is used.

Source details retain each benchmark's close, SMA50, prior SMA50, direction and completed timestamp, and VIX close. Evidence links to public instrument pages; data continues through the existing market abstraction. These simple thresholds are provisional and are not a recommendation engine.

## Configuration and caches

All variables are backend-only and documented in `.env.example`. Defaults:

| Setting | Default |
| --- | --- |
| OUTLOOK_SEC_ENABLED / OUTLOOK_FRED_ENABLED / OUTLOOK_MARKET_ENABLED | true / true / true |
| OUTLOOK_SEC_USER_AGENT | empty; SEC stays unconfigured until supplied |
| FRED_API_KEY | empty; FRED stays unconfigured until supplied |
| OUTLOOK_CIK_CACHE_TTL | 86400 seconds |
| OUTLOOK_SEC_CACHE_TTL | 3600 seconds |
| OUTLOOK_ECONOMIC_CACHE_TTL | 21600 seconds |
| OUTLOOK_MARKET_CACHE_TTL | 900 seconds |
| OUTLOOK_FAILURE_CACHE_TTL | 60 seconds |
| OUTLOOK_HTTP_TIMEOUT | 5 seconds |
| OUTLOOK_HTTP_ATTEMPTS | 1; configurable up to 2 |
| OUTLOOK_SEC_REQUEST_INTERVAL | 1 second minimum |

In-process bounded caches retain up to 256 keys per provider, use locks for single-flight loading, return isolated copies, and negatively cache failures. SEC caches mapping and issuer metadata; FRED caches each series payload; Market caches the shared snapshot. Empty/partial successful snapshots remain cached for their normal TTL. Expired successful entries are not silently served after a failed refresh. Each worker/replica has independent caches; restarts clear them. There is no production evidence database or migration.

The SEC/FRED JSON client limits response size to 8 MiB and uses explicit timeouts. Attempts are bounded; 4xx, including throttling, are not retried. Optional retry is limited to server/transient failures. FRED requests are spaced by a shared half-second gate. Normal logs include provider/error type/status, not credentials, full request URLs or provider payloads. Market retains the existing history service's ten-second request timeout and failure classification. Provider execution is sequential; slow cold sources can delay the response within those bounds but do not erase other providers' evidence. Shared caches and failure backoff limit repeated load.

To configure, set backend environment variables through the normal operator process and restart the backend so cached provider instances use them. Nothing was written to the real `.env`. Disabling a provider produces a truthful unavailable category; disabling all three restores disconnected behavior. Do not place FRED keys in Vite variables.

## Inspection and validation

From `backend`:

```powershell
& .\venv\Scripts\python.exe -m app.cli.inspect_outlook AAPL
& .\venv\Scripts\python.exe -m app.cli.inspect_outlook AAPL --json
```

The command is read-only for application data; it performs configured provider reads and fills process-local caches. JSON includes normalized evidence, never the FRED key. It does not start the web app or touch the trading database.

Automated tests use mocked official response shapes and fixture history, not external network. Coverage includes ticker/CIK normalization, SEC items and provenance-only forms, deduplication, missing identity/configuration, cache expiry/single-flight/backoff, timeouts, retry limits, FRED changes/period gaps/staleness, Market regimes and completed sessions, partial category counts, failure isolation, authenticated HTTP serialization, and source rendering. Final full backend run: **330 passed, 46 skipped, 148 subtests passed**. PostgreSQL-dependent tests were skipped without a disposable target. Tests used in-memory/isolated databases. **Frontend tests, lint, production build and git diff checks passed.**

Manual live check: the sandbox blocked Yahoo connections; the authorized read-only network check then succeeded, returning Market Mixed with 2 supported events and 1/6 categories. SEC and FRED remained `missing_configuration`; no live certification is claimed for either. No browser interaction/visual certification was performed. Existing FastAPI startup deprecation and frontend bundle-size warnings remain.

## Files changed

- `.env.example`, `backend/app/config.py`
- `backend/app/models/outlook.py`, `backend/app/models/outlook_evidence.py`
- `backend/app/services/outlook.py`, `outlook_evidence.py`, `outlook_policy.py`
- New `backend/app/services/outlook_structured/`: `__init__.py`, `transport.py`, `policy.py`, `sec.py`, `fred.py`, `market.py`
- New `backend/app/cli/inspect_outlook.py`
- `backend/tests/test_outlook.py`, `test_outlook_evidence.py`, new `test_outlook_structured.py`
- `frontend/src/components/OutlookPanel.jsx`, `frontend/tests/outlook.mjs`
- This report and the Phase 2 documentation link

## Remaining decisions

Supply and verify SEC identity/FRED credentials; calibrate impact/materiality/decay against real cases; review macro correlations and company sensitivities; decide release-vintage/revision semantics, amendment/event supersession, distributed request budgets and cache topology; validate foreign-issuer coverage and market symbol access. Earnings, Industry, Geopolitical, breadth, news and LLM interpretation remain separate future work. Phase 3B has not started.
