# Phase 6A.2D.2 — Industry Precision

**Status:** implemented with deliberately limited precise coverage  
**Taxonomy version:** `1`  
**Benchmark mapping version:** `1`  
**Frozen AI contract:** prompt `outlook-analyst-2.4`; schema `2.2`

## Architecture

Yahoo structured metadata remains the classification input. Exact observed Yahoo industry labels pass through a small, code-versioned normalization table. A supported normalized industry selects one reviewed ETF price benchmark. Unsupported or missing industry labels use the existing sector ETF, explicitly marked `sector_fallback`; missing sector support remains insufficient data.

TradePilot calculates benchmark health and company-relative performance from aligned completed sessions. They are separate evidence records, so a weak group with an outperforming company (or the inverse) remains mixed rather than being collapsed into one claim. No LLM calculates returns, states, or breadth.

SEC SIC was deferred. The audit treats it as optional, and adding an SEC classification transport and SIC mapping would materially expand this bounded phase. SIC remains a possible validation/fallback enhancement.

## Normalization and benchmarks

The normalization table contains 15 observed Yahoo labels. Ten normalized groups have precise price benchmarks:

| Normalized industry | Benchmark |
| --- | --- |
| semiconductors | SOXX |
| semiconductor_equipment | SOXX |
| software_infrastructure | IGV |
| software_application | IGV |
| banks_diversified | KBE |
| banks_regional | KRE |
| biotechnology | XBI |
| pharmaceuticals | IHE |
| aerospace_defense | ITA |
| integrated_oil_gas | XLE |

Consumer electronics, auto manufacturers, discount stores, internet content/information, and computer hardware are normalized but intentionally retain sector fallback because no narrow benchmark was sufficiently defensible for this phase. Classification quality is categorical: `exact_industry`, `sector_fallback`, or `unknown`. No numeric classification confidence is created.

## Returns and states

Returns use 21 and 63 completed trading sessions:

`relative_return = company_return - benchmark_return`

The result is a percentage-point difference. Company-relative deadbands are ±3 percentage points at 21 sessions and ±5 points at 63 sessions. Both horizons must agree outside the deadbands for `outperforming` or `underperforming`; stronger states require more than ±8 and ±12 points respectively. Both horizons inside their deadbands are `roughly_in_line`; other conflicts are `mixed`.

Benchmark health reuses the conservative existing unanimity rule: 21-session return outside ±1%, 63-session return outside ±3%, and position versus the 50-session average must agree. The result is `positive`, `negative`, or `mixed`. Health and relative strength never overwrite one another.

## Breadth

Breadth is optional and only attempted for supported industry ETFs. Up to ten weight-ranked holdings are considered, with the target excluded. At least five valid, aligned histories are required. The facts are positive 21-session-return share, share above the 50-session average, median 21-session return, configured count, valid count, and `positive`/`negative`/`mixed` breadth using the existing two-thirds rule.

Sector fallbacks do not reuse sector top holdings as purported industry peers. Missing holdings, failed peers, or fewer than five valid peers leave breadth unavailable without removing benchmark health or company-relative performance.

## Caching and failures

Classification remains cached for seven days, ETF holdings for one day, shared histories for 15 minutes, calculated results for 30 minutes, and failures for 60 seconds. A precise cold request is bounded to one metadata lookup, one holdings lookup, benchmark and target histories, and at most ten peer histories. Histories are shared across users/tickers.

An unavailable precise ETF history falls back once to the configured sector ETF and records `industry_benchmark_history_unavailable`. Target-history failure preserves group health. A failed sector benchmark leaves Industry insufficient without affecting other categories.

## Representative behavior

- NVDA resolves to `semiconductors`, SOXX, `industry_etf`; AAPL/MSFT are no longer injected as Technology-sector peers.
- TSLA normalizes to `auto_manufacturers` but explicitly uses XLY `sector_fallback`; Amazon, Home Depot, and McDonald's are not presented as auto peers.
- JPM, XOM, LLY, and BA resolve to KBE, XLE, IHE, and ITA respectively.
- AAPL, GOOGL, WMT, and SMCI retain explicit sector fallback.

These are deterministic mappings and test fixtures, not claims about a live provider response at a later date.

## Known limitations and deferred work

- Yahoo/yfinance taxonomy and data-rights limitations remain.
- ETF mandates and holdings-use rights need periodic operator review.
- Coverage is intentionally uneven; sector fallback is a valid outcome.
- Holdings breadth has no added security-master, liquidity, or market-cap filtering in this bounded version.
- Licensed GICS/reference data could improve stable identity, coverage, and maintenance, but is not required for the private beta.
- SEC SIC validation/fallback and broader calibrated taxonomy coverage are deferred.

No UI, prompt, schema, scoring policy, paid provider, OpenAI request path, or database migration was added.
