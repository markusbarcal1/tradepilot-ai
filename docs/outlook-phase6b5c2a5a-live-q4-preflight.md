# Phase 6B.5C.2A.5A — Offline Direct-Q4 Live-Certification Preflight

## Status and scope

This phase is an offline, documentation-only preflight for a possible future bounded live certification of the direct fourth-quarter normalizer. It does not perform SEC, issuer, Yahoo, OpenAI, or paid-provider requests. It does not register the historical service with Analyze, enable the service, alter the research DTO, or change production behavior.

The preflight is limited to these issuer-period targets:

- AAPL fiscal 2024 fourth quarter
- AAPL fiscal 2025 fourth quarter
- NVDA fiscal 2025 fourth quarter
- NVDA fiscal 2026 fourth quarter

The repository and saved certification artifacts remain authoritative. Candidate identifiers that are not present in those artifacts remain unresolved rather than being guessed.

## Local evidence inventory

### Verified locally

The saved Phase 6B.5C.2A.2 diagnostics establish the following annual filing identities and annual period end dates. They do not establish that a qualifying standalone fourth-quarter fact exists in those filings.

| Issuer | CIK | Target | Annual period | Locally verified 10-K accession | Primary document | SEC-hosted 8-K/exhibit |
| --- | --- | --- | --- | --- | --- | --- |
| AAPL | `0000320193` | FY2024 Q4 | 2023-10-01 through 2024-09-28 | `0000320193-24-000123` | Unresolved | Unresolved |
| AAPL | `0000320193` | FY2025 Q4 | 2024-09-29 through 2025-09-27 | `0000320193-25-000079` | Unresolved | Unresolved |
| NVDA | `0001045810` | FY2025 Q4 | 2024-01-29 through 2025-01-26 | `0001045810-25-000023` | Unresolved | Unresolved |
| NVDA | `0001045810` | FY2026 Q4 | 2025-01-27 through 2026-01-25 | `0001045810-26-000021` | Unresolved | Unresolved |

The dates above identify the annual reporting periods and the target fourth-quarter end dates. The exact standalone Q4 start dates are not established by the retained artifacts. A future certification must obtain them from an explicit source context; it must not infer them by adding one day to a preceding quarter or by calendar-month heuristics.

The frozen NVDA evaluation material also identifies an issuer-newsroom release titled “NVIDIA Announces Financial Results for Fourth Quarter and Fiscal 2025,” published February 26, 2025, and describes a quarter ended January 26, 2025. That fixture is normalized evaluation evidence, not retained SEC filing provenance. It does not establish an SEC accession, filing document name, exhibit name, or SEC URL and therefore cannot be used as an SEC live-certification candidate.

### Unresolved locally

The repository does not retain enough authoritative metadata to identify any of the following without a future bounded SEC metadata request:

- the primary HTML document name for each verified 10-K accession;
- the relevant earnings 8-K accession for each target period;
- the primary document name for any such 8-K;
- the earnings-release exhibit document name and URL;
- the exact standalone-Q4 start date for any target;
- whether each target document exposes revenue and diluted EPS in a parser-compatible, explicitly standalone three-month context.

No accession, document name, exhibit number, URL, period start, or fact value is supplied by this preflight where local evidence does not establish it.

## Current direct-Q4 implementation

The direct-Q4 provider is disabled by default and is not registered with the Analyze path. It consumes explicitly selected `DirectQ4Document` inputs rather than discovering filings itself. Its existing limits include a request budget, serial request behavior, a response-size ceiling, cache support, official-host and accession validation, and fail-closed parsing.

The implementation accepts a value only when it can retain source provenance and establish an exact standalone fourth-quarter reporting context. It does not derive Q4 revenue from annual less interim results and does not derive diluted EPS by subtraction.

No production code change is warranted in this preflight. Until authoritative document identities are discovered, adding a live entry point or a static candidate manifest would encode unverified source metadata. The existing default-disabled and unregistered state is the correct safety posture.

## Parser compatibility assessment

### 10-K inline XBRL and XBRL

The current XBRL adapter supports inline `ix:nonFraction` facts and supported plain `us-gaap` facts. It requires:

- DEI fiscal-year identity;
- DEI fiscal period `FY`;
- a matching document period end;
- an exact-duration context with start and end dates;
- matching issuer identity when available;
- no dimensional context;
- a supported concept and exact compatible unit; and
- explicit nearby table language identifying “three months ended” or “fourth quarter ended.”

This is deliberately stricter than accepting any three-month fact hosted by a 10-K. It prevents annual and year-to-date facts from being mislabeled as Q4.

Known pre-certification limitations are:

- Explicit Q4 identity is associated through English text in the same parsed table. Different wording, headings outside the table, nested presentation structures, or facts separated from the heading may fail closed.
- A plain XBRL instance can expose facts and contexts but ordinarily does not preserve the presentation-table heading used by the current explicit-Q4 rule. A plain instance document by itself is therefore not expected to qualify a fact under the current adapter.
- Namespace aliases, unit QNames, fact scaling, sign presentation, and issuer-specific concept choices must be verified from the selected live documents. Current support must not be presumed from semantic similarity.
- The parser does not provide a general rendering model for complex `rowspan`/`colspan` presentation tables.

These are compatibility limitations, not permission to weaken the standalone-Q4 requirement. A rejected but plausible live document should be retained as diagnostic evidence for a later offline parser phase.

### 8-K earnings-release exhibits

The current earnings-release adapter is intentionally narrow. It expects:

- an exact ISO-style heading such as `Fourth Quarter Ended YYYY-MM-DD to YYYY-MM-DD`;
- recognized row labels, currently including `Revenue` and `GAAP Diluted EPS`; and
- explicit units such as `USD millions` or `USD/share`.

Real issuer releases commonly use human-readable month names, multi-row comparative column headings, scale declarations in captions, “three months ended” terminology, and nested cells. The retained local evidence does not demonstrate that any of the four target exhibits match the current grammar. The likely outcome for a normal issuer release is a safe rejection until a saved source document supports a narrowly tested offline extension.

A future live certification must not broaden parsing rules during the live run. It should save bounded diagnostic metadata and, only if explicitly approved, the permitted source artifact for subsequent offline correction.

## Proposed bounded live-certification design

This section specifies a future operation; it does not authorize or execute it.

### Candidate discovery

Use the locally verified CIK values as a fixed two-issuer allowlist. Do not make a ticker-to-CIK mapping request. For each issuer:

1. Request the SEC submissions record once.
2. Locate only filings needed for the two named target periods.
3. If the submissions record points to an older submissions file needed for those targets, request at most one such file for that issuer.
4. Match the already verified 10-K accession before selecting its primary document.
5. Identify at most one earnings 8-K candidate per target period using filing date, form, items metadata where present, and filing index metadata.
6. Fetch the selected 10-K primary document.
7. For the selected 8-K, fetch its primary document or filing index only to resolve a single earnings-release exhibit, then fetch at most one selected exhibit.
8. If a source identity remains unresolved within the cap, record `unavailable` and stop. Do not widen dates, scan unrelated filings, or consume spare requests speculatively.

The discovery process must not substitute issuer-newsroom URLs for the requested SEC-hosted source certification.

### Exact cold-cache attempt budget

The proposed aggregate maximum is **16 HTTP attempts**, with **8 attempts per issuer** and no retries:

| Request class | Per issuer | Aggregate | Purpose |
| --- | ---: | ---: | --- |
| Ticker/CIK mapping | 0 | 0 | CIKs are pinned by local verified artifacts |
| Current submissions metadata | 1 | 2 | Filing/accession/document discovery |
| Referenced historical submissions metadata | 1 | 2 | Only if required by the submissions manifest |
| Selected 10-K primary documents | 2 | 4 | One per named target period |
| Selected 8-K primary/index documents | 2 | 4 | At most one per named target period |
| Selected earnings-release exhibits | 2 | 4 | At most one per named target period |
| **Maximum** | **8** | **16** | Cold-cache hard ceiling |

This budget assumes no cache entries. An unused historical-submissions allowance may not be repurposed to scan extra filings or exhibits. Cache hits should be recorded but do not authorize more network attempts. An operator who requires live ticker-to-CIK re-verification must approve a revised aggregate ceiling of 17 before execution; it is outside this proposed 16-attempt plan.

Additional hard limits for the future run:

- issuer allowlist: exactly AAPL and NVDA;
- target-period allowlist: exactly the four periods listed above;
- candidate filings: at most two 10-Ks and two 8-Ks per issuer;
- documents per 10-K: one primary document;
- documents per 8-K: one primary/index document and one exhibit;
- concurrency: one;
- retries: zero;
- request timeout: five seconds;
- SEC request spacing: at least one second;
- response body: at most 1 MiB under the current provider limit;
- redirects: final host must still satisfy the official SEC-host policy;
- attempts are charged immediately before dispatch, including failed, timed-out, oversized, or unparsable responses.

The live runner should use a certification-specific budget rather than silently relying on the current direct-Q4 default request budget of four. Enabling the provider globally is not an acceptable substitute.

### Execution and artifact behavior

The future command should be an explicit operator-only certification command with all live behavior opt-in. It should require:

- a live flag;
- an explicit acknowledgment of the 16-attempt maximum;
- an SEC-compliant user agent already present in configuration;
- the fixed issuer/period manifest; and
- an output path outside production persistence.

For every attempted request, the diagnostic artifact should record:

- ordinal attempt number and remaining aggregate/per-issuer budget;
- issuer, CIK, target fiscal identity, requested form/source role;
- requested URL and final validated host;
- accession and document name when established;
- cache hit/miss;
- HTTP outcome, timeout/size rejection, and received byte count;
- parser adapter and deterministic acceptance/rejection reason;
- concept, unit, exact period dates, fact value, and provenance only for accepted facts;
- conflicts without choosing a winner when deterministic rules cannot resolve them.

Secrets, full response bodies, and unrelated filing content must not be written to diagnostics. If saving a source artifact becomes necessary for offline parser work, its scope, licensing/retention treatment, path, and redaction policy require separate operator approval.

## Acceptance and fail-closed rules

Certification is evaluated independently for each issuer, fiscal period, metric, and source document. A period is not “certified” merely because one metric or one source parses.

A direct Q4 observation is accepted only when all of the following are established:

- official source host and exact accession/document provenance;
- issuer identity;
- fiscal year and explicit fourth-quarter identity;
- exact standalone period start and end;
- supported concept identity;
- exact compatible unit and scaling;
- non-dimensional, non-annual, non-year-to-date context;
- deterministic value extraction; and
- no unresolved conflicting accepted observation.

Repeated identical facts may collapse only under the existing deterministic identity rules. Amendments must remain distinguishable from repetitions. Unresolved conflicts remain an explicit conflict/unavailable state.

Results must distinguish:

- `accepted`: exact source and fact satisfy every rule;
- `source_unavailable`: no permitted candidate was established within bounds;
- `parser_incompatible`: the selected source is authoritative but its structure is unsupported;
- `metric_unavailable`: source parsed but did not provide the requested compatible metric;
- `conflict`: multiple qualifying observations cannot be resolved deterministically;
- `request_failed`: transport, host, size, or HTTP policy prevented assessment.

No status may be converted to an inferred value.

## Coverage implications

The saved historical normalization diagnostics contain surrounding accepted quarters but omit direct Q4 observations. One compatible direct Q4 can bridge adjacent fiscal-year blocks and may be enough to meet a five-observation presentation minimum for a metric. That arithmetic is only a readiness indication; it is not certification of the Q4 fact or authorization for production integration.

Expected local sequence implications are:

- AAPL FY2024 Q4 could connect accepted FY2024 interim observations to FY2025 observations.
- AAPL FY2025 Q4 could connect FY2025 and FY2026 observations.
- NVDA FY2025 Q4 could connect FY2025 and FY2026 observations; existing incompatible or conflicting EPS observations remain independently governed.
- NVDA FY2026 Q4 could connect FY2026 and FY2027 observations where the surrounding facts remain accepted and comparable.

Revenue and diluted EPS must qualify independently. A successful revenue observation does not make EPS available, and vice versa.

## Readiness gates before any live run

Another phase may perform the bounded live certification only after operator approval and after these gates are met:

1. A fixture-only test proves the runner enforces the fixed issuer/period manifest and the exact 16-attempt cold-cache ceiling.
2. Tests prove attempts are charged before dispatch and that no retry, redirect-host escape, candidate widening, or unused-budget reassignment is possible.
3. Tests cover missing historical-submissions files, unresolved document names, multiple 8-K candidates, missing exhibits, oversized responses, timeouts, and parser rejection.
4. The command cannot register the provider with Analyze, mutate a database, or trigger AI generation.
5. Artifact output is deterministic, bounded, and excludes secrets and full source bodies.
6. The operator explicitly approves the live SEC requests and the final manifest/budget.

Production readiness requires a later, separate decision. Live acceptance for one or more observations would not by itself authorize schema changes, UI integration, Analyze registration, persistence, or broader issuer coverage.

## Offline validation

The preflight validation remains fully offline and consists of:

- focused direct-Q4 parser/provider tests;
- historical SEC normalization regression tests; and
- `git diff --check`.

No live certification, external provider request, paid operation, database migration, production integration, or source-control operation is part of this phase.

## Files changed by this phase

- `docs/outlook-phase6b5c2a5a-live-q4-preflight.md`
