# Phase 6B.5C.2A.5W.10 — Offline revenue certification artifact completeness

## 1. Executive result

Future eight-document certification artifacts now carry a typed, complete partition-replay record for every qualified operand. A pure offline path validates, reconstructs, and replays those records without documents, network access, manifest inference, or issuer backfilling. Qualification and partition semantics are unchanged.

## 2. Root cause of incomplete replay

The Phase 5W.6 schema-1 artifact retained concept, period, unit, dimensions, accounting basis, scope, and source identifiers, but omitted the qualified context's entity scheme and entity value. Both values participate in exact partition identity, so the historical artifact cannot reproduce its original validator inputs.

## 3. Validator replay-field audit

Current `validate_revenue_operand_partition` consumes:

- operand role;
- expanded QName through exact or certified concept identity;
- unit numerator measures, denominator measures, structural form, and currency;
- context entity scheme and entity value;
- explicit dimensions and typed-dimension count;
- accounting basis and target fiscal year;
- context period start and end.

Dimensions also determine the validator's scope conflict. `reporting_scope` is retained for round-trip fidelity but is not independently compared by the current validator. Numeric values, ticker, issuer, CIK, accession, filing metadata, source URL, context/unit IDs, ordinal provenance, and DEI anchors are not validator inputs. Existing provenance identifiers remain retained separately.

## 4. Files changed

- `backend/app/models/outlook_inline_revenue.py`
- `backend/app/services/outlook_structured/inline_revenue_document_certification.py`
- `backend/tests/test_inline_revenue_document_certification.py`
- This report

## 5. Artifact/schema versioning

The runner is now `inline-revenue-eight-document-certification-2` and its artifact schema is `2`. Each replay DTO has its own required schema version `1`. Historical Phase 5W.6 remains schema `1`; it was not rewritten or upgraded.

## 6. Complete replay DTO

`RevenueOperandReplayEvidence` is immutable and contains role, expanded QName, canonical unit structure, replay context, accounting basis, target fiscal year, reporting scope, and typed provenance. `RevenueOperandReplayOperand` is the minimal immutable object presented to the existing validator after reconstruction.

The replay context contains exact entity scheme/value, period bounds, explicit dimensions, and typed-dimension count. The canonical unit excludes the non-semantic unit ID; the original unit ID remains in provenance.

## 7. Entity scheme/value retention

Serialization copies both values directly from the exact qualified operand context. It does not parse again or infer from ticker, CIK, URL, accession, or manifest data. Reconstruction returns the exact serialized lexical values.

## 8. Sanitization and bounds

The replay DTO rejects extra fields and is frozen. Entity scheme and value are required, nonempty, and capped at 512 characters. Context/unit identifiers are capped at 512; policy names at 128; currency at 32; dimensions and unit measure collections at 16; typed dimensions at 16; occurrence ordinals at 256. Completeness diagnostics retain at most 32 field names, each capped at 128 characters. No XML, filing prose, unrelated contexts, or unrelated identifiers are retained.

## 9. Round-trip reconstruction

The pure path is:

`qualified operand -> RevenueOperandReplayEvidence -> JSON-safe serialization -> validated evidence -> RevenueOperandReplayOperand`.

Tests compare every validator field and retained provenance across the round trip. Reconstruction uses only serialized evidence and supplies no defaults for partition-relevant fields.

## 10. Replay completeness contract

`assess_partition_replay_evidence` returns `complete` only when the entire typed record validates. Otherwise it returns `incomplete` with bounded field paths and no evidence object. `replay_certification_artifact_partitions` returns `replay_unavailable` with `incomplete_replay_evidence` if any of a partition's four roles is absent or incomplete. It never patches an input.

## 11. Historical 5W.6 behavior

`docs/diagnostics/phase6b5c2a5w6-qualifier-v2-live-certification-20261001.json` remains identifiable as schema `1`. Offline tests confirm both partitions are `replay_unavailable / incomplete_replay_evidence`. The artifact is read-only in the test and remains byte-for-byte unchanged. Known CIK values are not used to backfill entity identity.

## 12. Future certification-runner serialization

For each qualified role, the schema-2 runner adds `partition_replay_evidence` and a deterministic `partition_replay_completeness` assessment. The earlier sanitized qualified-operand summary remains present. Request accounting, exact URL allowlisting, manifest fingerprint validation, attempt limits, transport, parsing, qualification, and partition invocation are unchanged.

## 13. Partition/equivalence diagnostics

Offline replay calls the unchanged `revenue-operand-partition-identity-2` validator. Exact QName and `us-gaap-2024-2025-revenue-concept-equivalence-1` diagnostics are regenerated from the preserved original QNames. Tests confirm the certified cross-version state, original four QNames, record identity, and package fingerprints survive serialization and replay.

## 14. Test matrix

All required cases A–W are covered: complete round trip; exact entity, QName, unit, dimensions, accounting, fiscal year, periods, role, scope, and provenance preservation; four-operand direct/replay equality; entity mutation conflicts; exhaustive required-field removal; historical schema-1 rejection without backfill; network-path absence; unchanged runner safeguards; and Phase 5W.9 diagnostics after replay.

## 15. Validation

- Replay/artifact plus operand/partition/equivalence: **141 passed**.
- Date-transform, fiscal-anchor, and document certification: **137 passed**.
- Historical SEC/company: **49 passed**.
- Direct-Q4/XBRL: **350 passed**.
- Combined SEC/Q4: **649 passed**.
- Earnings/research/structured/frozen-AI: **122 passed**, with 2 existing FastAPI deprecation warnings.
- Full backend: **1,501 passed, 46 skipped, 148 subtests passed**, with the same 2 warnings.
- Compilation: successful.
- `git diff --check`: successful; it emitted only pre-existing line-ending conversion warnings for unrelated tracked files.

## 16. Known limitations

No historical artifact can become complete without a new authorized certification because missing entity identity is deliberately not inferred. The replay helper is bounded to the frozen AAPL FY2025 and NVDA FY2026 certification target set. It validates partition identity and geometry only; it performs no revenue arithmetic.

## 17. Production status

Only the future certification artifact evidence contract and pure offline replay path changed. The qualifier remains `sec-inline-xbrl-revenue-operand-2`; partition identity remains `revenue-operand-partition-identity-2`; the two taxonomy equivalence records are unchanged. No provider, database, research DTO, AI contract, or production integration changed.

## 18. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO LIVE CERTIFICATION WAS EXECUTED.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
NO QUALIFIER RULE WAS CHANGED.
NO PARTITION IDENTITY RULE WAS CHANGED.
NO TAXONOMY EQUIVALENCE RECORD WAS CHANGED.
THE HISTORICAL PHASE 5W.6 ARTIFACT WAS NOT MODIFIED OR BACKFILLED.
FUTURE CERTIFICATION ARTIFACTS NOW RETAIN COMPLETE PARTITION-REPLAY EVIDENCE.
NO REVENUE Q4 VALUE WAS DERIVED.
NO REVENUE SUBTRACTION WAS PERFORMED.
NO DILUTED EPS VALUE WAS DERIVED.
NO Q4 DERIVATION COMPONENT WAS IMPLEMENTED.
DIRECT-Q4-1 WAS NOT MODIFIED.
NO RESEARCH DTO OR AI CONTRACT WAS CHANGED.
NO DATABASE OR PRODUCTION PROVIDER WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
