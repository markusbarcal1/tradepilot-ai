# Financial Score v1.1 (Phase 1A)

The ticker-level Financial Score measures general business quality using
fundamentals from the existing cached `yfinance` provider. It remains separate
from Technical Score and Trade Quality Score, and it is not used by the scanner.
Valuation metrics and recommendations are intentionally excluded; valuation
will eventually be a separate score family.

## Categories and weights

- Profitability (30): ROIC 8, ROCE 6, ROE 5, Gross Margin 4, Operating Margin 4,
  and Net Margin 3.
- Growth (25): Revenue Growth 7, EPS Growth 6, Free Cash Flow Growth 5, and
  Operating Income Growth 7.
- Financial Health (25): Debt to Equity 9, Current Ratio 6, Interest Coverage 5,
  and Net Debt to EBITDA 5.
- Cash Flow Quality (20): Positive Free Cash Flow 4, Operating Cash Flow to Net
  Income 5, Free Cash Flow Margin 4, Positive Cash Flow Consistency 3, and
  Operating Cash Flow Margin 4.

Metric weights, labels, units, directions, and four-point scoring anchors are
centralized in `app/services/financial_analysis/config.py`. Scores use monotonic
piecewise-linear interpolation between poor, acceptable, good, and excellent
anchors. The default profile is deliberately structured so sector and industry
overrides can be added later, but Phase 1A uses only general-company thresholds.

ROIC uses NOPAT divided by average invested capital when current and prior
balance-sheet values are available, otherwise current invested capital. A 21%
configured tax rate is used when the observed effective rate is unavailable or
outside the supported 0%–50% range. ROE requires positive equity and uses
average equity when possible. Sign-aware growth calculations cap loss/profit
transitions and reject near-zero comparison bases.

## Missing data and coverage

Missing or invalid metrics are explicit `N/A` values and are excluded rather
than scored as zero. Each category is normalized over its available metric
weight. The response includes available and expected metric counts, category
coverage, overall count coverage, weighted coverage, and a confidence label.
A score requires at least two scoreable categories and 50% weighted coverage;
otherwise the endpoint returns a controlled unavailable response.

Conventional leverage ratios remain excluded for financial-sector companies.
ETFs, mutual funds, indexes, and cryptocurrencies remain unsupported.

## Limitations

Provider row names, statement coverage, and reporting periods vary by ticker and
geography. Statement restatements and provider lag can affect results. Phase 1A
does not include sector-specific or industry-specific thresholds, financial
institution models, REIT FFO/AFFO, valuation ratios, fair-value estimates, or
analyst targets.
