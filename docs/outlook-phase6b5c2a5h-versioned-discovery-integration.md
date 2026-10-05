# Phase 6B.5C.2A.5H — Versioned Earnings-8-K Discovery Integration

## Outcome

The Phase 5G bounded filing-window policy is now integrated into an explicit, versioned metadata-only diagnostic path. Future metadata artifacts produced by this path identify:

- runner: `direct-q4-metadata-discovery-2`
- discovery policy: `bounded-filing-window-item-202-1`
- artifact schema: `2`

The full Q4 certification runner continues to use the legacy exact-`reportDate` helper. There is no fallback or automatic selection between policies. Historical artifacts remain immutable and retain the semantics of the runner identity that created them.

## Architecture

`q4_discovery_policy.py` contains a pure, deterministic metadata function. It performs no I/O and accepts only normalized submissions rows plus a pre-verified period end and approved 10-K accession.

`MetadataOnlyDiscoveryRunner` is fixed to policy `bounded-filing-window-item-202-1`. It calls the policy only after one bounded current-submissions response has been normalized. Its output exposes the policy identity at artifact level and inside each diagnostic block.

`Q4CertificationRunner` remains unchanged in effective behavior: it continues to invoke `_discover_eight_k()`, whose exact-`reportDate`, Item 2.02, and safe-primary-document sequence is retained for compatibility. The direct-Q4 financial parser was not changed.

The metadata CLI now creates non-overwriting files named:

`phase6b5c2a5h-metadata-discovery-v2-<UTC timestamp>.json`

This makes a future policy-v2 artifact visibly distinct from the immutable Phase 5F artifact.

## Schema compatibility

The artifact remains schema 2 because all changes are additive and self-describing:

- the new runner identity prevents old and new runner behavior from being conflated;
- the new top-level `discovery_policy` field states the exact algorithm;
- the diagnostic block is policy-specific and includes its own `policy_version`; and
- no existing schema-1 or schema-2 artifact is rewritten, migrated, or reinterpreted.

A schema increment is unnecessary because no existing field has changed meaning within an existing runner version. Consumers must use runner and policy identity rather than assuming that every schema-2 diagnostic uses the same discovery algorithm.

## Old versus new discovery behavior

| Behavior | Full certification runner | Metadata-only runner v2 |
| --- | --- | --- |
| Policy identity | legacy exact-reportDate behavior | `bounded-filing-window-item-202-1` |
| Fiscal identity | fixed verified target | fixed verified target |
| Date association | `reportDate == period_end` | `period_end < filingDate <= approved 10-K filingDate` |
| Item 2.02 | mandatory | mandatory |
| Safe primary document | mandatory | mandatory |
| Safe accession | document URL path validates later | mandatory during metadata discovery |
| Exact duplicates | remain separate | collapsed by exact reporting identity |
| Multiple candidates | ambiguous | ambiguous |
| Document retrieval | bounded paths exist in full runner | structurally absent |

There is no hidden fallback from the new filing-window policy to exact `reportDate`, or vice versa.

## Approved 10-K boundary resolution

For each fixed target, the policy:

1. accepts the already verified fiscal-period end and approved 10-K accession;
2. examines only 10-K/10-K/A rows when resolving the upper boundary;
3. collects filing dates only from rows matching the approved accession;
4. fails closed if a matching filing date is missing or invalid;
5. fails closed unless exactly one distinct valid date remains; and
6. rejects the boundary if it is on or before the fiscal-period end.

It never derives the boundary from accession structure, issuer calendars, ticker-specific dates, proximity, or array order.

## Candidate algorithm

After the boundary resolves:

1. Reject non-8-K/8-K-A forms.
2. Reject a missing or invalid filing date.
3. Reject filing dates on or before the verified fiscal-period end.
4. Reject filing dates after the approved 10-K boundary; allow a candidate filed on the 10-K date.
5. Require the existing explicit comma-delimited Item 2.02 semantics.
6. Require a safe SEC accession identity.
7. Require the existing safe primary-document basename.
8. Collapse only exact duplicates matching accession, form, filing date, report date, items, and primary document.
9. Return unavailable for zero distinct candidates, plausible for exactly one, and ambiguous for more than one.

An 8-K and 8-K/A remain distinct. Different accessions never collapse. The algorithm never chooses the nearest, first, or last candidate.

## Bounded diagnostic contract

Every successful metadata assessment reports these sanitized controls and counts:

- `policy_version`
- `count_semantics`
- `count_limit`
- `counts_capped`
- `upper_boundary_status`
- `metadata_rows_examined`
- `approved_10k_rows_examined`
- `approved_10k_accession_matches`
- `invalid_or_missing_10k_filing_dates`
- `distinct_approved_10k_filing_dates`
- `rows_rejected_by_form`
- `eight_k_rows_examined`
- `rows_rejected_by_missing_or_invalid_filing_date`
- `rows_rejected_at_or_before_period_end`
- `rows_rejected_after_approved_10k_boundary`
- `rows_inside_valid_filing_window`
- `rows_rejected_by_item_202`
- `rows_rejected_by_unsafe_or_missing_accession`
- `rows_rejected_by_unsafe_or_missing_primary_document`
- `exact_duplicate_rows_collapsed`
- `distinct_qualifying_candidates`
- `ambiguous_qualifying_candidates`

Counts cap at 4,096. `counts_capped` is true when any raw count exceeds that bound. No candidate identities are retained in the artifact.

### Sequential semantics

Boundary resolution occurs first. If it fails, candidate filtering does not run and later zeroes mean “not evaluated,” not “passed.”

After boundary resolution, each 8-K/8-K-A row stops at its first failure: filing-date validity, lower boundary, upper boundary, Item 2.02, accession safety, then primary-document safety. `rows_inside_valid_filing_window` counts rows that passed the three filing-date gates; later counters partition subsequent outcomes. Exact duplicates are counted only after all eligibility gates pass.

The diagnostic output retains no submissions body, candidate accession, primary filename, candidate filing date, item string, filing row, URL, response body, header, raw exception, User-Agent/contact value, credential, or candidate list.

## Request-budget and transport invariants

The metadata-only runner remains limited to:

- AAPL current submissions: maximum 1 attempt;
- NVDA current submissions: maximum 1 attempt;
- aggregate: maximum 2 attempts;
- every other request class: disabled.

Issuer allowances are non-transferable. Each request is charged before dispatch. A failure receives no retry. Redirect following remains disabled and redirects are rejected. Manifest, budget, request-class, retry, redirect, and User-Agent failures occur before dispatch.

## Isolation

The metadata-only class has no transition to `_document_url()`, 10-K or 8-K document retrieval, filing-index retrieval, exhibit retrieval, `DirectQ4Document`, `qualify_direct_q4()`, or financial parsing. It remains absent from configured production providers and cannot be reached through production research or Analyze.

Historical SEC and direct-Q4 production features remain disabled/unregistered. No database, frontend, research DTO, frozen AI contract, prompt, schema, scoring, or deterministic intelligence behavior changed.

## Offline coverage

Tests cover all requested cases, including:

- nonmatching or missing `reportDate` with one otherwise valid candidate;
- lower and upper filing boundaries, including an allowed same-day 10-K candidate;
- missing filing date, missing Item 2.02, unsafe accession, and unsafe document identity;
- exact duplicate collapse and distinct-accession preservation;
- multiple Item 2.02 candidates and 8-K/8-K-A ambiguity;
- missing, invalid, and multiple approved-10-K filing dates;
- no-candidate behavior, sequential first-failure counts, saturation, and sanitization;
- exact two-attempt accounting, issuer isolation, no retries, and redirect rejection;
- pre-dispatch User-Agent, manifest, budget, and request-class gates;
- absence of document/parser/production paths;
- unchanged legacy exact-`reportDate` behavior in the full runner; and
- unchanged Earnings, research, structured, frozen-AI, and complete backend behavior.

Synthetic fixture filing dates are generated relative to each verified test period end. They are not real issuer evidence.

## Validation results

All validation was offline:

- Focused discovery/Q4/certification/SEC-history suite: **102 passed in 2.16 seconds**.
- Earnings/research/structured/frozen-AI regressions: **122 passed, 2 warnings in 4.14 seconds**.
- Full backend suite: **978 passed, 46 skipped, 2 warnings in 19.10 seconds**.
- Skips are existing optional PostgreSQL cases. Warnings are existing FastAPI `on_event` deprecations.
- `git diff --check`: **passed**. Explicit no-index checks of the phase files also found no whitespace errors; Git emitted only LF-to-CRLF working-copy notices.

## Changed files

- `backend/app/services/outlook_structured/q4_discovery_policy.py`
- `backend/app/services/outlook_structured/q4_certification.py`
- `backend/app/cli/inspect_q4_metadata.py`
- `backend/tests/test_q4_discovery_policy.py`
- `backend/tests/test_q4_certification.py`
- `docs/outlook-phase6b5c2a5h-versioned-discovery-integration.md`

## Pre-authorization review

If separately authorized in a future phase, the exact policy would be `bounded-filing-window-item-202-1` through runner `direct-q4-metadata-discovery-2`. The ceiling would be exactly two current-submissions attempts: one AAPL and one NVDA. No document retrieval is possible. The retained diagnostic fields are exactly the bounded fields listed above plus existing sanitized transport accounting and fixed target identity.

The future command would be:

```powershell
venv\Scripts\python.exe -m app.cli.inspect_q4_metadata --live --acknowledge "I ACKNOWLEDGE THE 2-ATTEMPT METADATA-ONLY LIMIT" --output-dir ..\docs\diagnostics
```

**That command was NOT executed in this phase.**

## Remaining limitations and next step

The new policy has only synthetic/offline qualification. The immutable 5F artifact lacks filing-level metadata and cannot be replayed through the new algorithm. The policy therefore has no verified AAPL/NVDA candidate counts, and a plausible metadata candidate would still not prove an earnings release, directly reported Q4 metric, parser compatibility, or production readiness.

The next step, only with a new explicit operator authorization, is one metadata-only live run of runner v2 under the two-request ceiling. Review its bounded counters before considering any document-retrieval authorization. Do not combine those authorizations.

**NO EXTERNAL REQUESTS WERE MADE.**

**THE NEW DISCOVERY POLICY HAS NOT BEEN LIVE-CERTIFIED.**

**NO DOCUMENT RETRIEVAL WAS PERFORMED.**

**NO PRODUCTION INTEGRATION WAS PERFORMED.**

**A NEW EXPLICIT OPERATOR AUTHORIZATION IS REQUIRED BEFORE ANY LIVE METADATA RUN.**
