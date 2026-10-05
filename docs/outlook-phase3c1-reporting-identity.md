# Outlook Phase 3C.1: reporting identity and evaluation foundation

Implemented 2026-09-17. Metadata and offline evaluation only; no calibration change.

## Scope and preserved behavior

The existing Phase 3C and availability-diagnostics work was already uncommitted when this phase started. It was preserved. No commit, deployment, environment change, paid provider, LLM, UI change, or new provider request was introduced.

Production Earnings still uses the existing 45-day half-life, 120-day results maximum age, two-event minimum, 0.75 support minimum, confidence/materiality gates, direction formula, and label thresholds. Guidance and all other categories retain their policies. Production clustering, factor aggregation, and overall aggregation are unchanged. No experimental B/C/D/E model, overdue grace period, or earnings-date predictor was implemented.

## Representation and clocks

`ReportingPeriodIdentity` contains issuer, fiscal year, Q1/Q2/Q3/Q4/FY, and optional period start/end. Its stable key is `TICKER:FYyyyy:Qn` (or `:FY`); document IDs and accessions are not part of that key.

`ReportingIdentity` contains authoritative/unknown/conflict status, an explicit reason, zero or more periods, extraction provenance, and an optional revision marker. Authoritative status requires both periods and provenance. Status is categorical metadata reliability, not OutlookEvidence confidence. Provenance records extraction method, source URL, document ID, accession when present, and basis. A document may explicitly contain both Q4 and FY; this does not turn FY into Q4.

`SourceDocument.reporting_identity` optionally retains structured extraction. Primary-text identity is resolved on demand. Results and margin evidence receive the resolved identity in `source_details.reporting_identity`. Guidance does not inherit it.

Financial period start/end are distinct from `published_at`, filing date, and `observed_at`. Identity extraction never changes these timestamps, event IDs, expiry, confidence, materiality, or financial magnitude. Dates ending after publication and invalid fiscal-year values fail closed. Start dates remain unknown unless explicitly supplied; a year-to-date XBRL duration start is not assumed to be a quarter start.

## Extraction sources and precedence

1. Same-context inline XBRL DEI facts from supplied 10-Q/10-K HTML (including /A): `DocumentFiscalYearFocus`, `DocumentFiscalPeriodFocus`, `DocumentPeriodEndDate`. Missing contexts, malformed facts, conflicting values/contexts, and future ends fail closed. An 8-K DEI period-end/event date is deliberately not accepted as an earnings financial period.
2. Explicit primary-source result headings and reporting introductions: fiscal-year/ordinal-quarter wording, explicit quarterly year labels, and period-ended statements. Forecast/guidance sentences do not establish results identity. Text inspection is bounded to the first 4,000 extracted characters plus title.
3. Validated GAAP current-column identity from the existing deterministic comparison-table recognizer. This retains its alignment, accounting-basis, current/prior-year, and ambiguity checks. Conflicting heading/table identities fail closed.
4. Unknown, with an explicit reason; no guess based on ticker, fixture name, evidence ID, filing month, calendar quarter, or generic quarterly wording.

Structured identity is preferred when supplied. The current bounded SEC provider still retrieves 8-K items and earnings exhibits, not new 10-Q/10-K bodies. Consequently the live path gains primary-text/table identity; the structured parser is exercised by supplied HTML/offline tests and is ready for already available structured documents. This phase does not claim live 10-Q retrieval coverage or introduce companyfacts/submissions requests.

## Fiscal years and known calendar

Fiscal-year labels come from the source, not a date's calendar year. The real NVDA FY2025 Q1/Q2/Q3 reports end in April/July/October 2024; Q4 ends January 26, 2025. Apple FY2025 Q1 ends December 28, 2024.

`KnownFiscalCalendar` retains known period identities/ends and their provenance. Diagnostics provide the next logical quarter identity, never a predicted period-end or publication date. Calendar dates are not assumed to be three months apart. An Apple FY2023 source fixture represents its 53-week year; the actual Q1 end is December 31, 2022. A separate boundary test represents a 14-week quarter. The later 10-K basis for the 53-week fact is retained with its knowledge date and is not used by replay extraction.

## Continuity, missing periods, and uncertainty

`consecutive(previous, current)` uses issuer and fiscal ordinal, including Q4 -> next FY Q1. Q1 -> Q3 is false; annual involvement or unknown identity returns unknown. Explicit date order must also be consistent when both ends are known.

Diagnostics distinguish current known quarter, previous known quarter, immediately previous quarter when actually present, expected previous quarter, and missing interior quarters. The word known is intentional: an unresolved later source or an annual-only report may conceal a newer quarter. Unknown sources and conflicting period ends are visible; no statement of complete coverage is implied.

A Q1/Q3 inventory explicitly lists Q2 as missing and does not call Q1 Q3's immediately preceding quarter. Missing report versus retrieval failure is not inferred. Evaluation packages may declare a `ReportingGap` with cause (`confirmed_missing_report`, `retrieval_gap`, `unknown_identity`), basis, and `known_at`. Declarations are point-in-time filtered and remain separate from inferred inventory gaps.

## Multiple documents and revisions

Documents sharing issuer/fiscal-year/fiscal-period resolve to the same diagnostic period inventory entry. Available end dates can fill an unknown end; contradictory known ends are reported as conflicts rather than silently chosen. All source rows remain visible.

Amended structured forms preserve an amendment marker. They do not invent an original-accession link. `ReportingRevision` can retain a known original document/accession and basis. Existing explicit evaluation relationships are visible only when both endpoints are observable. Amendment/correction/supersession links remove the original from the active diagnostic inventory while preserving both provenance rows; forecast updates do not do this. This handles corrected-period identity without manufacturing another quarter.

This is a metadata inventory, NOT a new production deduplication or revision engine. Existing production release clustering and its scoring event count are deliberately unchanged. No reliable original-filing relationship is guessed from /A alone, shared dates, or a similar title. Real partial amendments and chain ambiguities still need additional reviewed source cases.

## Q4, FY, and guidance

FY alone does not imply Q4. Q3 -> FY is not a confirmed quarterly transition. Explicit Q4 and FY remain separate identities, so Q3 -> Q4 continuity can be evaluated without treating the annual report as a fifth quarter. A financial fact in a combined annual/quarterly document is assigned a period only if its numeric current-period label disambiguates it; otherwise its identity is unknown while its existing production interpretation is preserved.

The NVDA FY2025 Q4/annual fixture has both identities, an explicit Q4 end, and no guessed annual end. Its financial facts are intentionally omitted. Guidance identity/target-period redesign is out of scope; results identity is not attached to guidance evidence.

## Corpus expansion and source fidelity

The unchanged original corpus has 34 packages / 48 replay points and 394 passing checks. Its original AAPL-style fixture remains unknown; its NVDA-style fixture resolves FY2027 Q1/Q2 from GAAP headers, with unknown period ends. Nineteen original quarterly-results packages still lack trustworthy identity. They were not backfilled using fixture names.

The new `reporting-v1.json` adds six packages, 17 primary-source documents, and 17 replay points. Five issuer sequences cover technology, semiconductors, automotive, banking, and energy. The sixth package covers Apple's FY2023 53-week-year Q1. Together: 40 packages, 65 replay points, seven reliably identified packages (one original plus six new), and five real issuers. The synthetic original NVDA-style package uses ticker TEST and is not counted as another real issuer.

| Issuer | Source-grounded sequence | Period-end coverage | Financial replay coverage |
|---|---|---|---|
| AAPL | FY2025 Q1-Q3; separate FY2023 Q1 | All four ends explicit | FY2025 consolidated revenue facts, normalized factual paraphrases |
| NVDA | FY2025 Q1-Q4 plus FY | Q1-Q4 ends explicit; FY end unknown | Q1-Q3 consolidated revenue facts; Q4/FY identity only |
| TSLA | FY2025 Q1-Q3 | Unknown in retained release-notice snippets | Identity only |
| JPM | FY2025 Q1-Q3 | Unknown in retained release-notice snippets | Identity only |
| XOM | FY2025 Q1-Q3 | Unknown in retained release-heading snippets | Identity only |

Short real reporting clauses/headings are retained with primary URLs. Revenue figures and year-over-year percentages for AAPL/NVDA are factual paraphrases; they are NOT represented as complete raw filings or verbatim financial-parser fidelity tests. Identity-only notices do not fabricate financial events. These are selective frozen fixtures, not fresh live provider captures.

Sources provide publication dates, not uniformly verified intraday times. Fixtures explicitly use end-of-day UTC and simulated observation for deterministic replay; this is a convention, not a claim about actual release or ingestion time. Separate synthetic late-observation tests exercise real clock separation. Source-review date is 2026-09-17; historical observation times are simulated, not falsely described as archived system captures.

## Primary-source inventory

- [aapl-reported-1](https://www.apple.com/newsroom/2025/01/apple-reports-first-quarter-results/): published 2025-01-30.
- [aapl-reported-2](https://www.apple.com/newsroom/2025/05/apple-reports-second-quarter-results/): published 2025-05-01.
- [aapl-reported-3](https://www.apple.com/newsroom/2025/07/apple-reports-third-quarter-results/): published 2025-07-31.
- [nvda-reported-1](https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-first-quarter-fiscal-2025): published 2024-05-22.
- [nvda-reported-2](https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2025): published 2024-08-28.
- [nvda-reported-3](https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-third-quarter-fiscal-2025): published 2024-11-20.
- [nvda-reported-4](https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-fourth-quarter-and-fiscal-2025): published 2025-02-26.
- [tsla-reported-1](https://ir.tesla.com/press-release/tesla-releases-first-quarter-2025-financial-results): published 2025-04-22.
- [tsla-reported-2](https://ir.tesla.com/press-release/tesla-releases-second-quarter-2025-financial-results): published 2025-07-23.
- [tsla-reported-3](https://ir.tesla.com/press-release/tesla-releases-third-quarter-2025-financial-results): published 2025-10-22.
- [jpm-reported-1](https://jpmorganchaseco.gcs-web.com/news-releases/news-release-details/jpmorganchase-reports-first-quarter-2025-financial-results): published 2025-04-11.
- [jpm-reported-2](https://jpmorganchaseco.gcs-web.com/news-releases/news-release-details/jpmorganchase-reports-second-quarter-2025-financial-results): published 2025-07-15.
- [jpm-reported-3](https://jpmorganchaseco.gcs-web.com/news-releases/news-release-details/jpmorganchase-reports-third-quarter-2025-financial-results): published 2025-10-14.
- [xom-reported-1](https://corporate.exxonmobil.com/news/news-releases/2025/0502_exxonmobil-announces-first-quarter-2025-results): published 2025-05-02.
- [xom-reported-2](https://corporate.exxonmobil.com/news/news-releases/2025/0801_exxonmobil-announces-second-quarter-2025-results): published 2025-08-01.
- [xom-reported-3](https://corporate.exxonmobil.com/news/news-releases/2025/1031-exxonmobil-announces-third-quarter-2025-results): published 2025-10-31.
- [aapl-53-week-q1](https://www.apple.com/newsroom/2023/02/apple-reports-first-quarter-results/): published 2023-02-02.

- [Apple FY2023 10-K calendar disclosure](https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm): 53-week fiscal year, additional week in Q1. Not a source for projected future dates.

## Replay and diagnostics

Scoring and identity diagnostics share `replay_documents`, including HTML extraction and both publication/observation cutoffs. No source appears before either clock. Relationships and declared gaps are also filtered as of the replay time. Future corrections cannot suppress an existing period early. Original publication time remains unchanged after late discovery or correction.

The evaluation CLI runs both corpora by default; `--corpus` still selects one file. It reports reliable identity package counts and per-replay reporting diagnostics. Explicit fixture expectations assert period inventory and missing periods alongside existing financial outcomes. JSON includes provenance, periods, lag, relationships, calendar, and unknown/conflict reasons.

`inspect_outlook` shows reporting identity in normal developer output and JSON, including SEC documents that yielded no directional interpretation. It also supports deterministic offline inspection without providers:

```powershell
# Run from backend
.\venv\Scripts\python.exe -m app.cli.inspect_outlook AAPL --offline-case aapl_primary_reporting_sequence
.\venv\Scripts\python.exe -m app.cli.inspect_outlook NVDA --offline-case nvda_primary_reporting_sequence --replay after_report_3 --json
.\venv\Scripts\python.exe -m app.cli.evaluate_outlook
.\venv\Scripts\python.exe -m app.cli.evaluate_outlook --corpus app/evaluation/outlook/v1.json
```

There is no normal-UI rendering change. No live provider certification was performed; source verification used primary pages, while automated evaluation/tests remained offline.

## Validation

- Reporting identity tests cover IDs/month/calendar non-inference; fiscal-year naming; same-period documents; amendments and corrected periods; Q1/Q2 and Q4/Q1 continuity; Q1/Q3 gaps; late/out-of-order discovery; future visibility; 52/53-week dates; unknown/conflict handling; structured precedence; context isolation; guidance separation; annual ambiguity; offline CLI; and baseline financial invariance.
- The original corpus's financial snapshots are compared with reporting metadata removed. Availability, labels, support, direction, event count, and confidence remain identical.
- Combined offline evaluation: 535 checks passed, zero failed, 40 packages / 65 replays.
- Full backend suite: 586 passed, 46 skipped, 148 subtests passed. The 46 skips require a configured disposable PostgreSQL test target; none was configured or created. Two existing FastAPI startup deprecation warnings remain. The suite includes 43 new reporting-identity test cases.
- Frontend tests passed; lint passed; production build passed. Build retains its non-failing chunk-size advisory.
- Diff review and whitespace checks completed; pre-existing working-tree changes retained.

## Remaining limits and calibration readiness

Metadata coverage is materially broader than the previous one-package baseline. It is sufficient to rerun period identity, continuity, missing-period, replay, and provisional AAPL/NVDA state/history plumbing experiments responsibly, with explicit exclusions.

It is NOT yet sufficient to select production state/history calibration across sectors. Financial direction coverage in the new sequences is positive revenue-only and limited to AAPL/NVDA. TSLA/JPM/XOM are identity-only; raw multi-factor reversals, internally mixed quarters, reliable period ends across sectors, real amendments, partial corrections, and more fiscal calendar transitions remain needed. The original 19 unsupported quarterly packages remain unsupported. Grace periods, historical weights, and current-strength gates are still unvalidated.

Unsupported extraction includes PDF/image parsing, arbitrary XBRL namespaces/continuations, missing or conflicting DEI contexts, generic date-only reports without explicit fiscal labels, ambiguous quarter/annual fact scope, most complex comparison tables, and guidance target periods. No quarter is derived by subtracting annual and nine-month values. No forecast publication dates or fiscal ends are manufactured.

## Files changed in this phase

- `backend/app/models/outlook_reporting.py` (new models and continuity helper)
- `backend/app/models/outlook_document.py` (optional typed identity)
- `backend/app/models/outlook_evaluation.py` (gap declarations and period expectations)
- `backend/app/services/outlook_reporting.py` (new extraction and diagnostics)
- `backend/app/services/outlook_interpreter.py` (results/margin provenance only)
- `backend/app/services/outlook_structured/sec.py` (retained document identity diagnostics)
- `backend/app/services/outlook_evaluation.py` (shared replay documents and assertions)
- `backend/app/cli/evaluate_outlook.py` (both corpora and reporting diagnostics)
- `backend/app/cli/inspect_outlook.py` (identity and deterministic offline inspection)
- `backend/app/evaluation/outlook/reporting-v1.json` (new sourced corpus)
- `backend/tests/test_outlook_reporting.py` (new regressions)
- `docs/outlook-phase3c1-reporting-identity.md` (this report)

Pre-existing changes in `outlook_evidence.py`, `test_outlook_remediation.py`, and the earlier Phase 3C files were not reverted or folded into an unrelated refactor.
