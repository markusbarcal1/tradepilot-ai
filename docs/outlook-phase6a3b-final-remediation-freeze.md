# Phase 6A.3B — Final Outlook Remediation & Intelligence Freeze

**Status:** complete  
**Prompt:** `outlook-analyst-2.5`  
**Schema:** `2.2`  
**Freeze decision:** **OUTLOOK INTELLIGENCE LAYER FROZEN**

## Phase 6A.3A defect and root cause

The live audit found a repeated model-contract ambiguity for MSFT, XOM, and PLTR. The model sometimes treated positive substantive category evidence plus unavailable categories, limitations, or an upcoming catalyst as an Overall `Mixed` result. Missing information is not conflicting evidence, so the unchanged grounding validator correctly rejected those responses.

The deterministic facts, category ratings, category ownership, and validator logic were correct. The defect was ambiguity in the analyst prompt's explanation of Overall `Mixed`.

## Prompt remediation

Prompt `outlook-analyst-2.5` explicitly states:

- Insufficient Data is absence of evidence, not conflicting evidence.
- Missing categories, incomplete coverage, limitations, uncertainty, and informational facts do not independently justify Overall `Mixed`.
- Mixed requires substantive positive/negative conflict or a substantive category rated Mixed because its verified evidence is mixed/conflicting.
- Gaps should be expressed in prose without manufacturing conflict.
- The model still chooses Very versus Mostly qualitatively; it must not score, count, vote, or mechanically aggregate categories.

Schema `2.2` and the shape of Overall (`rating`, `summary`) remain unchanged. `overall.supporting_categories` was not reintroduced.

## Validator and deterministic intelligence

The grounding validator is unchanged. It continues to reject:

- directional Overall ratings without compatible substantive categories;
- Mixed without a substantive Mixed category or conflicting positive/negative categories;
- Overall Insufficient Data unless all six categories are insufficient;
- unknown/cross-category fact references and invalid watch-event selections.

No deterministic provider, interpretation rule, taxonomy, benchmark, directionality, materiality, event normalization, or category ownership changed.

## Regression coverage

Frozen tests now cover:

1. two positive substantive categories plus insufficient categories: Mixed invalid, positive eligible;
2. two negative substantive categories plus insufficient categories: Mixed invalid, negative eligible;
3. positive plus negative substantive categories: Mixed eligible;
4. substantive Mixed plus positive category: Mixed eligible;
5. all six insufficient: Overall Insufficient Data eligible;
6. prompt language distinguishing missingness/limitations from conflict.

These tests validate eligibility rather than deterministically selecting the final model rating.

## Live revalidation

| Ticker | Attempts | Overall | Substantive categories | Grounding | Semantic review |
| --- | ---: | --- | --- | --- | --- |
| MSFT | 2 | Mixed | Industry Mixed; Market Mostly Positive | Pass on retry | Valid current conflict inside Industry; gaps described without being treated as negative |
| XOM | 1 | Mostly Positive | Industry and Market Mostly Positive | Pass | Missing issuer/expectation data remained limitations, not conflict |
| PLTR | 1 | Mostly Positive | Industry and Market Mostly Positive | Pass | Upcoming earnings remained informational |
| NVDA | 1 | Very Positive | Earnings Very Positive; Industry/Economic Mixed; Market/Geopolitical Mostly Positive | Pass | Legitimate Mixed categories remained available to synthesis |

MSFT's first attempt repeated the original invalid pattern: Industry and Market were Mostly Positive while Overall was Mixed. The unchanged validator rejected it. On the permitted retry, the model classified the currently supplied Industry evidence as substantive Mixed—positive group health but conflicting company-relative windows—making Overall Mixed eligible. This is a valid live result and confirms that the remediation did not weaken the validator.

All accepted summaries remained category-grounded. Insufficient categories were not negative evidence. Watch selections resolved to real earnings events for MSFT, XOM, and PLTR; NVDA had no supplied upcoming event and no watch item. No response invented consensus, expected move, beat probability, date, or cross-category support.

## Cache version behavior

The process cache key already includes prompt version. Advancing from `outlook-analyst-2.4` to `outlook-analyst-2.5` therefore produces a distinct key naturally. No cache deletion or cache architecture change was made. Schema remains `2.2`.

## Latency, token usage, and cost

For the four accepted revalidation outputs:

- Average latency: **5.00 seconds**.
- Average input tokens: **6,763**.
- Average output tokens: **702**.
- Average total tokens: **7,465**.
- Successful-output token estimate: **$0.0329**.
- Approximate five-request cost including MSFT's rejected first attempt: **$0.0412**, using the accepted-call average for the failed attempt because failed-call usage was unavailable.

Pricing follows Phase 6A.3A: `gpt-5.4-mini` at $0.75/M uncached input tokens and $4.50/M output tokens. Cached-input detail is not retained, so input is conservatively treated as uncached.

## Audit serializer resolution

The retained Phase 6A.3A audit CLI now:

- merges Industry diagnostics across both evidence records rather than selecting one incomplete record;
- uses actual context diagnostics fields;
- iterates fixed category objects correctly;
- records the imported prompt/schema versions rather than stale literals;
- accepts an explicit bounded ticker subset for revalidation.

These changes are audit-only and do not affect production serialization or runtime behavior.

## Validation

- Focused AI tests: **61 passed**.
- Relevant Outlook regression suite: **594 passed**, two existing FastAPI deprecation warnings.
- Full backend: **860 passed, 46 skipped, 148 subtests passed**, two existing FastAPI deprecation warnings.
- Frozen evaluation corpus: **535 passed, 0 failed** across 40 cases and 65 historical replays.
- Live revalidation: four tickers, five generations, one retry, four grounded results.
- `git diff --check`: passed after final artifacts.

No automated test made an OpenAI request.

## Intelligence freeze

The following layer is frozen at prompt `outlook-analyst-2.5` and schema `2.2`:

- deterministic fact architecture;
- category ownership;
- directionality and materiality;
- Company, Earnings, Economic, Market, Industry Precision, and Geopolitical intelligence;
- AI context architecture;
- grounding architecture;
- Overall qualitative synthesis contract.

Future changes require a demonstrated defect or a separately approved feature phase. Phase 6B must not casually alter these contracts while changing presentation.

## Explicitly deferred capabilities

- production earnings-consensus provider;
- macro consensus/surprise provider;
- options-implied expected move;
- beat probability;
- broader licensed taxonomy/reference data;
- broader Company-event coverage;
- multi-worker/distributed AI caching;
- additional premium intelligence providers.

These are future enhancements, not freeze blockers.

## Next phase

**Phase 6B — Outlook UI Redesign.** Presentation work must consume the frozen intelligence contract without reopening its evidence, ownership, scoring, or grounding architecture.
