"""Phase 2A Relative Valuation Score configuration."""

VALUATION_SCORING_VERSION = "2A.1"
VALUATION_PROFILE_VERSION = "2A.1"
CACHE_TTL_SECONDS = 12 * 60 * 60
MINIMUM_COVERAGE_PERCENT = 50
DISCREPANCY_TOLERANCE = 0.10


def lower(excellent, good, acceptable, poor):
    return {
        "excellent": excellent, "good": good,
        "acceptable": acceptable, "poor": poor,
    }


def higher(poor, acceptable, good, excellent):
    return {
        "poor": poor, "acceptable": acceptable,
        "good": good, "excellent": excellent,
    }


DEFAULT_VALUATION_PROFILE = {
    "relative_valuation": {
        "label": "Relative Valuation",
        "weight": 100,
        "metrics": {
            "forward_pe": {
                "label": "Forward P/E", "weight": 20, "direction": "lower",
                "unit": "multiple", "thresholds": lower(10, 16, 24, 40),
            },
            "trailing_pe": {
                "label": "Trailing P/E", "weight": 12, "direction": "lower",
                "unit": "multiple", "thresholds": lower(10, 17, 25, 45),
            },
            "peg_ratio": {
                "label": "PEG Ratio", "weight": 15, "direction": "lower",
                "unit": "multiple", "thresholds": lower(0.75, 1.25, 2.0, 3.5),
            },
            "ev_to_ebitda": {
                "label": "EV / EBITDA", "weight": 18, "direction": "lower",
                "unit": "multiple", "thresholds": lower(6, 10, 15, 25),
            },
            "price_to_sales": {
                "label": "Price / Sales", "weight": 10, "direction": "lower",
                "unit": "multiple", "thresholds": lower(1, 3, 6, 12),
            },
            "price_to_book": {
                "label": "Price / Book", "weight": 8, "direction": "lower",
                "unit": "multiple", "thresholds": lower(1, 2, 4, 8),
            },
            "free_cash_flow_yield": {
                "label": "Free Cash Flow Yield", "weight": 12, "direction": "higher",
                "unit": "percent", "thresholds": higher(0, 0.03, 0.06, 0.10),
            },
            "earnings_yield": {
                "label": "Earnings Yield", "weight": 5, "direction": "higher",
                "unit": "percent", "thresholds": higher(0, 0.025, 0.05, 0.09),
            },
        },
    },
}

METRIC_EXPLANATIONS = {
    "forward_pe": "Measures the price paid for each dollar of expected earnings.",
    "trailing_pe": "Measures the price paid for each dollar of trailing earnings.",
    "peg_ratio": "Relates forward earnings valuation to expected EPS growth.",
    "ev_to_ebitda": "Compares enterprise value with trailing operating earnings before financing and non-cash charges.",
    "price_to_sales": "Compares market capitalization with trailing revenue.",
    "price_to_book": "Compares market capitalization with common shareholder equity.",
    "free_cash_flow_yield": "Measures free cash flow generated relative to market capitalization.",
    "earnings_yield": "Measures trailing net income generated relative to market capitalization.",
}
