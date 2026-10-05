# Phase 6B.5C.2A — Live SEC Historical Coverage Certification

Date: 2026-09-27

## Decision

**No-go for Phase 6B.5C.2B production integration.** The bounded live run completed within the authorized SEC-only request budget, but the current normalizer accepted no historical observations for AAPL, NVDA, or ABTC. This result fails closed and is not evidence that the issuers lack reported results. It shows that the current Company Facts selection and fiscal-identity rules are not yet qualified against these live records.

No Analyze endpoint, public research DTO, frontend, frozen AI contract, scoring, authentication, database, or provider registration was changed. The historical service remains internal, disabled by default, and unregistered with Analyze.

## Authorized scope and safeguards

The operator authorized one cold attempt for each of AAPL, NVDA, and ABTC, with at most three official SEC requests per attempt and nine requests total. Yahoo, OpenAI, paid providers, and all other external providers were out of scope.

Before live access:

- the existing offline SEC history suite passed (`17 passed` before the live run);
- the diagnostic CLI was restricted to the three authorized symbols before constructing the live provider;
- an offline test proves an unauthorized symbol such as MSFT exits before provider construction;
- the SEC User-Agent was confirmed configured without printing its value;
- configuration was confirmed as three requests, one HTTP attempt, a five-second timeout, and a one-second fair-access interval;
- static inspection found no Yahoo or OpenAI dependency in the CLI or historical service;
- the configured Analyze providers did not include `sec_historical_financials`;
- the CLI retained the shared provider request gate, cache, timeout, and failure policy.

The smallest diagnostic extension added an AAPL/NVDA/ABTC live allowlist and an optional JSON artifact path. Artifacts contain no credentials.

## Actual retrieval results

| Ticker | Status | SEC requests | Source facts seen | Facts processed | Accepted observations | Recorded rejections |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| AAPL | Unavailable | 3 | 932 | 143 | 0 | 256 |
| NVDA | Unavailable | 3 | 625 | 181 | 0 | 119 |
| ABTC | Unavailable | 3 | 163 | 129 | 0 | 95 |
| **Total** | — | **9** | — | — | **0** | — |

Each ticker received exactly one cold attempt. No retry or expanded request budget was used.

Bounded evidence:

- `docs/diagnostics/phase6b5c2a-aapl.json`
- `docs/diagnostics/phase6b5c2a-nvda.json`
- `docs/diagnostics/phase6b5c2a-abtc.json`

## Per-ticker and per-metric coverage

Because no current observation was accepted, the result is the same for both supported metrics:

| Ticker | Metric | Accepted fiscal periods | Five consecutive quarters | Eight comparable quarters | Sequential comparisons | YoY comparisons |
| --- | --- | --- | --- | --- | --- | --- |
| AAPL | Revenue | None | No | No | None | None |
| AAPL | Diluted EPS | None | No | No | None | None |
| NVDA | Revenue | None | No | No | None | None |
| NVDA | Diluted EPS | None | No | No | None | None |
| ABTC | Revenue | None | No | No | None | None |
| ABTC | Diluted EPS | None | No | No | None | None |

There are consequently no accepted period starts/ends, normalized values, filing sources, amendment statuses, missing-period sequences, or eligible comparisons to certify. Missing data was not converted to zero and continuity was not inferred.

### AAPL

The first run exposed an ordering defect: the bounded source-fact cap was applied before selecting newest facts, while Company Facts arrived oldest-first for the relevant arrays. The rejection buffer was also exhausted by old Basic EPS diagnostics (`basic_eps_not_diluted: 256`). The artifact therefore cannot support a useful recent-period or annual-fact assessment. The source-cap ordering was corrected and protected offline after this attempt, but AAPL was not retried under the one-attempt rule. AAPL remains a certification failure for this run.

### NVDA

The bounded artifact records 69 `not_standalone_quarter`, 32 `ambiguous_quarterly_context`, 10 `annual_period_not_normalized_in_this_phase`, and 8 `basic_eps_not_diluted` rejections. Live data demonstrated that a later filing can repeat a prior comparative quarter while carrying the later filing's `fy`/`fp` metadata. Grouping solely by row `fy`/`fp` therefore combined different period dates and failed closed as ambiguous. No value, concept, or source was promoted through that conflict.

### ABTC

The bounded artifact records 47 `not_standalone_quarter`, 32 `ambiguous_quarterly_context`, 8 `annual_period_not_normalized_in_this_phase`, and 8 `basic_eps_not_diluted` rejections. It showed the same comparative-context fiscal-identity problem as NVDA, with fewer source facts and issuer-history complexity. No sparse-data exception was made.

## Fourth-quarter investigation

The 10-Q/10-Q/A-only rule necessarily prevents a continuous series across fiscal year-end because Q4 is normally represented in a 10-K rather than a 10-Q. The live bounded evidence contains annual `FY` facts in NVDA and ABTC, but the current diagnostic deliberately rejects them and does not retain enough raw context to certify a standalone Q4 value.

- **Directly reported standalone Q4:** none certified by this run. A short-duration fact in a 10-K would require explicit period/context qualification; `fp=FY` alone is insufficient.
- **Potentially derivable Q4:** annual minus accepted Q1–Q3 may be mathematically possible for additive flow metrics such as revenue, but was not attempted. It requires concept, unit, scope, duration, version, and restatement compatibility across all operands. EPS is not safely derived by subtracting year-to-date EPS because share-weighting and rounding can differ.
- **Unsupported or ambiguous:** all annual evidence in these artifacts remains in this class. AAPL's bounded rejection buffer did not retain annual diagnostics after the ordering failure.

A future Q4 design needs a separately approved, tested contract that distinguishes issuer-reported standalone quarterly facts from derived values, records every operand and derivation provenance, and never presents a derived observation as directly reported.

## Reconciliation with saved Phase 6B.5B evidence

The saved recent Earnings evidence and this historical run have different retrieval dates and normalization contracts. Phase 6B.5B accepts current issuer-primary earnings evidence; the historical service attempts a comparable multi-quarter Company Facts series.

| Issuer | Saved recent evidence | Historical result | Classification |
| --- | --- | --- | --- |
| AAPL | FY2026 Q3 revenue and diluted EPS evidence exists, with reported YoY comparisons rather than reconstructed prior amounts | No accepted historical revenue or diluted-EPS observation | **Missing observation**; exact value/unit/source comparison could not be performed |
| NVDA | FY2027 Q2 revenue and gross-margin evidence exists; diluted EPS was not part of the saved accepted display | No accepted historical revenue or diluted-EPS observation | Revenue: **missing observation**. Diluted EPS: no like-for-like saved metric. Gross margin is outside the historical service's supported metrics |

No disagreement was classified as a value mismatch because the historical side produced no accepted value. There was no silent change to either pipeline and no attempt to force agreement. The observed live grouping issue is an unresolved reporting-identity conflict, not evidence that the saved recent result is wrong.

## Recommended normalization changes

Before another live certification:

1. Derive fiscal identity from the fact's actual period/context and filing provenance rather than trusting a comparative row's host-filing `fy`/`fp` in isolation.
2. Reconcile repeated comparative facts deterministically by accession, period dates, concept, unit, value, form, and filing chronology; preserve real conflicts rather than treating every repeat as an amendment.
3. Apply source limits newest-first per supported concept/unit and prevent unsupported Basic EPS diagnostics from exhausting the bounded rejection buffer.
4. Add offline fixtures reproducing later filings that repeat prior quarters with changed host-filing fiscal labels.
5. Define a separate Q4 contract covering direct 10-K quarter contexts and, only if approved, transparent revenue derivation with operand-level provenance. Do not derive EPS by subtraction.
6. Expand diagnostics to summarize raw annual and candidate contexts without persisting full SEC payloads or exposing configuration.

These changes must remain internal until a new bounded certification produces accepted, comparable periods.

## Go/no-go criteria for Phase 6B.5C.2B

Proceed only after all of the following are demonstrated in offline tests and a separately authorized live re-certification:

- current and comparative quarter fiscal identity is stable across repeated filings;
- AAPL and NVDA current accepted revenue agrees with the same-period Phase 6B.5B evidence in metric identity, exact value, unit, and primary-source provenance;
- each displayed metric independently meets its declared minimum history requirement;
- conflicts, amendments, gaps, and concept changes remain fail-closed;
- Q4 observations are explicitly identified as directly reported or derived, with no ambiguous labeling;
- the total retrieval path remains bounded, cached, SEC-only, disabled by default, and outside Analyze;
- no UI or public DTO integration occurs until coverage and presentation requirements are approved.

The present decision is **no-go**.

## Validation

- Pre-live focused suite: `17 passed`.
- Post-ordering focused suite: `18 passed`.
- Relevant post-certification regression suite: `78 passed`, with two existing FastAPI `on_event` deprecation warnings.
- Live provider calls: exactly 9 SEC HTTP requests; zero Yahoo, OpenAI, paid-provider, or other external-provider requests.
- No database operation or migration was performed.
- No production integration was performed.

- `git diff --check`: passed for tracked changes; additional no-index checks passed for the new certification document and diagnostic JSON artifacts. The three pre-existing Phase 6B.5C.1 Python files initially reported an extra blank line at EOF; those endings were corrected and rechecked.

## Remaining operator decisions

1. Approve or reject a bounded fiscal-identity/repeated-context normalization phase.
2. Decide whether Q4 scope may include provenance-rich revenue derivation, or only directly reported standalone 10-K quarter contexts.
3. After offline qualification, explicitly authorize any second live AAPL/NVDA/ABTC certification; this phase does not reuse or expand the current nine-request authorization.
4. Keep Phase 6B.5C.2B production integration blocked until the go criteria above pass.

This three-ticker diagnostic does not establish broad issuer coverage.
