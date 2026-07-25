# Financial Score v1.0

The ticker-level Financial Score uses fundamentals from the existing `yfinance`
provider. It excludes valuation and is not used by the scanner.

Weights: Profitability 30, Growth 25, Financial Health 25, and Cash Flow
Quality 20. Metric weights and interpolation anchors are centralized in
`app/services/financial_analysis/config.py`.

Missing metrics are excluded rather than scored as zero. Each category is
normalized over its available metric weight, while coverage retains the
original 100-point weighting. A score requires at least two categories and 50%
coverage. Lower coverage returns an unavailable result; coverage below 100%
returns a partial result. Conventional leverage ratios are excluded for
financial-sector companies. ETFs, funds, indexes, and cryptocurrencies are
unsupported.

Limitations: provider fields vary by ticker and geography; business-type and
industry-relative thresholds are not yet modeled; statement restatements and
provider lag may affect results; REIT-specific FFO/AFFO is not available.
