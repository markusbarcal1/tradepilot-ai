# Phase 6B.5C.2A.5J — Offline Filing-Index Relationship Discovery

## Outcome

A new versioned, index-enabled certification architecture is implemented and fixture-qualified without making any external request.

The identities are independent:

- Retrieval runner: `direct-q4-candidate-retrieval-2`
- Metadata discovery: `bounded-filing-window-item-202-1`
- Filing-index relationship policy: `sec-index-json-ex99-earnings-1`
- Financial parser: unchanged `direct-q4-1`

Version 1 remains intact and reproducible. Version 2 adds a filing-index step only after the selected primary document produces no accepted observation and exposes zero eligible primary-document relationships.

## Phase 5I evidence boundary

The live Phase 5I run established, for four fixed AAPL/NVDA targets:

- unique metadata rediscovery and exact candidate binding;
- successful HTTP 200 retrieval of each selected primary document;
- HTML-like primary content;
- zero `direct-q4-1` candidates and accepted observations;
- zero eligible relationships from the primary-document matcher; and
- no filing-index or exhibit request.

The sanitized artifact retained no filing body, candidate identity, URL, or exhibit metadata. It cannot establish whether a filing index lists an earnings exhibit. No real filing or index was inspected during this phase.

## Why parser changes are deferred

The Phase 5I result does not show that `direct-q4-1` is defective. It shows only that the selected primary 8-K documents did not contain a table recognized by the existing parser. The issuer-primary earnings material may be a separate exhibit discoverable through the filing relationship manifest.

Changing the financial parser before locating the intended issuer-primary document would conflate retrieval with financial qualification. Version 2 therefore changes only relationship discovery and continues to treat unsupported financial layouts as parser incompatibility.

## Filing-index representation

The architecture selects the official accession-scoped SEC archive `index.json` representation rather than scraping filing-index HTML.

The index URL is constructed deterministically from the already bound identity:

```text
https://www.sec.gov/Archives/edgar/data/{integer CIK}/{accession without dashes}/index.json
```

This needs no guessed filename, search endpoint, directory enumeration, ticker, or issuer calendar. Both CIK and accession pass existing strict identity checks before path construction.

The structured `directory.item` array supplies bounded relationship metadata used by the narrow normalizer:

- safe document basename;
- explicit exhibit type; and
- bounded description text used only for discovery classification.

Descriptions are discovery metadata, never financial evidence. No value, period, fiscal identity, or investment meaning is inferred from them.

## Index normalization and eligibility

`q4_filing_index.py` performs only:

```text
SEC filing index JSON -> bounded exhibit relationship metadata
```

It does not parse financial values or infer Q4.

Filtering is sequential:

1. Require a safe basename with no slash, traversal, query, fragment, or external URL.
2. Require explicit EX-99-family type.
3. Require bounded earnings semantics in the explicit description.
4. Collapse only the same safe document/type identity.
5. Return unavailable for zero, resolved for one, and ambiguous for more than one.

### EX-99 normalization

Accepted forms are `EX-99` or numeric suffixes such as `EX-99.1`, `EX-99.01`, and `EX-99.001`. Numeric suffixes normalize by integer value, so the latter three normalize to `EX-99.1`. Non-numeric suffixes and other exhibit families are rejected.

### Description semantics

The bounded matcher requires explicit terms such as earnings, financial results, quarterly results, press release, or results release. A lone EX-99 type is insufficient. The runner never chooses based on table order, proximity, filename familiarity, ticker text, or being the only non-primary document.

When multiple entries qualify, the target is ambiguous and no exhibit is retrieved.

## Conditional request architecture

Version 2 preserves the existing sequence:

1. Fetch current submissions once per issuer.
2. Rediscover and bind exactly one metadata candidate per target.
3. Retrieve and parse the selected primary document.
4. If the primary yields an accepted observation, stop.
5. Otherwise inspect existing primary-document relationships.
6. If exactly one primary relationship qualifies, retrieve it without an index request.
7. If multiple primary relationships qualify, fail closed as ambiguous.
8. Only if zero primary relationships qualify, retrieve one bound-accession `index.json`.
9. Normalize its bounded entries.
10. Retrieve an exhibit only when exactly one entry qualifies.
11. Feed that exhibit to unchanged `direct-q4-1` and stop.

No second exhibit, search, crawling, archive enumeration, browser fallback, or issuer-site request exists.

## Exact future request budget

The hard ceiling remains the proposed 14 because every target may independently require all three document steps:

| Request class | Per target | Per issuer | Aggregate |
| --- | ---: | ---: | ---: |
| Current submissions | shared | 1 | 2 |
| Selected primary document | 1 | 2 | 4 |
| Filing index | 1 | 2 | 4 |
| Earnings exhibit | 1 | 2 | 4 |
| **Total** | **3 document requests** | **7 requests** | **14 requests** |

A smaller absolute ceiling would prevent one of the four fixed targets from completing the authorized worst-case path. The ceiling is not a target: primary success uses no index or exhibit, and one primary relationship uses no index.

All issuer, target, and class allowances are non-transferable. Requests are charged before dispatch. Unused allowance cannot be donated. No retries or followed redirects are permitted.

## Transport safeguards

Version 2 reuses the existing strict SEC transport and fair-access gate. Every request requires:

- official SEC HTTPS host;
- bound, safe archive path;
- exact final URL and host;
- redirect rejection;
- one attempt;
- five-second prepared timeout;
- one-MiB prepared response ceiling;
- charge before dispatch; and
- bounded transport categories with status and bytes only when known.

No additional HTTP client was introduced.

## Diagnostic contract

The schema-1 versioned artifact identifies runner, discovery policy, index policy, and parser separately.

Per target it reports:

- discovery boundary, candidate cardinality, and binding state;
- primary attempt, transport/status/bytes, bounded content classification, relationship count, and parser counts/availability;
- whether index was required, attempted, transport/status/bytes, bounded `sec_index_json` classification, and sanitized index counters;
- document entries examined, EX-99 entries examined, sequential identity/type/description rejections, distinct eligible count, saturation, and ambiguity;
- exhibit attempt, transport/status/bytes, bounded content classification, parser candidates/accepted counts/rejections/conflict, and metric availability; and
- final state/reason plus top-level class, issuer, target, and aggregate accounting.

The index counter cap is 512 with an explicit saturation flag. Artifacts retain no index, filing, or exhibit body; arbitrary HTML; unrestricted descriptions or document lists; candidate accession; filename; URL; header; User-Agent/contact value; credential; or raw exception.

## Stop conditions

A target stops on discovery or boundary failure, candidate ambiguity, binding drift, unsafe identity, primary qualification, multiple primary relationships, transport failure, redirect, oversized/unsupported index, zero or multiple index candidates, exhibit failure, parser incompatibility, or financial conflict.

An upstream failure never spends downstream allowance. Other targets continue only within their independently reserved budgets.

## Fixture coverage

Synthetic offline tests cover:

- primary success with zero index/exhibit requests;
- one primary relationship with zero index and one exhibit;
- zero primary relationships with exactly one index request;
- zero, unrelated, one, or multiple index EX-99 entries;
- EX-99 numeric normalization;
- unsafe basename, external URL, cross-path/cross-accession escape prevention;
- deterministic accession-scoped index construction with no search or enumeration;
- index/exhibit redirects, timeouts, oversize outcomes, no retry, and byte semantics;
- charge-before-dispatch and non-transferable class/target/issuer ceilings;
- aggregate ceiling and target-local failure isolation;
- exact revenue and diluted EPS through the unchanged parser;
- Basic EPS exclusion, no EPS derivation through existing parser regressions, explicit parser incompatibility, and conflicts;
- diagnostic sanitization and production isolation;
- new acknowledgment and immutable CLI artifact behavior; and
- unchanged v1 retrieval, metadata-v2, and legacy certification behavior through the combined focused and full suites.

Synthetic entries, filenames, descriptions, and financial values are not issuer evidence.

## Parser and production isolation

`direct-q4-1` was not modified. The index parser is relationship-only and cannot produce a financial observation.

The v2 runner is absent from configured providers, research assembly, public APIs, and Analyze. Historical SEC/direct-Q4 remain disabled and unregistered. No frontend, DTO, database, migration, AI contract, prompt, grounding, score, rating, or historical-continuity behavior changed.

## Prepared future command

The new CLI requires a distinct 14-attempt acknowledgment:

```powershell
venv\Scripts\python.exe -m app.cli.certify_q4_index_retrieval --live --acknowledge "I ACKNOWLEDGE THE 14-ATTEMPT Q4 INDEX-ENABLED RETRIEVAL LIMIT" --output-dir ..\docs\diagnostics
```

It validates the exact identities, budgets, SEC configuration, fresh timestamped path, and overwrite refusal. It would write `phase6b5c2a5j-index-retrieval-<UTC timestamp>.json`.

**The command was not executed.**

## Validation results

All validation was offline:

- Focused discovery/retrieval/index/direct-Q4/certification/SEC-history tests: **159 passed in 4.62 seconds**.
- Earnings/research/structured/frozen-AI regressions: **122 passed, 2 warnings in 3.73 seconds**.
- Full backend suite: **1,035 passed, 46 skipped, 2 warnings in 19.33 seconds**.
- Skips are existing optional PostgreSQL cases; warnings are existing FastAPI `on_event` deprecations.
- `git diff --check`: **passed**. Explicit no-index checks of all phase files found no whitespace errors; Git emitted only LF-to-CRLF working-copy notices.

## Changed files

- `backend/app/services/outlook_structured/q4_filing_index.py`
- `backend/app/services/outlook_structured/q4_index_retrieval.py`
- `backend/app/cli/certify_q4_index_retrieval.py`
- `backend/tests/test_q4_index_retrieval.py`
- `docs/outlook-phase6b5c2a5j-offline-filing-index-discovery.md`

## Remaining unknowns and next step

No real index JSON has been retrieved or normalized. It remains unknown whether the four certified accessions expose structured EX-99 types/descriptions compatible with this policy, whether a unique exhibit will result, and whether any real exhibit will satisfy `direct-q4-1`.

The next step is operator review of the exact v2 identities, 14-request ceiling, index policy, diagnostics, and acknowledgment. A separately authorized live certification may then run exactly once. Parser or policy changes must not be bundled into that authorization.

**NO EXTERNAL REQUESTS WERE MADE.**

**NO REAL FILING INDEX OR EXHIBIT WAS RETRIEVED.**

**DIRECT-Q4-1 WAS NOT MODIFIED.**

**THE INDEX-ENABLED RUNNER HAS NOT BEEN LIVE-CERTIFIED.**

**NO PRODUCTION INTEGRATION WAS PERFORMED.**

**A NEW EXPLICIT OPERATOR AUTHORIZATION IS REQUIRED BEFORE ANY LIVE INDEX OR EXHIBIT REQUEST.**
