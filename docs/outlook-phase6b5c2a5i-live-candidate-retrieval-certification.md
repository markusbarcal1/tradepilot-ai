# Phase 6B.5C.2A.5I — Live Candidate-Retrieval Certification

## Result

The single authorized execution of `direct-q4-candidate-retrieval-1` completed within all request ceilings. Metadata rediscovery and candidate binding succeeded for all four fixed targets. Each selected primary document returned HTTP 200 and was classified `html_like`.

The unchanged `direct-q4-1` parser produced zero financial candidates from every primary document. Each target therefore required bounded exhibit discovery, but the already retrieved primary document exposed zero eligible exhibit relationships under the prepared EX-99 earnings/results rules. The runner stopped without requesting an exhibit or filing index.

No revenue or diluted-EPS observation was accepted.

## Authorization boundary

The operator authorized exactly one live CLI invocation with these hard ceilings:

- current submissions: 2 total, one per issuer;
- selected primary documents: 4 total, one per target;
- filing indexes: exactly 0;
- earnings exhibits: 4 total, one per target and only after an unqualified primary with exactly one safe relationship;
- per target: at most 2 document requests;
- per issuer: at most 5 HTTP attempts; and
- aggregate: at most 10 HTTP attempts.

Allowances were non-transferable. Every transaction was charged before dispatch. Retries and followed redirects were prohibited. The authorization expired when the one CLI invocation terminated; unused allowances did not survive.

No retry, browser investigation, manual request, supplementary SEC request, issuer-site request, Yahoo call, OpenAI call, or alternate-provider call occurred.

## Mandatory preflight

All product gates passed before the live invocation:

- Focused discovery/retrieval/direct-Q4/certification/SEC-history tests: **127 passed in 2.89 seconds**.
- Runner was exactly `direct-q4-candidate-retrieval-1`.
- Discovery policy was exactly `bounded-filing-window-item-202-1`.
- Parser was exactly `direct-q4-1` and was not modified for the run.
- The fixed AAPL FY2024/FY2025 and NVDA FY2025/FY2026 manifest was unchanged.
- Aggregate, class, issuer, and target ceilings were exactly 10; 2/4/0/4; 5; and 2 respectively.
- Fixture regressions confirmed non-transferable allowances.
- HTTP attempts were one, retries disabled, redirects rejected, and charge-before-dispatch active.
- The effective SEC User-Agent passed contact validation without being printed or retained.
- Response limit was exactly 1 MiB and timeout exactly five seconds.
- Official SEC HTTPS host and safe archive-path restrictions remained active.
- No previous retrieval artifact occupied the generated output path; overwrite remained prohibited.
- The runner remained absent from production providers, research assembly, the API, and Analyze.
- No filing-index request transition existed.
- The CLI constructed only `CandidateRetrievalRunner`.

An initial ad hoc structural-audit command contained a shell-quoting syntax error and exited before importing or running application code. It made no request and did not represent a failed product gate. The same read-only checks then executed successfully before live authorization was consumed.

## Identities and artifact

- Runner: `direct-q4-candidate-retrieval-1`
- Discovery policy: `bounded-filing-window-item-202-1`
- Financial parser: `direct-q4-1`
- Artifact schema: `1`
- Immutable artifact: `docs/diagnostics/phase6b5c2a5i-candidate-retrieval-20260930T155542060400Z.json`

The artifact contains bounded accounting and states only. It does not retain submissions bodies, document bodies, candidate accessions, filenames, URLs, item strings, headers, User-Agent/contact data, credentials, or raw exceptions.

## Exact HTTP accounting

### Totals

- Aggregate: **6 / 10**
- AAPL: **3 / 5**
- NVDA: **3 / 5**
- Current submissions: **2 / 2**
- Selected primary documents: **4 / 4**
- Filing indexes: **0 / 0**
- Earnings exhibits: **0 / 4**
- Retries: **0**
- Followed redirects: **0**
- Prohibited request classes: **none invoked**

### Attempt log

| Attempt | Issuer/target | Request class | Outcome | HTTP | Bytes |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | AAPL shared metadata | current submissions | success | 200 | 163,840 |
| 2 | AAPL FY2024 | selected primary document | success | 200 | 40,561 |
| 3 | AAPL FY2025 | selected primary document | success | 200 | 39,163 |
| 4 | NVDA shared metadata | current submissions | success | 200 | 159,785 |
| 5 | NVDA FY2025 | selected primary document | success | 200 | 24,731 |
| 6 | NVDA FY2026 | selected primary document | success | 200 | 25,487 |

Each target consumed exactly one document request. No target spent its exhibit allowance.

## Per-target results

All four targets had the same bounded state progression:

1. Approved-10-K boundary resolved.
2. Exactly one metadata candidate rediscovered.
3. Candidate identity bound exactly.
4. Selected primary document retrieved successfully.
5. Primary classified as HTML-like.
6. Parser invoked on the primary through `earnings_release_table`.
7. Parser produced zero candidates and zero accepted observations.
8. Exhibit discovery became required.
9. Zero eligible exhibit relationships were found.
10. No exhibit or filing index was requested.
11. Final state was unavailable with `parser_incompatible_no_eligible_exhibit`.

| Target | Boundary | Candidates | Binding | Primary HTTP / bytes | Primary parser candidates / accepted | Eligible exhibits | Exhibit requested | Final |
| --- | --- | ---: | --- | --- | --- | ---: | --- | --- |
| AAPL FY2024 Q4 | resolved | 1 | bound | 200 / 40,561 | 0 / 0 | 0 | no | unavailable |
| AAPL FY2025 Q4 | resolved | 1 | bound | 200 / 39,163 | 0 / 0 | 0 | no | unavailable |
| NVDA FY2025 Q4 | resolved | 1 | bound | 200 / 24,731 | 0 / 0 | 0 | no | unavailable |
| NVDA FY2026 Q4 | resolved | 1 | bound | 200 / 25,487 | 0 / 0 | 0 | no | unavailable |

For every target:

- primary request attempted: yes;
- primary transport: success;
- content classification: `html_like`;
- parser invoked: yes;
- parser source family: `earnings_release_table`;
- rejection categories: none, because the parser did not recognize any candidate row to reject;
- conflict state: false;
- revenue available: false;
- diluted EPS available: false;
- bounded exhibit discovery required: yes;
- filing-index request attempted: false;
- exhibit ambiguity: false;
- exhibit request attempted: false;
- exhibit parser invoked: no;
- target document requests: 1.

The empty rejection list must not be interpreted as positive parser validation. With zero parser candidates, no candidate reached metric-level rejection checks.

## Financial coverage decision

`direct-q4-1` accepted none of the eight desired observations:

| Observation | Established? | Reason |
| --- | --- | --- |
| AAPL FY2024 Q4 revenue | No | zero parser candidates; no eligible exhibit relationship |
| AAPL FY2024 Q4 diluted EPS | No | zero parser candidates; no eligible exhibit relationship |
| AAPL FY2025 Q4 revenue | No | zero parser candidates; no eligible exhibit relationship |
| AAPL FY2025 Q4 diluted EPS | No | zero parser candidates; no eligible exhibit relationship |
| NVDA FY2025 Q4 revenue | No | zero parser candidates; no eligible exhibit relationship |
| NVDA FY2025 Q4 diluted EPS | No | zero parser candidates; no eligible exhibit relationship |
| NVDA FY2026 Q4 revenue | No | zero parser candidates; no eligible exhibit relationship |
| NVDA FY2026 Q4 diluted EPS | No | zero parser candidates; no eligible exhibit relationship |

No value, unit, or financial provenance can be reported because no observation passed the frozen parser. Basic EPS was not substituted, and no value was derived or inferred.

## Comparison with metadata-only certification

Phase 5H established state 1: one plausible metadata candidate per target. This run independently reproduced that result and additionally established states 2 and 3: exact binding and successful primary retrieval.

It did not establish later states:

- no exhibit relationship was discovered;
- no exhibit was retrieved;
- no parser candidate was produced;
- no financial observation was accepted; and
- no historical continuity was achieved.

HTTP 200 confirmed transport success only. It did not establish parser compatibility or financial coverage.

## Remaining unknowns and historical continuity

The sanitized artifact cannot explain the real primary-document layout or why no relationship matched without retaining prohibited content. It remains unknown whether earnings material is represented through filing-index relationships, document metadata unavailable to the runner, a layout outside the bounded link matcher, or another unsupported structure. This phase provides no authorization to inspect those possibilities online.

Because none of the eight observations was accepted, the experiment adds no verified standalone-Q4 point to SEC history and does not improve five-quarter continuity. Existing missing-quarter and comparison gates must remain unchanged.

## Production status

The retrieval runner, direct-Q4 provider, and historical SEC path remain disabled/unregistered. No observation was persisted or integrated. No production provider, research DTO, frontend, database, AI contract, prompt, grounding rule, comparison gate, rating, or score changed.

## Recommended next offline step

Perform an offline retrieval-relationship audit using only the sanitized outcome and synthetic fixtures. Evaluate whether the architecture needs a separately versioned, tightly bounded filing-index discovery step, what exact SEC relationship metadata it would accept, how it would avoid arbitrary enumeration, and what new request ceiling would be required. Do not change the parser or perform another request during that audit.

Any future filing-index or exhibit request requires a new explicit authorization. The unused four exhibit allowances from this run are expired and cannot be reused.

## Post-run validation

All post-run checks were offline:

- Focused discovery/retrieval/direct-Q4/certification/SEC-history regressions: **127 passed in 2.26 seconds**.
- Earnings/research/structured/frozen-AI regressions: **122 passed, 2 warnings in 3.75 seconds**.
- Warnings are the existing FastAPI `on_event` deprecations.
- `git diff --check`: **passed**. Explicit no-index checks of the new report and artifact found no whitespace errors; Git emitted only LF-to-CRLF working-copy notices.

## Changed and generated files

- Generated immutable artifact: `docs/diagnostics/phase6b5c2a5i-candidate-retrieval-20260930T155542060400Z.json`.
- Added this report: `docs/outlook-phase6b5c2a5i-live-candidate-retrieval-certification.md`.
- No application code, configuration, policy, parser, production registration, frontend, database, or AI behavior was changed during this live certification phase.
