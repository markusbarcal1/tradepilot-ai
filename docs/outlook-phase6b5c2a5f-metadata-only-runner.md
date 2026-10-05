# Phase 6B.5C.2A.5F — Offline Metadata-Only SEC Discovery Diagnostic Mode

## Outcome

An isolated metadata-only diagnostic runner and CLI are implemented and fixture-tested. A future authorized invocation can make exactly one current-submissions request for AAPL and one for NVDA, apply the unchanged Phase 6B.5C.2A.5E earnings 8-K filters to the four fixed targets, write bounded schema-2 diagnostics, and stop.

This phase was offline only. The live mode was not invoked and no external request was made.

## Architecture

### Isolated runner

`MetadataOnlyDiscoveryRunner` lives beside the existing certification code so it can reuse:

- the immutable four-target `MANIFEST`;
- `StrictSecTransport` and its SEC fair-access gate;
- official-host validation;
- bounded schema-2 transport categories;
- `_rows()` submissions normalization; and
- the unchanged `_discover_eight_k()` sequential counter policy.

It does not call or reference:

- `_document_url()`;
- `DirectQ4Document`;
- `qualify_direct_q4()`;
- the direct-Q4 provider;
- 10-K, 8-K, filing-index, or exhibit retrieval;
- ticker mapping or historical submissions;
- issuer sites or alternate providers; or
- production research or Analyze.

The runner has no transition from submissions processing into document retrieval or financial parsing.

### Separate CLI

The operator entry point is `app.cli.inspect_q4_metadata`, separate from the full certification CLI. It provides mutually exclusive fixture and live modes. Default behavior cannot silently become live because one mode is required explicitly.

The CLI:

- validates and reserves a fresh timestamp-derived output path before runner execution;
- constrains output to `docs/diagnostics` or a descendant;
- refuses an existing artifact path;
- uses `FixtureTransport` for offline fixtures;
- uses the existing `StrictSecTransport` only after an explicit live gate;
- requires the existing effective SEC User-Agent configuration;
- requires one HTTP attempt, a five-second timeout, and at least one-second SEC spacing; and
- writes no source payload.

There is no startup hook, scheduled task, background task, API route, production provider registration, or Analyze integration.

## Exact request budget

The metadata runner's budget is structurally fixed:

| Request class | AAPL | NVDA | Aggregate |
| --- | ---: | ---: | ---: |
| Current submissions | 1 | 1 | 2 |
| Ticker mapping | 0 | 0 | 0 |
| Historical submissions | 0 | 0 | 0 |
| 10-K documents | 0 | 0 | 0 |
| 8-K/index documents | 0 | 0 | 0 |
| Exhibits | 0 | 0 | 0 |

Each issuer owns one non-transferable allowance. The aggregate and issuer counters are charged immediately before dispatch. Failure of AAPL does not give NVDA a second request, and vice versa. After one attempt for each issuer—or after either/both fail—the runner terminates.

The transport has no retry loop and the mode requires `http_attempts=1`. Redirect following is disabled; a redirect is a bounded failure rather than another request.

## Fail-closed safeguards

Before any runner dispatch, preflight requires:

- the effective User-Agent to pass the existing contact-address syntax validator;
- the manifest to equal the exact four approved targets;
- aggregate budget exactly 2;
- per-issuer budget exactly 1;
- enabled request classes exactly `current_submissions`;
- HTTP attempts exactly 1; and
- redirect following false.

The CLI additionally requires:

- explicit `--live`;
- exact acknowledgment `I ACKNOWLEDGE THE 2-ATTEMPT METADATA-ONLY LIMIT`;
- safe runtime timeout/attempt/spacing configuration; and
- a non-existing output path verified before runner construction.

Any mismatch fails before dispatch. These values are not general-purpose CLI options, so an operator cannot expand the manifest or budget through command arguments.

## Discovery behavior

For AAPL FY2024 Q4, AAPL FY2025 Q4, NVDA FY2025 Q4, and NVDA FY2026 Q4, the runner applies only the existing sequential rules:

1. form is `8-K` or `8-K/A`;
2. `reportDate` exactly equals the target period end;
3. `items` satisfies the existing explicit Item 2.02 matcher; and
4. primary document satisfies the existing safe-basename rule.

It does not relax report dates, introduce filing windows, guess accessions, retain candidate identities, or retrieve a qualifying candidate.

Per-target states are bounded to:

- `qualifying_candidate` with `qualifying_earnings_8k_found`;
- `ambiguous` with `multiple_plausible_earnings_8ks`;
- `source_unavailable` with `earnings_8k_unresolved`; or
- `request_failed` with a bounded transport category.

A qualifying state means metadata passed the unchanged filters. It does not certify an exhibit, document layout, revenue value, diluted EPS value, or standalone Q4 observation.

## Diagnostic artifact contract

The artifact retains only:

- `schema_version: 2`;
- runner identity `direct-q4-metadata-discovery-1`;
- offline/live mode;
- exact aggregate, per-issuer, and enabled-class budget accounting;
- one sanitized request record per attempted issuer;
- bounded transport outcome;
- HTTP status when known;
- response byte count when known, otherwise `null`;
- cache state (`miss`; this narrow runner has no shared response cache);
- fixed target ticker, CIK, fiscal year, Q4 identity, and period end;
- bounded final state and reason; and
- Phase 6B.5C.2A.5E `discovery_diagnostics` with the 4,096 cap and `counts_capped` flag.

It explicitly excludes:

- submissions bodies;
- complete or partial filing rows;
- qualifying or rejected 8-K accessions;
- primary document names;
- filing dates;
- item strings;
- unrelated filing metadata;
- candidate lists;
- URLs in the artifact;
- response bodies;
- headers or authorization data;
- raw exceptions;
- User-Agent and contact/email values; and
- credentials.

The output filename contains a UTC timestamp following the existing diagnostic convention. The artifact body does not add a timestamp because the existing schema-2 certification body does not use one.

## Offline tests

Fixture coverage proves:

1. Two successful submissions responses produce exactly two charged attempts.
2. Calls are exactly AAPL and NVDA current-submissions endpoints, once each.
3. The runner class contains no document URL, direct-Q4 document, or financial-parser path.
4. A timeout is attempted once and does not retry.
5. Redirect-host rejection is bounded and retains known response bytes.
6. One issuer's failure does not transfer its allowance.
7. User-Agent validation failure dispatches nothing.
8. A changed manifest dispatches nothing.
9. Wrong aggregate or issuer budgets dispatch nothing.
10. Enabling another request class dispatches nothing.
11. Enabling retries or redirects dispatches nothing.
12. All four targets receive existing sequential counters.
13. Exact-date, Item 2.02, and safe-document rejections remain observable.
14. Qualifying and ambiguous counts remain observable without identities.
15. Counter saturation remains capped at 4,096.
16. Artifact output excludes filing-level metadata and secrets.
17. Existing full certification behavior remains covered unchanged.
18. The mode is absent from production providers and Analyze.
19. Existing `direct-q4-1` parser tests remain unchanged and passing.
20. The output path is checked before runner construction and refuses overwrite.

## Validation results

All validation was offline.

- Focused certification, direct-Q4, and SEC-history suites:
  - `venv\Scripts\python.exe -m pytest tests\test_q4_certification.py tests\test_q4_direct.py tests\test_sec_history.py`
  - **80 passed in 2.12 seconds**.
- Relevant Earnings, research, structured, and frozen-AI regressions:
  - `venv\Scripts\python.exe -m pytest tests\test_outlook_earnings_events.py tests\test_outlook_research.py tests\test_outlook_structured.py tests\test_outlook_ai.py`
  - **122 passed in 4.99 seconds**, with two existing FastAPI `on_event` deprecation warnings.
- Full backend suite:
  - `venv\Scripts\python.exe -m pytest`
  - **956 passed, 46 skipped, 2 warnings in 18.18 seconds**.
  - Skips remain optional PostgreSQL coverage; warnings remain the existing FastAPI `on_event` deprecations.
- `git diff --check`: **passed**. Explicit no-index checks of the new/untracked service, CLI, test, and report files found no whitespace errors; Git emitted only existing LF-to-CRLF notices.

No SEC, browser, issuer-site, Yahoo, OpenAI, paid-provider, database, production, or other external operation occurred.

## Changed files

- `backend/app/services/outlook_structured/q4_certification.py`
- `backend/app/cli/inspect_q4_metadata.py`
- `backend/tests/test_q4_certification.py`
- `docs/outlook-phase6b5c2a5f-metadata-only-runner.md`

## Remaining limitations

- The mode has not been exercised against real SEC metadata.
- A qualifying metadata row is not a certified earnings-release exhibit or financial observation.
- Exact report-date and Item 2.02 requirements remain conservative assumptions.
- No candidate identifiers are retained, so the artifact alone cannot support later document retrieval.
- The diagnostic deliberately has no historical-submissions fallback.
- A failed submissions request leaves both issuer targets with the same bounded request failure and no discovery counters.
- The mode cannot diagnose the earlier 10-K document failures because it is prohibited from requesting documents.

## Future authorized command

From the `backend` directory, the command that would be used after a separate explicit authorization is:

```powershell
venv\Scripts\python.exe -m app.cli.inspect_q4_metadata --live --acknowledge "I ACKNOWLEDGE THE 2-ATTEMPT METADATA-ONLY LIMIT" --output-dir ..\docs\diagnostics
```

This command was documented only. It was not executed.

NO EXTERNAL REQUESTS WERE MADE.
THE METADATA-ONLY LIVE MODE HAS NOT BEEN AUTHORIZED OR EXECUTED.
A SEPARATE EXPLICIT OPERATOR AUTHORIZATION IS REQUIRED BEFORE ANY LIVE RUN.
