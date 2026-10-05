# Phase 6B.5C.2A.5Y.3 — Offline Generic Revenue Operand Filing Selection

## 1. Executive result

`PRODUCTION-GENERIC-SELECTION-READY`

A pure deterministic offline policy now selects the exact FY/Q1/Q2/Q3 SEC filing identities for one explicit issuer and target fiscal year. This classification covers metadata selection only. It does not authorize submissions retrieval, filing-document retrieval, qualification, Q4 derivation, provider wiring, or production traffic.

## 2. Evidence/input boundary

The selector accepts an already-acquired SEC submissions metadata envelope and a separate explicit target request. It makes no I/O. Certification uses the retained `phase6b5c2a5w2-inline-revenue-metadata-20261001.json` artifact. That artifact preserves the required submissions identity fields for the eight frozen roles, but not the complete raw submissions responses; certification reconstructs only those retained submissions-shaped rows and records this limitation rather than claiming a raw-payload replay.

The target request supplies issuer, CIK, target fiscal year, and accepted Q1/Q2/Q3 report-period anchors. Those anchors are the safe handoff from already-qualified historical observations. The selector never derives fiscal year from ticker, wall-clock year, month number, Company Facts host-filing `fy/fp`, or issuer-specific knowledge.

## 3. Files changed

- `backend/app/models/outlook_revenue_filing_selection.py` — frozen input, provenance, selected-role, and result contracts.
- `backend/app/services/outlook_structured/revenue_filing_selection.py` — pure policy implementation.
- `backend/tests/test_revenue_filing_selection.py` — generic A–U matrix and retained-artifact certification.
- `docs/outlook-phase6b5c2a5y3-offline-generic-revenue-filing-selection.md` — this report.

## 4. Selection policy/version

The policy is `revenue-operand-filing-selection-1`. It is independent of `sec-inline-xbrl-revenue-operand-2`, `revenue-operand-partition-identity-2`, and `revenue-q4-derivation-1`.

## 5. Input schema

`RevenueFilingSelectionRequest` freezes ticker, issuer, ten-digit CIK, explicit target fiscal year, and exactly three role-labelled quarter-end anchors. `SecSubmissionsSelectionInput` freezes source identity, issuer, CIK, and at most 4,096 `SecSubmissionFilingRow` values. Each row carries accession, form, filing date, acceptance time, report date, primary document, and source ordinal.

## 6. Output schema

`RevenueFilingSelectionResult` has one of `selected`, `unavailable`, `ambiguous`, or `conflict`, a bounded reason, policy version, issuer identity, and target year. Success contains exactly four immutable `SelectedRevenueFiling` values in FY/Q1/Q2/Q3 order. Each preserves a safe future-retrieval `SelectedFilingDocument`, explicit `original` amendment state, source identity, and every collapsed source ordinal.

## 7. Supported forms

Quarter roles accept only `10-Q` candidates and detect `10-Q/A`. FY accepts only `10-K` candidates and detects `10-K/A`. Other forms cannot fill a role.

## 8. Fiscal identity

Fiscal identity comes from the caller's explicit target fiscal year and accepted Q1/Q2/Q3 report-period anchors, matched against submissions report dates. This supports calendar, non-calendar, 52-week, and 53-week calendars without month assumptions.

## 9. Role assignment

Q1/Q2/Q3 require exact report-date matches to their respective anchors. FY requires a 10-K report date following Q3 within the reviewed 70–105 day quarter bound. A candidate is never assigned by proximity alone: the three named anchors must first be strictly ordered and sequentially bounded.

## 10. Period geometry

Adjacent Q1→Q2 and Q2→Q3 report ends must each differ by 70–105 days. Q3→FY must also differ by 70–105 days, and FY must bound all quarter ends. Exact 90/91-day assumptions are absent.

## 11. Amendment policy

Submissions metadata cannot prove whether an amendment supersedes relevant financial statements. Consequently, any amendment candidate for a requested role—alone or beside an original—returns `ambiguous / amendment_ambiguous`. Newest-wins and accession-order rules are forbidden.

## 12. Duplicate policy

Rows collapse only when accession, form, filing date, report date, and primary document are identical. Their source ordinals are retained. Distinct accessions for one role return the appropriate multiple-candidate ambiguity.

## 13. Primary-document safety

Every selected role requires a ten-digit-CIK-correlated SEC accession, a filing date, and one bounded basename containing only ASCII letters, digits, dot, underscore, or hyphen. Missing names are unavailable; traversal, path separators, whitespace, and external URLs conflict. The archive URL is constructed only after these checks using the official SEC HTTPS origin.

## 14. Target-FY semantics

The selector processes exactly one explicitly requested target fiscal year. Unrelated rows for other years remain inert because they do not match the explicit quarter anchors and bounded annual geometry. Future orchestration—not this phase—may identify a Q4 gap and build this request from accepted historical observations.

## 15. Failure reasons

The frozen reasons are: `issuer_identity_missing`, `target_fiscal_year_missing`, `issuer_mismatch`, `annual_filing_missing`, `quarter_filing_missing`, `multiple_annual_candidates`, `multiple_quarter_candidates`, `amendment_ambiguous`, `report_period_missing`, `primary_document_missing`, `primary_document_invalid`, `fiscal_geometry_invalid`, `quarter_order_invalid`, `filing_date_missing`, and `accession_invalid`. No exception text is exposed as policy state.

## 16. AAPL FY2025 offline certification

Generic selection returned `selected` with FY/Q1/Q2/Q3. Accession, form, filing date, report date, and primary document exactly matched all four frozen 5W manifest identities. No AAPL constant exists in production selection code.

## 17. NVDA FY2026 offline certification

Generic selection returned `selected` with FY/Q1/Q2/Q3. The same five identity fields exactly matched all four frozen 5W manifest identities. No NVDA constant exists in production selection code.

## 18. Synthetic generic certification

Cases A–U cover calendar and non-calendar issuers; 52/53-week geometry; missing and duplicate roles; missing and duplicate annuals; original-plus-amendment and amendment-only metadata; missing reports; malformed/unsafe documents; wrong forms; out-of-bound annual geometry; reversed quarters; issuer mismatch; exact duplicates; multiple years; and explicit-year isolation.

## 19. Test matrix

The new suite has 23 passing tests. Parameterization separately certifies cases A–D, I–J, and primary-document variants, while named tests cover every requested A–U scenario and the two retained targets.

## 20. Validation

- New filing-selection tests: **23 passed**.
- Historical SEC submissions/date/fiscal tests: **25 passed**.
- Inline operand, partition/equivalence, anchor, date-transform, and certification tests: **250 passed**.
- Q4 derivation/reconciliation tests: **39 passed**.
- Series/projection/DTO tests: **40 passed**.
- Direct-Q4 regression tests: **350 passed**.
- Frozen AI/research tests: **70 passed**, 2 pre-existing FastAPI deprecation warnings.
- Full backend: **1,603 passed, 46 skipped, 148 subtests passed**, 2 pre-existing FastAPI deprecation warnings.
- Python compilation: **passed**.
- `git diff --check`: **passed** for the phase files.

## 21. Known limitations

- The selector requires Q1/Q2/Q3 anchors from accepted upstream history; it does not create fiscal facts.
- The retained AAPL/NVDA artifact is identity-complete for comparison but is not a byte-for-byte retained raw submissions response.
- Amendment-bearing roles deliberately fail closed.
- No filing content is inspected, so selection does not assert that revenue evidence exists.
- The policy covers domestic 10-K/10-Q issuers only.

## 22. Production status

`PRODUCTION-GENERIC-SELECTION-READY` for the isolated offline selection boundary. No production acquisition or provider status changed.

## 23. Selection-readiness decision

The first 5Y.2 blocker is resolved: a production-generic selected-filing builder now exists and is fixture-certified. Its output is sufficient for a future bounded retriever while preserving exact metadata provenance and failing closed on ambiguity.

## 24. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
ONLY OFFLINE FILING-METADATA SELECTION WAS IMPLEMENTED.
NO FILING DOCUMENT WAS RETRIEVED.
NO INLINE XBRL WAS PARSED.
NO Q4 VALUE WAS DERIVED.
NO Q4 RECONCILIATION WAS PERFORMED.
NO TAXONOMY EQUIVALENCE WAS CHANGED.
NO HISTORICAL PROVIDER WAS ENABLED.
NO PROVIDER WAS REGISTERED.
NO ANALYZE WIRING WAS CHANGED.
NO RESEARCH DTO WAS CHANGED.
NO AI CONTRACT OR PROMPT WAS CHANGED.
NO FRONTEND WAS CHANGED.
NO DATABASE OR SCANNER BEHAVIOR WAS CHANGED.
NO DEPLOYMENT WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
