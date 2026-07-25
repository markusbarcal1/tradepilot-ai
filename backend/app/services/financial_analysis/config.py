"""Financial Score v1.0 configuration.

Thresholds use broad, cross-industry ranges and linear interpolation so small
changes do not create binary pass/fail jumps. Valuation is intentionally
excluded. Missing metrics are excluded and their weights become score coverage.
"""

SCORE_VERSION = "1.0"
CACHE_TTL_SECONDS = 12 * 60 * 60
MINIMUM_COVERAGE_PERCENT = 50
MINIMUM_CATEGORIES = 2

CATEGORY_WEIGHTS = {
    "profitability": 30,
    "growth": 25,
    "financial_health": 25,
    "cash_flow_quality": 20,
}

METRIC_WEIGHTS = {
    "profitability": {
        "return_on_capital": 12,
        "operating_margin": 10,
        "net_margin": 8,
    },
    "growth": {
        "revenue_growth": 10,
        "eps_growth": 9,
        "free_cash_flow_growth": 6,
    },
    "financial_health": {
        "debt_to_equity": 9,
        "current_ratio": 6,
        "interest_coverage": 5,
        "net_debt_to_ebitda": 5,
    },
    "cash_flow_quality": {
        "free_cash_flow": 6,
        "operating_cash_flow_to_net_income": 6,
        "free_cash_flow_margin": 5,
        "positive_cash_flow_consistency": 3,
    },
}

# (weak, strong) anchors. Descending anchors make lower values score better.
THRESHOLDS = {
    "return_on_capital": (0.0, 0.20),
    "operating_margin": (0.0, 0.25),
    "net_margin": (0.0, 0.20),
    "revenue_growth": (-0.10, 0.20),
    "eps_growth": (-0.20, 0.25),
    "free_cash_flow_growth": (-0.20, 0.25),
    "debt_to_equity": (3.0, 0.3),
    "current_ratio": (0.7, 2.0),
    "interest_coverage": (0.0, 10.0),
    "net_debt_to_ebitda": (5.0, 1.0),
    "operating_cash_flow_to_net_income": (0.5, 1.2),
    "free_cash_flow_margin": (-0.05, 0.15),
    "positive_cash_flow_consistency": (0.0, 1.0),
}
