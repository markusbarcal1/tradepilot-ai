# Phase 6B.5C.2A.5B — Offline Live-Q4 Certification Runner

## Outcome

This phase implements an internal, offline-testable runner for a future bounded direct-Q4 SEC certification. No live certification was executed. The runner is separate from the existing fixture-only parser diagnostic, disabled from normal application execution, and absent from Analyze and configured production providers.

The implementation preserves the direct-Q4 parser rules from Phase 6B.5C.2A.4. It adds source discovery, a non-transferable request budget, security validation, deterministic diagnostics, and an operator-only live gate. It does not improve anticipated coverage by weakening fiscal, metric, unit, context, or provenance requirements.

## Architecture and changed files

- `backend/app/services/outlook_structured/q4_certification.py`
  - fixed certification manifest;
  - deterministic submissions and document discovery;
  - aggregate, issuer, and request-class budget ledger;
  - injected offline transport and strict live SEC transport;
  - URL, accession, document-name, exhibit-relationship, and response validation;
  - bounded diagnostic assembly and fail-closed outcomes.
- `backend/app/cli/certify_q4.py`
  - separate offline-fixture and explicitly gated live modes;
  - output containment and no-overwrite behavior.
- `backend/tests/test_q4_certification.py`
  - synthetic SEC metadata/document fixtures and runner safeguards.
- `docs/outlook-phase6b5c2a5b-certification-runner.md`
  - this implementation and operating record.

No frontend, database, public research DTO, parser rule, prompt, schema, scoring, Analyze route, provider registration, or production startup file changed in this phase.

## Fixed certification manifest

The manifest is defined in code and accepts no CLI expansion:

| Issuer | CIK | Target | Period end | Approved annual accession |
| --- | --- | --- | --- | --- |
| AAPL | `0000320193` | FY2024 Q4 | 2024-09-28 | `0000320193-24-000123` |
| AAPL | `0000320193` | FY2025 Q4 | 2025-09-27 | `0000320193-25-000079` |
| NVDA | `0001045810` | FY2025 Q4 | 2025-01-26 | `0001045810-25-000023` |
| NVDA | `0001045810` | FY2026 Q4 | 2026-01-25 | `0001045810-26-000021` |

The accessions identify annual filings only. The runner does not treat them as verified standalone-Q4 observations. Primary document names, earnings 8-K accessions, exhibit names, exact Q4 starts, and values must be discovered and qualified.

## Discovery rules

For each of the two fixed issuers, the runner:

1. Builds the current-submissions URL from the pinned CIK.
2. Reads the SEC recent-filings arrays through the injected or live transport.
3. Fetches at most one referenced historical submissions file only if an approved 10-K accession is absent from current metadata and one safe metadata file uniquely covers the target period.
4. Requires an exact approved 10-K accession and form match, then validates its primary document name.
5. Considers an earnings 8-K only when its report date exactly matches the target period end and its items metadata explicitly includes Item 2.02.
6. Fails closed if more than one qualifying 8-K remains.
7. Loads at most one 8-K primary document per target and selects at most one explicitly related EX-99 earnings/results/press-release link.
8. Requires the exhibit to remain inside the same CIK and accession archive directory.
9. Passes retrieved documents to the unchanged direct-Q4 normalizer.

The runner never scans unrelated filings, guesses a primary filename, selects an arbitrary 8-K, derives a fourth quarter, or changes target periods.

An unresolved exact 10-K identity stops that target branch. An unresolved or ambiguous 8-K/exhibit stops only that alternative-source branch; an already fetched 10-K remains available to the parser.

## Budget enforcement

The budget ledger has three simultaneous limits:

- 16 actual HTTP attempts for the complete run;
- 8 attempts per issuer; and
- per-issuer request-class limits:
  - current submissions: 1;
  - historical submissions: 1;
  - selected 10-K documents: 2;
  - selected 8-K primary/index documents: 2;
  - selected earnings-release exhibits: 2.

An attempt is charged immediately before transport dispatch. Failures, timeouts, rejected responses, and parser-incompatible responses remain charged. A cache hit is recorded without consuming an attempt, but the manifest and per-class discovery limits remain unchanged. An unused class allowance cannot be reassigned, and one issuer cannot use another issuer's allowance.

The offline all-current fixture uses 14 attempts: one current submissions response and six selected documents per issuer. A fixture that needs one historical submissions file per issuer reaches exactly 16. There are zero mapping requests and zero retries.

## Security and network safeguards

The live transport is present for a separately approved future phase but was not invoked here. Its boundaries are:

- HTTPS only;
- host restricted to `data.sec.gov` or `www.sec.gov`;
- no credentials, custom ports, queries, or fragments;
- serial execution;
- existing global SEC fair-access gate with at least one-second spacing;
- five-second command-level timeout requirement;
- one request per dispatch and no retry loop;
- at most 1 MiB per configured document/metadata response;
- redirects rejected rather than followed, preventing uncounted secondary requests or host escape;
- accessions matched to the SEC accession grammar;
- historical filenames restricted to the SEC submissions filename grammar;
- document names restricted to a basename without path separators or traversal;
- exhibit links revalidated after URL resolution and constrained to the selected accession directory.

Rejecting all redirects is stricter than validating a followed final host. The runner intentionally does not follow them because the existing shared client can follow redirects without exposing each transaction to the certification ledger. If SEC begins requiring a redirect for a selected endpoint, the run fails closed. Supporting redirects would require a later offline-tested manual redirect implementation that charges every hop.

Transport exceptions and rejected responses are represented with bounded reason codes. Raw exception text, authorization headers, response bodies, and secrets are excluded from diagnostics.

## Live execution gate

The new command is `python -m app.cli.certify_q4`. It has two mutually exclusive modes:

- `--fixture PATH` uses only an injected response map and is offline.
- `--live` constructs the strict SEC transport.

Live mode additionally requires:

- the exact acknowledgment `I ACKNOWLEDGE THE 16-ATTEMPT LIMIT` through `--acknowledge`;
- a configured SEC User-Agent containing operator contact information;
- exactly one configured HTTP attempt;
- a five-second timeout;
- at least one-second SEC spacing; and
- an output directory contained by `docs/diagnostics`.

The manifest and attempt ceilings are not CLI parameters. The command creates a timestamped artifact and refuses to overwrite an existing path. There is no default live behavior, startup hook, scheduler, background task, automatic retry, Analyze integration, or provider registration.

The live flag was not used during this phase.

## Diagnostic artifact contract

The bounded JSON document uses runner schema version `1` and records:

- the complete approved manifest;
- runner mode and direct-Q4 parser version;
- total, per-issuer, and per-class attempt usage;
- every cache read or attempted request with class, ordinal, requested URL, validated final host, cache state, bounded HTTP outcome, received byte count, and remaining budgets;
- per-target status, approved annual accession, resolved document identities, and accepted metrics;
- candidate and rejection counts;
- accepted direct-Q4 observations using the existing exact fiscal identity, concept, unit, value, context/table locator, source family, version, conflict, and comparison-eligibility contract; and
- coverage change from the saved historical state of missing direct Q4 to the certification result for each fixed target.

The artifact does not include full response bodies, raw exception details, headers, credentials, unrelated filings, or dynamically broadened candidates.

## Fail-closed outcomes

Per-target diagnostics distinguish:

- `accepted`: one or more current exact observations qualified;
- `source_unavailable`: a required source identity could not be uniquely established;
- `parser_incompatible`: authoritative source documents were found but yielded unsupported candidate structure;
- `metric_unavailable`: selected documents yielded no supported exact metric;
- `conflict`: qualifying observations conflict under existing version rules;
- `request_failed`: transport or response policy prevented source assessment.

A successful HTTP result is only retrieval evidence. It is not certification. Likewise, a parser-incompatible release is not described as the issuer lacking Q4 data.

## Offline fixtures and safeguard coverage

The new tests use injected submissions JSON, 10-K inline-XBRL, 8-K document relationships, and exhibit bodies. They cover:

- the exact issuer/period allowlist and approved annual accessions;
- current and one-file historical submissions discovery;
- exact document resolution;
- unresolved and hostile primary document names;
- multiple plausible 8-Ks;
- missing and multiple exhibit behavior;
- every class limit, both issuer limits, and the aggregate limit;
- charge-before-dispatch on failure and timeout;
- oversized responses and no retries;
- redirect-host rejection;
- external, query-bearing, and traversal exhibit paths;
- cache-hit accounting without budget expansion;
- deterministic runner artifacts;
- secret and response-body exclusion;
- exact live flag, acknowledgment, User-Agent, and output-directory gates;
- fixture CLI execution with zero external requests; and
- absence of Analyze, database, AI, or configured-provider registration.

The existing direct-Q4 and Company Facts history tests continue to cover exact metric qualification, units, fiscal contexts, amendment/conflict behavior, bounded provider retrieval, and historical comparison rules.

## Validation results

All commands ran from `backend` with the repository virtual environment unless noted.

- New runner plus existing direct-Q4 and SEC-history suites:
  - `venv\Scripts\python.exe -m pytest tests\test_q4_certification.py tests\test_q4_direct.py tests\test_sec_history.py`
  - **53 passed in 2.01 seconds**.
- Relevant Earnings, research, structured, and frozen-AI regressions:
  - `venv\Scripts\python.exe -m pytest tests\test_outlook_earnings_events.py tests\test_outlook_research.py tests\test_outlook_structured.py tests\test_outlook_ai.py`
  - **122 passed in 3.64 seconds**, with two existing FastAPI `on_event` deprecation warnings.
- Full backend suite:
  - `venv\Scripts\python.exe -m pytest`
  - **929 passed, 46 skipped, 2 warnings in 18.17 seconds**.
  - The skips are the existing optional PostgreSQL coverage. The warnings are the existing FastAPI `on_event` deprecations in `app/main.py` and FastAPI's application wrapper.
- `git diff --check`: **passed**. Explicit no-index `--check` runs for all four new untracked files also reported no whitespace errors. Git emitted only the repository's existing LF-to-CRLF conversion notices.

No test used SEC, Yahoo, OpenAI, a paid provider, a browser, a production database, or another external service.

## Unsupported cases and limitations

- The current direct-Q4 parsers retain the narrow layout support documented in Phase 6B.5C.2A.5A. This phase does not broaden them.
- SEC submissions metadata may not make a single Item 2.02 candidate identifiable by exact report date. Such periods remain `source_unavailable`.
- Some 8-K primary documents may not expose an exhibit link in a form supported by the narrow relationship scanner.
- Redirects are rejected, including same-host redirects.
- Only one historical submissions file may be read per issuer. If targets require different historical files, unresolved targets remain unavailable rather than expanding the budget.
- Source-document retention is not implemented. Diagnostics retain bounded metadata and parsed observations, not source bodies.
- Live acceptance would not establish production display rights or authorize production integration.

## Proposed Phase 6B.5C.2A.5C execution procedure

Phase 6B.5C.2A.5C must be separately authorized by the operator. After authorization:

1. Re-run the offline certification, direct-Q4, SEC-history, and relevant regression tests without changing parser rules.
2. Confirm the exact manifest and ensure the output directory contains no path that the new run could overwrite.
3. Confirm `OUTLOOK_HTTP_ATTEMPTS=1`, a five-second timeout, at least one-second SEC spacing, the 1 MiB ceiling, and an SEC-compliant User-Agent without printing the User-Agent value.
4. Record that the approved ceiling is 16 attempts and that zero ticker-mapping requests are permitted.
5. Invoke the operator command once with `--live`, the exact acknowledgment, and the bounded diagnostics directory.
6. Do not re-run after a partial failure without new operator approval. A failed or timed-out attempt remains consumed in that run.
7. Review the artifact for request counts, final hosts, source identities, rejection states, conflicts, and accepted observations.
8. Run offline regressions again without adapting the parser to the live result.
9. Document findings and make a separate production-integration decision. Do not register the provider, modify the DTO/UI, or initiate another live run automatically.

This document and implementation do not authorize Phase 6B.5C.2A.5C, any live request, or production integration.
