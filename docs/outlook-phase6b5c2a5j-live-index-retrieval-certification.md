# Phase 6B.5C.2A.5J — Live Index-Enabled Retrieval Certification

## Result

The one renewed, authorized execution of `direct-q4-candidate-retrieval-2` completed within every request ceiling. Metadata discovery, exact candidate binding, primary-document retrieval, and accession-scoped filing-index retrieval succeeded for all four fixed targets.

Each primary document returned HTTP 200 and was classified as HTML-like, but the unchanged `direct-q4-1` parser found zero candidates. Each corresponding SEC `index.json` returned HTTP 200 and was classified as `sec_index_json`. The bounded index policy examined 70 document entries in total; all 70 failed the approved EX-99-family type gate. No eligible exhibit was identified, no exhibit request was made, and no financial observation was accepted.

All eight requested revenue and diluted-EPS coverage decisions are **Not established**. This certification does not establish historical continuity or production readiness.

## Authorization boundary

The prior attempted certification stopped during a defective supplemental read-only diagnostic, invoked no live CLI, and made zero external requests. That authorization expired. The operator then renewed authorization for exactly one live CLI invocation with these non-transferable ceilings:

- 14 aggregate HTTP attempts;
- 2 current-submissions requests, one per issuer;
- 4 selected-primary requests, one per target;
- 4 filing-index requests, one per target;
- 4 earnings-exhibit requests, one per target;
- 7 attempts per issuer; and
- 3 document requests per target: primary, index, and exhibit.

Every request was charged before dispatch. The runner used one attempt per transaction, no retries, a five-second timeout, a one-MiB response ceiling, and rejected rather than followed redirects. The authorization expired immediately when the single CLI invocation terminated. The four unused exhibit allowances expired and cannot be reused.

No browser inspection, retry, supplementary SEC request, issuer-site request, Yahoo call, OpenAI call, or alternate-provider request occurred after the CLI terminated.

## Mandatory preflight

The mandatory offline product preflight passed before any external request:

- Focused discovery/retrieval/index/direct-Q4/certification/SEC-history tests: **159 passed in 2.48 seconds**.
- Runner: `direct-q4-candidate-retrieval-2`.
- Discovery policy: `bounded-filing-window-item-202-1`.
- Filing-index policy: `sec-index-json-ex99-earnings-1`.
- Financial parser: unchanged `direct-q4-1`.
- Fixed manifest: AAPL FY2024 Q4, AAPL FY2025 Q4, NVDA FY2025 Q4, and NVDA FY2026 Q4 only.
- Exact aggregate, class, issuer, and target limits matched the authorization.
- Fixture-qualified regressions covered non-transferable budgets, charge-before-dispatch, no retries, redirect rejection, bounded official-host URL construction, relationship cardinality, parser isolation, and production isolation.
- Runtime settings confirmed one HTTP attempt, five-second timeout, one-MiB document ceiling, and a contact-valid effective SEC User-Agent. Its value and contact address were not printed, logged, or retained.
- Semantic AST/import checks confirmed the live CLI constructs the exact v2 runner and the v2 module is not imported by production application modules.
- Filing-index URL behavior resolved only the bound CIK/accession to the accession-scoped official SEC `index.json` path.

Two optional local read-only diagnostics required correction before the live run. The first incorrectly expected a `fiscal_quarter` attribute on the manifest target even though Q4 identity is represented by the fixed target contract and fiscal-year/period-end fields. The second used a star import, which intentionally omitted the underscore-prefixed `_index_url` helper. Neither diagnostic reached the network or changed application code, configuration, policy, or parser. Both were corrected to precise semantic checks, and the corrected audit passed. These were diagnostic implementation errors, not failed product gates.

## Artifact and identities

- Artifact: `docs/diagnostics/phase6b5c2a5j-index-retrieval-20260930T165008139485Z.json`
- Artifact schema: `1`
- Mode: `live`
- Runner: `direct-q4-candidate-retrieval-2`
- Discovery policy: `bounded-filing-window-item-202-1`
- Index policy: `sec-index-json-ex99-earnings-1`
- Parser: `direct-q4-1`

The immutable artifact retains bounded accounting and diagnostic states. It does not retain response bodies, complete submissions payloads, URLs, filenames, headers, the User-Agent/contact value, credentials, or raw exceptions.

## Exact HTTP accounting

### Totals

- Aggregate: **10 / 14**
- AAPL: **5 / 7**
- NVDA: **5 / 7**
- Current submissions: **2 / 2**
- Selected primary documents: **4 / 4**
- Filing indexes: **4 / 4**
- Earnings exhibits: **0 / 4**
- Retries: **0**
- Followed redirects: **0**
- Prohibited request classes: **none**

### Attempt log

| Attempt | Issuer/target | Class | Outcome | HTTP | Bytes |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | AAPL shared metadata | current submissions | success | 200 | 163,840 |
| 2 | AAPL FY2024 Q4 | selected primary document | success | 200 | 40,561 |
| 3 | AAPL FY2024 Q4 | filing index | success | 200 | 1,994 |
| 4 | AAPL FY2025 Q4 | selected primary document | success | 200 | 39,163 |
| 5 | AAPL FY2025 Q4 | filing index | success | 200 | 1,890 |
| 6 | NVDA shared metadata | current submissions | success | 200 | 159,785 |
| 7 | NVDA FY2025 Q4 | selected primary document | success | 200 | 24,731 |
| 8 | NVDA FY2025 Q4 | filing index | success | 200 | 1,980 |
| 9 | NVDA FY2026 Q4 | selected primary document | success | 200 | 25,487 |
| 10 | NVDA FY2026 Q4 | filing index | success | 200 | 1,876 |

Each target consumed exactly two document requests: one primary and one index. No target spent its exhibit allowance.

## Per-target progression

All four targets followed the same bounded progression:

1. The approved-10-K upper boundary resolved.
2. Exactly one metadata candidate qualified.
3. Candidate identity bound successfully.
4. The selected primary document returned HTTP 200 and was classified HTML-like.
5. `direct-q4-1` ran against the primary and found zero candidates and zero accepted observations.
6. The primary exposed zero eligible bounded exhibit relationships.
7. The accession-scoped SEC filing index became eligible and returned HTTP 200.
8. The index was classified as `sec_index_json`.
9. Every examined entry failed the approved EX-99-family type gate.
10. Index cardinality was zero; therefore no exhibit was selected or requested.
11. Final state was `unavailable` with reason `no_eligible_index_exhibit`.

| Target | Discovery / binding | Primary HTTP / bytes | Primary candidates / accepted | Index HTTP / bytes | Entries / EX-99 / eligible | Exhibit | Final |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AAPL FY2024 Q4 | resolved, 1, bound | 200 / 40,561 | 0 / 0 | 200 / 1,994 | 18 / 0 / 0 | not requested | unavailable |
| AAPL FY2025 Q4 | resolved, 1, bound | 200 / 39,163 | 0 / 0 | 200 / 1,890 | 17 / 0 / 0 | not requested | unavailable |
| NVDA FY2025 Q4 | resolved, 1, bound | 200 / 24,731 | 0 / 0 | 200 / 1,980 | 18 / 0 / 0 | not requested | unavailable |
| NVDA FY2026 Q4 | resolved, 1, bound | 200 / 25,487 | 0 / 0 | 200 / 1,876 | 17 / 0 / 0 | not requested | unavailable |

For every target, the primary content classification was `html_like`; parser source family was `earnings_release_table`; rejection categories were empty; conflict state was false; and both revenue and diluted EPS remained unavailable. An empty rejection list is not acceptance: zero parser candidates reached metric-level rejection checks.

## Index normalization funnel

The index diagnostics use bounded, sequential first-failure counters with a 512-entry limit. No target saturated that limit.

| Target | Entries examined | Unsafe identity | Type rejection | EX-99 examined | Description rejection | Distinct eligible | Ambiguous |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AAPL FY2024 Q4 | 18 | 0 | 18 | 0 | 0 | 0 | 0 |
| AAPL FY2025 Q4 | 17 | 0 | 17 | 0 | 0 | 0 | 0 |
| NVDA FY2025 Q4 | 18 | 0 | 18 | 0 | 0 | 0 | 0 |
| NVDA FY2026 Q4 | 17 | 0 | 17 | 0 | 0 | 0 | 0 |
| **Total** | **70** | **0** | **70** | **0** | **0** | **0** | **0** |

This establishes only that the four accession-scoped indexes contained no entry qualifying under the frozen explicit EX-99-family type rule. It does not establish that no earnings information exists elsewhere, that a non-EX-99 document is financial evidence, or that eligibility rules should be weakened.

## Eight financial coverage decisions

Only a `direct-q4-1` accepted observation counts as Established. None was accepted.

| Observation | Decision | Evidence |
| --- | --- | --- |
| AAPL FY2024 Q4 revenue | **Not established** | zero primary parser candidates; zero eligible index exhibits |
| AAPL FY2024 Q4 diluted EPS | **Not established** | zero primary parser candidates; zero eligible index exhibits |
| AAPL FY2025 Q4 revenue | **Not established** | zero primary parser candidates; zero eligible index exhibits |
| AAPL FY2025 Q4 diluted EPS | **Not established** | zero primary parser candidates; zero eligible index exhibits |
| NVDA FY2025 Q4 revenue | **Not established** | zero primary parser candidates; zero eligible index exhibits |
| NVDA FY2025 Q4 diluted EPS | **Not established** | zero primary parser candidates; zero eligible index exhibits |
| NVDA FY2026 Q4 revenue | **Not established** | zero primary parser candidates; zero eligible index exhibits |
| NVDA FY2026 Q4 diluted EPS | **Not established** | zero primary parser candidates; zero eligible index exhibits |

No exact financial observations, units, or financial source provenance can be reported. No Basic EPS substitution, annual subtraction, EPS subtraction, rounded-YoY reverse engineering, manual inference, or other derived value was used.

## Comparison with Phase 5I

Phase 5I consumed 6 requests: two submissions and four primary documents. It established exact discovery/binding and HTTP-successful primary retrieval, but zero primary parser candidates and zero primary relationships stopped each target.

Phase 5J reproduced those results exactly and then consumed four newly authorized accession-scoped index requests. Each index retrieval succeeded, adding transport and normalized-index evidence. However, all 70 entries failed the approved exhibit-type gate, so Phase 5J still produced zero exhibit requests, zero exhibit parser invocations, and zero accepted observations.

The result narrows the evidence gap from “no relationship found in the primary” to “no approved EX-99-family earnings exhibit found through either the primary relationship path or the bounded filing-index path.” It does not justify expanding eligibility automatically.

## Historical continuity and remaining unknowns

No verified standalone-Q4 observation was added. Five-quarter continuity, comparable-period eligibility, and any historical Earnings visualization remain unchanged and unavailable where previously gated.

Remaining unknowns include whether these filings encode potentially relevant material under a different document type, whether another verifiable primary-source path is needed, and whether any such path can be qualified without weakening provenance or financial acceptance rules. The sanitized artifact deliberately cannot answer content-level questions outside its bounded metadata contract.

## Production status and recommended next step

The v2 runner, filing-index normalizer, direct-Q4 service, and historical SEC service remain disabled and unregistered. No observation was integrated or persisted. No production provider, Analyze path, public API, research assembler/DTO, comparison gate, database, frontend, frozen AI contract, grounding rule, rating, or score changed.

The recommended next step is a separate **offline document-type and SEC index-semantics audit** using the immutable bounded counters, saved prior artifacts, SEC form/exhibit rules already available offline, and synthetic fixtures. Its purpose should be to determine whether an additional exact, provenance-safe document-type relationship can be justified. It must not broaden eligibility, alter `direct-q4-1`, or initiate another request. Any future live request requires fresh explicit operator authorization.

## Post-run validation

All post-run validation was offline:

- Focused discovery/retrieval/index/direct-Q4/certification/SEC-history suite: **159 passed in 2.42 seconds**.
- Earnings/research/structured/frozen-AI suite: **122 passed, 2 warnings in 3.68 seconds**.
- The warnings are the existing FastAPI `on_event` deprecations.
- `git diff --check`: **passed** before this report was added; it emitted only existing LF-to-CRLF working-copy notices. A final check was run after documentation creation.

## Generated files

- Immutable live artifact: `docs/diagnostics/phase6b5c2a5j-index-retrieval-20260930T165008139485Z.json`.
- This certification report: `docs/outlook-phase6b5c2a5j-live-index-retrieval-certification.md`.

No application code or configuration was changed during this certification run.
