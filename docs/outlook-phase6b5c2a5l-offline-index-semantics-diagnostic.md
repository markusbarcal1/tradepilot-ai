# Phase 6B.5C.2A.5L — Offline Index-Semantics Diagnostic

## 1. Outcome

A distinct, production-isolated metadata diagnostic is implemented and fixture-qualified. It can measure bounded semantics from `directory.item[].name`, `.type`, and `.description` after fresh same-run SEC candidate discovery and exact binding.

The diagnostic does not select an exhibit, retrieve a primary document or exhibit, invoke `direct-q4-1`, apply the EX-99 eligibility policy, or create financial evidence. No live command was executed.

## 2. Phase 5K evidence boundary

Phase 5K found no offline proof that `directory.item[].type` is an SEC exhibit-type field. Phase 5J retained only aggregate counts: 70 safe-name entries all failed the existing EX-99 normalization gate, while raw type tokens and descriptions were deliberately discarded.

This phase builds a measurement instrument for a separately authorized future run. It does not resolve the semantic uncertainty or alter `sec-index-json-ex99-earnings-1`.

## 3. Diagnostic identities

- Runner: `direct-q4-index-semantics-diagnostic-1`
- Diagnostic: `sec-index-semantics-1`
- Artifact schema: `1`
- Frozen discovery policy: `bounded-filing-window-item-202-1`
- Fixed targets: AAPL FY2024 Q4, AAPL FY2025 Q4, NVDA FY2025 Q4, NVDA FY2026 Q4

The diagnostic identity is intentionally separate from the unchanged `sec-index-json-ex99-earnings-1` eligibility policy.

## 4. Same-run ephemeral-binding architecture

For each issuer, a future run retrieves current submissions once. For each fixed target it then:

1. applies the unchanged bounded filing-window/Item 2.02 policy;
2. requires a uniquely resolved approved-10-K boundary and exactly one candidate;
3. repeats exact binding against the same submissions rows;
4. validates safe CIK/accession identity;
5. constructs only the bound accession-scoped official SEC `index.json` URL;
6. retrieves at most one index;
7. computes sanitized schema aggregates; and
8. stops the target.

The accession remains ephemeral and is not emitted. Old sanitized artifacts cannot shortcut binding. Discovery failure, ambiguity, or binding drift prevents the index request.

## 5. Exact future six-request budget

| Class | Aggregate maximum | Per target |
| --- | ---: | ---: |
| Current submissions | 2 | shared once per issuer |
| Filing index | 4 | 1 |
| Selected primary document | 0 | 0 |
| Earnings exhibit | 0 | 0 |
| Filing document | 0 | 0 |
| **Total** | **6** | **one document request** |

Per-issuer maximum is three. Allowances are non-transferable, charged before dispatch, and cannot be donated. Six is a ceiling, not a target.

## 6. Transport safeguards

The runner reuses the existing strict SEC transport and fair-access gate. Prepared live settings require:

- one attempt and zero retries;
- rejected, never followed, redirects;
- five-second timeout;
- one-MiB response ceiling;
- official SEC HTTPS host validation;
- no query, fragment, traversal, search, archive enumeration, arbitrary href, or ticker-built URL;
- bounded transport categories with status/bytes only when known; and
- validated User-Agent contact syntax without retaining or printing its value.

No second HTTP client was added.

## 7. Observed schema paths

Only these explicit paths are examined:

- `directory.item`
- `directory.item[].name`
- `directory.item[].type`
- `directory.item[].description`

The code does not recursively inspect unknown fields or crawl a generic schema. It records structure validity, bounded entry count/saturation, field presence/absence/null states, and the path identity that produced each diagnostic.

Names produce only present, absent, null, safe-basename, and unsafe/unrepresentable counts. Filenames are never emitted and never used to infer type.

## 8. Type-token representation contract

Type tokens are observational strings, not document-type conclusions.

- surrounding whitespace is removed;
- representable tokens are normalized to uppercase;
- grammar: first character alphanumeric, followed only by ASCII letters, digits, `.`, `-`, `_`, or `/`;
- maximum length: 32 characters;
- no EX-99 mapping, semantic conversion, filename derivation, or missing-value inference;
- non-strings, overlength values, and disallowed characters count as `other_or_unrepresentable` without retaining raw content;
- at most 16 distinct token identities are retained per target;
- further token observations increment overflow and set saturation without retaining new identities.

The output includes representable/unrepresentable counts, bounded token counts, retained distinct count, saturation, and overflow.

## 9. Description categorization contract

Raw descriptions are never retained. Values are truncated in memory to 512 characters only for matching and assigned one category by deterministic most-specific-first precedence:

1. `quarterly_results`
2. `financial_results`
3. `results_release`
4. `press_release`
5. `earnings`
6. `other`

Absent, null, empty, and non-string/unrepresentable states remain separately counted. Categories are observational and establish no eligibility or provenance.

## 10. Cross-tab contract

For retained normalized type tokens, the diagnostic counts `TOKEN|DESCRIPTION_CATEGORY` observations. Cross-tab identities are bounded by the same 16-token cap. When new token identities exceed the cap, those observations increment overflow and are excluded from identity-bearing cells. Saturation is explicit.

The cross-tab may reveal coexistence patterns in a later live diagnostic. It cannot promote a token to an exhibit or financial-evidence type.

## 11. Sanitized artifact schema

Top level includes schema, runner, diagnostic and discovery identities; mode and timestamp; a non-accession manifest; exact budgets/accounting; bounded request outcomes; and per-target results.

Per target includes:

- discovery boundary, cardinality, and binding states;
- index required/attempted, bounded transport outcome, status, bytes, and classification;
- entry structure/count/cap/saturation;
- name-path safety counts;
- type-path presence/null/representation/token/overflow counts;
- description-path presence/empty/category/unrepresentable counts;
- bounded cross-tab counts/saturation; and
- final state/reason and requests consumed.

Malformed JSON and invalid/missing/non-list `directory.item` fail closed without inventing observations.

## 12. Privacy and data-minimization boundary

Artifacts exclude index and submissions bodies, arbitrary JSON/strings, descriptions, filenames, document lists, accessions, primary-document identities, URLs, headers, User-Agent/contact data, credentials, raw exceptions, financial values/tables, and filing/exhibit bodies.

The diagnostic cannot become an archive browser: it retains only a fixed small token vocabulary and aggregate categories.

## 13. Stop conditions

A target stops on unresolved/ambiguous discovery, unresolved approved-10-K boundary, binding drift, unsafe CIK/accession, budget rejection, URL-policy rejection, transport failure, redirect, response-size failure, non-200 response, malformed JSON, or unsupported index structure.

Regardless of outcome, it stops immediately after one index attempt. There is no primary, exhibit, parser, alternate-accession, guessed-document, index-HTML, or archive-listing transition.

## 14. Fixture coverage

The 33-test focused suite covers exact identities and manifest; six-request/non-transferable budgets; charge-before-dispatch; retry/redirect/timeout/size behavior; bound index URL behavior; unavailable/ambiguous discovery and binding drift; one-index maximum; malformed and missing structures; non-dictionary entries; name safety; absent/null/representable/unrepresentable type states; whitespace/case/length/character rules; 16-token and 512-entry saturation; all description categories and precedence; cross-tab bounds; sanitization; no parser/financial transition; distinct live gating; immutable CLI output; frozen v1/v2/EX-99/parser identities; and production isolation.

Synthetic fixtures qualify internal behavior only. They do not establish actual SEC field semantics.

## 15. CLI and acknowledgment

Prepared module:

```text
app.cli.inspect_q4_index_semantics
```

Exact future acknowledgment:

```text
I ACKNOWLEDGE THE 6-ATTEMPT Q4 INDEX-SEMANTICS DIAGNOSTIC LIMIT
```

Live mode requires `--live`, exact acknowledgment, safe settings, validated contact syntax, and a fresh timestamped path under `docs/diagnostics`:

```text
phase6b5c2a5l-index-semantics-<UTC timestamp>.json
```

Existing output is never overwritten. Fixture mode remains available for offline qualification. The live CLI was not executed.

## 16. Production isolation

The new runner and normalizer are not registered with configured providers, research assembly, public API, Analyze, historical financial services, frontend, database/migrations, AI contracts, or scoring/rating.

The following remain unchanged and separately versioned:

- `direct-q4-1`
- `bounded-filing-window-item-202-1`
- `sec-index-json-ex99-earnings-1`
- `direct-q4-candidate-retrieval-1`
- `direct-q4-candidate-retrieval-2`

No historical continuity or financial acceptance state changed.

## 17. Validation

All checks were offline:

- New focused diagnostic tests: **33 passed in 2.02 seconds**.
- Combined discovery/retrieval/index/diagnostic/direct-Q4/certification/SEC-history suite: **192 passed in 2.72 seconds**.
- Earnings/research/structured/frozen-AI regressions: **122 passed, 2 warnings in 4.25 seconds**.
- Full backend suite: **1,068 passed, 46 skipped, 148 subtests passed, 2 warnings in 19.37 seconds**.
- Warnings are the existing FastAPI `on_event` deprecations.
- `git diff --check`: run after documentation creation.

## 18. Changed files

- `backend/app/services/outlook_structured/q4_index_semantics.py`
- `backend/app/services/outlook_structured/q4_index_semantics_runner.py`
- `backend/app/cli/inspect_q4_index_semantics.py`
- `backend/tests/test_q4_index_semantics.py`
- `docs/outlook-phase6b5c2a5l-offline-index-semantics-diagnostic.md`

## 19. Exact next step

Operator review of the **offline diagnostic implementation**.

Only after review may the operator separately authorize **one metadata-only live diagnostic execution** under the exact six-request ceiling. Implementation and authorization remain separate.

**NO EXTERNAL REQUESTS WERE MADE.**

**THE INDEX-SEMANTICS DIAGNOSTIC WAS NOT EXECUTED LIVE.**

**NO PRIMARY DOCUMENT OR EXHIBIT WAS RETRIEVED.**

**NO FINANCIAL OBSERVATION WAS CREATED.**

**SEC-INDEX-JSON-EX99-EARNINGS-1 WAS NOT MODIFIED.**

**DIRECT-Q4-1 WAS NOT MODIFIED.**

**NO PRODUCTION INTEGRATION WAS PERFORMED.**

**A NEW EXPLICIT OPERATOR AUTHORIZATION IS REQUIRED BEFORE ANY LIVE DIAGNOSTIC REQUEST.**
