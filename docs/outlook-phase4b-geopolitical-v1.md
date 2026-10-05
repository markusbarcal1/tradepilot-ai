# Outlook Phase 4B: Geopolitical intelligence V1

## Outcome and product boundary

Geopolitical is now connected to a bounded, free, primary-government source with deterministic interpretation and explicit industry exposure resolution. Production evidence passes through the existing `OutlookEvidence` validation, exposure guard, deduplication, freshness and aggregation. There is no final-label logic in the provider, no generic news sentiment, and no paid/model dependency.

The live 2026-09-18 snapshot produced one qualifying export-control observation for NVDA and AMD. Other validation companies had no matched observation. **Every live Geopolitical category remained Insufficient Data with no label; available categories stayed 3/6.** One observation does not satisfy the unchanged two-event gate, and this older observation also has little freshness-weighted support. This is evidence integration, not a claim of broad live geopolitical coverage or an artificially activated fourth category.

Direction describes potential business exposure to a documented action. It does not grade a government, political party, ideology, or policy as intrinsically good or bad. Market, Industry, Company, Economic and all other scoring/calibration remain unchanged.

## Sources evaluated

| Source | Evaluation | V1 decision |
|---|---|---|
| [Federal Register API](https://www.federalregister.gov/developers/documentation/api/v1) | Public JSON; tested without an API key; document identity, agency, abstract, action, publication/effective dates, RINs and correction references | Selected for bounded BIS final-rule retrieval |
| [BIS](https://www.bis.gov/) | Primary export-control authority; its rules are available through Federal Register; web guidance adds forms and interpretation complexity | Use BIS rules via Federal Register, not a separate website crawler |
| [OFAC Sanctions List Service](https://ofac.treasury.gov/sanctions-list-service) | Structured official designations are useful, but matching foreign entities to analyzed U.S. businesses requires reliable legal-entity/counterparty relationships | Deferred; never treat same-industry membership as sanctions exposure |
| [USTR tariff actions](https://ustr.gov/issue-areas/enforcement/section-301-investigations/tariff-actions) | Authoritative actions can involve tariff schedules, exclusions, countries and producer/importer distinctions; company industry alone does not resolve tariff incidence | Deferred pending controlled product/import exposure and tariff parsing |
| [EIA Open Data](https://www.eia.gov/opendata/documentation.php) | Free structured energy series, with API-key registration; ordinary price/supply observations do not establish geopolitical causation | Deferred; no oil-price-to-geopolitics inference |
| [MARAD advisories](https://www.maritime.dot.gov/msci-advisories) | Authoritative dated route advisories exist, but route-specific company exposure and a verified stable structured retrieval path were not established in this phase | Deferred; no generic shipping-news scraper |

Only one runtime source was added. No arbitrary site crawling, article-body ingestion, search-engine retrieval, sanctions-list guessing, or generic news-service coupling occurs. The existing `NewsSourceProvider` boundary remains intact; this is a government-document adapter using the existing `SourceDocument` model.

## Retrieval and normalized model

`FederalRegisterSource.get_documents()` requests `https://www.federalregister.gov/api/v1/documents.json` with BIS agency, RULE type, a 400-day publication lookback, current-date upper bound, newest ordering, at most 100 results, and an explicit field list. No pagination fan-out or follow-up article requests. Returned count must match the complete result list and must not exceed 100; otherwise fail closed because omitted amendments could make older evidence misleading.

Validate document ID, authoritative HTTPS publication URL containing that ID, agency identity, publication date/window and bounded source-model fields. Source observations become shared `SourceDocument` records with `ticker="GLOBAL"`, primary-authoritative quality, an official abstract, source URL, retrieval time, and structured date/action/reference metadata. `GLOBAL` is a source scope marker, never a stock exposure or scored ticker.

The internal immutable `GeopoliticalEvent` references that document and holds product family, effective date, review cutoff, destination countries, interpreted policy change, exclusion reason, and RIN action identities. It is an intermediate interpretation, not a parallel aggregation system. The immutable `ExposureAssessment` holds match/no-match, reason, and an `ExposureLink`.

One actual government abstract is frozen in `backend/tests/fixtures/outlook-geopolitical-bis.json`. Offline tests combine that observation with synthetic bounded source records. No live provider is needed by automated tests.

## Controlled exposure and event taxonomy

| Product group | Required exact Yahoo industry | Exposure interpretation |
|---|---|---|
| Advanced computing | Semiconductors | Potential export-licensing exposure of the semiconductor product group |
| Semiconductor manufacturing | Semiconductor Equipment & Materials | Potential export-licensing exposure of semiconductor manufacturing equipment |

Only supported `EQUITY` instruments with United States company-country metadata qualify. Industry matching normalizes case and whitespace. Sector, ticker, company name, multinational status, brand mentions and inferred foreign revenues never establish exposure. The resolver reuses Industry's seven-day classification cache in the configured provider set, without fetching Industry price histories or changing Industry scoring.

These are industry-level relationships, not assertions that every company sells a controlled product or qualifies for a license. That limitation is explicit in every matched summary. Generic Technology is insufficient: AAPL and MSFT are excluded. Equipment classification is not silently treated as a chip-product match: AMAT is excluded from the live advanced-computing event.

Added exactly one event type, `export_control`. Existing `trade_restriction` is broader; the narrower event permits an explicit policy lifecycle without changing freshness/evaluation behavior for existing trade-restriction fixtures. Existing sanctions, tariff, conflict and supply-chain event types are untouched and unsupported by this source interpreter.

## Exact interpretation, impact, confidence and materiality

Only a supported final/interim-final BIS rule with a known simple effective date and explicit recognized destination scope may contribute. Recognized destinations are China, Macau, Russia, Iran, North Korea and Belarus. Unsupported wording/destinations fail closed; the list is a parser scope, not an assumption that every country has active controls.

The title must identify exactly one controlled product group. A structured RIN or correction reference can attach a renamed amendment to an already recognized family, but does not establish direction.

* **-1:** A sentence starts with BIS (or the full agency name), explicitly states it is imposing/imposes/is adding/adds new or additional export license requirements, and contains the supported product group. The sentence must have an explicit destination clause. Negated, modal, proposed, conditional, or historical wording is excluded.
* **+1:** For advanced computing only, the first sentence explicitly states that BIS is revising the license-review policy for exports of certain semiconductors, changing from a presumption of denial to case-by-case review. Interpret as **conditional licensing opportunity**, never unrestricted exports or guaranteed approval. Negation/uncertainty in that assertion is excluded.
* Conflicting, unsupported, missing, entity-specific or ambiguous interpretations generate **no directional evidence**, not a zero-impact substitute. No +/-2 values are generated.

Destination names come from the current action clause, not arbitrary countries mentioned in background text. Entity-list/designated/named/listed-entity/affiliate language is explicitly excluded because industry matching cannot establish those relationships.

Confidence is **0.80** for every accepted observation: authoritative publication and explicit interpretation, moderated by industry-level rather than verified product/transaction exposure. Materiality is **0.60**: a direct controlled product-group relationship, with company-specific transactions unverified. Neither changes with rhetoric, political identity, share price, or imagined revenue percentages. Missing/weak relationships are excluded instead of assigned fabricated precision.

Source links lead to the returned Federal Register publication URL. Each exposure link also records the structured-company-metadata relationship and navigable Yahoo profile URL. Evidence provenance includes publication title/ID, effective date/text, review cutoff, destinations, product group, change direction, RINs, industry/sector, classification source and interpreter version.

## Lifecycle, deduplication and supersession

Publication and effective dates are distinct. Future-effective actions do not score and do not prematurely replace today's effective predecessor. Missing or complex effective-period language (exceptions, suspension, until/through, expiration) is excluded rather than guessed. Date-only government fields are represented at UTC midnight; no intraday effective-time precision is claimed.

`export_control` has a **90-day half-life and 365-day maximum age**, measured conservatively from original publication; evidence also explicitly expires at that review cutoff. The cutoff is an application review horizon, **not a claim that the legal rule expires then**. Known effective dates gate eligibility, but refetching an unchanged publication never rejuvenates it. V1 does not maintain a legal-currentness engine or retain indefinite influence simply because a rule might still be in force.

Before central deduplication, group overlapping product/destination observations, shared RINs and linked amendments conservatively. Retain only the latest applicable publication in each connected action family. An ambiguous newer action/correction suppresses the older directional claim instead of extending it. Identical copies do not create extra votes; conflicting same-day actions/versions fail closed. Disjoint destination actions can be separate events, but one multi-country publication stays one event. Do not split an action into one vote per country.

This is intentionally conservative: an overlapping amendment can suppress an entire earlier scope even if only part changed. No attempt is made to reconstruct detailed legal text. The existing evidence deduplication then runs normally. Existing Phase 3C reporting identity, event/factor semantics and aggregate thresholds were not modified.

## Cache and network behavior

| Item | Default/behavior |
|---|---|
| `OUTLOOK_GEOPOLITICAL_ENABLED` | `true` |
| `OUTLOOK_GEOPOLITICAL_CACHE_TTL` | 21600 seconds / six hours |
| Shared source snapshot cache | One process-local entry, reused across tickers; existing single-flight lock/deep-copy behavior |
| Classification | Existing seven-day, 256-entry Industry classification cache in production |
| Failure backoff | Existing `OUTLOOK_FAILURE_CACHE_TTL`, default 60 seconds |
| Request timing | Existing HTTP timeout and attempt settings; dedicated Geopolitical rate gate, 0.5-second spacing |
| Network bound | One source request per cold shared snapshot; at most one company metadata loader if its shared cache is cold |
| Warm request | Zero source/metadata loader calls; bounded in-memory normalization and exposure resolution |

No separate ticker-calculation cache is needed: re-evaluating at most 100 bounded documents is cheap and allows effective/expiry boundaries to advance while source data is cached. Cached source retrieval time remains preserved. Multiple backend workers have separate caches. Yahoo metadata calls may internally use multiple HTTP requests; service-call counts are not packet counts. No new global Yahoo configuration or price/history request is introduced.

The existing JSON transport was extended only with a separate Geopolitical rate gate. SEC/FRED rates and settings remain unchanged. There were no real `.env` edits.

## Failure/no-evidence semantics

Transport failure or truncated snapshot is isolated by existing provider orchestration, with failure backoff and no effect on charts/scanner or other provider categories. A malformed row retains source diagnostics and suppresses the entire snapshot's directional use, since that row could have been a superseding action. No stale last-good directional result is silently substituted.

Missing classification, unsupported instrument/jurisdiction/product mapping, ambiguous policy, future/expired observation or unestablished entity relationship produces no evidence for the ticker. Unrelated document IDs/reasons are retained only in operator diagnostics; irrelevant headlines never appear in the user's normal category card.

V1 returns **Insufficient Data**, not **Not Material**, for an unmatched ticker. A limited BIS export-control search cannot establish that all geopolitical exposure was reviewed and immaterial. This preserves the existing distinction between missing support and explicitly reviewed zero materiality.

## UI and CLI

No component/CSS redesign. When two sufficiently supported events qualify, the existing category label, qualitative factors, source links, summary and category count populate normally. An authenticated HTTP fixture and rendered React fixture verify this behavior. Summaries explain the action, matched industry, potential business direction and limitations; no numeric contribution appears in the normal UI.

The live one-event case is retained as evidence/provenance in the API and CLI but does not produce normal-card factors under the unchanged availability gate. No unsupported fourth category is shown. This limitation is deliberate, not hidden by lowering thresholds. Automated markup/API checks are not interactive browser certification.

`python -m app.cli.inspect_outlook TICKER` now prints Geopolitical source/candidate counts, source completeness, classification, normalized candidate details, matches, excluded document IDs/reasons, supported event count and evidence explanations, followed by existing category availability diagnostics. `--json` adds `geopolitical_diagnostics`. Diagnostic retrieval shares caches; offline corpus replay does not call configured providers.

## Live validation: 2026-09-18

The [full JSON capture](outlook-phase4b-live-validation.json) preserves each ticker's classification, candidates, matched/excluded observations and reasons, evidence, availability/summary, category counts and request measurements.

One shared API call returned **21** complete BIS rule documents within the 400-day window; **one** normalized event was selected. The other **20** documents were outside the supported product/event classes. The event is [Federal Register 2026-00789](https://www.federalregister.gov/documents/2026/01/15/2026-00789/revision-to-license-review-policy-for-advanced-computing-commodities), published and effective January 15, 2026. It describes moving certain semiconductor exports to China/Macau from presumption of denial to conditional case-by-case review. Its age remains approximately 246 days; fetching it now does not make it new.

| Ticker | Sector / industry | Candidate events | Matched / excluded documents | Supported events | Availability / label | Categories |
|---|---|---:|---:|---:|---|---|
| AAPL | Technology / Consumer Electronics | 1 | 0 / 21 | 0 | Insufficient Data / none | 3 -> 3 |
| NVDA | Technology / Semiconductors | 1 | 1 / 20 | 1 | Insufficient Data / none | 3 -> 3 |
| TSLA | Consumer Cyclical / Auto Manufacturers | 1 | 0 / 21 | 0 | Insufficient Data / none | 3 -> 3 |
| JPM | Financial Services / Banks - Diversified | 1 | 0 / 21 | 0 | Insufficient Data / none | 3 -> 3 |
| XOM | Energy / Oil & Gas Integrated | 1 | 0 / 21 | 0 | Insufficient Data / none | 3 -> 3 |
| MSFT | Technology / Software - Infrastructure | 1 | 0 / 21 | 0 | Insufficient Data / none | 3 -> 3 |
| KO | Consumer Defensive / Beverages - Non-Alcoholic | 1 | 0 / 21 | 0 | Insufficient Data / none | 3 -> 3 |
| AMD | Technology / Semiconductors | 1 | 1 / 20 | 1 | Insufficient Data / none | 3 -> 3 |
| AMAT | Technology / Semiconductor Equipment & Materials | 1 | 0 / 21 | 0 | Insufficient Data / none | 3 -> 3 |

For NVDA/AMD, the matched observation describes a conditional export licensing opportunity through the controlled semiconductor industry relationship; it does not assert that a particular product, transaction or company has an approved license. Category summary: `Insufficient independent evidence: 1 qualifying events.` Both event count and decayed support are below the category requirements. For every other ticker, the candidate is excluded with `no_controlled_product_industry_relationship`; summary: `Insufficient independent evidence: 0 qualifying events.`

The before count removes Geopolitical availability from the same snapshot, not a different historical assessment. Nothing gained a fourth available category. KO is the explicit unrelated negative control; AAPL/MSFT additionally prove that a technology sector alone is insufficient; AMAT tests the narrow boundary between chip products and manufacturing equipment.

The nine-ticker sequence made **one Geopolitical source call total**. Industry had already populated company metadata, so Geopolitical added **zero classification loader calls**. Every warm Geopolitical request made zero calls. Warm assessments took approximately **1.04-1.73 ms** locally. Full Outlook requests took roughly 18.95 seconds initially and 3.77-6.40 seconds thereafter; those timings include existing SEC/FRED/Market/Industry work, not just Geopolitical. They are not hosting performance guarantees.

## Validation and changed files

Offline coverage includes real frozen-source normalization, direct exposure, negative controls, missing/ambiguous classification, unsupported entity sanctions, current/future/expired/complex dates, duplicates/conflicts, renamed amendments and corrections, future amendments, source failure/partial corruption/truncation, cache reuse/backoff/expiry/concurrency, shared metadata, central exposure guard, policy-neutral wording, and authenticated HTTP/CLI contracts.

Cross-exposure decision: a synthetic oil disruption produces **no directional evidence for either an oil producer or an airline**. V1 has neither an authoritative event adapter nor verified physical/route/cost exposure for that case. It does not manufacture a positive producer benefit to force symmetry.

Validation results: 36 new Geopolitical tests and 18 Industry regression tests passed; 447 Outlook tests passed. Full backend suite: 643 passed, 46 skipped, 148 subtests passed. Existing evaluation: 40 cases, 65 replays, **535 checks passed, zero failures**. Frontend tests, lint and build passed; diff/whitespace review passed. Existing FastAPI lifespan deprecation and frontend large-bundle warnings remain.

Changed files:

* `backend/app/services/outlook_structured/geopolitical.py`: bounded shared source and evidence provider.
* `backend/app/services/outlook_geopolitical.py`: normalized event, exposure resolver, narrow interpretation/lifecycle and supersession.
* `backend/app/services/outlook_structured/__init__.py`: registration and existing classification-cache sharing.
* `backend/app/services/outlook_structured/transport.py`: dedicated source rate gate.
* `backend/app/models/outlook_taxonomy.py`: `export_control` event.
* `backend/app/services/outlook_policy.py`: freshness for that new event only.
* `backend/app/config.py`: enablement and source-cache TTL.
* `backend/app/cli/inspect_outlook.py`: operator diagnostics.
* `backend/tests/test_outlook_geopolitical.py` and `backend/tests/fixtures/outlook-geopolitical-bis.json`: offline validation.
* `backend/tests/test_outlook_diagnostics.py`: explicitly isolate the mocked CLI test from live configured providers.
* `frontend/tests/outlook.mjs`: populated and unrelated Geopolitical rendering cases.
* This document and `docs/outlook-phase4b-live-validation.json`: methodology and live evidence.

## Limitations and V2 opportunities

Coverage is deliberately narrow: only two export-control product groups, six destination names and a small set of unambiguous official-abstract constructions. New wording may be excluded rather than interpreted. Source retrieval is a recent BIS rules snapshot, not comprehensive geopolitical news or a complete legal-currentness service. Amendments outside the window/source, unstated product eligibility, and court/executive actions are not reconstructed. A source change that exceeds the bounded snapshot fails closed until reviewed.

The industry mapping does not certify product classification, ECCN, export destination, foreign customer, company revenue exposure, or transaction eligibility. Fixed moderate confidence/materiality and explicit summaries reflect this. Process-local caches are not shared across workers. There is no persisted historical source archive for point-in-time backtesting.

Sanctions/entity lists, tariffs, conflicts, commodity disruptions and shipping routes remain unsupported. Ordinary oil prices, global tensions, multinational status and theoretical disruption beneficiaries never become evidence.

Recommended V2 work: verified product/ECCN and legal-entity relationships; structured amendment/repeal coverage and action lifecycles; narrow tariff/product mappings with importer/producer roles; authoritative route events paired with factual route exposure; bounded persistent source snapshots for audits/replay. Add these through the same source/exposure boundary without changing category thresholds to manufacture coverage.

No commit, deployment, real environment edit, or production data mutation was performed.
