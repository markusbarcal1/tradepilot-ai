from .config import (
    CATEGORY_WEIGHTS, METRIC_WEIGHTS, MINIMUM_CATEGORIES,
    MINIMUM_COVERAGE_PERCENT, SCORE_VERSION, THRESHOLDS,
)
from .metrics import format_metric, valid_number

METRIC_LABELS = {
    "return_on_capital": "Return on Capital",
    "operating_margin": "Operating Margin",
    "net_margin": "Net Margin",
    "revenue_growth": "Revenue Growth",
    "eps_growth": "EPS Growth",
    "free_cash_flow_growth": "Free Cash Flow Growth",
    "debt_to_equity": "Debt to Equity",
    "current_ratio": "Current Ratio",
    "interest_coverage": "Interest Coverage",
    "net_debt_to_ebitda": "Net Debt / EBITDA",
    "free_cash_flow": "Free Cash Flow",
    "operating_cash_flow_to_net_income": "Operating Cash Flow / Net Income",
    "free_cash_flow_margin": "Free Cash Flow Margin",
    "positive_cash_flow_consistency": "Positive Cash Flow Consistency",
}

METRIC_EXPLANATIONS = {
    "return_on_capital": "Measures profit generated from the capital invested in the business.",
    "operating_margin": "Measures operating profitability after core business expenses.",
    "net_margin": "Measures bottom-line profit retained from revenue.",
    "revenue_growth": "Measures the year-over-year direction of company revenue.",
    "eps_growth": "Measures the year-over-year direction of earnings per share.",
    "free_cash_flow_growth": "Measures improvement or deterioration in free cash flow.",
    "debt_to_equity": "Measures debt relative to shareholder equity.",
    "current_ratio": "Measures short-term assets available to cover short-term obligations.",
    "interest_coverage": "Measures operating earnings available to cover interest expense.",
    "net_debt_to_ebitda": "Measures net leverage relative to operating earnings.",
    "free_cash_flow": "Checks whether the business currently generates positive free cash flow.",
    "operating_cash_flow_to_net_income": "Measures whether reported earnings are supported by operating cash flow.",
    "free_cash_flow_margin": "Measures free cash flow generated from each dollar of revenue.",
    "positive_cash_flow_consistency": "Measures how consistently recent annual free cash flow has remained positive.",
}

METRIC_REFERENCES = {
    "return_on_capital": "Scoring range: 0% to 20%",
    "operating_margin": "Scoring range: 0% to 25%",
    "net_margin": "Scoring range: 0% to 20%",
    "revenue_growth": "Scoring range: -10% to 20%",
    "eps_growth": "Scoring range: -20% to 25%",
    "free_cash_flow_growth": "Scoring range: -20% to 25%",
    "debt_to_equity": "Lower is stronger; scoring range: 3.0x to 0.3x",
    "current_ratio": "Scoring range: 0.7x to 2.0x",
    "interest_coverage": "Scoring range: 0x to 10x",
    "net_debt_to_ebitda": "Lower is stronger; scoring range: 5.0x to 1.0x",
    "free_cash_flow": "Positive free cash flow receives full credit",
    "operating_cash_flow_to_net_income": "Scoring range: 0.5x to 1.2x",
    "free_cash_flow_margin": "Scoring range: -5% to 15%",
    "positive_cash_flow_consistency": "Scoring range: 0% to 100%",
}


def score_label(score):
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Strong"
    if score >= 55:
        return "Fair"
    if score >= 40:
        return "Weak"
    return "Poor"


def _normalized_quality(key, value):
    value = valid_number(value)
    if value is None:
        return None
    if key == "free_cash_flow":
        return 1.0 if value > 0 else 0.0
    low, high = THRESHOLDS[key]
    if high == low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def score_financial_metrics(metrics):
    categories = {}
    available_weight = 0
    available_categories = 0
    total_weighted_points = 0.0

    for category, max_score in CATEGORY_WEIGHTS.items():
        weighted_points = 0.0
        category_available = 0
        metric_results = []
        for key, weight in METRIC_WEIGHTS[category].items():
            value = metrics.get(key)
            quality = _normalized_quality(key, value)
            if quality is None:
                metric_results.append({
                    "key": key,
                    "label": METRIC_LABELS[key],
                    "value": None,
                    "formatted_value": "Data unavailable",
                    "score": None,
                    "max_score": weight,
                    "status": "unavailable",
                    "availability": "unavailable",
                    "explanation": METRIC_EXPLANATIONS[key],
                    "reference": "Excluded from score normalization",
                })
                continue
            points = quality * weight
            weighted_points += points
            total_weighted_points += points
            category_available += weight
            available_weight += weight
            metric_results.append({
                "key": key,
                "label": METRIC_LABELS[key],
                "value": value,
                "formatted_value": format_metric(key, value),
                "score": round(points, 1),
                "max_score": weight,
                "status": score_label(round(quality * 100)).lower(),
                "availability": "available",
                "explanation": METRIC_EXPLANATIONS[key],
                "reference": METRIC_REFERENCES[key],
            })

        if category_available:
            available_categories += 1
            normalized = round(weighted_points / category_available * max_score)
            normalized = max(0, min(normalized, max_score))
            categories[category] = {
                "score": normalized,
                "max_score": max_score,
                "label": score_label(round(normalized / max_score * 100)),
                "available_weight": category_available,
                "metrics": metric_results,
                "details": metric_results,
                "normalization_note": (
                    f"Category score normalized using "
                    f"{sum(item['availability'] == 'available' for item in metric_results)} "
                    f"of {len(metric_results)} available metrics."
                    if category_available < max_score else None
                ),
            }
        else:
            categories[category] = {
                "score": None,
                "max_score": max_score,
                "label": "Unavailable",
                "available_weight": 0,
                "metrics": metric_results,
                "details": metric_results,
                "normalization_note": "No category metrics were available; this category was excluded from score normalization.",
            }

    coverage = round(available_weight)
    confidence = "high" if coverage >= 80 else "moderate" if coverage >= 60 else "low" if coverage else "none"
    coverage_result = {
        "percentage": coverage,
        "available_weight": available_weight,
        "total_weight": 100,
        "confidence": confidence,
    }
    if coverage < MINIMUM_COVERAGE_PERCENT or available_categories < MINIMUM_CATEGORIES:
        return {
            "status": "unavailable",
            "score": None,
            "label": "Unavailable",
            "coverage": coverage_result,
            "reason_code": "insufficient_financial_data",
            "message": "The financial-data provider did not return enough reliable information.",
            "categories": categories,
            "version": SCORE_VERSION,
        }

    total = round(total_weighted_points / available_weight * 100)
    total = max(0, min(total, 100))
    status = "available" if coverage == 100 else "partial"
    return {
        "status": status,
        "score": total,
        "label": score_label(total),
        "coverage": coverage_result,
        "categories": categories,
        "message": "Score is based on limited available financial data." if status == "partial" else None,
        "version": SCORE_VERSION,
    }
