# Phase 6B.5C.2A.5K — Offline SEC Document-Type and Index-Semantics Audit

## 1. Executive conclusion

**Recommendation D: offline evidence is insufficient to determine the actual document-type semantics of the accession-scoped SEC `index.json`.**

The current `sec-index-json-ex99-earnings-1` implementation reads `directory.item[].type` as though it were an SEC exhibit/document type and accepts normalized EX-99-family values. Synthetic fixtures prove that the normalizer behaves deterministically under that assumed contract. They do not prove that the real SEC field has those semantics.

The Phase 5J artifact proves that four real index responses parsed, exposed 70 item dictionaries with safe `name` identities, and supplied no value in the currently read `type` field that normalized as EX-99. It does not retain the raw type values and contains no real description samples. Therefore it cannot distinguish among these possibilities:

- the filings have no EX-99-family attachment;
- `directory.item[].type` is not the SEC exhibit-type field;
- the live index schema represents exhibit type differently; or
- another unsupported schema/layout issue exists.

The repository contains no retained real index payload or independently verified offline schema example that resolves this question. The frozen policy and `direct-q4-1` remain unchanged. No alternative document type is justified.

## 2. Phase 5J evidence boundary

Phase 5J established, for AAPL FY2024/FY2025 and NVDA FY2025/FY2026 Q4:

- two current-submissions responses, four selected primary documents, and four bound accession indexes returned HTTP 200;
- discovery resolved one candidate per target and exact binding succeeded;
- each primary was HTML-like;
- `direct-q4-1` produced zero primary candidates and accepted observations;
- primary relationship discovery produced zero eligible links;
- all four index bodies decoded as JSON and were classified `sec_index_json`;
- 70 index entries were examined;
- no unsafe `name` identity was observed by the implemented check;
- all 70 entries stopped at the implemented type gate;
- zero entry reached description matching;
- no exhibit was requested; and
- all eight desired financial observations remained Not established.

The sanitized artifact intentionally omits index bodies, raw type tokens, descriptions, filenames, URLs, accession identities, and unrestricted entry lists. Phase 5J therefore certifies transport and the implemented normalization outcome, not the external semantics assigned to each source field.

## 3. Actual index parser schema contract

`backend/app/services/outlook_structured/q4_filing_index.py` implements `sec-index-json-ex99-earnings-1` as a relationship-only normalizer. It cannot create financial observations.

The exact read path is:

```text
payload
  -> directory (dictionary expected)
  -> item (list expected)
  -> each dictionary entry
       -> name
       -> type
       -> description
```

If the payload is not a dictionary, `directory` is absent/non-dictionary, or `item` is not a list, the implementation treats the item set as empty. Non-dictionary list entries count as type rejections.

Filtering is sequential first-failure:

1. `name` must match the safe basename expression.
2. `type` must normalize as EX-99 or EX-99 plus a numeric suffix.
3. The first 512 characters of `description` must include an approved earnings/results/press-release phrase.
4. Eligible entries collapse by `(safe document, normalized type)`.
5. Zero candidates is unavailable, one is resolved, and more than one is ambiguous.

Counts are bounded to 512 and carry an explicit saturation flag. The parser does not infer values, periods, issuer identity, financial provenance, or Q4 identity.

## 4. Field-by-field semantic audit

| JSON path | Expected runtime type | Current interpretation | Parser behavior proven? | Real SEC semantics proven offline? |
| --- | --- | --- | --- | --- |
| root | object | accession index payload | yes | only that four live bodies decoded as objects compatible enough to expose entries |
| `directory` | object | archive directory container | yes | supported incompletely by successful live traversal; raw object omitted |
| `directory.item` | list | document relationship entries | yes | supported incompletely: live counters prove 70 iterable entries, not their complete schema |
| `directory.item[].name` | scalar stringable value | document basename/path identity | yes | supported incompletely: all 70 passed the safe-basename check; raw names omitted |
| `directory.item[].type` | scalar stringable value | SEC exhibit/document type | yes | **unknown**; no real raw token or verified schema sample is retained |
| `directory.item[].description` | scalar stringable value | bounded relationship description | yes | **unknown for real qualifying entries**; no live entry reached this gate and raw values are omitted |

Synthetic fixtures prove only that inputs shaped as `name`, `type`, and `description` are processed according to the code. The prior Phase 5J design report described these fields as relationship metadata, but that report was an implementation design statement, not independent retained evidence of SEC schema semantics.

The most important proposition—“`directory.item[].type` is the SEC exhibit-type field and contains values such as EX-99.1”—is **UNKNOWN** from the allowed offline evidence.

## 5. Live normalization trace

The saved artifact supports this exact trace:

```text
HTTP 200 index response
  -> JSON decoding succeeded
  -> classification = sec_index_json
  -> directory.item yielded 17 or 18 entries per target
  -> each entry was a dictionary with a name that passed SAFE_DOCUMENT
  -> item.get("type") failed EX99 normalization for every entry
  -> description was never evaluated
  -> eligible cardinality = 0
  -> final reason = no_eligible_index_exhibit
```

Information is discarded at several points:

- the complete response body is discarded after normalization;
- `name` is used for safety and potential candidate identity but is not retained in diagnostics;
- raw `type` is normalized or rejected and is not retained;
- `description` is truncated locally to 512 characters only after the type gate, then not retained;
- only bounded aggregate counters and final cardinality survive.

All 70 entries reached type rejection because none failed identity first and none produced a normalized EX-99-family token from the value returned by `item.get("type")`. The actual raw type values are **UNKNOWN**. They cannot be reconstructed from counters or guessed from filenames.

## 6. Document, form, item, exhibit, and provenance distinctions

The repository uses several independent identities that must not substitute for one another:

| Layer | Current source/contract | What it establishes | What it does not establish |
| --- | --- | --- | --- |
| Filing form | submissions `form` | `8-K` versus `8-K/A` filing identity | Item 2.02, exhibit type, earnings content, Q4 values |
| Filing item | submissions `items` | explicit Item 2.02 signal under the comma-delimited matcher | a unique earnings release, fiscal identity, exhibit identity, financial acceptance |
| Primary document | submissions `primaryDocument` plus bound accession/CIK | safe primary filing document identity | that the primary contains earnings tables or is parser-compatible |
| Exhibit/document type | currently assumed index `item[].type` | only an internal eligibility token if its external semantics are valid | financial provenance or metric acceptance |
| Description | currently assumed index `item[].description` | bounded text classification after type qualification | values, units, dates, or fiscal period |
| Filename/path | primary links or index `name` | safe bound archive document identity | exhibit semantics, earnings purpose, financial truth |
| Financial provenance | unchanged `direct-q4-1` document/table/metric checks | directly reported standalone Q4 metric only after full acceptance | cannot be supplied by form, item, type, description, or filename alone |

Repository document-type assumptions include:

- forms are restricted to `8-K` and `8-K/A` in metadata discovery;
- Item 2.02 remains mandatory in the bounded filing-window policy;
- 8-K and 8-K/A are distinct candidates and are not automatically collapsed;
- primary link discovery requires a safe same-accession URL plus nearby EX-99 and earnings/results/press-release language;
- index discovery accepts `EX-99` and numeric suffix variants, normalizing leading zeros;
- index descriptions must contain explicit earnings, financial results, quarterly results, press release, or results release semantics;
- filenames, order, proximity, ticker text, and “only attachment” status never establish eligibility; and
- neither metadata route creates financial provenance or bypasses `direct-q4-1`.

These are narrow internal contracts. Only the submissions form/item/primary-document behavior has retained real metadata certification. The live index field-to-exhibit semantic mapping has not.

## 7. Evidence matrix

| Proposition | Classification | Basis |
| --- | --- | --- |
| Current submissions can identify the bounded 8-K candidate | **PROVEN** | Phase 5H/5I/5J resolved exactly one candidate per fixed target |
| Candidate binding works | **PROVEN** | all four Phase 5I/5J targets bound and retrieved their selected primary |
| Primary retrieval works | **PROVEN** | four HTTP 200 primary responses in both 5I and 5J |
| Primary documents are not parser-sufficient under `direct-q4-1` | **PROVEN for these retrieved documents** | zero candidates and zero accepted observations for all four |
| Accession-scoped `index.json` retrieval works | **PROVEN for these targets** | four HTTP 200 responses with exact bound paths |
| Index JSON parses successfully | **PROVEN for these targets** | all four classified `sec_index_json` and yielded bounded entry counts |
| Safe basename checks work mechanically | **PROVEN** | synthetic safety tests plus live counter behavior |
| The real indexes contained zero unsafe identities among the 70 examined entries | **PROVEN under the implemented `name` interpretation** | live unsafe-identity count was zero |
| The field currently interpreted as exhibit type had no accepted EX-99-family value | **PROVEN under the implemented extraction** | 70 type rejections; zero normalized EX-99 entries |
| That field is definitively the SEC exhibit-type field | **UNKNOWN** | no retained raw schema example or independent offline specification |
| These filings contain no EX-99 exhibits | **UNKNOWN** | requires the unproven field-semantic mapping |
| These filings contain no earnings release | **UNKNOWN** | no exhibit body or verified alternate relationship evidence was retained |
| Another document type is appropriate financial evidence | **UNKNOWN** | no generic provenance-safe alternative is established |
| Description semantics were tested on real qualifying exhibit entries | **CONTRADICTED** | zero real entry passed the type gate; description rejection count stayed zero |
| `direct-q4-1` is incompatible with the actual earnings release | **UNKNOWN** | no independently established earnings-release exhibit was retrieved |
| `direct-q4-1` is incompatible with the four selected primary 8-K documents | **PROVEN for their observed layouts** | parser ran and found zero candidates |
| Index policy proves zero eligible exhibits under its own implementation | **PROVEN** | deterministic zero-cardinality result on all four indexes |
| Index policy proves absence of issuer earnings evidence | **CONTRADICTED** | eligibility outcome is narrower than evidence absence |

## 8. Fixture realism audit

The Phase 5J tests construct index payloads with `directory.item` entries containing `name`, `type`, and `description`.

| Fixture assumption | Classification | Explanation |
| --- | --- | --- |
| Nested `directory.item` traversal | **semantically unverified** | compatible with live traversal, but no retained real payload shows the complete schema |
| Entry is a dictionary | **supported but incomplete** | live entries passed dictionary/identity processing, but raw samples are absent |
| `name` represents a document identity | **supported but incomplete** | 70 live values passed safe-basename checks; external meaning is not independently documented offline |
| `type` contains EX-99-family exhibit types | **behavior-only synthetic and semantically unverified** | fixture convenience; no retained real value or verified schema evidence |
| `description` carries earnings/results labels | **behavior-only synthetic and semantically unverified** | no live entry reached description evaluation |
| EX-99.01/EX-99.001 normalize to EX-99.1 | **internal parser contract only** | deterministic normalization behavior, not evidence that SEC emits these variants here |
| zero/one/multiple eligible candidates control cardinality | **schema-independent parser mechanics** | valid fail-closed internal behavior once eligibility inputs are trusted |
| unsafe names are rejected | **schema-independent safety mechanics** | useful defense regardless of external semantics |

The fixtures remain valuable for mechanics, safety, budgeting, ambiguity, and parser isolation. They must not be cited as issuer evidence or as proof that live `index.json` uses `type` for exhibit identity.

No production or test change was needed to encode this conclusion: the existing tests already identify themselves as fixture-only and the documentation now states the semantic boundary explicitly. Changing fixtures would risk implying a policy correction that the evidence cannot support.

## 9. Existing offline evidence found

The audit searched repository code, tests, JSON fixtures, saved diagnostic artifacts, and prior phase reports for `index.json`, `directory.item`, EX-99 variants, exhibit-type claims, and retained filing relationships.

Found:

- synthetic Phase 5J index fixtures;
- the relationship normalizer and runner code;
- sanitized 5J entry/rejection counters;
- prior submissions artifacts and reports establishing form, Item 2.02, candidate, and primary-document behavior;
- prior design prose describing the intended index contract; and
- primary-HTML relationship fixtures and tests.

Not found:

- a retained real accession `index.json` payload or bounded schema fragment;
- a retained real raw `directory.item[].type` token;
- a retained real `directory.item[].description` value;
- an offline authoritative schema definition mapping the implemented `type` field to SEC exhibit type;
- an issuer-specific safe list of index documents;
- evidence establishing an alternate document type as generic earnings evidence; or
- a retrieved, independently identified earnings-release exhibit against which `direct-q4-1` compatibility could be tested.

Prior design documentation is evidence of intended behavior, not independent proof of SEC external semantics.

## 10. Unknowns

- The four real raw values returned by each entry's implemented `type` lookup.
- Whether `type` denotes exhibit type, another file/content category, an empty field, or a schema element with different semantics.
- Whether another index field carries SEC exhibit type.
- Whether the four indexes contain EX-99 attachments represented outside the assumed field.
- Whether descriptions are present and how they classify.
- Whether a qualifying earnings exhibit exists under a provenance-safe relationship.
- Whether such an exhibit would satisfy `direct-q4-1`.
- Whether an alternative explicit document type is generically valid financial evidence.

None may be filled from filenames, issuer familiarity, general memory, or inference.

## 11. Policy decision

**RECOMMENDATION D** is selected.

Offline evidence is insufficient to determine actual index document-type semantics. Recommendation A would overstate an unverified field contract. Recommendation B is unavailable because the interpretation is not demonstrably wrong. Recommendation C is unavailable because no other explicit document/exhibit type is proven to be a generic issuer-primary earnings relationship.

Keep `sec-index-json-ex99-earnings-1` unchanged and unregistered. Do not broaden it in place. A later, separately versioned policy is appropriate only after a minimal diagnostic establishes real bounded field semantics.

## 12. Minimal future diagnostic design and request budget

This is design only; no diagnostic or live behavior is implemented here.

### Question

For the same four fixed targets, what bounded document-type tokens and description classifications are actually present in each already-known, freshly rebound accession index?

### Required fresh safety sequence

The saved artifacts intentionally omit accessions and cannot safely authorize reuse of hidden live identities. A future run should preserve ephemeral same-run binding:

1. retrieve current submissions once per issuer;
2. rerun the frozen `bounded-filing-window-item-202-1` policy;
3. require exactly one candidate and exact safe binding per target;
4. request only that target's bound accession-scoped `index.json`;
5. collect bounded semantic aggregates; and
6. stop without primary-document or exhibit retrieval.

### Absolute minimum future HTTP budget

- current submissions: 2 total, one per issuer;
- filing indexes: 4 total, one per target;
- aggregate: **6 attempts**;
- per issuer: 3 attempts;
- retries: zero;
- followed redirects: zero;
- primary documents: zero;
- exhibits: zero.

Using only four index requests would bypass the ephemeral-binding safety model because the sanitized artifact intentionally omitted bound accessions. That shortcut is not recommended.

### Minimum retained diagnostics

Per target, retain only:

- discovery boundary/cardinality/binding states;
- index transport category, status, known bytes, and content classification;
- bounded entry count and saturation;
- safe versus unsafe identity counts;
- presence/absence counts for the candidate type-bearing fields under evaluation;
- normalized distinct type tokens from a conservative character allowlist, with counts and a small fixed cardinality cap;
- an explicit `other_or_unrepresentable` count rather than raw unsafe tokens;
- description-present count;
- bounded description category counts such as earnings/results/press-release/other, without raw descriptions;
- a bounded cross-tab of normalized type token by description category when cardinality permits; and
- explicit schema-path/version identity for every extracted token.

Do not retain index bodies, raw descriptions, full document lists, filenames, URLs, headers, credentials, User-Agent/contact data, raw exceptions, financial content, or unrestricted strings.

Candidate accession does not need to appear in the artifact. It should remain an ephemeral bound input used only to construct the official index URL. A target key of ticker/fiscal year and a non-reversible run-local binding state are sufficient for the diagnostic question.

The diagnostic must not decide financial eligibility. It should reveal field semantics for a later offline policy audit.

## 13. Parser isolation

`direct-q4-1` was not modified. No parser input, table rule, standalone-Q4 rule, concept rule, EPS rule, fiscal-identity rule, conflict rule, or provenance rule changed.

The observed zero candidates apply to the selected primary documents only. Because no independently qualified exhibit was retrieved, the evidence does not establish parser incompatibility with an actual issuer earnings release.

## 14. Production isolation

Confirmed through existing code/tests and the full regression suite:

- direct-Q4 remains unregistered;
- historical SEC remains disabled/unregistered;
- candidate-retrieval v1 remains unregistered;
- index-enabled candidate-retrieval v2 remains unregistered;
- no API route changed;
- no research assembler or DTO changed;
- no frontend changed;
- no database or migration changed;
- no AI prompt, schema, grounding, or generation behavior changed;
- no score, rating, directionality, or materiality rule changed; and
- no historical observation, comparison eligibility, or continuity state changed.

## 15. Validation

All validation was offline:

- Focused discovery/retrieval/index/direct-Q4/certification/SEC-history suite: **159 passed in 2.60 seconds**.
- Earnings/research/structured/frozen-AI regressions: **122 passed, 2 warnings in 3.86 seconds**.
- Full backend suite: **1,035 passed, 46 skipped, 148 subtests passed, 2 warnings in 18.46 seconds**.
- Skips are the existing optional cases; warnings are the existing FastAPI `on_event` deprecations.
- `git diff --check`: run after report creation and passed, with only existing line-ending notices where applicable.

No live CLI was executed during this phase.

## 16. Changed files

- Added `docs/outlook-phase6b5c2a5k-offline-document-type-semantics-audit.md`.

No application code, test behavior, configuration, immutable artifact, frontend, database, or production registration was changed.

## 17. Exact next step

Operator review should decide whether to authorize a later **offline implementation phase** for a versioned, metadata-only index-semantics diagnostic matching the six-request design above. That implementation must be fixture-qualified, production-isolated, and reviewed before any separate live authorization is considered.

Do not modify `sec-index-json-ex99-earnings-1` or `direct-q4-1` based on Phase 5J counters alone. Do not automatically run the proposed diagnostic.

**NO EXTERNAL REQUESTS WERE MADE.**

**NO REAL FILING, INDEX, OR EXHIBIT WAS RETRIEVED.**

**NO FINANCIAL ACCEPTANCE RULE WAS RELAXED.**

**DIRECT-Q4-1 WAS NOT MODIFIED.**

**NO PRODUCTION INTEGRATION WAS PERFORMED.**

**ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.**
