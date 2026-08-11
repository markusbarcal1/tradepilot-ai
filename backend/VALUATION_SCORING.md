# Valuation Analysis: Relative Valuation Phase 2A and Intrinsic Value Phase 2B

The Relative Valuation Score estimates how attractive a company's current
market multiples appear under a broad sector-aware model. It is independent
from the Financial Score: valuation measures the price being paid, while
financial scoring measures business quality.

Phase 2A remains the independent Relative Valuation component. Phase 2B adds
the Intrinsic Value range and attractiveness score. The top-level Valuation
Score combines those two components with transparent equal weights.

## Phase 2A active model

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

Phase 2A itself does not include intrinsic value, DCF, historical valuation
percentiles, peer-company rankings, analyst targets, margin of safety,
bank-specific tangible-book valuation, REIT FFO/AFFO, utility dividend or
rate-base models, or energy cycle normalization. Forward estimates depend on
provider availability and methodology. Market prices and financial statements
can have different timestamps, and the engine does not convert currencies.

## Phase 2B intrinsic value

Intrinsic Value estimates a range of business values from independent models.
It reports bear/base/bull or low/mid/high values rather than a falsely precise
target. The existing Phase 2A score, thresholds, weights, normalization, and
classification bands are unchanged. The API preserves all legacy top-level
Phase 2A fields and adds `relative_valuation` and `intrinsic_value` components.

### Discounted Cash Flow

The initial implementation uses a documented simplified trailing-free-cash-flow
DCF. It does not silently claim statement-derived FCFF when full working-capital
and tax reconciliation is unavailable. Five annual cash flows fade from a
resolved initial growth rate toward terminal growth. Terminal value uses the
perpetuity-growth formula. Enterprise value is converted to equity value by
subtracting debt, adding cash, and dividing by positive diluted shares.

Growth blends finite historical FCF, revenue, and operating-income growth with
available forward revenue and EPS growth. A median limits one-year outliers;
sign-changing and near-zero growth observations are excluded. Centralized
sector caps are more conservative for utilities, staples, energy, and materials.
Bear/base/bull cases vary initial growth, discount rate, and terminal growth.
The engine rejects cases where the discount rate does not exceed terminal
growth and reports terminal value as a percentage of enterprise value. More
than 80% terminal-value dependence reduces confidence.

WACC uses a configured 4% risk-free rate, 5% equity-risk premium, provider beta,
market equity and debt weights, after-tax debt cost, and a tax rate. Missing or
unsafe values use centralized, disclosed fallbacks. Beta is calculation-capped
to 0.5–2.0 while the raw provider value is retained. Missing beta, tax rate,
cost of debt, or capital weights appears in `fallbacks_used` and reduces
confidence. No live Treasury dependency is introduced.

### Earnings Power

Earnings Power uses the median of three to five annual diluted EPS observations
and applies configured sector-specific bear/base/bull P/E multiples. A median
prevents one extreme year from dominating the model. Fewer than three finite
observations or non-positive normalized EPS makes the model unavailable.
Energy and Materials receive lower multiples and reduced confidence.

### Historical Multiple Reversion

This model applies the 25th percentile, median, and 75th percentile of at least
three aligned historical multiples to the current fundamental base. P/E is the
ordinary default; Financials prefer Price/Book. It never substitutes the current
multiple for unavailable history and rejects non-positive or extreme multiples.
Provider snapshots without aligned historical ratios return this model as
unavailable. Cyclical sectors receive reduced confidence.

### Owner Earnings

Owner Earnings uses normalized annual net income plus depreciation and
amortization less a maintenance-CapEx proxy. Maintenance CapEx is the lesser of
total CapEx and D&A times a centralized sector multiplier. This approximation
is always disclosed in assumptions and fallbacks. The median of three annual
observations is divided by diluted shares and valued with sector-specific
cash-earnings multiples. Non-positive owner earnings or missing history is
unavailable. It is intentionally independent from the DCF forecast.

### Sector support and weights

Default configured model weights are DCF 40%, Earnings Power 20%, Historical
Multiple Reversion 25%, and Owner Earnings 15%. Energy uses 25/30/35/10.
Financials use Earnings Power 45% and Historical Reversion 55%; standard
corporate DCF and Owner Earnings are unsupported. Real Estate uses Historical
Reversion only because FFO, AFFO, and NAV are not implemented. Utilities use
conservative growth and terminal assumptions and lower Owner Earnings
confidence because of heavy capital requirements.

Weights normalize only across available supported models. Unsupported models
are excluded from coverage. Missing supported models reduce weighted coverage
but are excluded from aggregation. Combined low, midpoint, and high values are
weighted averages of available model ranges.

### Coverage, disagreement, and confidence

The response exposes configured, supported, available, missing-supported, and
unsupported model counts; available and supported weights; weighted and count
coverage; and the explicit coverage method. Model disagreement is the spread
between the largest and smallest available model midpoint divided by the
combined midpoint. Under 15% is low, 15–30% moderate, and over 30% high.

Confidence measures reliability, not attractiveness. High confidence requires
at least 80% weighted coverage, low disagreement, and almost no fallbacks.
Moderate confidence requires at least 50% coverage, no more than moderate
disagreement, and limited fallbacks. Other publishable results are Low. A model
can remain available at Low confidence when its estimate is still defensible.

### Current-price comparison

`discount_to_midpoint = (midpoint - current price) / midpoint` remains the
signed compatibility field, and
`price_to_fair_value = current price / midpoint`. Ratios at or below 0.85 are
described as Below Estimated Fair Value; above 0.85 through 1.15 as Near
Estimated Fair Value; and above 1.15 as Above Estimated Fair Value. These labels
are descriptive and are not margin-of-safety thresholds or recommendations.
Presentation metadata converts the signed comparison into a positive magnitude:
below midpoint is `Discount to Midpoint`, above midpoint is `Premium to
Midpoint`, and an effectively equal price is `Difference to Midpoint`.

### Intrinsic Value Score

Phase 2B also publishes a separate 0–100 Intrinsic Value Score. It does not
alter or blend with the Phase 2A Relative Valuation Score. The raw score is a
piecewise-linear mapping of current price divided by the intrinsic midpoint:
0.60=100, 0.75=90, 0.85=80, 1.00=60, 1.15=40, 1.30=20, and 1.50=0. Values
outside the anchors are bounded to 100 or 0.

The raw score is multiplied by confidence (High 1.00, Moderate 0.90, Low
0.75), weighted model coverage (`0.70 + 0.30 × coverage`), and model
disagreement (Low 1.00, Moderate 0.95, High 0.85). Low disagreement is below
15%, Moderate is 15–30%, and High is above 30%. Adjustments can only preserve
or reduce attractiveness. The final result is bounded to 0–100 and rounded at
serialization. Missing current price, midpoint, or available model evidence
returns a null score rather than zero.

Neutral score labels are Very Attractive (85–100), Attractive (70–84.9), Fair
(45–69.9), Expensive (25–44.9), and Very Expensive (0–24.9). These labels are
not Buy, Sell, or Hold recommendations.

### Combined Valuation Score

The final Phase 2B hierarchy is:

```text
Valuation Score
├── Relative Valuation — 50%
└── Intrinsic Value — 50%
```

Equal weighting is the initial transparent default because both components
answer independent questions and there is not yet empirical evidence for a
more precise split. Weights are centralized and can be recalibrated later.
Intrinsic Value already applies confidence, model coverage, and disagreement;
the combined score does not apply those penalties again.

When both scores are available, the combined score is their weighted average.
Missing supported components are excluded from the score denominator rather
than treated as zero. For example, an available Relative score of 70 with an
unavailable Intrinsic score remains 70, but combined coverage shows the missing
evidence. The existing Relative classification bands classify the combined
score: Deeply Undervalued 85–100, Undervalued 70–84.99, Fairly Valued 45–69.99,
Expensive 25–44.99, and Very Expensive below 25.

Top-level coverage is component-weighted evidence metadata:

```text
combined coverage =
    50% × relative weighted coverage
  + 50% × intrinsic model weighted coverage
```

Coverage does not multiply the combined score. Unsupported components are
excluded from its denominator, while missing supported components reduce it.
Relative and Intrinsic scores and their individual coverage remain available
in `relative_valuation`, `intrinsic_value`, and `score_components`.

Margin of Safety is not a separate score because current price versus fair
value is already the primary Intrinsic Value signal. Market Expectations is not
a separate score because forward P/E, PEG, forward EPS and growth inputs, and
DCF growth assumptions already incorporate forward expectations. Historical
context remains represented by Historical Multiple Reversion.

### Known limitations

Intrinsic estimates remain sensitive to growth, WACC, terminal growth, and
multiple assumptions. Forward estimates and historical statements depend on
provider availability and alignment. Maintenance CapEx is simplified. There is
no bank-specific excess-return or dividend model, REIT FFO/AFFO/NAV, utility
dividend model, commodity-cycle normalization, analyst-target aggregation,
Monte Carlo simulation, or Margin of Safety score. Negative DCF equity value is
floored at zero and disclosed; it is never treated as undervaluation.

> Intrinsic Value is an estimate based on model assumptions and
> historical/forward financial data. It is not a guaranteed future price,
> analyst price target, or investment recommendation.
