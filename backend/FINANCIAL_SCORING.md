# Financial Score v1.2 — Sector-Aware Phase 1B

The ticker-level Financial Score answers how financially strong a company is
relative to broad expectations for its sector. It keeps the Phase 1A accounting
formulas, four categories, 0–100 scale, graduated curves, and missing-data
normalization. Sector profiles change interpretation, not raw metric
calculation.

Valuation remains a separate future score family. The Financial Score does not
use P/E, EV/EBITDA valuation, fair value, analyst targets, recommendations,
scanner ranking, Technical Score, or Trade Quality Score.

## Profile selection

The provider's explicit sector is normalized to one of these canonical
profiles:

- General Company (default)
- Technology
- Communication Services
- Healthcare
- Financials
- Consumer Discretionary
- Consumer Staples
- Industrials
- Energy
- Materials
- Utilities
- Real Estate

Aliases account for provider terms such as `Information Technology`,
`Financial Services`, `Consumer Cyclical`, `Consumer Defensive`, and
`Basic Materials`. Matching ignores capitalization and repeated surrounding
whitespace. Missing or unknown sectors use the default profile and preserve the
raw sector in the API response. Unknown values are logged for future mapping
improvements.

Profiles inherit the Phase 1A default configuration and apply only their
threshold, weight, category, or unsupported-metric overrides. Resolution creates
an immutable configuration and never mutates the default. Startup validation
checks every profile for:

- Category weights totaling 100.
- Active metric weights matching their category maximum.
- Finite, nonnegative weights.
- Valid metric directions.
- Monotonic scoring anchors.
- Valid, nonduplicated base metrics.

The response adds `sector`, `sector_profile`, `sector_profile_label`,
`sector_source`, `used_default_profile`, and `profile_version`. Cache keys
include both scoring and profile versions so older results cannot cross a model
change.

## Main sector adjustments

| Sector profile | Main adjustment |
|---|---|
| Technology | Higher margin, ROIC, growth, and cash-generation expectations |
| Communication Services | Moderate margin expectations and somewhat greater leverage tolerance |
| Healthcare | Moderate margin and growth expectations without pre-revenue biotech assumptions |
| Financials | Ordinary corporate leverage, liquidity, ROCE, and gross-margin metrics excluded |
| Consumer Discretionary | Lower margin expectations with leverage and cash flow retained |
| Consumer Staples | Lower growth expectations and greater cash-flow consistency emphasis |
| Industrials | Moderate margins and growth for capital-intensive cyclicality |
| Energy | Growth de-emphasized; financial health and cash flow emphasized |
| Materials | Lower margin and growth expectations with cash-flow stability retained |
| Utilities | Slower growth and higher leverage tolerated, but not automatically rewarded |
| Real Estate | Misleading GAAP earnings and free-cash-flow metrics excluded |

The default profile is unchanged from Phase 1A and remains the fallback for
unknown sectors.

## Unsupported metrics and coverage

`unsupported_for_sector` is distinct from provider-missing `unavailable` data.
Unsupported metrics have zero active weight, display as `N/A`, and do not count
in expected metrics or coverage. Missing supported metrics remain part of the
denominator and therefore reduce coverage.

Financials currently exclude ROCE, Gross Margin, Debt to Equity, Current Ratio,
Interest Coverage, and Net Debt to EBITDA. This prevents ordinary corporate
capital structure from distorting banks, insurers, and diversified financial
companies. The remaining profile emphasizes ROE, net margin, growth, and
supported cash-flow measures.

Real Estate currently excludes Net Margin, EPS Growth, Free Cash Flow Growth,
Free Cash Flow Margin, and Operating Cash Flow to Net Income. Revenue and
operating growth, margins, leverage, operating cash flow margin, and stability
remain supported.

Each category is normalized over available supported weight. The API returns
configured, supported, available, missing-supported, and unsupported metric
counts. In this terminology:

- Configured metrics are every metric in the base schema.
- Supported metrics are configured metrics active in the resolved profile.
- Available metrics are supported metrics with a finite value and valid score.
- Missing-supported metrics are active metrics without usable data.
- Unsupported metrics are intentional sector exclusions.

Category scores use metric weights, never metric counts:

```text
normalized category score =
earned points from available supported metrics
/ available supported metric weight
× category weight
```

Category weighted coverage is available weight divided by supported weight.
The separate `metric_count_coverage` field is available count divided by
supported count. Overall `coverage.percentage`, `coverage.ratio`, and
`weighted_coverage` are weight-based; `coverage_method` is `weighted`.

When a category has no available supported metrics, it is excluded once from
the overall category-weight denominator. The remaining normalized category
scores are scaled over their available category weights. This preserves the
Phase 1A missing-data philosophy without treating a missing category as zero or
normalizing an available category twice. At least two scoreable categories and
50% weighted coverage remain required.

## Limitations

These are initial broad-sector assumptions, not calibrated industry profiles or
peer percentiles. Heterogeneous sectors may still contain companies whose
economics differ materially from their broad profile.

- Financials do not yet include CET1, net interest margin, efficiency,
  non-performing loan, reserve, or insurance-solvency metrics.
- Real Estate does not yet include FFO, AFFO, NAV, occupancy, same-store NOI, or
  payout ratios.
- Healthcare has no pre-revenue biotechnology model.
- Utilities have no rate-base model.
- Energy has no commodity-cycle normalization.
- Provider row coverage, restatements, reporting periods, and sector metadata
  can vary by ticker and geography.

Industry-specific and company-type overrides are intentionally deferred.
Thresholds should be treated as model assumptions subject to later calibration.
