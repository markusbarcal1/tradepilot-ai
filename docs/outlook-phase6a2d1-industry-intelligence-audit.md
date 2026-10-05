# Phase 6A.2D.1 — Industry Intelligence Architecture & Data Audit

**Audit date:** 2026-09-21

**Scope:** architecture/data-quality audit and Phase 6A.2D.2 design only

**Runtime changes:** none

**Frozen contracts:** prompt `outlook-analyst-2.4`; schema `2.2`

## 1. Executive summary

TradePilot's current Industry provider is accurately described as **sector context**, not precise industry intelligence. Yahoo structured metadata supplies both `sector` and `industry`, but only `sector` affects computation. Eleven Yahoo sector names map to Select Sector ETFs. The provider measures the sector ETF's 21/63-session returns, its relative performance against SPY, and breadth among six of that sector ETF's largest holdings. It never calculates the target company's return or company-versus-industry relative return.

A bounded live audit on 2026-09-21 demonstrates the mismatch. NVDA's Yahoo industry is `Semiconductors`, but its benchmark is XLK and its sampled “peers” include AAPL and MSFT. TSLA's industry is `Auto Manufacturers`, but its XLY sample includes Amazon, Home Depot, McDonald's, Booking, TJX, and Starbucks. BA and RKLB are `Aerospace & Defense`, yet their XLI sample includes Caterpillar, GE Vernova, Union Pacific, and Deere. The current summaries correctly call these sector samples; the category name is simply more precise than the underlying data.

Useful Industry Precision can be implemented with current/free sources **with limited coverage and explicit fallbacks**. The smallest defensible approach is:

1. normalize a controlled subset of observed Yahoo industry strings;
2. optionally validate/fallback with SEC SIC;
3. map only well-understood normalized industries to a small, versioned industry-ETF benchmark catalog;
4. use the ETF's market price, separately from any holdings license, for industry trend;
5. calculate target-company versus benchmark returns over 20 and 60 completed sessions;
6. use at most 6–10 constituents from an approved narrow-industry ETF holdings source for breadth, or mark breadth unavailable;
7. fall back explicitly to the existing sector ETF rather than pretending sector context is industry context;
8. preserve categorical provenance (`normalized_industry`, `sic_fallback`, `sector_fallback`, `unknown`).

SEC SIC is free, authoritative filer metadata and useful as a cross-check or fallback. It is too old/coarse for many modern investment groups and should not be the primary taxonomy. NAICS is a better modern statistical taxonomy, but TradePilot does not currently receive issuer NAICS assignments. GICS is designed for investment comparison but is proprietary and requires a license.

Paid reference data is **not required for a meaningful Phase 6A.2D.2**, but free/Yahoo coverage and licensing remain limitations. The phase should proceed as **LIMITED**: improve supported groups, retain sector fallback, never manufacture a narrow peer set, and do not build a giant security master.

## 2. Current Industry architecture

```text
yfinance Ticker.get_info()
  -> sector + industry + instrument metadata
  -> sector-only BENCHMARKS lookup
  -> sector ETF price history + SPY history
  -> absolute sector trend + sector-vs-SPY relative strength

yfinance sector ETF funds_data.top_holdings
  -> weight-ranked symbols
  -> exclude target / ETF / SPY
  -> first six usable peers
  -> positive-return and above-SMA50 breadth

two OutlookEvidence records
  -> sector_performance
  -> industry_peer_breadth (name is historical; summary says sector sample)
  -> ordinary Industry aggregation and existing fact/context pipeline
```

`IndustryEvidenceProvider.inspect()` owns the calculation. `OutlookHistory` reuses `get_price_history(symbol, "6mo", "1d")` through a shared single-flight cache. `completed_history()` admits only completed U.S. sessions. Provider orchestration isolates exceptions, and missing evidence remains insufficient rather than negative.

The provider emits at most two evidence events so correlated 21/63-session values do not become four votes. The normal category gate still requires two qualifying events, so benchmark-only or breadth-only data usually leaves Industry insufficient.

The AI context receives existing grounded Industry evidence/factors. Phase 6A documentation already states that company-versus-sector and company-versus-peer returns are not consistently available as first-class facts, so the model must not claim them.

## 3. Current data sources

| Source | Fields/use | Runtime and cache | Fallback/failure | Concern |
| --- | --- | --- | --- | --- |
| Yahoo via yfinance `get_info()` | sector, industry, quote type, exchange, country, name, business summary | One lookup per ticker; classification cache 7 days; failure backoff 60s | Missing sector fails classification; unsupported sector/instrument returns no evidence | Unofficial Yahoo interface; string taxonomy has no stable documented IDs/version contract; private-beta usage rights remain an obvious dependency. |
| Yahoo via `funds_data.top_holdings` | sector ETF top constituents and weights | One lookup per unique ETF; holdings cache 1 day; capacity 16 | Failure removes breadth but can preserve performance | Holdings are issuer/proprietary fund composition data. Access through yfinance does not itself prove redistribution/storage rights. |
| Existing `get_price_history` / Yahoo-adjusted closes | target-independent ETF, SPY, and peer history | Shared 15-minute cache, capacity 128; 10-second underlying timeout | Missing benchmark history fails closed; missing SPY preserves breadth; partial peers allowed at lower confidence | Normal market-price dependency; current Yahoo operational/licensing posture remains relevant. |
| Static `BENCHMARKS` | 11 Yahoo sector string → ETF symbols | Code/version controlled | Unsupported string fails closed | Stable and testable, but intentionally sector-level. |
| SEC | Currently not used by Industry | Existing bounded SEC infrastructure elsewhere | n/a | SIC can be reused later without a new paid source. |

Current configuration defaults:

- Industry enabled;
- calculated-result cache: 1,800 seconds;
- classification cache: 604,800 seconds;
- holdings cache: 86,400 seconds;
- history cache: 900 seconds;
- failure backoff: 60 seconds.

A cold request performs one classification lookup, one holdings lookup, and at most eight history loads (sector ETF, SPY, six peers). If Market already loaded SPY, that history is shared. A warm calculation performs no source calls.

## 4. Current taxonomy

The only company taxonomy is Yahoo's unversioned display strings:

- `sector`, used to select a benchmark;
- `industry`, retained in diagnostics/provenance but ignored computationally.

There is no GICS, ICB, NAICS, SIC, stable industry identifier, TradePilot normalization ID, or taxonomy version in the Industry provider. Names may change or split without a controlled migration. Semantically adjacent labels can be distinct (`Semiconductors`, `Semiconductor Equipment & Materials`, `Computer Hardware`, `Electronic Components`), while broad labels can combine companies with dissimilar economics.

The current sector map is explicit and conservative:

`Technology→XLK`, `Financial Services→XLF`, `Energy→XLE`, `Healthcare→XLV`, `Industrials→XLI`, `Consumer Cyclical→XLY`, `Consumer Defensive→XLP`, `Utilities→XLU`, `Basic Materials→XLB`, `Real Estate→XLRE`, and `Communication Services→XLC`.

No arbitrary ticker-to-sector map exists.

## 5. Taxonomy alternatives

| Option | Coverage/precision | Cost/rights | Mapping burden | Recommendation |
| --- | --- | --- | --- | --- |
| Existing Yahoo industry | Broad US equity coverage; useful investment-oriented labels but string-only and undocumented stability | Already operational, but unofficial Yahoo/data-rights limitations remain | Small normalization layer needed | Primary input for limited implementation, never sole unquestioned authority. |
| SEC SIC | Strong SEC filer coverage; stable numeric code and official label; often coarse/legacy | Free public EDGAR data under SEC access rules | Moderate SIC→TradePilot family mapping | Validation and fallback, not primary peer taxonomy. |
| NAICS | Modern, detailed establishment-based statistical taxonomy | Standard/reference files are public | TradePilot lacks reliable issuer→NAICS assignments; multi-establishment issuers complicate mapping | Do not add unless a reliable assignment source appears. |
| GICS | Excellent investment hierarchy and maintenance | Proprietary to MSCI/S&P; use/access requires a license | Low if licensed data includes codes, otherwise impermissible reconstruction risk | Best paid/reference option, not needed for limited phase. |
| ETF provider classification | Directly aligned to benchmark product | Classification/holdings terms are provider-specific | Mapping product names/index methodologies | Use ETF price as benchmark; treat holdings rights separately. |
| SEC filing/business-description inference | Potentially nuanced | SEC text is public | High ambiguity; would require rules/LLM and frequent reassessment | Do not infer taxonomy from prose in this phase. |
| Small TradePilot normalization | Controlled, explainable coverage; explicit unknowns | No extra data fee, but source rights still apply | Manageable at roughly 15–30 initial normalized families | Recommended overlay, not a universal taxonomy. |

Do not casually merge semiconductors and semiconductor equipment. They may share an umbrella benchmark in a fallback tier, but the normalized identity should preserve the narrower source label and record the broader benchmark granularity.

## 6. SEC SIC assessment

The SEC publishes a SIC code list and says SIC codes in disseminated EDGAR filings indicate a company's type of business. Company/filing metadata exposes SIC, and SEC submissions APIs are public, keyless, updated throughout the day, and already compatible with TradePilot's SEC transport practices.

Strengths:

- stable numeric identity and official description;
- broad domestic public-filer coverage;
- free, cacheable, provenance-friendly;
- useful negative control when Yahoo classification is clearly inconsistent;
- can place missing-Yahoo issuers into a coarse family.

Limitations:

- SIC was superseded by NAICS for federal statistical purposes and has weak modern technology granularity;
- the issuer's assigned code can reflect its principal reported business but not diversified segment economics;
- foreign private issuers, shell/SPAC structures, funds, and recent business transitions need care;
- exact SIC does not ensure comparable scale, business model, or investment behavior;
- SEC updates do not constitute a point-in-time investment taxonomy service.

Recommendation: `sic_fallback` or `sic_validated`, never “exact industry” solely because two issuers share a SIC code. Do not use SIC alone to generate a large peer universe in Phase 6A.2D.2.

## 7. Current benchmark behavior

The benchmark is always the sector ETF selected from `BENCHMARKS`; SPY is the comparison baseline. Industry metadata has no effect.

For the ETF and aligned SPY history:

- 21-session ETF return, deadband ±1%;
- 63-session ETF return, deadband ±3%;
- ETF above/below its 50-session mean;
- 21-session ETF-minus-SPY return, deadband ±1 percentage point;
- 63-session ETF-minus-SPY return, deadband ±2 percentage points.

Absolute trend is directional only when all three trend votes agree. Relative strength is directional only when both horizons agree. `sector_performance` impact is directional only when absolute trend and relative strength agree. Conflicts remain Mixed.

This is conservative and reusable, but it answers “how is the sector doing versus the market?” rather than “how is the company's business group doing?”

## 8. Benchmark design options

Recommended hierarchy:

1. **Controlled industry ETF price** when the normalized group and ETF mandate are a defensible match.
2. **Validated narrow peer basket benchmark** only when at least five eligible peers can be constructed without target inclusion and with adequate history.
3. **Existing sector ETF**, explicitly labeled `sector_fallback`.
4. **Insufficient data** if classification or sector benchmark is unavailable.

Do not use SPY as an “industry benchmark.” SPY remains the broad-market comparator used to understand whether an industry benchmark is strengthening relative to the market.

Example candidate catalog for design validation, not an implemented mapping:

| Normalized group | Candidate price benchmark | Caveat/fallback |
| --- | --- | --- |
| semiconductors | SOXX or SMH | Choose one after index-methodology/liquidity review; equipment/design/manufacturing mix remains. |
| banks diversified | KBE | Regional-bank-heavy KRE is not a JPM default. XLF fallback. |
| biotechnology | XBI or IBB | Equal-weight versus cap-weight behavior differs; preserve benchmark choice. |
| aerospace & defense | ITA or XAR | Size weighting materially affects BA/RKLB comparison. |
| pharmaceuticals | IHE | Verify holdings/mandate; XLV fallback. |
| software | IGV | Not all infrastructure/security/application firms fit equally. XLK fallback. |
| integrated oil & gas | XLE may be adequate | XLE is sector-labeled but concentrated in integrated/large energy; record actual granularity. |
| consumer electronics / discount retail / auto manufacturers | peer basket or sector fallback | No narrow benchmark should be forced merely to fill coverage. |

A final map should select one benchmark per normalized group, document the mandate and fallback, and be versioned in code.

## 9. ETF price versus ETF holdings

These are separate dependencies:

- An ETF's exchange-traded market price is ordinary instrument price history. Comparing NVDA return with SOXX return does not require ingesting SOXX holdings.
- ETF holdings are a proprietary composition dataset published by the sponsor/index ecosystem. Using them to name peers, store weights, or display constituents can carry separate terms, attribution, and refresh obligations.

Therefore Phase 6A.2D.2 can materially improve industry trend and company-relative performance using only an approved ETF's market price, even if holdings rights remain unresolved. Breadth should be optional and independently unavailable rather than blocking benchmark analysis.

## 10. Current peer construction

Peers currently come exclusively from the selected **sector ETF's top holdings**:

1. yfinance reads `funds_data.top_holdings`;
2. positive finite weights are sorted descending, ticker ascending for ties;
3. at most ten valid symbols are retained;
4. target, benchmark, and SPY are excluded;
5. at most six symbols are sampled;
6. no replacement fan-out occurs when a history fails;
7. at least four aligned peer histories are required.

There is no industry match, SIC match, provider peer endpoint, market-cap band, liquidity screen, or metadata validation for each holding. This is deliberate V1 boundedness, but the resulting sample is sector leadership—not economic peers.

## 11. Proposed peer construction

Use a bounded hybrid:

1. Resolve target to a normalized industry and classification quality.
2. If an approved narrow-industry ETF exists, use up to ten of its valid holdings, excluding the target.
3. If holdings use is not approved or the product is too broad, use a small deterministic same-normalized-industry candidate universe only when such a universe already exists from an approved source.
4. Apply simple eligibility: US-listed common equity/ADR policy, valid 60-session history, minimum liquidity, and broad size compatibility.
5. Rank deterministically by market cap, then ticker, and select a bounded sample.
6. If fewer than five valid peers remain, breadth is unavailable; fall back to benchmark-only industry context or sector context.

Do not build subjective ticker lists. Do not query arbitrary Yahoo “recommended symbols.” Do not infer peers from description text. Do not recursively fetch replacements.

For Phase 6A.2D.2, narrow ETF holdings are the most practical discovery mechanism for supported groups, provided their use is approved. SIC can validate family membership but should not alone make two companies peers.

## 12. Peer-set sizing

Recommend **6–10 selected peers**, with **minimum five valid histories**:

- six preserves current cost and is enough for a coarse participation signal;
- ten reduces single-name distortion while remaining bounded;
- fewer than five makes percentages too sensitive (one name moves breadth by 20–25 points);
- more than ten adds requests and false precision without much private-beta value.

The exact selected list and valid count must be stored in provenance. The target never contributes to breadth.

## 13. Relative-performance design

Calculate TradePilot-owned values on aligned completed sessions:

```text
company_return_20 = company_close[-1] / company_close[-21] - 1
benchmark_return_20 = benchmark_close[-1] / benchmark_close[-21] - 1
relative_return_20 = company_return_20 - benchmark_return_20

company_return_60 = company_close[-1] / company_close[-61] - 1
benchmark_return_60 = benchmark_close[-1] / benchmark_close[-61] - 1
relative_return_60 = company_return_60 - benchmark_return_60
```

Use 20/60 sessions as readable approximations to one/three months. Migrating from existing 21/63 windows should be an explicit version change; retaining 21/63 is also reasonable and reduces behavioral churn. Do not add a 5-day signal initially: it is noisy and begins to duplicate Technical.

Semantic states:

- `strongly_outperforming`
- `outperforming`
- `roughly_in_line`
- `underperforming`
- `strongly_underperforming`
- `mixed`
- `unavailable`

Thresholds should not be invented in this audit. Phase 6A.2D.2 should validate candidate deadbands against a frozen cross-industry corpus. The current sector-vs-SPY deadbands (1 pp at 21 sessions and 2 pp at 63 sessions) are useful baselines, but single-stock volatility likely requires wider company-relative bands. Strong states should require both greater magnitude and non-conflicting longer-horizon confirmation.

## 14. Industry-trend design

Keep three small features:

1. benchmark 20-session return;
2. benchmark 60-session return;
3. benchmark above/below 50-session moving average.

Reuse the current unanimity rule to classify `strengthening`, `weakening`, or `mixed`. Optionally retain benchmark-versus-SPY relative strength as a separate factual field, but do not recreate Technical Score indicators such as RSI/MACD/volatility patterns.

Industry trend describes the group. Company-relative performance describes the issuer. They should not be collapsed into one number before presentation.

## 15. Peer-breadth design

Use only:

- proportion of valid peers with positive 20-session return;
- proportion above the 50-session moving average;
- median 20-session peer return as a robust descriptive value.

The existing two-thirds agreement rule is conservative and can be retained provisionally: broad strength requires both participation measures ≥ 2/3; broad weakness requires both negative-return and below-SMA measures ≥ 2/3; otherwise mixed. Median return adds context but should not create a third independent vote.

Rules:

- minimum five valid peers;
- aligned completed sessions only;
- no synthetic filling;
- IPO/sparse/delisted histories excluded with reason;
- median rather than mean limits outlier influence;
- breadth unavailable if the source peer set or minimum coverage fails;
- percentage is descriptive, not a confidence score.

## 16. Directionality design

Classification identity and benchmark selection are informational. Directional evidence may come from two separate families:

1. **industry health:** benchmark trend plus broad breadth;
2. **company relative strength:** target versus benchmark, with sufficiently stable multi-horizon confirmation.

Recommended combination:

| Industry health | Company relative state | Category meaning |
| --- | --- | --- |
| strong | outperforming | supportive industry plus issuer leadership; positive facts |
| weak | underperforming | adverse industry plus issuer weakness; negative facts |
| strong | underperforming | mixed: healthy group, lagging company |
| weak | outperforming | mixed: weak group, resilient company |
| mixed | directional relative state | relative fact can be reported, but do not label industry health accordingly |
| unavailable | any | retain only independently verified facts; category may remain insufficient |

Do not make classification granularity or benchmark availability itself directional. Do not treat company outperformance as proof that its industry is healthy.

## 17. Weak-industry / strong-company edge case

Example: company +10%, benchmark −5%, relative +15 pp.

- industry health: `weakening`;
- company relative performance: `strongly_outperforming` if calibrated thresholds/longer horizon confirm;
- combined context: `mixed`, with two explicit facts;
- never rewrite the Industry category as simply Positive.

The inverse (company −5%, benchmark +10%) is also mixed structurally: healthy industry with strong company-specific underperformance. That negative relative fact is important but does not make the industry weak.

This separation should be visible in normalized context even if the existing single category label remains backend-authoritative.

## 18. Benchmark fallback hierarchy

```text
normalized industry + approved mapped industry ETF
  -> benchmark_type=industry_etf

else validated normalized-industry peer basket (>=5)
  -> benchmark_type=peer_basket

else existing mapped sector ETF
  -> benchmark_type=sector_etf
     classification_quality=sector_fallback

else
  -> insufficient_data
```

Do not use a broad-market benchmark as the group. SPY can remain the comparison baseline. Every fact must carry benchmark symbol/name, benchmark type, taxonomy source, mapping version, and fallback reason.

## 19. Classification-quality design

Use categorical provenance, not an arbitrary score:

- `exact_industry`: source industry maps one-to-one to a supported normalized group and benchmark;
- `normalized_industry`: multiple documented synonyms map to one supported group;
- `sic_validated`: Yahoo identity is consistent with a supporting SIC family;
- `sic_fallback`: Yahoo industry unavailable; SIC supplies a coarse family;
- `sector_fallback`: only the broad sector benchmark is defensible;
- `unknown`: no defensible classification.

Also retain raw Yahoo industry/sector and SEC SIC/code description. The AI must not describe `sector_fallback` as an industry comparison.

## 20. Market-cap and size assessment

Size filtering materially improves peer quality but should remain simple:

- prefer peers between roughly 0.2× and 5× the target market cap when enough candidates remain;
- if that leaves fewer than five, relax once to 0.1×–10× and record the relaxation;
- never use size alone to establish economic comparability;
- require ordinary liquidity/history eligibility independently.

These bands are design candidates, not approved thresholds. Validate them against large and small controls, including BA versus RKLB and NVDA versus smaller semiconductor firms. For an ETF-holdings sample, market-cap weighting already biases toward large issuers; an explicit band prevents a mega-cap target from being compared only with tiny constituents or vice versa.

## 21. Controlled benchmark-map assessment

A small map is appropriate if it remains:

- normalized-industry → one benchmark symbol, never ticker → benchmark;
- approximately 15–30 high-value groups initially;
- versioned and reviewed when ETF mandates/tickers change;
- accompanied by source-label aliases, excluded ambiguous labels, benchmark type, and sector fallback;
- covered by positive and negative-control tests.

Maintenance is modest: quarterly review plus change-triggered review for ETF closure, mandate change, or source taxonomy rename. The map must not grow opportunistically for each requested ticker. Unsupported industries use sector fallback.

## 22. Representative ticker audit

Bounded live metadata/holdings retrieval was performed on 2026-09-21 through the installed yfinance dependency, using a temporary cache and no paid API or application database. Results are point-in-time and provider-reported.

| Ticker | Yahoo sector / industry | Current benchmark | Current first-six sample after target exclusion | Current granularity/problem | Proposed approach / fallback |
| --- | --- | --- | --- | --- | --- |
| AAPL | Technology / Consumer Electronics | XLK | NVDA, MSFT, AVGO, MU, AMD, INTC | Sector; semiconductor-heavy peers are not consumer-electronics peers | No forced narrow ETF; normalized industry + peer basket if approved, else XLK sector fallback. |
| NVDA | Technology / Semiconductors | XLK | AAPL, MSFT, AVGO, MU, AMD, INTC | Sector sample mixes software/hardware; some semiconductor names happen to appear | SOXX/SMH industry ETF; narrow holdings/sample; XLK fallback. |
| MSFT | Technology / Software - Infrastructure | XLK | NVDA, AAPL, AVGO, MU, AMD, INTC | Mostly hardware/semiconductor sector leaders, poor software peers | IGV-like software benchmark after mandate review; XLK fallback. |
| GOOGL | Communication Services / Internet Content & Information | XLC | META, GOOG, T, VZ, CMCSA, NFLX | Mixes internet platforms, telecom, cable; includes alternate Alphabet share class | XLC may remain explicit sector fallback; deduplicate issuer share classes in breadth. |
| JPM | Financial Services / Banks - Diversified | XLF | BRK-B, V, MA, BAC, GS, WFC | Includes conglomerate, payments, broker/dealer; only BAC/WFC are close banks | KBE or validated large-bank basket; XLF fallback. |
| XOM | Energy / Oil & Gas Integrated | XLE | CVX, COP, MPC, PSX, VLO, SLB | Sector sample includes E&P, refining, services; XLE price is nevertheless large-integrated-heavy | XLE may be acceptable coarse industry ETF with explicit granularity; integrated-energy peers if approved. |
| LLY | Healthcare / Drug Manufacturers - General | XLV | JNJ, ABBV, MRK, UNH, AMGN, TMO | Includes insurer and tools company | IHE-like pharma benchmark; XLV fallback. |
| WMT | Consumer Defensive / Discount Stores | XLP | COST, KO, PG, PM, TGT, CL | Only COST/TGT are close retailers | Same-industry retail basket if available; XLP sector fallback. |
| BA | Industrials / Aerospace & Defense | XLI | CAT, GE, RTX, GEV, UNP, DE | Only RTX close; heavy machinery/rail/power dominate | ITA/XAR industry ETF; XLI fallback. |
| TSLA | Consumer Cyclical / Auto Manufacturers | XLY | AMZN, HD, MCD, BKNG, TJX, SBUX | No auto peers at all | Auto peer basket or carefully reviewed auto ETF; XLY fallback. |
| PLTR | Technology / Software - Infrastructure | XLK | NVDA, AAPL, MSFT, AVGO, MU, AMD | Only MSFT is remotely same software family | Software benchmark with cautious normalization; XLK fallback. |
| SMCI | Technology / Computer Hardware | XLK | NVDA, AAPL, MSFT, AVGO, MU, AMD | Broad technology leaders; mixed hardware and semiconductors | Hardware/server peer basket if supported; XLK fallback. |
| RKLB | Industrials / Aerospace & Defense | XLI | CAT, GE, RTX, GEV, UNP, DE | Size/business mismatch and non-aerospace peers | XAR/ITA benchmark price; size-aware peers or benchmark-only; XLI fallback. |

The live check did not download price histories, calculate ratings, or make OpenAI requests. It establishes classification and peer-construction behavior only.

## 23. Performance and caching analysis

Current cold Industry maximum: one metadata + one holdings + eight history service calls. Proposed bounded maximum:

- one target metadata lookup;
- optionally one cached SEC classification lookup;
- one industry benchmark history;
- one SPY history, shared with Market;
- one target history, likely shared with other services where possible;
- at most ten peer histories;
- one holdings lookup only for supported narrow benchmarks.

Worst case becomes roughly **13 history loads** (benchmark, SPY, target, 10 peers), versus current 8: at most five additional history loads. With a six-peer default it is **9 histories**, only one more than today because target history is new. Shared global caches make this market intelligence user-independent.

Recommended caches:

- classification result and normalized mapping: 7 days;
- SEC SIC: reuse SEC metadata cache / at least 1 day;
- benchmark map: static versioned code;
- ETF holdings: 1 day if approved;
- peer resolution: 1 day keyed by target classification/map version;
- histories: existing shared 15 minutes;
- calculated result: 30 minutes;
- failure backoff: existing 60 seconds.

Never fan out beyond the configured peer cap. Fetch sequentially or with a very small concurrency bound. Cache by symbol across all users and targets.

## 24. Failure isolation

| Failure | Behavior |
| --- | --- |
| Yahoo industry missing | Try SIC fallback; otherwise sector fallback. |
| Yahoo and SIC disagree | Preserve both, choose no narrow benchmark unless an explicit normalization rule resolves it; sector fallback. |
| Industry benchmark missing/unmapped | Sector ETF fallback with categorical provenance. |
| Industry ETF/history unavailable | Do not substitute another “similar” ETF dynamically; try sector fallback. |
| Target history unavailable | Industry health may remain, company-relative fact unavailable. |
| Holdings unavailable/unapproved | Breadth unavailable; benchmark trend/relative fact may remain. |
| Some peers fail | Continue only if minimum five valid aligned histories remain; record exclusions. |
| Too few peers | No breadth event; never fabricate neutral breadth. |
| Market/SPY unavailable | Preserve absolute industry benchmark trend if policy permits; relative-to-market unavailable. |
| Sector benchmark unavailable | Industry insufficient; other categories continue unchanged. |
| ETF closes/changes mandate | Disable mapping until reviewed; use sector fallback. |

No Industry failure may affect Company, Earnings, Economic, Market, Geopolitical, Technical, Financial, or Valuation processing.

## 25. AI context implications

The existing fact model can carry compact structured values in evidence details without changing prompt/schema 2.2:

```text
industry_name
raw_industry_name
classification_quality
taxonomy_sources
benchmark_symbol / benchmark_name / benchmark_type
company_return_20 / benchmark_return_20 / relative_return_20
company_return_60 / benchmark_return_60 / relative_return_60
relative_performance_state
benchmark_trend_state
positive_return_breadth_20
above_sma50_breadth
median_peer_return_20
valid_peer_count
```

TradePilot calculates every literal number and categorical state. The AI interprets only cited facts and must preserve distinctions between sector fallback, industry health, breadth, and company relative strength. Do not expand the model contract unless existing bounded fact values cannot carry these fields after implementation tests.

## 26. UI implications

No UI change is part of this phase. An eventual Industry detail can reliably communicate:

- Industry: Semiconductors (or “Technology sector fallback”);
- group trend: strengthening/mixed/weakening;
- company versus group: outperforming/in line/underperforming with 20/60-session facts;
- peer participation: broad strength/weakness/mixed and valid peer count;
- source provenance under existing methodology disclosure.

Do not expose internal terms such as SIC normalization, peer resolution, or cache tiers in the primary view. Classification quality should influence wording; detailed provenance/diagnostics may show it behind disclosure.

## 27. Minimum Phase 6A.2D.2 scope

1. Add a small versioned Yahoo-industry normalization table and categorical quality/fallback metadata.
2. Add a controlled industry→ETF benchmark map for a limited set of high-value groups, with existing sector fallback.
3. Use benchmark market price independently of holdings.
4. Load target history and calculate aligned 21/63-session company-versus-benchmark return, reusing current windows unless a tested migration justifies 20/60.
5. For approved narrow ETFs, reuse the bounded holdings path with 6–10 peers and minimum five valid histories; otherwise make breadth unavailable.
6. Keep industry health and company relative strength as separate deterministic facts and evidence families.
7. Add explicit benchmark type, mapping version, classification quality, raw labels, peer count, and failure reason to provenance/diagnostics.
8. Add frozen representative tests including the 13 audited tickers, synonym/ambiguity negative controls, weak-industry/strong-company cases, missing holdings, sparse peers, size mismatch, and cache-call bounds.
9. Preserve UI, scoring contract, prompt, schema, other providers, and all consensus work.

SEC SIC integration can be included only if it reuses existing SEC metadata cleanly; otherwise make it a later fallback enhancement rather than expanding the minimum phase.

## 28. External-data requirement

**B. YES, WITH LIMITED COVERAGE/FALLBACKS.**

Useful Industry Precision does not require paid data. Existing Yahoo industry strings, market-price history, a small controlled benchmark map, bounded ETF constituent data where usage is approved, and optional SEC SIC validation can materially improve the current sector-only behavior.

Limitations remain:

- Yahoo taxonomy and yfinance are unofficial dependencies with data-rights and stability concerns;
- ETF holdings rights should be confirmed separately from price use;
- coverage will be uneven and sector fallback common;
- no free source reviewed provides a complete, maintained investment taxonomy plus peers, size, liquidity, and corporate-action history with unambiguous multi-user rights.

A licensed GICS/reference-data product would improve stable codes, hierarchy, coverage, and corporate maintenance, but is not required for the narrowly scoped private-beta improvement.

## 29. Exact recommended next phase

Proceed with **Phase 6A.2D.2 — Industry Precision Implementation**, limited to the minimum scope in section 27.

Before using ETF holdings in production, document the selected source's permitted storage/display behavior. If that remains unresolved, implement benchmark-price trend and company-relative performance first, leave peer breadth on the existing sector path or unavailable, and do not block the phase.

Do not alter current thresholds until a frozen cross-industry fixture set demonstrates the proposed company-relative state boundaries. No OpenAI call or production UI redesign is needed.

## Official references

Accessed 2026-09-21.

- SEC: [EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [SIC code list](https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list), [accessing EDGAR data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
- U.S. Census Bureau: [NAICS](https://www.census.gov/naics/)
- MSCI/S&P: [GICS overview](https://www.msci.com/indexes/index-resources/gics), [GICS methodology](https://www.msci.com/indexes/documents/methodology/0_MSCI_Global_Industry_Classification_Standard_GICS_Methodology_20240801.pdf)
- yfinance: [Ticker reference](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html), [FundsData reference](https://ranaroussi.github.io/yfinance/reference/api/yfinance.scrapers.funds.FundsData.html), [project/legal notice](https://github.com/ranaroussi/yfinance)
- Select Sector SPDRs: [sector fund family](https://www.sectorspdrs.com/)
- Candidate benchmark issuers/methodologies require product-level review before mapping: [iShares SOXX](https://www.ishares.com/us/products/239705/ishares-phlx-semiconductor-etf), [VanEck SMH](https://www.vaneck.com/us/en/investments/semiconductor-etf-smh/), [SPDR KBE](https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-bank-etf-kbe), [iShares ITA](https://www.ishares.com/us/products/239502/ishares-us-aerospace-defense-etf), [SPDR XAR](https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-aerospace-defense-etf-xar)

## Final summary

**CURRENT INDUSTRY APPROACH**

Yahoo sector metadata selects one of 11 sector ETFs. TradePilot measures that ETF versus SPY and calculates breadth from six sector-ETF top holdings. Yahoo industry is diagnostic only; target-company relative performance is absent.

**PRIMARY WEAKNESS**

The category often compares a company with broad sector leaders rather than its economic peer group, producing misleading “peer” samples for NVDA, TSLA, BA, PLTR, and others.

**RECOMMENDED TAXONOMY**

A small versioned normalization layer over Yahoo industry strings, with raw-label provenance, optional SEC SIC validation/fallback, categorical classification quality, and explicit sector fallback. Do not recreate or claim GICS.

**RECOMMENDED BENCHMARK STRATEGY**

Controlled normalized-industry→ETF price map for supported groups; validated peer basket only when adequate; existing sector ETF fallback; otherwise insufficient data. SPY remains a broad comparison baseline.

**RECOMMENDED PEER STRATEGY**

Six to ten deterministic, eligible constituents from an approved narrow-industry source, target excluded, minimum five valid aligned histories, simple size/liquidity constraints, and no replacement fan-out or subjective ticker lists.

**RECOMMENDED RELATIVE-PERFORMANCE SIGNALS**

Company, benchmark, and company-minus-benchmark returns over the existing 21/63 sessions (or explicitly tested 20/60 migration), plus calibrated outperforming/in-line/underperforming states. Keep company relative strength separate from industry health.

**RECOMMENDED BREADTH SIGNALS**

Positive 20/21-session participation, above-SMA50 participation, median peer return, and valid peer count. Require at least five peers; otherwise unavailable.

**PAID DATA REQUIRED?**

PARTIAL: not required for a useful limited implementation, but paid reference data would improve stable taxonomy, coverage, peer maintenance, and licensing clarity.

**CAN PHASE 6A.2D.2 PROCEED?**

LIMITED.

**MINIMUM IMPLEMENTATION**

Industry normalization, small benchmark map, explicit sector fallback, target-versus-benchmark returns, bounded optional breadth, classification/benchmark provenance, cache bounds, and representative frozen tests.

**NEXT PHASE**

Phase 6A.2D.2 — Industry Precision Implementation
