# Phase 6B.5C.2A.5G — Earnings 8-K Date Semantics and Discovery Policy

## Decision

Recommend **replacing exact `reportDate` equality with a specifically defined bounded policy**, but only in a subsequent offline implementation phase followed by separately authorized metadata certification. This phase does not change either live runner.

The proposed association rule starts with an already verified issuer/CIK, fiscal year, fiscal-year end, and approved 10-K accession. It uses the uniquely resolved filing date of that approved 10-K as the upper boundary. An 8-K/8-K/A is eligible only when its filing date is strictly after the verified fiscal-year end and no later than the approved 10-K filing date, Item 2.02 is explicit, accession and primary-document identities are safe, and exactly one distinct candidate remains after exact-duplicate collapse. Zero candidates are unavailable; two or more are ambiguous. No ranking breaks a tie.

This is a design recommendation, not evidence that any AAPL or NVDA candidate satisfies it.

## Evidence boundary

The repository evidence used was limited to code, tests, retained diagnostics, existing issuer-primary evidence, and synthetic fixtures. The live Phase 5F artifact contains bounded counters, request outcomes, target identities, and period ends; it intentionally does not retain submissions rows, candidate dates, accessions, item strings, or document identities. Consequently this phase cannot reconstruct real candidate identities or test the proposed policy against issuer-specific rows.

Phase 5F established that both bounded current-submissions requests succeeded and that:

- AAPL had 105 8-K/8-K-A rows examined for each target; all 105 failed exact `reportDate` equality.
- NVDA had 61 8-K/8-K-A rows examined for each target; all 61 failed exact `reportDate` equality.
- No live row reached Item 2.02 or safe-primary-document evaluation.

Those counts prove that exact equality is the current bottleneck for the four targets. They do not reveal which alternate dates exist or prove that a qualifying earnings filing exists.

## SEC metadata-field audit

The existing `_rows()` adapter consumes the parallel arrays under SEC submissions `filings.recent` or an equivalent saved historical-submissions object. Its normalized row exposes:

| SEC submissions field | Existing normalized key | Available to discovery | Retained in 5F artifact |
| --- | --- | --- | --- |
| `accessionNumber` | `accession` | yes | no |
| `filingDate` | `filing_date` | yes | no |
| `reportDate` | `report_date` | yes | no |
| `form` | `form` | yes | no; only aggregate form counts |
| `items` | `items` | yes, coerced to a string | no |
| `primaryDocument` | `primary_document` | yes | no |
| `acceptanceDateTime` | none | no | no |
| `primaryDocDescription` | none | no | no |

`acceptanceDateTime` and `primaryDocDescription` may be fields supported by SEC submissions generally, but the current repository adapter does not copy them into discovery rows. They therefore cannot be inputs to the proposed policy without a separate normalization change and evidence review.

The fixed manifest provides issuer, CIK, fiscal year, fiscal-year period end, and approved annual 10-K accession. The matching submissions row can provide the approved 10-K filing date. The prototype requires that date to resolve uniquely; it does not guess it from an accession or fiscal calendar.

## Why exact `reportDate` failed

The production-independent discovery helper currently interprets `reportDate` as if it must equal the known fiscal-year end. The repository contains no retained issuer-row evidence establishing that an earnings 8-K's `reportDate` should carry that fiscal-period-end value. Synthetic fixtures previously encoded equality, but fixture design is not issuer evidence.

Live 5F counters demonstrate non-equality for every examined 8-K/8-K-A row under all four targets. Because filtering is sequential, the artifact establishes only that the values were not exactly equal; it cannot establish their meanings or whether any nonmatching row was an earnings filing. Exact equality therefore has demonstrated false-negative behavior while lacking retained evidence for its semantic premise.

## Candidate-policy comparison

### A. Fixed filing-date window after fiscal-year end

Inputs are the verified period end and a chosen number of days. The rule is deterministic and tolerates a nonmatching or missing `reportDate`, but the day count would be an unsupported universal assumption in current evidence. Too short creates false negatives under unusual announcement timing; too long can cross into unrelated 8-Ks or another quarter. Multiple events remain possible. This design is not recommended by itself.

### B. Period end through approved 10-K filing date

Inputs are the verified period end, approved 10-K accession, and the uniquely matched 10-K filing date. These inputs already exist or can be resolved from the same submissions rows. The issuer's actual annual filing supplies a deterministic upper boundary without ticker-specific timing. Using a strict lower bound prevents pre-period events; using an inclusive upper bound permits same-day earnings and 10-K filing.

The window can still contain unrelated 8-Ks or multiple earnings-related filings. It can miss an unusual earnings release filed after the 10-K, and it cannot establish earnings identity alone. It is appropriate only as period association combined with mandatory evidence gates.

### C. Mandatory Item 2.02 plus filing-date association

Item 2.02 is an explicit results-of-operations signal and sharply reduces unrelated 8-K false positives. It remains insufficient by itself because more than one Item 2.02 filing may occur within a window, amendments can coexist, and the item does not manufacture fiscal identity. Missing or malformed `items` metadata creates a deliberate false negative. This should remain mandatory, not merely ranked.

### D. Item 2.02 plus other retained SEC metadata

Safe accession and primary-document identity are useful safety/qualification gates. Form distinguishes 8-K from 8-K/A. `reportDate` may be retained diagnostically but has no demonstrated qualification semantics here. Acceptance time and primary-document description are unavailable to the current adapter, so they cannot responsibly rank candidates in this phase. Available metadata does not justify textual scoring or heuristic ranking.

### E. Bounded hybrid with fail-closed ambiguity

Combining B, C, form/accession safety, safe primary-document identity, exact-duplicate collapse, and fail-closed cardinality is deterministic and testable. It does not select by ticker, infer a period from an 8-K, or arbitrarily prefer proximity. Its principal false-negative risks are multiple legitimate candidates, missing metadata, or an earnings filing outside the annual-filing boundary. Its principal false-positive risk is a single Item 2.02 filing in the window that pertains to something other than the verified Q4; document qualification remains necessary before any financial observation can be accepted. This is the recommended design.

## Proposed deterministic algorithm

1. Accept only a pre-verified target containing issuer/CIK, fiscal year, fiscal-year end, and approved 10-K accession.
2. Find rows whose accession equals the approved accession and whose form is 10-K or 10-K/A.
3. Parse their `filingDate` values. Continue only if exactly one distinct valid filing date is established and it is after the verified period end; otherwise return unavailable.
4. Examine only rows whose form is 8-K or 8-K/A.
5. Require a valid `filingDate` satisfying `period_end < filing_date <= approved_10k_filing_date`. A missing date, pre/end-date row, or post-10-K row is ineligible.
6. Require the existing explicit, comma-delimited Item 2.02 matcher. Item 2.02 identifies a results disclosure; it does not assign fiscal identity by itself.
7. Require a syntactically safe accession and the unchanged safe primary-document basename. Do not retrieve anything during discovery.
8. Collapse only exact repeated metadata observations using accession, form, filing date, report date, items, and primary document. Do not collapse different accessions or an 8-K/A into its original filing.
9. If zero distinct candidates remain, return unavailable. If exactly one remains, return a plausible metadata candidate. If more than one remains, return ambiguous without ranking or choosing.
10. Treat discovery as candidate association only. Subsequent separately authorized retrieval and existing parser qualification would still have to establish a directly reported standalone-Q4 metric and provenance.

No calendar-month inference, fixed-day assumption, nearest-date ranking, ticker hardcoding, or fallback to arbitrary candidate order is permitted.

## Amendments and ambiguity

- **8-K followed by 8-K/A:** retain both as distinct candidates and return ambiguous. Current metadata does not prove supersession scope or allow safe automatic preference.
- **Multiple Item 2.02 filings:** return ambiguous even if one is nearer the period end or 10-K date.
- **Duplicate rows:** collapse only exact repeated reporting identity; conflicting fields remain distinct and therefore ambiguous where both qualify.
- **Missing `reportDate`:** do not reject solely for absence; the value is neither used to assign the period nor treated as positive evidence. Retain it for provenance if a later contract permits.
- **Missing/nonmatching items:** unavailable for that row because Item 2.02 remains mandatory.
- **Missing/invalid `filingDate`:** unavailable for that row because the period window cannot be established.
- **Unsafe/missing primary document or accession:** unavailable for that row; the existing safety rule remains intact.
- **Multiple equally plausible candidates:** ambiguous. Never select by array order, proximity, issuer, or hardcoding.

## Offline prototype and tests

`q4_discovery_policy.py` implements the algorithm as a pure helper. It is not imported by `_discover_eight_k()`, either CLI, either certification runner, provider registration, research assembly, or Analyze. It performs no I/O and has no retrieval or parser transition.

Synthetic-only tests cover:

1. nonmatching `reportDate` with one bounded Item 2.02 filing;
2. multiple non-earnings 8-Ks;
3. multiple Item 2.02 filings;
4. 8-K plus 8-K/A;
5. missing `reportDate`;
6. missing Item 2.02;
7. missing `filingDate`;
8. unsafe primary document;
9. a candidate after the approved 10-K;
10. a candidate on the fiscal period end;
11. exact duplicate rows;
12. no plausible candidate;
13. two equally plausible candidates; and
14. an unresolved approved-10-K filing boundary.

All synthetic accessions and dates are test constructs, not claims about AAPL, NVDA, or any real issuer.

## Remaining unknowns

- The live artifact does not retain real row dates, items, accessions, or primary documents, so real candidate counts under the proposed policy are unknown.
- The repository has not established whether issuer earnings 8-Ks normally fall before the approved 10-K, whether same-day filing order matters, or whether amendments should supersede originals.
- `reportDate` semantics for the target issuers remain unverified; this policy deliberately stops treating it as fiscal-period identity.
- Acceptance time and primary-document description are unavailable to the current discovery adapter.
- A single metadata candidate may still be unrelated to standalone Q4 metrics or parser-incompatible.
- Historical-submissions coverage may be required when a target row is outside the bounded current set; no retrieval is authorized here.

## Production status and next phase

Historical SEC and direct-Q4 remain disabled and unregistered. `_discover_eight_k()` remains unchanged and both live CLIs retain exact `reportDate` behavior.

The exact recommended next phase is an **offline runner-integration phase** that ports this algorithm into a new, versioned discovery function; preserves old behavior for existing artifacts; adds bounded sequential diagnostics for window, Item 2.02, identity, duplicates, and ambiguity; and proves through source-isolation tests that no request budgets or retrieval paths change. Only after that passes should the operator consider a fresh, separately authorized two-request metadata-only certification. No document retrieval should be included in that authorization.

## Validation

All checks were offline:

- Focused prototype/Q4/certification/SEC-history tests: **94 passed in 2.18 seconds**.
- Earnings/research/structured/frozen-AI regressions: **122 passed, 2 warnings in 3.75 seconds**.
- Full backend suite: **970 passed, 46 skipped, 2 warnings in 18.49 seconds**.
- Skips are the existing optional PostgreSQL cases; warnings are the existing FastAPI `on_event` deprecations.
- `git diff --check`: **passed**. Explicit no-index checks of all three new files also found no whitespace errors; Git emitted only LF-to-CRLF working-copy notices.

## Changed files

- `backend/app/services/outlook_structured/q4_discovery_policy.py` — offline-only pure prototype.
- `backend/tests/test_q4_discovery_policy.py` — synthetic policy coverage.
- `docs/outlook-phase6b5c2a5g-earnings-8k-date-policy.md` — this audit and recommendation.

**NO EXTERNAL REQUESTS WERE MADE.**

**NO LIVE DISCOVERY POLICY WAS CHANGED.**

**NO PRODUCTION INTEGRATION WAS PERFORMED.**
