# Phase 6B.5C.2A.5I — Offline Candidate-Retrieval Certification Architecture

## Outcome

A new isolated candidate-retrieval certification path is implemented and fixture-qualified. It is not registered with production and was not executed live.

The identities remain deliberately separate:

- Retrieval runner: `direct-q4-candidate-retrieval-1`
- Metadata discovery policy: `bounded-filing-window-item-202-1`
- Existing financial parser: `direct-q4-1`

The runner performs fresh metadata discovery and ephemeral candidate binding within the same run. It cannot retrieve a candidate from the immutable Phase 5H artifact because that artifact intentionally contains no candidate identity.

## Evidence boundary

The architecture uses repository code, the live-certified aggregate findings from Phase 5H, existing strict SEC transport behavior, the existing direct-Q4 parser, and synthetic fixtures. No real candidate accession, filename, filing date, HTML, filing index, exhibit, or financial value was obtained in this phase.

Phase 5H established one plausible metadata candidate for each fixed target, but its sanitized artifact cannot drive retrieval. A future run must rediscover each candidate from a newly authorized current-submissions response.

## Candidate-binding contract

After policy `bounded-filing-window-item-202-1` returns exactly one candidate, the runner binds this complete normalized identity in memory:

- ticker and CIK;
- target fiscal year and verified period identity;
- accession;
- form;
- filing date;
- report date;
- qualifying Item 2.02 string;
- safe primary-document basename.

The selected identity must match exactly one normalized submissions row. Accession and primary-document safety are rechecked before URL construction. Retrieval URLs are derived only from the bound CIK, accession, and primary document through the existing safe SEC archive-path constructor.

The runner fails before document dispatch when discovery returns zero or multiple candidates, identity matching drifts, or accession/document safety fails. Candidate identity remains ephemeral and is not emitted in the diagnostic artifact.

## Minimum-request audit

### Can the selected primary document be sufficient?

Yes. The existing parser's `earnings_release_table` path accepts an 8-K/8-K-A document containing an explicit “Fourth Quarter Ended” table with exact revenue or GAAP diluted EPS. The new runner therefore parses the selected primary document first.

### Does the parser require an exhibit?

No. `direct-q4-1` accepts a `DirectQ4Document` from the `earnings_release_table` source family regardless of whether the SEC document is the filing's primary document or a linked exhibit. An exhibit is needed only when the selected primary document produces no accepted observation.

### Is a separate filing index required?

No. Submissions metadata already supplies the selected primary-document basename. The existing bounded relationship parser can inspect explicit links in that retrieved primary document. Consequently the filing-index request ceiling is zero.

### How are exhibits constrained?

The existing relationship logic requires an explicit anchor with nearby EX-99 identity and earnings/results/press-release language. The resolved link must remain HTTPS on an official SEC host, have no query, fragment, or path traversal, use a safe basename, and remain in the selected accession's archive directory. Zero links is unavailable; multiple equally eligible links is ambiguous. Filenames are never guessed and arbitrary links are never crawled.

## Exact future request budget

| Request class | Per target | Per issuer | Aggregate |
| --- | ---: | ---: | ---: |
| Current submissions | shared issuer request | 1 | 2 |
| Selected primary document | 1 | 2 | 4 |
| Filing index | 0 | 0 | 0 |
| Earnings exhibit | 1 | 2 | 4 |
| **All classes** | **maximum 2 document requests** | **5 total requests** | **10 total requests** |

The four targets remain AAPL FY2024, AAPL FY2025, NVDA FY2025, and NVDA FY2026. Each target owns its primary and exhibit allowances. Issuer, target, and request-class allowances are non-transferable. A failed or unused allowance cannot be donated. Every HTTP transaction is charged before dispatch. Retries and followed redirects are disabled.

The ten-attempt ceiling is a maximum, not a target. A parser-qualified primary document stops the target after one document request, so the exhibit allowance remains unused.

## Retrieval sequence

1. Fetch current submissions once per issuer.
2. Normalize rows and rerun the fixed metadata policy independently for each target.
3. Continue only for exactly one candidate with a uniquely resolved approved-10-K boundary.
4. Bind and revalidate the complete candidate identity.
5. Retrieve exactly the selected primary document.
6. Classify it as bounded `html_like`, `text_like`, or `unsupported_binary` without retaining its body.
7. Invoke unchanged parser `direct-q4-1` as `earnings_release_table`.
8. If an observation is accepted, stop for that target.
9. Otherwise inspect the primary document for bounded explicit earnings-exhibit relationships.
10. Retrieve exactly one exhibit only when exactly one safe eligible relationship exists.
11. Invoke the unchanged parser on that exhibit and stop.

There is no speculative crawling, archive enumeration, issuer-site access, manual URL input, alternative provider, or hidden fallback.

## Transport safeguards

The runner reuses `StrictSecTransport` and the repository's SEC fair-access gate. It enforces:

- official SEC HTTPS hosts;
- validated final host and exact final URL;
- safe accession and basename construction;
- five-second timeout under the prepared CLI;
- one-MiB response ceiling under current settings;
- charge before dispatch;
- redirect rejection;
- zero retries; and
- bounded error categories with HTTP status and response bytes only when known.

No second general-purpose HTTP client was introduced.

## Parser isolation

`direct-q4-1` was not modified. The retrieval runner supplies a `DirectQ4Document` and consumes only its existing result. Existing rules remain authoritative, including directly reported standalone Q4 identity, exact GAAP revenue, exact diluted EPS, no Basic EPS substitution, no EPS subtraction, no reverse-engineered percentages, Decimal arithmetic, explicit quarterly tables, provenance, and fail-closed conflicts.

An unsupported real layout will remain parser incompatibility. Retrieval certification does not relax financial acceptance.

## Sanitized diagnostic contract

The schema-1 retrieval-certification artifact identifies the three independent versions and records only bounded states.

Per target it reports:

- discovery boundary status, candidate cardinality, and binding status;
- whether the selected-primary request was attempted;
- bounded transport outcome, known HTTP status, known bytes, and content classification;
- whether the primary produced an accepted parser observation;
- whether exhibit discovery was required;
- filing-index request attempted, which is always false under this version;
- eligible exhibit-reference count, ambiguity, exhibit request state, outcome, status, and known bytes;
- parser invocation, source family, candidate count, accepted count, up to 32 rejection categories plus saturation, conflict state, revenue availability, and diluted-EPS availability; and
- final bounded state/reason.

Top-level accounting reports aggregate, issuer, class, and per-target ceilings and attempts.

Artifacts do not retain document or submissions bodies, arbitrary HTML/text, candidate accessions, filenames, filing dates, item strings, URLs, link lists, headers, User-Agent/contact values, credentials, or raw exceptions. If future production financial evidence is ever authorized, bounded accession and SEC source URL belong in the existing `SourceDocument`/observation provenance contract—not in this diagnostic artifact. That is outside this phase.

## Stop conditions

A target stops on unavailable or ambiguous discovery, unresolved approved-10-K boundary, binding drift, unsafe identity, URL-policy failure, transport failure, redirect, oversized content, unsupported encoding/content, zero or multiple exhibits, parser incompatibility, or conflicting exact financial observations. No downstream allowance is spent after a target-local stop.

Other independently authorized targets may continue only within their own reserved allowances.

## Fixture coverage

The offline suite covers:

- one bound candidate and exactly one primary request;
- zero/ambiguous discovery with zero document requests;
- binding drift and unsafe accession/document rejection;
- parser-sufficient primary content with no exhibit/index request;
- deterministic one-exhibit retrieval;
- multiple, missing, hostile, and external exhibit relationships;
- impossibility of guessed filenames;
- redirect, timeout, oversized-response, and known/unknown byte behavior;
- no retry, charge-before-dispatch, non-transferable target/class/issuer allowances, and aggregate ceiling;
- parser incompatibility, exact revenue, exact diluted EPS, Basic EPS exclusion, no subtraction through existing parser regressions, and conflicting observations;
- artifact sanitization;
- exact live acknowledgment and pre-dispatch configuration gates;
- immutable artifact naming and non-overwriting output behavior;
- production isolation; and
- unchanged full-certification and metadata-only-v2 runners.

Synthetic fixture identities and values are not real issuer evidence.

## Production isolation

The new runner is not included in `configured_providers()`, research assembly, the public API, or Analyze. No DTO, frontend, database, migration, AI contract, prompt, grounding, scoring, or production configuration was changed. Historical SEC and direct-Q4 remain disabled/unregistered.

## Future live CLI

The prepared command uses a new retrieval-specific acknowledgment:

```powershell
venv\Scripts\python.exe -m app.cli.certify_q4_candidate_retrieval --live --acknowledge "I ACKNOWLEDGE THE 10-ATTEMPT Q4 CANDIDATE-RETRIEVAL LIMIT" --output-dir ..\docs\diagnostics
```

The CLI requires `--live`, validates the exact runner budgets and current SEC configuration, refuses output overwrite, and would create `phase6b5c2a5i-candidate-retrieval-<UTC timestamp>.json`.

**The live command was not executed.**

## Validation results

All validation was offline:

- Focused discovery/retrieval/direct-Q4/certification/SEC-history tests: **127 passed in 2.47 seconds**.
- Earnings/research/structured/frozen-AI regressions: **122 passed, 2 warnings in 3.73 seconds**.
- Full backend suite: **1,003 passed, 46 skipped, 2 warnings in 19.74 seconds**.
- Skips are existing optional PostgreSQL cases; warnings are existing FastAPI `on_event` deprecations.
- `git diff --check`: **passed**. Explicit no-index checks of the phase files also found no whitespace errors; Git emitted only LF-to-CRLF working-copy notices.

## Changed files

- `backend/app/services/outlook_structured/q4_discovery_policy.py`
- `backend/app/services/outlook_structured/q4_candidate_retrieval.py`
- `backend/app/cli/certify_q4_candidate_retrieval.py`
- `backend/tests/test_q4_candidate_retrieval.py`
- `docs/outlook-phase6b5c2a5i-offline-candidate-retrieval-architecture.md`

## Remaining unknowns and recommended next step

No real primary filing or exhibit layout has passed through this runner. It remains unknown whether each live candidate's primary document contains a parser-sufficient table, exposes exactly one eligible exhibit, uses a supported encoding, or yields accepted revenue/EPS observations.

The next step is a separate operator review of this exact runner, budget, diagnostic contract, and acknowledgment. Only a new explicit authorization may permit one bounded live execution. That authorization should not include production integration or parser changes. Any post-run parser limitation should return to an offline engineering phase rather than being relaxed during certification.

**NO EXTERNAL REQUESTS WERE MADE.**

**NO REAL FILING OR EXHIBIT WAS RETRIEVED.**

**THE RETRIEVAL RUNNER HAS NOT BEEN LIVE-CERTIFIED.**

**NO PRODUCTION INTEGRATION WAS PERFORMED.**

**A NEW EXPLICIT OPERATOR AUTHORIZATION IS REQUIRED BEFORE ANY LIVE DOCUMENT RETRIEVAL.**
