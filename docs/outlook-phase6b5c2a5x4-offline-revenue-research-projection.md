# Phase 6B.5C.2A.5X.4 — Offline revenue research projection and growth

## 1. Executive result

An isolated deterministic projection now converts an already-assembled, research-eligible quarterly revenue series into chart-ready points, exact Decimal QoQ/YoY growth, explicit derived-evidence annotations, and bounded descriptive statistics. Actual retained evidence produces seven AAPL points with three YoY comparisons and six NVDA points with two YoY comparisons.

## 2. Input/evidence boundary

The only input is typed `RevenueHistoricalSeriesResult`. It must be `available`, `research_eligible=true`, contain at least five points, and remain independently consecutive/comparable. Insufficient, conflicting, malformed, non-consecutive, or shorter series return typed unavailable/conflict results. No history is reconstructed.

## 3. Files changed

- `backend/app/models/outlook_revenue_research.py`
- `backend/app/services/outlook_structured/revenue_research.py`
- `backend/tests/test_revenue_research.py`
- this report

No upstream policy, provider, research DTO, API, AI, or frontend file changed.

## 4. Projection policy/version

Policy identity is `revenue-research-projection-1`; schema is `1`. It remains separate from assembly, reconciliation, derivation, and qualification policies.

## 5. Research-quarter schema

Each frozen `RevenueResearchQuarter` contains established fiscal identity and display label, exact period/duration, exact Decimal revenue, separate billions display value, unit/currency/basis, source kind/policy, derived flag, evidence identity, optional derivation/reconciliation policies, and typed QoQ/YoY results.

## 6. Exact/display revenue

`exact_revenue` remains authoritative. `revenue_billions` is a separate Decimal division by `1000000000`; it never replaces source value. Pydantic JSON-mode serialization represents Decimal values as strings, avoiding binary-float conversion.

## 7. QoQ calculation

For each adjacent established fiscal quarter, QoQ is `(current - previous) / previous * 100`. The first point is unavailable; a zero prior value returns `zero_denominator`. The projection independently rejects non-consecutive series rather than calculating across gaps.

## 8. YoY calculation

YoY uses lookup key `(fiscal_year - 1, same fiscal_quarter)`, then applies the same Decimal formula. It never uses calendar months, array position alone, annual revenue, interpolation, or inferred missing points.

## 9. Derived-evidence growth semantics

Authoritative derived Q4 participates normally. Every growth result retains current/comparison source kinds and `uses_derived_evidence`. Direct Q3→derived Q4 and derived Q4→direct Q1 QoQ are flagged. Synthetic coverage also verifies YoY with derived current or prior evidence.

## 10. Precision/quantization

Financial calculations use Decimal with precision `50`. The unquantized Decimal result remains in `exact_growth_pct`. Only `display_growth_pct` is quantized afterward to `0.1` percentage point with `ROUND_HALF_UP`. No float conversion occurs.

## 11. Summary statistics

The descriptive summary contains observation/direct/derived counts, earliest/latest quarters, latest exact revenue, latest available exact QoQ/YoY, comparison counts, minimum/maximum revenue, and absolute first-to-latest change. It contains no score, classification, forecast, CAGR, regression, estimate, or recommendation.

## 12. Chart-ready projection

The output is structured data only: fiscal label, period, exact/display revenue, source identity, derived status, QoQ, YoY, and evidence references. No chart library, colors, style, tooltip prose, frontend component, or API contract was added.

## 13. Provenance

Each point retains its assembly evidence identity and source policy. Derived points additionally expose `revenue-q4-reconciliation-1` and `revenue-q4-derivation-1`; upstream typed series provenance still contains the complete reconciliation and four operands. Growth explicitly records whether either operand was derived.

## 14. AAPL offline result

Seven points; 6 QoQ and 3 YoY comparisons; 6 direct and 1 derived.

| Quarter | Exact revenue | Source | Exact QoQ % (display) | Exact YoY % (display) |
|---|---:|---|---:|---:|
| FY2025 Q1 | 124300000000 | direct | unavailable | unavailable |
| FY2025 Q2 | 95359000000 | direct | -23.283185840707964601769911504424778761061946902655 (-23.3) | unavailable |
| FY2025 Q3 | 94036000000 | direct | -1.3873887100326135970385595486529850354974360049917 (-1.4) | unavailable |
| FY2025 Q4 | 102466000000 | derived | 8.9646518354672678548640946020672933770045514483815 (9.0), derived evidence | unavailable |
| FY2026 Q1 | 143756000000 | direct | 40.296293404641539632658637987234790076708371557395 (40.3), derived evidence | 15.652453740949316170555108608205953338696701528560 (15.7) |
| FY2026 Q2 | 111184000000 | direct | -22.657836890286318484098055037702774145079161913242 (-22.7) | 16.595182415922985769565536551348063633217630218438 (16.6) |
| FY2026 Q3 | 109417000000 | direct | -1.5892574471146927615484242337026910346812491005900 (-1.6) | 16.356501765281381598536730613807477987153855970054 (16.4) |

Summary: latest revenue `109417000000`; latest exact QoQ `-1.5892574471146927615484242337026910346812491005900`; latest exact YoY `16.356501765281381598536730613807477987153855970054`; minimum `94036000000`; maximum `143756000000`; first-to-latest change `-14883000000`.

## 15. NVDA offline result

Six points; 5 QoQ and 2 YoY comparisons; 5 direct and 1 derived.

| Quarter | Exact revenue | Source | Exact QoQ % (display) | Exact YoY % (display) |
|---|---:|---|---:|---:|
| FY2026 Q1 | 44062000000 | direct | unavailable | unavailable |
| FY2026 Q2 | 46743000000 | direct | 6.0846080522899550633198674594889020017248422677137 (6.1) | unavailable |
| FY2026 Q3 | 57006000000 | direct | 21.956228740132212309864578653488222835504781464604 (22.0) | unavailable |
| FY2026 Q4 | 68127000000 | derived | 19.508472792337648668561204083780654667929691611409 (19.5), derived evidence | unavailable |
| FY2027 Q1 | 81615000000 | direct | 19.798317847549429741512175789334625038530978907041 (19.8), derived evidence | 85.227633788752212791067132676682855975670645908039 (85.2) |
| FY2027 Q2 | 96221000000 | direct | 17.896220057587453286773264718495374624762604913313 (17.9) | 105.85114348672528506942215946772778811800697430631 (105.9) |

Summary: latest revenue `96221000000`; latest exact QoQ `17.896220057587453286773264718495374624762604913313`; latest exact YoY `105.85114348672528506942215946772778811800697430631`; minimum `44062000000`; maximum `96221000000`; first-to-latest change `52159000000`.

## 16. Test matrix

The 14 focused tests cover eligible/rejected/conflict inputs; exact revenue and labels; exact QoQ and deterministic display quantization; zero denominators; exact fiscal YoY identity; malformed fiscal chronology; actual AAPL/NVDA point and YoY counts; derived Q4 policies; direct→derived and derived→direct QoQ; derived-current/prior YoY flags; exact summaries; and source inspection for float, network, EPS, scoring, classification, forecasting, and production DTO dependencies.

## 17. Validation

- New research projection: **14 passed**.
- Projection/series/reconciliation/derivation: **72 passed**.
- Full revenue stack through operand/partition/equivalence/replay: **213 passed**.
- Date-transform, fiscal-anchor and document certification: **137 passed**.
- Historical SEC/company: **49 passed**.
- Direct-Q4/XBRL plus projection stack: **563 passed**.
- Combined SEC/Q4: **612 passed**.
- Earnings/research/structured/frozen-AI: **122 passed**, with 2 existing FastAPI `on_event` deprecation warnings.
- Full backend: **1,573 passed, 46 skipped, 148 subtests passed**, with the same 2 warnings.
- Compilation: successful.
- `git diff --check`: successful, with only pre-existing line-ending notices.

## 18. Known limitations

The layer is descriptive and bounded to the assembled run. Decimal division uses deterministic precision 50 because repeating ratios have no finite Decimal representation. It does not forecast, classify, score, annualize, interpolate, calculate CAGR, project EPS, or integrate any production DTO/UI.

## 19. Production status

The projection is isolated and unregistered. Historical qualification/providers, Q4 derivation/reconciliation, series assembly, production research DTO, routes, AI prompt/context, frontend/charts, API, persistence, database, scanner, and configuration are unchanged.

## 20. Exact next step

REVIEW ONLY.

NO EXTERNAL REQUESTS WERE MADE.
NO SEC OR FASB RESOURCE WAS RETRIEVED.
ONLY OFFLINE REVENUE RESEARCH PROJECTION WAS IMPLEMENTED.
ALL REVENUE AND GROWTH CALCULATIONS USE DECIMAL ARITHMETIC.
YOY REQUIRES THE SAME ESTABLISHED FISCAL QUARTER ONE FISCAL YEAR APART.
DERIVED Q4 REMAINS EXPLICITLY IDENTIFIED.
GROWTH USING DERIVED EVIDENCE REMAINS EXPLICITLY IDENTIFIED.
NO SCORING, FORECASTING, OR TREND CLASSIFICATION WAS IMPLEMENTED.
NO DILUTED EPS HISTORY OR GROWTH WAS IMPLEMENTED.
NO HISTORICAL PROVIDER WAS REGISTERED.
NO PRODUCTION RESEARCH DTO WAS MODIFIED.
NO AI CONTRACT OR PROMPT WAS CHANGED.
NO FRONTEND OR API WAS CHANGED.
NO DATABASE OR PRODUCTION PROVIDER WAS CHANGED.
NO PRODUCTION INTEGRATION WAS PERFORMED.
ANY FUTURE EXTERNAL REQUEST REQUIRES NEW EXPLICIT OPERATOR AUTHORIZATION.
