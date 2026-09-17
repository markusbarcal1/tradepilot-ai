# Outlook Phase 3B: free intelligence foundation

This records the initial foundation delivery. The subsequent [real-world SEC remediation report](outlook-phase3b-remediation.md) documents the corrected exhibit selection, reporting-language/table coverage, event independence, diagnostics, and updated live acceptance results.

TradePilot interprets supported events conservatively. Missing evidence is preferable to fabricated certainty.

## Architecture

`SEC observations / bounded primary documents → SourceDocument → OutlookInterpreter → OutlookEvidence → existing validation, clustering, freshness and aggregation → existing Outlook UI`.

Providers retrieve material; interpreters identify supported events; the existing engine determines category and overall Outlook. No recommendations, model calls, scanner integration, score changes, UI redesign, database changes or new runtime dependencies are included.

`SourceDocument` is a frozen, validated, provider-independent Pydantic model: stable identity, ticker, title, optional source description, bounded extracted text, aware publication/observation timestamps, source name/type/URL, provider/document identity, related tickers, objective source quality and JSON metadata. Text is capped at 60,000 characters. Empty text is legitimate metadata-only material, never a fabricated article. The model supports filings, exhibits, company releases, news metadata and industry/government material, rejects invalid URLs/naive times, and requires observation at or after publication.

`OutlookInterpreter.interpret(ticker, documents, company_context)` returns normalized evidence. The production `DeterministicOutlookInterpreter` has versioned rules and isolates document errors. SEC accepts an injected interpreter. Existing `CompanyContext` gains optional company name, country and description; only the company name from existing SEC submissions is populated. No profile subsystem or inferred exposure is added.

## SEC retrieval

Existing ticker/CIK mapping, submissions, timestamps, identified user agent, process-wide rate gate, timeout, retries and caches remain. Routine 10-K/10-Q observations remain non-directional; their bodies are never fetched.

By default, at most two 8-K filings per ticker receive text retrieval (configurable 1–3). Item 2.02 has priority, then Item 3.01, newest first within each group. The existing 180-day lookback remains; no historical submissions traversal is added.

Fetch the official primary document and isolate Item 2.02/3.01 text. Missing/repeated item headings are rejected. For earnings, follow at most one explicitly numbered Exhibit 99/99.1/99.01 link within the exact same SEC accession directory. Both linked exhibit numbers and separate exhibit-number/linked-description table cells are supported. Earnings/financial-results context must appear near the exhibit beginning. No arbitrary destination sites, PDF bodies, complete submissions or publisher articles are fetched.

Text responses are capped at 1 MiB, extracted items at 15,000 characters, exhibits at 60,000. Truncation drops the incomplete final line. Script/style/inline-XBRL header content is ignored; table cells remain separate. URLs must use safe filenames inside the filing directory. This reads official filing documents, not arbitrary SEC website pages.

## Company rules

| Item | Interpretation |
| --- | --- |
| 1.03 | Existing restructuring, bankruptcy/receivership, impact -2 |
| 1.05 | Existing cybersecurity event, material incident, impact -1 |
| 2.06 | New `material_impairment`, impact -1 |
| 3.01 | Metadata non-directional because the item also includes listing transfers. Explicit issuer receipt of a Nasdaq/NYSE noncompliance notice in the targeted item can produce existing `regulatory_action`, impact -1. |
| 1.01, 1.02 | Agreement/termination observations; no assumed benefit or loss |
| 2.01, 2.05, 3.02, 5.02 | Acquisition/disposition, exit costs, equity issuance, officer/director changes remain non-directional |
| 7.01, 8.01, routine/unknown | No automatic direction |

Distinct adverse item types in one filing may become distinct events; repeat representations of one event type are clustered. Contract economics and executive-departure causality are not parsed. Existing category evidence/weight thresholds remain.

## Earnings and numeric rules

Require primary-source issuer earnings context (Item 2.02 or a company earnings release), complete bounded assertions and explicit issuer/comparison context. Secondary headlines are not interpreted in this version.

* Explicit issuer raises/lowers/cuts full-year, fiscal-year, annual or FY-year guidance/outlook: existing `guidance_raise` / `guidance_cut`.
* Explicit withdrawal of previously issued guidance: new `guidance_withdrawal`, impact -1. No duplicate `guidance_lower` synonym.
* Explicit revenue, diluted EPS or earnings-per-share percentage increase/decrease with a year-over-year/same-prior-year comparison: existing `earnings_result`.
* Explicit revenue from/to dollar amounts in matching million/billion units, year-over-year: `earnings_result`.
* Explicit gross/operating margin from/to percentages, year-over-year: existing `margin_change`, preserving percentage-point change.
* Guidance ranges in the exact form `from $10-$12 billion to $11-$13 billion` (also en dash or million units): matching units, ordered positive bounds, both endpoints moving in the asserted direction.

Decimal parsing checks direction and comparable units. Reject malformed grouping, negative/non-finite numbers, zero changes, nonpositive revenue baselines, revenue declines above 100%, growth above 1,000%, margins outside 0–100%, and monetary levels/ranges above 1e12 in the stated unit. Loss-to-profit transitions and mixed units are not guessed.

Negation, conditional language, analyst/consensus claims, segment-only and adjusted/pro-forma qualifiers are rejected. Generic positive/negative words never create evidence. Unsupported wording, tables and narrative fragments commonly produce nothing. No consensus, surprises or investment outcomes are reconstructed.

Earnings impact is +/-1, confidence normally 0.9, qualitative guidance materiality 0.8. Numeric materiality is capped at 0.8 and scales down with magnitude: percentage change / 10, margin percentage-point change / 2, guidance midpoint relative change * 10. Tiny changes fail existing materiality thresholds. These transparent weights are provisional, not empirical predictions. Existing bankruptcy/cybersecurity materiality is preserved; impairment uses 0.9, listing noncompliance 0.85. Impact, confidence and materiality remain separate validated concepts.

## Provenance and duplicates

Every interpreted event retains its factual assertion as summary and `evidence_basis`, source URL, source document ID, provider document identity, accession, CIK, form/items, filing/report dates, publication/observation timestamps, numeric values and interpreter version. Existing expanded UI source rendering is reused; filing bodies never enter the endpoint response.

Existing ticker/category/canonical-event-type clustering remains. Accession + event type identifies repeated SEC representations; standardized titles plus the existing 48-hour window cluster matching events across documents/providers. Filing/release/news representations do not automatically become independent votes. This can merge distinct same-type events close in time; period-aware identities are future work.

Evidence gains optional `source_quality`: `primary_authoritative`, `secondary_reporting`, `unknown`. In a duplicate cluster, explicit primary evidence is selected before secondary reports; a secondary conflict cannot suppress or refresh it. Conflicting primary interpretations remain excluded. Unknown-quality clusters retain previous behavior. Authority does not increase impact.

## Caching, failures and performance

Process-local bounded single-flight caches retain document results/SourceDocuments and versioned interpretations. URL/source identity and bounded document content identify cache entries; interpreter version prevents reuse across rule changes. Existing defaults remain: SEC TTL one hour, failure TTL one minute, CIK TTL one day, capacity 256 per cache, one-second SEC interval, five-second timeout, one attempt. No Redis, jobs or worker is added. At most four extra document requests per ticker cache miss with default settings.

Whole-filing errors use failure backoff and leave SEC observations intact. Exhibit errors preserve inline item text; that partial success can remain cached for the normal one-hour TTL. Interpreter errors are isolated per document; provider orchestration still protects FRED/Market. Logs retain only failure types, never exception text or credentials.

CLI output adds unique SEC filing observations, source-document counts (including metadata documents), interpreted candidates, and per-filing retrieval outcomes. Candidates precede dedup/freshness; category counts remain authoritative. Diagnostics are request-local provenance, not shared mutable state. No huge bodies are printed.

## Optional news and GDELT evaluation, 2026-09-15

`NewsSourceProvider` exposes ticker/industry discovery returning `SourceDocument` lists. No news adapter is installed or called. There is no news flag/key requirement: disabling SEC document retrieval still leaves metadata SEC, FRED and Market functioning.

The [official GDELT DOC description](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) documents article-list discovery, titles/URLs and JSON/RSS formats, with 75 default and up to 250 results. It does not establish dependable ticker identity or publication-time semantics for our evidence model. Discovery is not a license to reproduce publisher bodies.

A web-tool probe returned no usable data. A separate bounded direct request for Apple, article-list JSON, five records, one day returned HTTP 200 with a two-byte empty object: no article records or metadata. This does not prove an outage, but did not validate useful discovery. Current enforceable quota, beta commercial-use/attribution requirements and reliability were not sufficiently established from reviewed primary documentation. Do not confuse the separate GDELT Cloud product with the legacy API.

**GDELT is not implemented: suitability remains unverified.** No destination scraping, paywall access, fabricated article content or GDELT billing path exists.

## Cost/configuration

Normal direct Phase 3B API cost: **$0**. No OpenAI, Anthropic, Gemini, model installation, GPU, paid news or new financial-data API is required.

| Source | Access considerations |
| --- | --- |
| SEC | No paid key; identified operator contact required. [Official APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) are unauthenticated. [Developer guidance](https://www.sec.gov/about/developer-resources) caps aggregate automated access at 10 requests/second and asks users to download only needed material. This code retains a stricter one-request/second process gate. Multiple processes require an operator-managed aggregate budget. |
| FRED | Existing free key and series behavior unchanged; existing access/series rights still apply. No new series or billing integration. |
| Market | Existing market adapter/access constraints unchanged. No new feed or cost. This sprint does not certify commercial licensing or grant redistribution rights. |
| GDELT/news | No runtime integration, account or cost; suitability/terms remain unverified. |

Public SEC access was verified; third-party licensing is not expanded by this work. Preserve attribution/source links. Hosting, egress and existing infrastructure costs are outside the direct API-cost claim.

New example settings: `OUTLOOK_SEC_DOCUMENTS_ENABLED=true`, `OUTLOOK_SEC_MAX_DOCUMENT_FILINGS=2`. Existing SEC/FRED/Market settings remain. No real environment files changed; no credentials printed or committed.

## Remaining categories and upgrades

Industry remains unavailable; company events are not duplicated into it. Geopolitical remains unavailable; the existing explicit-exposure gate remains and no generic sentiment/geographic exposure is invented.

A future licensed news adapter implements `NewsSourceProvider`, preserving actual available content and source quality, then supplies documents through an `OutlookProvider.get_evidence` adapter to the injected interpreter. A future LLM implementation satisfies `OutlookInterpreter` and replaces the deterministic implementation. Register the evidence adapter in `configured_providers`; interpreter output preserves raw source-provider identity and passes existing validation. No `OutlookEvidence`, aggregation, response or UI redesign is required. No paid SDK or stub is included now.

## Validation

Synthetic fixtures live only in `backend/tests/test_outlook_intelligence.py`; production cannot select them. Tests cover validation/taxonomy/bounds, Company/Earnings events and rejections, numeric edges, provenance, authority, duplicates, bounded document parsing/URLs, caches, partial failures, disabled retrieval, ticker isolation and existing providers/endpoint. No automated test requires network or paid services; database tests use isolated targets.

Final full backend suite: **416 passed, 46 skipped, 148 subtests passed** (including 84 new intelligence tests). PostgreSQL tests were skipped without a disposable PostgreSQL target. **Frontend tests, frontend lint, production build and diff checks passed.** Existing FastAPI startup deprecation and frontend bundle-size warnings remain. No real application database was used as a test target.

Live inspection, network-enabled local CLI on 2026-09-15:

| Ticker | SEC filing observations | SourceDocuments including metadata | Supported Company / Earnings | Overall |
| --- | ---: | ---: | --- | --- |
| AAPL | 5 | 9 | 0 / 0 | Mixed, 2/6 |
| NVDA | 11 | 13 | 0 / 0 | Mixed, 2/6 |
| TSLA | 6 | 6 | 0 / 0 | Mixed, 2/6 |
| JPM | 17 | 21 | 0 / 0 | Mixed, 2/6 |
| XOM | 4 | 5 | 0 / 0 | Mixed, 2/6 |

SEC/FRED/Market were available for all five. FRED supplied four supported events, Market two. Company/Earnings remained insufficient; Industry/Geopolitical unavailable. The initial sandbox-only attempt had network errors; network-enabled inspection succeeded. AAPL's separate exhibit-number/description cells were verified and covered by a regression test. Real content was retrieved, but the sample did not match supported assertions. **Live Company/Earnings activation is not certified**; synthetic tests demonstrate activation. Rules were not loosened to manufacture ticker differences.

## Limitations and Phase 3C

English explicit prose only; one exhibit/filing; small recent-filing budget; no PDF/OCR/general table parser, foreign-issuer 6-K, amendments/supersession, full period/entity resolution, currency conversion, arbitrary ranges or news/IR adapters. Strict line/sentence/item boundaries miss legitimate evidence. Existing minimum two-event/category weights remain, so one valid event may still be insufficient. Cache/rate control is process-local; partial document errors can wait an hour to retry.

Recommended Phase 3C: manually reviewed primary-source evaluation corpus, measure precision/recall, then expand a few explicit issuer result formats; add period-aware event identity/amendment handling; verify additional exhibit layouts and hosted latency. Establish Industry/exposure sources independently. Revisit news only with verified suitability/licensing. Browser source-link rendering and hosted acceptance/performance remain manual. No deployment or commit occurred.

## Files

New: `backend/app/models/outlook_document.py`, `backend/app/services/outlook_interpreter.py`, `backend/app/services/outlook_structured/documents.py`, `backend/tests/test_outlook_intelligence.py`, this report.

Updated: `.env.example`, `backend/app/config.py`, `backend/app/models/outlook_evidence.py`, `backend/app/models/outlook_taxonomy.py`, `backend/app/services/outlook_providers.py`, `backend/app/services/outlook_evidence.py`, `backend/app/services/outlook_structured/{sec,transport,policy}.py`, `backend/app/cli/inspect_outlook.py`, `backend/tests/test_outlook_structured.py`, `docs/outlook-phase3a.md`.
