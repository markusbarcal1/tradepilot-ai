"""Central configuration for the general-company Financial Score."""

SCORE_VERSION = "1.1"
CACHE_TTL_SECONDS = 12 * 60 * 60
MINIMUM_COVERAGE_PERCENT = 50
MINIMUM_CATEGORIES = 2
FALLBACK_EFFECTIVE_TAX_RATE = 0.21
MIN_EFFECTIVE_TAX_RATE = 0.0
MAX_EFFECTIVE_TAX_RATE = 0.50
NEAR_ZERO_GROWTH_BASE = 1e-9

FINANCIAL_SCORING_CONFIG = {
    "default": {
        "profitability": {
            "weight": 30,
            "metrics": {
                "roic": {
                    "label": "Return on Invested Capital", "weight": 8,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": 0.00, "acceptable": 0.08, "good": 0.12, "excellent": 0.20},
                },
                # The legacy API key is retained, but now explicitly represents ROCE.
                "return_on_capital": {
                    "label": "Return on Capital Employed", "weight": 6,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": 0.00, "acceptable": 0.08, "good": 0.15, "excellent": 0.25},
                },
                "return_on_equity": {
                    "label": "Return on Equity", "weight": 5,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": 0.00, "acceptable": 0.08, "good": 0.15, "excellent": 0.25},
                },
                "gross_margin": {
                    "label": "Gross Margin", "weight": 4,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": 0.10, "acceptable": 0.20, "good": 0.40, "excellent": 0.60},
                },
                "operating_margin": {
                    "label": "Operating Margin", "weight": 4,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": 0.00, "acceptable": 0.08, "good": 0.15, "excellent": 0.25},
                },
                "net_margin": {
                    "label": "Net Margin", "weight": 3,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": 0.00, "acceptable": 0.05, "good": 0.12, "excellent": 0.20},
                },
            },
        },
        "growth": {
            "weight": 25,
            "metrics": {
                "revenue_growth": {
                    "label": "Revenue Growth", "weight": 7,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": -0.10, "acceptable": 0.00, "good": 0.10, "excellent": 0.25},
                },
                "eps_growth": {
                    "label": "EPS Growth", "weight": 6,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": -0.20, "acceptable": 0.00, "good": 0.12, "excellent": 0.30},
                },
                "free_cash_flow_growth": {
                    "label": "Free Cash Flow Growth", "weight": 5,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": -0.20, "acceptable": 0.00, "good": 0.10, "excellent": 0.25},
                },
                "operating_income_growth": {
                    "label": "Operating Income Growth", "weight": 7,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": -0.15, "acceptable": 0.00, "good": 0.10, "excellent": 0.25},
                },
            },
        },
        "financial_health": {
            "weight": 25,
            "metrics": {
                "debt_to_equity": {
                    "label": "Debt to Equity", "weight": 9, "direction": "lower", "unit": "multiple",
                    "thresholds": {"excellent": 0.30, "good": 1.00, "acceptable": 2.00, "poor": 3.00},
                },
                "current_ratio": {
                    "label": "Current Ratio", "weight": 6, "direction": "higher", "unit": "multiple",
                    "thresholds": {"poor": 0.70, "acceptable": 1.00, "good": 1.50, "excellent": 2.00},
                },
                "interest_coverage": {
                    "label": "Interest Coverage", "weight": 5, "direction": "higher", "unit": "multiple",
                    "thresholds": {"poor": 0.00, "acceptable": 2.00, "good": 5.00, "excellent": 10.00},
                },
                "net_debt_to_ebitda": {
                    "label": "Net Debt / EBITDA", "weight": 5, "direction": "lower", "unit": "multiple",
                    "thresholds": {"excellent": 1.00, "good": 2.00, "acceptable": 3.50, "poor": 5.00},
                },
            },
        },
        "cash_flow_quality": {
            "weight": 20,
            "metrics": {
                "free_cash_flow": {
                    "label": "Positive Free Cash Flow", "weight": 4,
                    "direction": "positive", "unit": "currency",
                },
                "operating_cash_flow_to_net_income": {
                    "label": "Operating Cash Flow / Net Income", "weight": 5,
                    "direction": "higher", "unit": "multiple",
                    "thresholds": {"poor": 0.50, "acceptable": 0.80, "good": 1.00, "excellent": 1.20},
                },
                "free_cash_flow_margin": {
                    "label": "Free Cash Flow Margin", "weight": 4,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": -0.05, "acceptable": 0.00, "good": 0.08, "excellent": 0.15},
                },
                "positive_cash_flow_consistency": {
                    "label": "Positive Cash Flow Consistency", "weight": 3,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": 0.00, "acceptable": 0.50, "good": 0.75, "excellent": 1.00},
                },
                "operating_cash_flow_margin": {
                    "label": "Operating Cash Flow Margin", "weight": 4,
                    "direction": "higher", "unit": "percent",
                    "thresholds": {"poor": 0.00, "acceptable": 0.08, "good": 0.15, "excellent": 0.25},
                },
            },
        },
    },
}

DEFAULT_SCORING_PROFILE = FINANCIAL_SCORING_CONFIG["default"]
CATEGORY_WEIGHTS = {
    category: settings["weight"] for category, settings in DEFAULT_SCORING_PROFILE.items()
}
METRIC_WEIGHTS = {
    category: {key: metric["weight"] for key, metric in settings["metrics"].items()}
    for category, settings in DEFAULT_SCORING_PROFILE.items()
}
# Compatibility export for callers that inspected the old two-anchor configuration.
THRESHOLDS = {
    key: metric.get("thresholds")
    for category in DEFAULT_SCORING_PROFILE.values()
    for key, metric in category["metrics"].items()
    if "thresholds" in metric
}
