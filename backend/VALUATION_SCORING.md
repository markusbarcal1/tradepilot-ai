# Relative Valuation Score Phase 2A

The Relative Valuation Score estimates how attractive a company's current
market multiples appear under a broad sector-aware model. It is independent
from the Financial Score: valuation measures the price being paid, while
financial scoring measures business quality.

The Relative Valuation Score is not an intrinsic-value estimate, price target,
or investment recommendation.

## Active model

Phase 2A contains one 100-point category:

| Metric | Default weight | Direction |
|---|---:|---|
| Forward P/E | 20 | Lower is more attractive |
| Trailing P/E | 12 | Lower is more attractive |
| PEG Ratio | 15 | Lower is more attractive |
| EV / EBITDA | 18 | Lower is more attractive |
| Price / Sales | 10 | Lower is more attractive |
| Price / Book | 8 | Lower is more attractive |
| Free Cash Flow Yield | 12 | Higher is more attractive |
| Earnings Yield | 5 | Higher is more attractive |

All metrics use bounded, monotonic piecewise-linear curves between excellent,
good, acceptable, and poor anchors. Thresholds and weights are centralized in
`valuation_analysis/config.py` and resolved sector overrides are immutable.

Classification bands are:

- 85–100: Deeply Undervalued
- 70–84.99: Undervalued
- 45–69.99: Fairly Valued
- 25–44.99: Expensive
- 0–24.99: Very Expensive

These labels describe relative valuation only and are not Buy, Sell, or Hold
recommendations.

## Metric formulas and source selection

- Trailing P/E = current price / positive trailing diluted EPS.
- Forward P/E = current price / positive forward EPS estimate.
- PEG = forward P/E / expected annual EPS growth in percentage points.
- EV / EBITDA = enterprise value / positive trailing EBITDA.
- Price / Sales = market capitalization / positive trailing revenue.
- Price / Book = market capitalization / positive common shareholder equity.
- Free Cash Flow Yield = trailing FCF / market capitalization.
- Earnings Yield = trailing net income / market capitalization.

Calculated values are preferred when finite inputs are available and currencies
are compatible. Provider-reported ratios are deterministic fallbacks when
calculation inputs are unavailable. Responses preserve the source, calculation
method, provider value, calculated value, and a discrepancy flag when the two
differ by more than 10%. Conflicting ratios are never averaged.

Price selection prefers regular-market price, then current price, then previous
close. The response exposes `price_source`, `price_as_of`, and
`price_is_fallback`. Valuation results use a versioned 12-hour cache; this
reduces provider traffic but means the score is not a streaming quotation.

## Economic support states

- `available`: finite and economically meaningful for scoring.
- `unavailable`: required provider data is missing.
- `not_meaningful`: the raw input exists but ordinary multiple interpretation
  is invalid, such as negative earnings, EBITDA, growth, or equity.
- `invalid`: a supported metric could not be scored safely.
- `unsupported_for_sector`: intentionally excluded by the resolved profile.

Economically invalid multiples display `N/M`; missing and unsupported values
display `N/A`. Negative FCF and earnings yields remain available raw values but
receive the bottom of the higher-is-better curve. Negative P/E, PEG, and
EV/EBITDA values are never interpreted as attractive.

## Sector profiles

Profiles use the canonical identifiers shared with Financial Analysis:
default, technology, communication services, healthcare, financials, consumer
discretionary, consumer staples, industrials, energy, materials, utilities,
and real estate.

Important broad adjustments include:

- Technology tolerates moderately higher P/E, EV/EBITDA, and Price/Sales;
  Price/Book is unsupported for the broad asset-light profile.
- Financials emphasize Forward P/E, Trailing P/E, Price/Book, and Earnings
  Yield; EV/EBITDA, Price/Sales, and FCF Yield are unsupported.
- Energy emphasizes EV/EBITDA and FCF Yield and reduces PEG weight.
- Utilities reduce FCF Yield weight and tolerate moderately higher EV/EBITDA
  and Price/Book.
- Real Estate uses Forward P/E, EV/EBITDA, Price/Sales, and Price/Book only.
  Trailing P/E, PEG, ordinary FCF Yield, and Earnings Yield are unsupported.

Other profiles make conservative weight or threshold adjustments. Unknown or
missing provider sectors use the default profile and expose that fallback.
These are sector-level assumptions, not industry or company-specific models.

## Currency consistency

The response exposes quote currency, financial-statement currency, and
`currency_consistent`. Obvious mismatches block independently calculated ratios
and yields; no currency conversion occurs. Missing currency metadata is exposed
as unknown rather than silently labeled consistent. Provider-reported
dimensionless ratios may still be used as fallbacks when available.

## Normalization and coverage

Configured metrics are the eight base metrics. Supported metrics remain active
after sector exclusions. Available metrics are supported metrics with valid
scores. Missing-supported metrics include unavailable, invalid, and
not-meaningful metrics.

```text
normalized score =
earned points from available supported metrics
/ available supported metric weight
× 100

weighted coverage =
available supported metric weight
/ total supported metric weight
```

Unsupported metrics are excluded from both denominators. Missing supported
metrics are excluded from the score denominator but remain in the coverage
denominator. `weighted_coverage`, `metric_count_coverage`, `percentage`, and
`coverage_method` make the definitions explicit. Results below 50% weighted
coverage return a controlled unavailable state rather than publishing a
low-support score.

## Unsupported instruments and limitations

ETFs, mutual funds, indexes, cryptocurrencies, preferred stock, and closed-end
funds return controlled unsupported responses.

Phase 2A does not include intrinsic value, DCF, historical valuation
percentiles, peer-company rankings, analyst targets, margin of safety,
bank-specific tangible-book valuation, REIT FFO/AFFO, utility dividend or
rate-base models, or energy cycle normalization. Forward estimates depend on
provider availability and methodology. Market prices and financial statements
can have different timestamps, and the engine does not convert currencies.

The architecture reserves room for future intrinsic value, market
expectations, and margin-of-safety categories, but Phase 2A does not expose
empty placeholder categories.
