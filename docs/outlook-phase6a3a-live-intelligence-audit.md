# Phase 6A.3A — Live Outlook Intelligence Audit

**Audit date:** 2026-09-24  
**Status:** complete  
**Configured model:** `gpt-5.4-mini`  
**Contract:** prompt `outlook-analyst-2.4`; schema `2.2`

## 1. Executive summary

TradePilot's deterministic Outlook layer behaved conservatively and is ready to freeze after no deterministic logic defect was found. Thirteen of sixteen final live generations passed schema and grounding validation. Three tickers—MSFT, XOM, and PLTR—failed closed because the model selected `Mixed` overall while every substantive category rating was positive. The validator correctly rejected this unsupported synthesis on both attempts for each ticker. This is a repeated **HIGH grounding/reliability defect** suitable for a narrow Phase 6A.3B fix; it does not justify reopening the architecture.

Successful reports were generally useful, concise, and appropriately uncertain. Upcoming earnings never made Earnings directional by itself. Company never borrowed Earnings facts. Sector fallbacks were described as sector context rather than precise peer analysis. The sparse ABTC case remained grounded and restrained. No output fabricated consensus, expected move, beat probability, event identity, or date.

## 2. Methodology and environment

The audit ran the existing deterministic pipeline, normalized context builder, configured OpenAI adapter, strict output schema, and grounding validator sequentially for the required 16 tickers. One process-cache repeat was performed for AAPL. No automated test called OpenAI.

- Environment: local development configuration.
- Active provider: OpenAI.
- Model: `gpt-5.4-mini`.
- LLM cache TTL: 3,600 seconds.
- Live provider and market data were retrieved through existing application paths.
- Audit tooling was diagnostic only and did not change production behavior.
- Baseline: 229 focused tests passed; two existing FastAPI deprecation warnings.

The first corpus pass made 17 requests but its audit serializer failed after generation. One additional AAPL request exposed a second serializer issue and was interrupted immediately. After a no-cost mock verification, the final pass made 19 requests, including three permitted retries. Total live OpenAI requests attributable to the audit were therefore approximately 37. The final artifact contains the authoritative 16-ticker results; lost first-pass usage is included only in the estimated total cost.

## 3. Audit universe

`AAPL`, `NVDA`, `MSFT`, `GOOGL`, `JPM`, `XOM`, `LLY`, `BA`, `WMT`, `TSLA`, `PLTR`, `AMD`, `META`, `KO`, `CAT`, and `ABTC`.

## 4. Provider availability

| Provider | Result across 16 tickers |
| --- | --- |
| SEC | 16 available; metadata-only observations remained excluded from Company context |
| FRED | 16 available |
| Market | 16 available |
| Industry | 16 available, including explicit partial/fallback facts |
| FOMC | 16 available |
| Macro | 16 partial, consistent with the intentionally absent consensus/surprise layer |
| Earnings events | 15 available; WMT correctly returned no events |
| Geopolitical | 2 available (NVDA, AMD); 14 no evidence |

A naturally observed SEC request/exhibit failure during the deterministic refresh did not destroy Market, Industry, or the overall audit run.

## 5. Per-ticker summary

| Ticker | Overall | Company | Earnings | Industry | Economic | Market | Geopolitical | Watch | Grounding | Classification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AAPL | Mostly Positive | ID | Very Positive | Mixed / XLK fallback | ID | Mixed | ID | Earnings | Pass | Correct/useful |
| NVDA | Mostly Positive | ID | Very Positive | Mixed / SOXX precise | Mixed | Mostly Positive | Mostly Positive | None | Pass | Correct/useful |
| MSFT | Unavailable | — | — | IGV precise | — | — | — | — | **Fail twice** | Grounding defect |
| GOOGL | Mixed | ID | ID | Mixed / XLC fallback | ID | Mostly Positive | ID | Earnings | Pass | Correct/useful |
| JPM | Mixed | ID | ID | Mostly Negative / KBE precise | ID | Mostly Positive | ID | Earnings | Pass | Correct/useful |
| XOM | Unavailable | — | — | XLE precise | — | — | — | — | **Fail twice** | Grounding defect |
| LLY | Mixed | ID | ID | Mixed / IHE precise | ID | Mostly Positive | ID | Earnings | Pass | Correct/useful |
| BA | Mixed | ID | ID | Mostly Negative / ITA precise | ID | Mostly Positive | ID | Earnings | Pass | Correct/useful |
| WMT | Mixed | ID | ID | Mixed / XLP fallback | Mixed | Mostly Positive | ID | None | Pass | Sparse but correct |
| TSLA | Mixed | ID | ID | Mostly Negative / XLY fallback | ID | Mostly Positive | ID | Earnings | Pass | Correct/useful |
| PLTR | Unavailable | — | — | IGV precise | — | — | — | — | **Fail twice** | Grounding defect |
| AMD | Mostly Positive | ID | ID | Mixed / SOXX precise | Mixed | Mostly Positive | Mostly Positive | Earnings | Pass | Correct/useful |
| META | Mostly Positive | ID | ID | Very Positive / XLC fallback | Mixed | Mostly Positive | ID | Earnings | Pass | Correct/useful |
| KO | Mixed | ID | ID | Mixed / XLP fallback | ID | Mostly Positive | ID | Earnings | Pass | Sparse but correct |
| CAT | Mixed | ID | ID | Mostly Negative / XLI fallback | ID | Mostly Positive | ID | Earnings | Pass | Correct/useful |
| ABTC | Mixed | ID | ID | Mixed / XLF fallback | ID | Mostly Positive | ID | Earnings | Pass | Sparse but correct |

`ID` means `insufficient_data`. The three failed generations expose no category response because TradePilot rejects the complete invalid response.

## 6. Fact and directionality summary

Packets contained 12–18 facts. Company contained zero included facts for all tickers because observed SEC metadata was non-material or provenance-only. Economic normally contributed eight informational facts. Market contributed two directional facts for every ticker. Industry contributed two facts except XOM and ABTC, where partial history left one group-health fact. Earnings had released facts for AAPL and NVDA; most other tickers had one informational upcoming-event fact. Only NVDA and AMD had a geopolitical fact.

This distribution explains the visible pattern without indicating a defect: shared macro/market context is expected, issuer-specific Company context is sparse, and Industry supplies most cross-ticker differentiation.

## 7. Industry precision

| Ticker group | Result |
| --- | --- |
| NVDA, AMD | Exact semiconductors; SOXX; eight valid peers; mixed breadth; no AAPL/MSFT sector-peer substitution |
| MSFT, PLTR | Exact software infrastructure; IGV; precise benchmark |
| JPM | Exact diversified banks; KBE; nine valid peers; negative breadth |
| XOM | Exact integrated oil and gas; XLE; group health available; company-relative history unavailable |
| LLY | Exact pharmaceuticals; IHE; nine valid peers; mixed breadth |
| BA | Exact aerospace and defense; ITA; nine valid peers; negative breadth |
| AAPL, GOOGL, WMT, TSLA, META, KO, CAT, ABTC | Explicit sector fallback |

TSLA used XLY with `sector_fallback`; AMZN, HD, and MCD were not presented as automobile peers. Successful responses kept industry health separate from company-relative strength. One presentation weakness remains: model prose sometimes says “industry” around explicit sector fallbacks, although the substance identifies the broader sector context and does not invent peers. This is low-risk wording for Phase 6B unless a narrower prompt wording change is already required in 6A.3B.

## 8. Earnings

AAPL and NVDA had released, deterministic year-over-year earnings facts and received Very Positive Earnings ratings. Neither claimed a beat or miss because no verified expectation existed. For all other tickers, an upcoming date alone remained informational and Earnings stayed Insufficient Data. WMT had neither a released fact nor an upcoming event and also remained Insufficient Data.

No production consensus source, actual-versus-consensus comparison, expected move, or beat probability was present. These are intentional gaps, not defects.

## 9. Company

Company was Insufficient Data for every successful response. Metadata-only SEC observations were excluded (four to seventeen omitted observations depending on ticker), and the model did not borrow revenue, margins, or upcoming earnings from Earnings. This is sparse but correct. It demonstrates a coverage limitation, not a reason to add broad SEC interpretation rules during stabilization.

## 10. Economic and Market

Macro providers supplied recent readings and scheduled/released events without verified expectations. The AI either returned Insufficient Data or Mixed informational context; it did not claim beats, misses, or surprise direction. Market was consistently supportive because the same broad benchmarks and volatility regime applied across the corpus. This commonality is expected shared context, not accidental ticker-specific fabrication.

## 11. Geopolitical

Only NVDA and AMD received a geopolitical fact. Both facts used the controlled semiconductor/advanced-computing exposure relationship and explicitly limited the link to industry-level exposure, with no claim of product qualification, customer relationship, or revenue share. The model retained conditional licensing language. Unrelated tickers remained Insufficient Data.

## 12. What to Watch

Eleven successful responses selected one real upcoming earnings event. NVDA and WMT had no supplied event; no watch item was invented. Every selected ID resolved exactly to TradePilot's event collection and carried the supplied title/date. The list remained selective and did not become a macro-event dump.

## 13. Grounding validation

Thirteen final responses passed all automated grounding checks:

- cited IDs existed and remained category-local;
- insufficient categories had no support or key points;
- directional ratings had compatible deterministic evidence;
- watch IDs exactly matched supplied upcoming events;
- no unsupported dates, consensus, expected move, or probabilities appeared.

MSFT, XOM, and PLTR failed the same rule on both attempts. Each response rated Industry and Market positive, had no negative or substantive Mixed category, but selected `Mixed` overall because of missing issuer data or an upcoming catalyst. Missing evidence is a limitation, not conflicting substantive evidence. The existing validator correctly rejected the output. This is a repeated model/contract alignment defect with safe failure behavior.

## 14. Semantic-quality and consistency review

The 13 accepted reports accurately summarized supplied facts, used uncertainty language, and were compact enough for a future UI. AAPL/NVDA earnings language was proportionate to deterministic year-over-year growth rather than fabricated expectations. GOOGL's upcoming earnings remained non-directional. Industry descriptions correctly captured tensions such as weak group/strong company and positive group/mixed relative performance.

Cross-ticker behavior was not uniformly Mixed: four accepted reports were Mostly Positive and nine were Mixed. Market was frequently positive, but Overall still reflected negative Industry evidence for JPM, BA, TSLA, and CAT. Geopolitical content appeared only for the two exposure-linked semiconductor issuers. Sparse ABTC did not fabricate issuer detail.

## 15. Failure isolation and cache

- Grounding failures produced unavailable AI intelligence while deterministic Outlook remained intact.
- XOM's missing company-relative/peer history preserved industry group health.
- Missing earnings expectations did not remove actual/YoY facts for AAPL or NVDA.
- Missing geopolitical evidence did not invalidate Overall.
- The AAPL identical-context repeat was a process-cache hit with zero-millisecond measured lookup and no second OpenAI request.

Cache identity includes ticker, provider, model, prompt version, schema version, and normalized context fingerprint. Changed facts or any contract/model change invalidates the entry. The cache is process-local and therefore does not coordinate multiple workers; this is a known deployment limitation rather than a new audit defect.

## 16. Latency, tokens, and cost

Successful final generations:

- Average input: 6,583 tokens; median 6,382.
- Average output: 727 tokens; median 639.
- Average total: 7,310 tokens; median 7,071.
- Average latency: 3.72 seconds; median 3.25 seconds.
- Corpus-observed p95-like latency: 4.86 seconds; maximum 5.42 seconds.

Official OpenAI pricing on 2026-09-24 for `gpt-5.4-mini` was $0.75 per million uncached input tokens, $0.075 per million cached input tokens, and $4.50 per million output tokens ([official model page](https://developers.openai.com/api/docs/models/gpt-5.4-mini)). TradePilot currently records total input/output but not cached-input detail, so estimates conservatively treat input as uncached.

- Average uncached generation: approximately **$0.00821**.
- 100 generations/month: approximately **$0.82**.
- 1,000 generations/month: approximately **$8.21**.
- 10,000 generations/month: approximately **$82.09**.
- Thirteen retained successful outputs: **$0.1067** measured-token estimate.
- Full audit, including serializer-loss repeats and grounding retries: approximately **$0.30**, estimated from 37 requests at the successful-call average. Failed-call usage and cached-input detail were unavailable, so this is approximate rather than billing reconciliation.

## 17. Findings by classification and severity

| Finding | Classification | Severity | Scope |
| --- | --- | --- | --- |
| Unsupported Mixed overall rejected for MSFT/XOM/PLTR on both attempts | Grounding defect | **HIGH** | Repeated model/validator alignment; safe failure |
| Company empty after metadata-only SEC exclusion | Sparse but correct | n/a | All tickers |
| Macro lacks consensus/surprise direction | Intentionally deferred data gap | n/a | All tickers |
| Earnings lacks production consensus/expected move/beat probability | Intentionally deferred data gap | n/a | Corpus except deterministic YoY facts |
| Limited precise taxonomy with explicit sector fallback | Intentionally deferred data gap | n/a | Eight tickers |
| Some fallback prose uses “industry” generically | Presentation weakness | n/a | Bounded; no false peer claim |
| Audit serializer caused repeated paid calls | Audit-tool reliability defect | LOW | Audit only; no production impact |

Defect totals: 0 Critical, 1 High systemic defect affecting three tickers, 0 Medium, and 1 Low audit-tool defect.

## 18. Recommended Phase 6A.3B scope

1. Tighten one demonstrated overall-rating ambiguity: when all substantive category ratings point in one direction and no substantive opposing/Mixed category exists, missing data and upcoming catalysts must not justify `Mixed` overall. Prefer the compatible directional overall rating or, if evidence is judged inadequate, a schema-valid result consistent with existing eligibility rules.
2. Add frozen regression cases reproducing MSFT, XOM, and PLTR category-rating combinations and assert a valid overall result.
3. Re-run a small live control set containing those three tickers plus one known passing ticker; do not rerun the full corpus unless the prompt/validator change affects broader behavior.
4. Preserve the validator's current fail-closed rule. Do not weaken it merely to accept these outputs.

Do **not** change deterministic directionality, materiality, taxonomy mappings, SEC rules, providers, earnings/macro consensus architecture, expected move, beat probability, UI, or category ownership. No finding justifies reopening the architecture.

## 19. Pre-freeze assessment

1. **Deterministic intelligence ready to freeze?** Yes.
2. **AI analyst ready to freeze?** After bounded remediation of the repeated overall-rating failure.
3. **Critical/High defects?** No Critical; one High systemic grounding/alignment defect affecting three tickers.
4. **Remaining gaps primarily intentional?** Yes.
5. **Reopen architecture?** No.
6. **Exactly what should 6A.3B change?** Overall-rating prompt/contract alignment and frozen regressions for the demonstrated pattern.
7. **What should remain unchanged?** Providers, scoring/directionality/materiality, category ownership, taxonomy scope, deferred data products, and UI.

## 20. Validation and source control

- Focused deterministic baseline: 229 passed, two existing deprecation warnings.
- Final live corpus: 16 tickers; 13 valid outputs; three failed closed after one retry each.
- Final-pass grounding failures: six attempts across three tickers.
- `git diff --check`: run after artifact/report creation.
- No migration, database mutation, commit, merge, push, deployment, UI change, or production-runtime change.
