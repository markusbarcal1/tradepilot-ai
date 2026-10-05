# Phase 6B.5C.2A.1 — Offline Historical SEC Normalizer Corrections

Date: 2026-09-27
Status: offline corrections complete; live re-certification and production integration remain blocked

## Outcome

The internal historical SEC normalizer now resolves a fact's represented fiscal period separately from the host filing's fiscal labels, recognizes repeated comparative disclosures, selects bounded supported sources without starving a metric, and can accept directly reported standalone Q4 facts from qualified 10-K/10-K/A contexts.

This phase made no provider request. The saved AAPL, NVDA, and ABTC certification artifacts were used only as diagnostic evidence of the failure patterns; they do not contain the raw Company Facts contexts needed to replay or certify issuer coverage. All new qualification uses synthetic offline fixtures. Synthetic success is not live certification.

The service remains disabled by default and unregistered with Analyze. No public research DTO, recent Earnings comparison, AI contract, scoring, Financial Score, Valuation, authentication, frontend, database, provider, or dependency changed.

## Root causes and corrections

### Host-filing identity was mistaken for represented-period identity

SEC Company Facts can repeat an earlier comparative quarter in a later filing while attaching the later host filing's `fy`/`fp`. The old normalizer grouped those rows directly by `fy`/`fp`, causing different exact periods to collide as `ambiguous_quarterly_context`.

The correction first groups candidates by metric, concept, unit, and exact start/end dates. It then resolves a canonical reporting identity:

1. The submissions `reportDate` is retained for each accession.
2. A candidate whose exact period end equals that accession's report date is an identity anchor.
3. For a 10-Q/10-Q/A anchor, the explicit fact `fy` and `Q1`–`Q4` establish the represented fiscal identity.
4. For a short-duration 10-K/10-K/A anchor with `fp=FY`, the explicit fiscal year plus the filing context establishes Q4.
5. Later facts with the same metric, concept, unit, and exact period dates may inherit one unambiguous anchor identity even if their host-filing labels differ.
6. If no report-date anchor is available, an older 10-Q fact can use explicit Company Facts FY/FQ only when every occurrence of that exact context agrees.
7. Multiple anchors or claims that cannot be reconciled are rejected as `conflicting_fiscal_identity`; an unanchored annual-filing quarter is rejected as `unresolved_fiscal_identity`.

No calendar-month mapping is used. Period dates validate context identity but do not guess a fiscal quarter.

### Repeated comparative disclosures were treated as context ambiguity

After fiscal identity resolution, versions are grouped by canonical metric/FY/FQ and checked for exact concept and context consistency.

- An identical row with the same accession, value, dates, and unit is diagnosed as `duplicate_source_fact` and emitted once.
- The same value repeated in a later non-amended filing is retained as a provenance-bearing `duplicate`; the earliest qualified disclosure remains `current`.
- A later 10-Q/A or 10-K/A for the same canonical identity may supersede the original. Both observations remain, and only the selected amendment is comparison eligible.
- Differing non-amendment values remain `conflict`.
- A later non-amendment cannot silently override an amendment.
- Multiple amendments without a deterministic chronology/value result remain conflicted.
- Concept or exact-context differences inside one resolved fiscal period remain ambiguous and are rejected rather than merged.

Observation identifiers and official accession URLs remain tied to each retained source version.

### The source cap could preserve old facts and starve supported metrics

Supported fact arrays are now sorted newest-first within each concept/unit stream. Streams are interleaved under the existing global `max_source_facts` processing cap, preventing a dense revenue stream from consuming the entire budget before diluted EPS is assessed.

Unsupported Basic EPS remains diagnostic-only and is appended after supported-fact assessment. It is bounded to the configured quarterly horizon and can no longer exhaust the 256-entry rejection buffer before relevant rejection evidence is recorded.

The cold request budget, cache behavior, maximum processed-source count, quarterly horizon, annual diagnostic bound, and version bound are unchanged.

## Q4 acceptance criteria

A fact is accepted as directly reported standalone Q4 only when all of the following are true:

- the form is 10-K or 10-K/A;
- the SEC fact has explicit integer `fy` and `fp=FY`;
- exact start, end, filing date, value, accession, supported concept, and supported unit are present;
- duration is 70–105 days inclusive;
- the accession's submissions report date exactly equals the fact's period end;
- the resulting exact context and fiscal identity do not conflict with another anchor or concept;
- normal version/amendment rules can select an unconflicted current observation.

Full-year facts remain `annual_period_not_normalized_in_this_phase`. Long year-to-date contexts remain rejected. A short 10-K context without an exact report-date anchor is unavailable. No Q4 revenue or EPS is derived, subtracted, interpolated, or inferred.

## Offline fixtures and regression coverage

The focused synthetic tests now cover:

- a later filing repeating an earlier comparative quarter with a conflicting host-filing FY label;
- inheritance from the original exact report-date anchor;
- conflicting exact-date anchors failing closed;
- exact duplicate source rows;
- same-value repeated disclosures across accessions;
- genuine 10-Q/A and 10-K/A amendments;
- unresolved differing non-amendment values;
- newest-first source selection;
- fair processing across supported concept/unit streams under a small cap;
- supported rejections remaining visible ahead of bounded Basic EPS diagnostics;
- directly reported standalone Q4 versus full-year and unanchored 10-K facts;
- explicit missing quarters;
- incompatible units, concepts, and quarterly contexts;
- comparison eligibility for active compatible observations only.

The saved live artifacts corroborate why these cases matter but cannot establish that the corrected code now covers AAPL, NVDA, or ABTC. Another live run requires separate operator authorization.

## Remaining unsupported cases

- Comparative contexts without an exact report-date anchor when their explicit FY/FQ claims disagree.
- Conflicting report-date anchors for the same exact financial context.
- Standalone Q4 contexts absent from Company Facts or not represented with exact dates and supported concepts/units.
- Annual-minus-interim Q4 derivation, including all EPS subtraction.
- Custom taxonomies, IFRS facts, dimensions not preserved by Company Facts, non-USD values, and unsupported concepts.
- Definitive amendment relationships beyond exact canonical identity plus explicit amended form and chronology.
- Fiscal identities requiring calendar-month inference or external issuer-calendar assumptions.
- Historical acceptance timestamps and primary-document metadata absent from the bounded submissions response.
- Live coverage of any issuer after these changes.

All such cases remain unavailable, rejected, or conflicted.

## Validation

All validation was offline. No SEC, Yahoo, OpenAI, paid-provider, or other external request was made.

- Focused SEC history suite after final correction: included in the regression group below; all 24 focused tests passed.
- SEC history plus relevant Earnings/research/structured regressions: `84 passed`, with two existing FastAPI `on_event` deprecation warnings.
- Full backend suite: `900 passed, 46 skipped, 148 subtests passed`, with the same two deprecation warnings, in 18.12 seconds.
- No frontend test was required because no frontend or public presentation contract changed.
- `git diff --check`: passed. Additional no-index whitespace checks passed for the new/untracked phase files.

No database or migration command ran. No source-control operation, deployment, live certification, or production integration occurred.

## Readiness criteria for another bounded live certification

Do not proceed automatically. A separately authorized certification should retain the prior three-request-per-ticker ceiling and should proceed only after confirming:

1. the exact deployed diagnostic code includes report-date metadata and the corrected resolver;
2. offline fixtures remain green and the service remains disabled/unregistered;
3. artifacts capture resolved identity, original host FY/FQ, exact dates, concept, unit, accession, form, version status, and rejection reasons;
4. AAPL and NVDA current revenue can be reconciled with saved Phase 6B.5B evidence by exact period, value, unit, concept, and source;
5. diluted EPS is independently assessed and never substituted with Basic EPS;
6. Q4 observations are explicitly identified as direct 10-K/10-K/A facts and are not derived;
7. coverage and sequential/YoY eligibility are reported independently by metric;
8. any unresolved metadata pattern fails closed without expanding the request budget.

Only a successful, separately approved live certification can inform a later Phase 6B.5C.2B integration decision.
