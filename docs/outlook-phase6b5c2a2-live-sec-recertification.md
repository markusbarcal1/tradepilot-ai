# Phase 6B.5C.2A.2 — Second Live SEC Historical Coverage Certification

Date: 2026-09-27

## Decision

**The corrected normalizer passed the targeted live correction check, but Phase 6B.5C.2B production integration remains no-go.**

All three issuers now produce accepted current revenue and diluted-EPS observations. Fiscal identity, repeated comparative disclosures, exact source provenance, and strict comparison gates operated on live records. However, no issuer produced an accepted Q4 observation, no metric reached five consecutive quarters, ABTC contains material unresolved version conflicts, and AAPL/NVDA each reach eight observations only by spanning Q4 gaps. Successful retrieval and isolated comparisons are not sufficient for the declared historical-visualization contract.

No normalization rule was changed after live execution. No Analyze, public DTO, frontend, AI, scoring, authentication, database, production-provider, or recent-Earnings pipeline was modified.

## Authorization and actual requests

The operator authorized one new cold attempt for AAPL, NVDA, and ABTC, at most three official SEC HTTP attempts per ticker and nine total. The batch used only the existing SEC ticker mapping, Company Facts, and submissions endpoints.

| Ticker | Status | HTTP attempts | Cache reads / loads / hits | Elapsed |
| --- | --- | ---: | --- | ---: |
| AAPL | Available | 3 | 1 / 1 / 0 | 2.193 s |
| NVDA | Available | 3 | 1 / 1 / 0 | 3.066 s |
| ABTC | Available | 3 | 1 / 1 / 0 | 2.989 s |
| **Total** | — | **9** | — | **8.248 s** |

The aggregate guard counted attempted client calls before dispatch and refused a tenth attempt. HTTP attempts were forced to one per client call. There were no retries, supplemental requests, or second runs.

New artifacts, separate from the first certification:

- `docs/diagnostics/phase6b5c2a2-aapl.json`
- `docs/diagnostics/phase6b5c2a2-nvda.json`
- `docs/diagnostics/phase6b5c2a2-abtc.json`

Each artifact records every retained observation's dates, concept, unit, exact decimal value, form, accession, filing and acceptance times, official URL, version state, comparison eligibility, missing periods, bounded rejections, source-processing counts, and certification execution statistics.

## Pre-live safeguard verification

Before network access:

- focused SEC history tests passed: `25 passed`;
- fiscal resolution was verified to anchor represented periods to exact dates and submissions report dates rather than host-filing FY/FQ alone;
- repeated disclosures, exact duplicates, amendments, and non-amendment conflicts had separate offline cases;
- supported concept/unit streams were newest-first and interleaved under the source cap;
- Basic EPS diagnostics ran after supported facts and were bounded;
- Q4 required a short 10-K/10-K/A context with exact report-date anchoring;
- history was disabled by default and absent from `configured_providers()`;
- the SEC User-Agent was configured without printing its value;
- configuration was three requests per ticker, one HTTP attempt, five-second timeout, and one-second SEC interval;
- no Yahoo, OpenAI, paid-provider, or other provider dependency existed in the diagnostic path;
- second-run artifact paths did not exist;
- the new aggregate nine-attempt guard had offline regression coverage.

## Live source processing

| Ticker | Supported source facts seen | Processed | Retained observations | Rejections |
| --- | ---: | ---: | ---: | ---: |
| AAPL | 1,014 | 256 | 26 | 120 |
| NVDA | 926 | 256 | 26 | 152 |
| ABTC | 192 | 155 | 26 | 83 |

AAPL and NVDA reached the existing 256-fact processing cap, but newest-first/fair allocation preserved the newest eight current quarters available for both metrics. ABTC did not reach the cap. The cap limits older-history assessment; it did not cause the recent-period gaps documented below.

## Accepted observations

All values below are `current`, comparison-eligible SEC Company Facts. Duplicate and conflicted versions remain in the artifacts with their own provenance and are not counted as distinct current quarters.

### AAPL

Both metrics use 10-Q filings. Revenue concept is `RevenueFromContractWithCustomerExcludingAssessedTax` in USD; EPS concept is `EarningsPerShareDiluted` in USD/shares.

| Fiscal period | Exact dates | Revenue | Diluted EPS | Accession |
| --- | --- | ---: | ---: | --- |
| FY2024 Q2 | 2023-12-31–2024-03-30 | 90,753,000,000 | 1.53 | `0000320193-24-000069` |
| FY2024 Q3 | 2024-03-31–2024-06-29 | 85,777,000,000 | 1.40 | `0000320193-24-000081` |
| FY2025 Q1 | 2024-09-29–2024-12-28 | 124,300,000,000 | 2.40 | `0000320193-25-000008` |
| FY2025 Q2 | 2024-12-29–2025-03-29 | 95,359,000,000 | 1.65 | `0000320193-25-000057` |
| FY2025 Q3 | 2025-03-30–2025-06-28 | 94,036,000,000 | 1.57 | `0000320193-25-000073` |
| FY2026 Q1 | 2025-09-28–2025-12-27 | 143,756,000,000 | 2.84 | `0000320193-26-000006` |
| FY2026 Q2 | 2025-12-28–2026-03-28 | 111,184,000,000 | 2.01 | `0000320193-26-000013` |
| FY2026 Q3 | 2026-03-29–2026-06-27 | 109,417,000,000 | 2.02 | `0000320193-26-000020` |

There are 8 current quarters and 5 later-filing duplicate disclosures per metric, with no retained conflict. Missing FY2024 Q4 and FY2025 Q4 break continuity.

### NVDA

Both metrics use 10-Q filings. Revenue concept is `Revenues` in USD; EPS concept is `EarningsPerShareDiluted` in USD/shares.

| Fiscal period | Exact dates | Revenue | Diluted EPS | Accession |
| --- | --- | ---: | ---: | --- |
| FY2025 Q1 | 2024-01-29–2024-04-28 | 26,044,000,000 | Conflict; no current value | `0001045810-24-000124` |
| FY2025 Q2 | 2024-04-29–2024-07-28 | 30,040,000,000 | 0.67 | `0001045810-24-000264` |
| FY2025 Q3 | 2024-07-29–2024-10-27 | 35,082,000,000 | 0.78 | `0001045810-24-000316` |
| FY2026 Q1 | 2025-01-27–2025-04-27 | 44,062,000,000 | 0.76 | `0001045810-25-000116` |
| FY2026 Q2 | 2025-04-28–2025-07-27 | 46,743,000,000 | 1.08 | `0001045810-25-000209` |
| FY2026 Q3 | 2025-07-28–2025-10-26 | 57,006,000,000 | 1.30 | `0001045810-25-000230` |
| FY2027 Q1 | 2026-01-26–2026-04-26 | 81,615,000,000 | 2.39 | `0001045810-26-000052` |
| FY2027 Q2 | 2026-04-27–2026-07-26 | 96,221,000,000 | 2.46 | `0001045810-26-000075` |

Revenue has 8 current quarters and 5 duplicates. Diluted EPS has 7 current quarters, 4 duplicates, and 2 conflicted FY2025 Q1 versions: 5.98 from the original 2024 filing and 0.60 repeated in a 2025 filing. The later value is consistent with a stock-split presentation change, but Company Facts does not provide a deterministic amendment relationship here, so the normalizer correctly leaves both in conflict.

### ABTC

Both metrics use 10-Q filings. Revenue concept is `Revenues` in USD; EPS concept is `EarningsPerShareDiluted` in USD/shares.

| Fiscal period | Exact dates | Revenue | Diluted EPS | Accession |
| --- | --- | ---: | ---: | --- |
| FY2024 Q1 | 2024-01-01–2024-03-31 | 7,490,000 | Conflict; no current value | `0001213900-24-042504` |
| FY2024 Q2 | 2024-04-01–2024-06-30 | 5,515,000 | -0.10 | `0001213900-24-068996` |
| FY2024 Q3 | 2024-07-01–2024-09-30 | Conflict; no current value | -0.15 | `0001213900-24-097500` |
| FY2025 Q1 | 2025-01-01–2025-03-31 | Conflict | Conflict | See artifact |
| FY2025 Q2 | 2025-04-01–2025-06-30 | Conflict | Conflict | See artifact |
| FY2025 Q3 | 2025-07-01–2025-09-30 | 64,220,000 | No current value | `0001193125-25-281390` |
| FY2026 Q1 | 2026-01-01–2026-03-31 | 62,118,000 | -0.08 | `0001193125-26-209008` |
| FY2026 Q2 | 2026-04-01–2026-06-30 | 67,015,000 | -0.80 | `0001193125-26-329472` |

Revenue has 5 current quarters, 2 duplicates, and 6 conflict versions across FY2024 Q3 and FY2025 Q1/Q2. Diluted EPS has 4 current quarters, 1 duplicate, and 8 conflict versions across FY2023 Q3, FY2024 Q1, and FY2025 Q1/Q2. Later non-amendment filings report materially different comparative values; these are not silently promoted.

## Coverage and strict comparisons

| Ticker | Metric | Current distinct quarters | Longest consecutive run | Five consecutive? | Eight comparable? |
| --- | --- | ---: | ---: | --- | --- |
| AAPL | Revenue | 8 | 3 | No | No |
| AAPL | Diluted EPS | 8 | 3 | No | No |
| NVDA | Revenue | 8 | 3 | No | No |
| NVDA | Diluted EPS | 7 | 3 | No | No |
| ABTC | Revenue | 5 | 2 | No | No |
| ABTC | Diluted EPS | 4 | 2 | No | No |

Eligible sequential comparisons:

- AAPL, both metrics: FY2024 Q2→Q3; FY2025 Q1→Q2 and Q2→Q3; FY2026 Q1→Q2 and Q2→Q3.
- NVDA revenue: FY2025 Q1→Q2 and Q2→Q3; FY2026 Q1→Q2 and Q2→Q3; FY2027 Q1→Q2.
- NVDA diluted EPS: FY2025 Q2→Q3; FY2026 Q1→Q2 and Q2→Q3; FY2027 Q1→Q2.
- ABTC revenue: FY2024 Q1→Q2 and FY2026 Q1→Q2.
- ABTC diluted EPS: FY2024 Q2→Q3 and FY2026 Q1→Q2.

Eligible YoY comparisons:

- AAPL, both metrics: FY2024 Q2→FY2025 Q2; FY2024 Q3→FY2025 Q3; FY2025 Q1/Q2/Q3→the matching FY2026 quarters.
- NVDA revenue: FY2025 Q1/Q2/Q3→matching FY2026 quarters and FY2026 Q1/Q2→matching FY2027 quarters.
- NVDA diluted EPS: FY2025 Q2/Q3→matching FY2026 quarters and FY2026 Q1/Q2→matching FY2027 quarters.
- ABTC: none.

The strict gate required matching metric, concept, unit, accounting/share/scope identities, active versions, and exact fiscal adjacency. Eight retained observations were not mislabeled as eight comparable consecutive quarters.

## Q4 certification

No directly reported standalone Q4 observation was accepted for any ticker or metric.

| Ticker | Direct Q4 | Annual/YTD evidence | Missing Q4 | Ambiguous/conflicting candidate |
| --- | --- | --- | --- | --- |
| AAPL | None | 10 annual-period rejections; 70 non-standalone contexts | FY2024 and FY2025, both metrics | Older short `fp=FY` contexts lacked exact report-date anchors or conflicted |
| NVDA | None | 10 annual-period rejections; 68 non-standalone contexts | FY2025 and FY2026, both metrics | 11 unresolved and 55 conflicting fiscal-identity rejections include older annual-host comparative contexts |
| ABTC | None | 8 annual-period rejections; 48 non-standalone contexts | FY2024/FY2025 revenue and EPS gaps | 3 unresolved and 12 conflicting fiscal-identity rejections; no qualifying direct Q4 |

The live evidence supports considering a separately approved, provenance-rich **revenue-only Q4 derivation audit** because missing Q4 prevents all five-quarter runs. Such a phase would need exact annual and Q1–Q3 operands with identical concept, unit, scope, version, and fiscal identity, plus explicit derived labeling. It must not derive diluted EPS by subtraction. No derivation was performed here.

## Reconciliation with saved recent Earnings evidence

### AAPL FY2026 Q3

- Fiscal identity and period end agree: FY2026 Q3 ended 2026-06-27. Historical Company Facts additionally provides start 2026-03-29.
- Historical revenue is exactly USD 109,417,000,000 from `RevenueFromContractWithCustomerExcludingAssessedTax` in 10-Q accession `0000320193-26-000020`. The saved earnings release stores USD 109.4 billion, rounded to one decimal billion. These values agree at the saved precision, but the saved evidence is not exact enough to assert exact-value identity.
- Historical diluted EPS is USD 2.02/share from `EarningsPerShareDiluted`; the saved value is USD 2.02/share. Metric and value agree.
- Historical scope is SEC Company Fact entity data from the 10-Q filed 2026-07-31. Saved evidence is the issuer earnings-release exhibit in 8-K accession `0000320193-26-000018`, published 2026-07-30. Provenance and timing are different and are not described as identical.

Classification: EPS agrees; revenue agrees at saved display precision with an exactness limitation; source-version difference is expected.

### NVDA FY2027 Q2

- Fiscal identity and period end agree: FY2027 Q2 ended 2026-07-26. Historical Company Facts provides start 2026-04-27.
- Historical revenue is exactly USD 96,221,000,000 using `Revenues`, from 10-Q accession `0001045810-26-000075` filed/accepted 2026-08-26.
- Saved evidence stores USD 96.2 billion from the issuer earnings-release exhibit in 8-K accession `0001045810-26-000073`. The values agree at saved precision, but exact equality cannot be asserted from the rounded saved amount.
- Reporting scope and source documents differ: Company Facts/10-Q versus issuer earnings release/8-K exhibit. Both are primary SEC-hosted sources.
- No diluted-EPS reconciliation was required because the saved accepted evidence lacks that metric.

Classification: revenue agrees at saved display precision; exact-value comparison is unavailable; source-version/provenance difference is expected.

## Failure analysis and comparison with the first certification

| Area | First certification | Second certification |
| --- | --- | --- |
| Retrieval | 3 requests each | 3 attempts each under a tested aggregate cap |
| Accepted observations | Zero for all issuers | AAPL 16 current, NVDA 15 current, ABTC 9 current |
| Source-cap ordering | AAPL exhausted diagnostics on old Basic EPS | Newest relevant facts accepted; Basic EPS bounded after supported facts |
| Comparative fiscal identity | NVDA/ABTC rejected all candidates as context ambiguity | Repeated exact-date disclosures resolve; genuine conflicts remain explicit |
| Q4 | None | Still none |
| Five-quarter continuity | None | Still none; longest run is three |
| Recent-Earnings reconciliation | Missing observation | Matching periods found for AAPL and NVDA, with rounded-value and provenance distinctions |

Remaining blockers are not retrieval failures or current-period source-cap failures:

- **Unsupported Q4 representation:** primary continuity blocker for AAPL and NVDA.
- **Amendment/version conflict:** NVDA FY2025 Q1 diluted EPS and multiple ABTC periods lack explicit amended-form linkage.
- **Genuine conflicting structured facts:** later ABTC non-amendment comparative values differ materially.
- **Missing filing metadata / fiscal identity:** older annual-host short contexts remain unresolved when no exact report-date anchor exists.
- **Bounded history:** AAPL/NVDA processing caps constrain older assessment, but not the newest declared horizon.
- **No qualifying structured fact:** applies where Company Facts exposes annual/YTD values but no directly reported anchored Q4.

No normalization rule was weakened to eliminate these blockers.

## Validation

- Pre-live focused SEC history suite: `25 passed`.
- Live execution: exactly 9 official SEC HTTP attempts, 3 per ticker, no retries.
- No Yahoo, OpenAI, paid-provider, or other external request occurred.
- Relevant post-certification SEC/Earnings/research/structured regressions: `85 passed`, with two existing FastAPI `on_event` deprecation warnings.
- `git diff --check`: passed. Additional no-index whitespace checks passed for the new/untracked certification files.

## Recommendation and integration gate

**No-go for Phase 6B.5C.2B.** The prior production criteria require at least five consecutive compatible observations for a rendered trend. Every metric fails that threshold, and direct Q4 coverage is zero.

Recommended next technical phase: an offline Q4 coverage and provenance design/audit. It should determine whether direct 10-K inline-XBRL contexts can be qualified beyond Company Facts and whether revenue-only annual-minus-Q1–Q3 derivation can be made deterministic and transparently labeled. EPS derivation should remain prohibited. ABTC corporate/reorganization-related comparative conflicts need a separate source-version policy audit, not automatic override logic.

Another live run, historical retrieval expansion, derivation implementation, or production integration requires separate operator approval.
