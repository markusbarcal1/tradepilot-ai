"""Centralized Phase 2A relative and Phase 2B intrinsic valuation configuration."""

RELATIVE_VALUATION_SCORING_VERSION = "2A.1"
VALUATION_SCORING_VERSION = "2B.3"
VALUATION_PROFILE_VERSION = "2A.1"
INTRINSIC_VALUE_VERSION = "2B.2"
CACHE_TTL_SECONDS = 12 * 60 * 60
MINIMUM_COVERAGE_PERCENT = 50
DISCREPANCY_TOLERANCE = 0.10

INTRINSIC_MODEL_WEIGHTS = {
    "discounted_cash_flow": 40,
    "earnings_power": 20,
    "historical_multiple_reversion": 25,
    "owner_earnings": 15,
}
INTRINSIC_SECTOR_OVERRIDES = {
    "financials": {"discounted_cash_flow": 0, "earnings_power": 45,
                   "historical_multiple_reversion": 55, "owner_earnings": 0},
    "energy": {"discounted_cash_flow": 25, "earnings_power": 30,
               "historical_multiple_reversion": 35, "owner_earnings": 10},
    "real_estate": {"discounted_cash_flow": 0, "earnings_power": 0,
                    "historical_multiple_reversion": 100, "owner_earnings": 0},
}
INITIAL_GROWTH_BOUNDS = {
    "default": (-0.10, 0.25), "technology": (-0.10, 0.30),
    "consumer_staples": (-0.08, 0.12), "utilities": (-0.05, 0.08),
    "energy": (-0.10, 0.10), "materials": (-0.10, 0.10),
}
TERMINAL_GROWTH_BOUNDS = (0.01, 0.035)
SECTOR_TERMINAL_GROWTH = {"utilities": 0.02, "energy": 0.02, "materials": 0.02}
DEFAULT_RISK_FREE_RATE = 0.04
DEFAULT_EQUITY_RISK_PREMIUM = 0.05
DEFAULT_TAX_RATE = 0.21
DEFAULT_COST_OF_DEBT = 0.055
BETA_CALCULATION_BOUNDS = (0.5, 2.0)
DISCOUNT_RATE_BOUNDS = (0.06, 0.18)
DCF_SCENARIOS = {
    "bear": {"growth_delta": -0.03, "discount_delta": 0.01, "terminal_delta": -0.005},
    "base": {"growth_delta": 0, "discount_delta": 0, "terminal_delta": 0},
    "bull": {"growth_delta": 0.03, "discount_delta": -0.0075, "terminal_delta": 0.005},
}
EARNINGS_MULTIPLES = {
    "default": (12, 16, 20), "technology": (16, 22, 28),
    "financials": (9, 12, 15), "energy": (8, 11, 14),
    "materials": (9, 12, 15), "utilities": (12, 15, 18),
}
OWNER_EARNINGS_MULTIPLES = {
    "default": (10, 14, 18), "technology": (14, 19, 24),
    "energy": (7, 10, 13), "materials": (8, 11, 14), "utilities": (8, 11, 14),
}
MAINTENANCE_CAPEX_MULTIPLIER = {
    "default": 1.0, "technology": 0.8, "utilities": 1.2,
    "energy": 1.1, "materials": 1.1,
}
COMPARISON_BANDS = (0.85, 1.15)
TERMINAL_DOMINANCE_THRESHOLD = 0.80
INTRINSIC_PRICE_SCORE_ANCHORS = (
    (0.60, 100.0), (0.75, 90.0), (0.85, 80.0), (1.00, 60.0),
    (1.15, 40.0), (1.30, 20.0), (1.50, 0.0),
)
INTRINSIC_CONFIDENCE_MULTIPLIERS = {
    "high": 1.00, "moderate": 0.90, "low": 0.75,
}
INTRINSIC_DISAGREEMENT_MULTIPLIERS = {
    "low": 1.00, "moderate": 0.95, "high": 0.85,
}
VALUATION_COMPONENT_WEIGHTS = {
    "relative_valuation": 0.50,
    "intrinsic_value": 0.50,
}


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
