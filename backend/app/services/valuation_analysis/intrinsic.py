"""Transparent multi-model Phase 2B intrinsic-value calculations and aggregation."""

import math
from statistics import median

from .assumptions import history_values, resolve_assumptions
from .config import (
    COMPARISON_BANDS, DCF_SCENARIOS, EARNINGS_MULTIPLES, INTRINSIC_MODEL_WEIGHTS,
    INTRINSIC_CONFIDENCE_MULTIPLIERS, INTRINSIC_DISAGREEMENT_MULTIPLIERS,
    INTRINSIC_PRICE_SCORE_ANCHORS, INTRINSIC_SECTOR_OVERRIDES,
    INTRINSIC_VALUE_VERSION, MAINTENANCE_CAPEX_MULTIPLIER,
    OWNER_EARNINGS_MULTIPLES, TERMINAL_DOMINANCE_THRESHOLD,
)
from .metrics import valid_number

LABELS = {
    "discounted_cash_flow": "Discounted Cash Flow",
    "earnings_power": "Earnings Power",
    "historical_multiple_reversion": "Historical Multiple Reversion",
    "owner_earnings": "Owner Earnings",
}


def _result(key, weight, status="unavailable", reason=None, **values):
    return {"model": key, "label": LABELS[key], "supported": status != "unsupported_for_sector",
            "status": status, "fair_value_low": None, "fair_value_mid": None,
            "fair_value_high": None, "confidence": "low", "weight": weight,
            "normalized_weight": 0, "assumptions": {}, "fallbacks_used": [],
            "reason": reason, **values}


def _confidence(fallbacks, warning=False):
    if warning or len(fallbacks) >= 3:
        return "low"
    return "moderate" if fallbacks else "high"


def score_price_to_fair_value(ratio):
    """Map price/fair-value to deterministic attractiveness on a 0-100 curve."""
    ratio = valid_number(ratio)
    if ratio is None or ratio < 0:
        return None
    anchors = INTRINSIC_PRICE_SCORE_ANCHORS
    if ratio <= anchors[0][0]:
        return anchors[0][1]
    if ratio >= anchors[-1][0]:
        return anchors[-1][1]
    for (left_ratio, left_score), (right_ratio, right_score) in zip(anchors, anchors[1:]):
        if left_ratio <= ratio <= right_ratio:
            position = (ratio - left_ratio) / (right_ratio - left_ratio)
            return left_score + position * (right_score - left_score)
    return None


def intrinsic_score_classification(score):
    if score >= 85:
        return "very_attractive", "Very Attractive"
    if score >= 70:
        return "attractive", "Attractive"
    if score >= 45:
        return "fair", "Fair"
    if score >= 25:
        return "expensive", "Expensive"
    return "very_expensive", "Very Expensive"


def calculate_intrinsic_score(price_to_fair_value, confidence, weighted_coverage, disagreement):
    raw_score = score_price_to_fair_value(price_to_fair_value)
    coverage = valid_number(weighted_coverage)
    disagreement = valid_number(disagreement)
    confidence_key = str(confidence or "").lower()
    if raw_score is None or coverage is None or disagreement is None:
        return None
    coverage = min(1.0, max(0.0, coverage))
    if disagreement < 0.15:
        disagreement_band = "low"
    elif disagreement <= 0.30:
        disagreement_band = "moderate"
    else:
        disagreement_band = "high"
    confidence_multiplier = INTRINSIC_CONFIDENCE_MULTIPLIERS.get(confidence_key)
    if confidence_multiplier is None:
        return None
    coverage_multiplier = 0.70 + 0.30 * coverage
    disagreement_multiplier = INTRINSIC_DISAGREEMENT_MULTIPLIERS[disagreement_band]
    score = min(100.0, max(0.0, raw_score * confidence_multiplier
                            * coverage_multiplier * disagreement_multiplier))
    status, label = intrinsic_score_classification(score)
    return {
        "score": round(score, 1), "score_status": status, "score_label": label,
        "raw_attractiveness_score": round(raw_score, 1),
        "score_adjustments": {
            "confidence_multiplier": confidence_multiplier,
            "coverage_multiplier": round(coverage_multiplier, 4),
            "disagreement_multiplier": disagreement_multiplier,
            "disagreement_band": disagreement_band,
        },
    }


def price_difference_metadata(current_price, fair_value_midpoint):
    current = valid_number(current_price)
    midpoint = valid_number(fair_value_midpoint)
    if current is None or midpoint is None or midpoint <= 0:
        return {
            "discount_to_midpoint": None, "price_difference_type": None,
            "price_difference_label": None, "price_difference_percentage": None,
        }
    signed_difference = (midpoint - current) / midpoint
    if abs(signed_difference) <= 1e-6:
        difference_type, difference_label = "difference", "Difference to Midpoint"
    elif signed_difference > 0:
        difference_type, difference_label = "discount", "Discount to Midpoint"
    else:
        difference_type, difference_label = "premium", "Premium to Midpoint"
    return {
        "discount_to_midpoint": signed_difference,
        "price_difference_type": difference_type,
        "price_difference_label": difference_label,
        "price_difference_percentage": abs(signed_difference),
    }


def _dcf_case(fcf, growth, discount, terminal, debt, cash, shares):
    if discount <= terminal or shares <= 0:
        return None
    flows, current = [], fcf
    for year in range(1, 6):
        faded = growth + (terminal - growth) * year / 5
        current *= 1 + faded
        flows.append(current)
    explicit = sum(flow / ((1 + discount) ** year) for year, flow in enumerate(flows, 1))
    terminal_value = flows[-1] * (1 + terminal) / (discount - terminal)
    pv_terminal = terminal_value / ((1 + discount) ** 5)
    enterprise = explicit + pv_terminal
    equity = enterprise - debt + cash
    return {"fair_value": max(0, equity / shares), "enterprise_value": enterprise,
            "equity_value": equity,
            "terminal_value_percentage_of_enterprise_value": pv_terminal / enterprise if enterprise > 0 else None}


def discounted_cash_flow(snapshot, profile, weight):
    if profile in {"financials", "real_estate"}:
        return _result("discounted_cash_flow", weight, "unsupported_for_sector",
                       "Standard corporate FCFF DCF is not used for this sector profile")
    raw = snapshot.values
    fcf = valid_number(raw.get("free_cash_flow"))
    if fcf is None:
        history = history_values(snapshot, "free_cash_flow")
        fcf = history[-1] if history else None
    if fcf is None or fcf <= 0:
        return _result("discounted_cash_flow", weight, reason="Positive trailing free cash flow unavailable")
    shares, debt, cash = (valid_number(raw.get(key)) for key in ("diluted_shares", "total_debt", "cash"))
    if shares is None or shares <= 0:
        return _result("discounted_cash_flow", weight, reason="Reliable positive diluted share count unavailable")
    assumptions = resolve_assumptions(snapshot, profile)
    fallbacks = list(assumptions["fallbacks_used"])
    debt, cash = max(0, debt or 0), max(0, cash or 0)
    cases = {}
    for name, scenario in DCF_SCENARIOS.items():
        terminal = assumptions["terminal_growth_rate"] + scenario["terminal_delta"]
        discount = assumptions["discount_rate"] + scenario["discount_delta"]
        case = _dcf_case(fcf, assumptions["initial_growth_rate"] + scenario["growth_delta"],
                         discount, terminal, debt, cash, shares)
        if case is None:
            return _result("discounted_cash_flow", weight, "invalid",
                           "Discount rate must exceed terminal growth")
        cases[name] = case
    values = [cases[name]["fair_value"] for name in ("bear", "base", "bull")]
    if not values[0] <= values[1] <= values[2]:
        return _result("discounted_cash_flow", weight, "invalid", "DCF scenarios were not monotonic")
    dominance = cases["base"]["terminal_value_percentage_of_enterprise_value"]
    distressed = cases["base"]["equity_value"] <= 0
    warning = distressed or (dominance is not None and dominance > TERMINAL_DOMINANCE_THRESHOLD)
    return _result("discounted_cash_flow", weight, "available", None,
                   fair_value_low=values[0], fair_value_mid=values[1], fair_value_high=values[2],
                   confidence=_confidence(fallbacks, warning), calculation_method="simplified_ttm_fcf_dcf",
                   assumptions=assumptions, fallbacks_used=fallbacks,
                   terminal_value_percentage_of_enterprise_value=dominance,
                   negative_equity_value=distressed)


def earnings_power(snapshot, profile, weight):
    if profile == "real_estate":
        return _result("earnings_power", weight, "unsupported_for_sector",
                       "GAAP earnings power is not used without FFO or AFFO")
    eps = history_values(snapshot, "eps")
    if len(eps) < 3:
        return _result("earnings_power", weight, reason="At least three annual diluted EPS observations are required")
    normalized = median(eps)
    if normalized <= 0:
        return _result("earnings_power", weight, reason="Normalized diluted EPS is not positive")
    multiples = EARNINGS_MULTIPLES.get(profile, EARNINGS_MULTIPLES["default"])
    values = [normalized * multiple for multiple in multiples]
    cyclical = profile in {"energy", "materials"}
    return _result("earnings_power", weight, "available", fair_value_low=values[0],
                   fair_value_mid=values[1], fair_value_high=values[2],
                   confidence="moderate" if cyclical else "high",
                   calculation_method="median_diluted_eps_times_sector_multiple",
                   assumptions={"normalized_eps": normalized, "earnings_multiples": list(multiples),
                                "history_years": len(eps)}, fallbacks_used=[])


def historical_multiple_reversion(snapshot, profile, weight):
    series = snapshot.history.get("valuation_multiples", []) if isinstance(snapshot.history, dict) else []
    preferred = "price_to_book" if profile == "financials" else "pe"
    values = [valid_number(row.get(preferred)) for row in series if isinstance(row, dict)]
    values = sorted(value for value in values if value is not None and 0 < value <= 100)
    base = valid_number(snapshot.values.get("common_equity_per_share" if preferred == "price_to_book" else "forward_eps"))
    if len(values) < 3 or base is None or base <= 0:
        return _result("historical_multiple_reversion", weight,
                       reason=f"Reliable aligned historical {preferred.replace('_', '/')} history unavailable")
    def percentile(position):
        index = (len(values) - 1) * position
        lower, upper = math.floor(index), math.ceil(index)
        return values[lower] if lower == upper else values[lower] + (values[upper] - values[lower]) * (index - lower)
    multiples = [percentile(0.25), percentile(0.5), percentile(0.75)]
    fair = [base * value for value in multiples]
    cyclical = profile in {"energy", "materials"}
    return _result("historical_multiple_reversion", weight, "available",
                   fair_value_low=fair[0], fair_value_mid=fair[1], fair_value_high=fair[2],
                   confidence="moderate" if cyclical else "high",
                   calculation_method=f"historical_{preferred}_percentile_reversion",
                   assumptions={"fundamental_base": base, "multiple_range": multiples,
                                "history_years": len(values)}, fallbacks_used=[])


def owner_earnings(snapshot, profile, weight):
    if profile in {"financials", "real_estate"}:
        return _result("owner_earnings", weight, "unsupported_for_sector",
                       "Owner earnings is not used for this sector profile")
    net, da, capex = (history_values(snapshot, key) for key in
                      ("net_income", "depreciation_amortization", "capital_expenditure"))
    shares = valid_number(snapshot.values.get("diluted_shares"))
    if min(len(net), len(da), len(capex)) < 3 or shares is None or shares <= 0:
        return _result("owner_earnings", weight,
                       reason="Three years of earnings, depreciation, CapEx, and positive shares are required")
    multiplier = MAINTENANCE_CAPEX_MULTIPLIER.get(profile, MAINTENANCE_CAPEX_MULTIPLIER["default"])
    observations = []
    for income, depreciation, expenditure in zip(net[-3:], da[-3:], capex[-3:]):
        total_capex = abs(expenditure)
        maintenance = min(total_capex, max(0, depreciation) * multiplier)
        observations.append(income + depreciation - maintenance)
    normalized = median(observations)
    if normalized <= 0:
        return _result("owner_earnings", weight, reason="Normalized owner earnings are not positive")
    multiples = OWNER_EARNINGS_MULTIPLES.get(profile, OWNER_EARNINGS_MULTIPLES["default"])
    per_share = normalized / shares
    fair = [per_share * value for value in multiples]
    warning = profile in {"utilities", "energy", "materials"}
    return _result("owner_earnings", weight, "available", fair_value_low=fair[0],
                   fair_value_mid=fair[1], fair_value_high=fair[2],
                   confidence="low" if warning else "moderate",
                   calculation_method="normalized_owner_earnings_multiple",
                   assumptions={"normalized_owner_earnings": normalized,
                                "maintenance_capex_method": "min_total_capex_or_da_times_sector_multiplier",
                                "maintenance_capex_multiplier": multiplier,
                                "owner_earnings_multiples": list(multiples)},
                   fallbacks_used=["maintenance_capex_proxy"])


def calculate_intrinsic_value(snapshot, profile):
    weights = dict(INTRINSIC_MODEL_WEIGHTS)
    weights.update(INTRINSIC_SECTOR_OVERRIDES.get(profile, {}))
    calculators = (discounted_cash_flow, earnings_power, historical_multiple_reversion, owner_earnings)
    models = [calculator(snapshot, profile, weights[calculator.__name__]) for calculator in calculators]
    available = [model for model in models if model["status"] == "available"]
    supported = [model for model in models if model["supported"]]
    available_weight = sum(model["weight"] for model in available)
    supported_weight = sum(model["weight"] for model in supported)
    weighted_coverage_raw = available_weight / supported_weight if supported_weight else 0
    coverage = {
        "configured_models": 4, "supported_models": len(supported), "available_models": len(available),
        "missing_supported_models": len(supported) - len(available),
        "unsupported_models": 4 - len(supported), "available_weight": available_weight,
        "supported_weight": supported_weight,
        "weighted_coverage": round(weighted_coverage_raw, 4),
        "model_count_coverage": round(len(available) / len(supported), 4) if supported else 0,
        "coverage_method": "configured_model_weight",
    }
    if not available_weight:
        return {"status": "unavailable", "message": "Insufficient data to estimate intrinsic value.",
                "score": None, "score_label": "Unavailable",
                "fair_value_low": None, "fair_value_mid": None, "fair_value_high": None,
                "current_price": valid_number(snapshot.values.get("current_price")),
                "confidence": "low", "model_disagreement": None,
                "coverage": coverage, "models": models, "version": INTRINSIC_VALUE_VERSION}
    for model in available:
        model["normalized_weight"] = round(model["weight"] / available_weight, 4)
    aggregate = lambda key: sum(model[key] * model["weight"] / available_weight for model in available)
    low, mid, high = aggregate("fair_value_low"), aggregate("fair_value_mid"), aggregate("fair_value_high")
    disagreement = ((max(model["fair_value_mid"] for model in available) -
                     min(model["fair_value_mid"] for model in available)) / mid) if len(available) > 1 and mid > 0 else 0
    coverage_ratio = coverage["weighted_coverage"]
    fallback_count = sum(len(model["fallbacks_used"]) for model in available)
    if coverage_ratio >= 0.8 and disagreement < 0.15 and fallback_count <= 1:
        confidence = "high"
    elif coverage_ratio >= 0.5 and disagreement <= 0.30 and fallback_count <= 4:
        confidence = "moderate"
    else:
        confidence = "low"
    current = valid_number(snapshot.values.get("current_price"))
    ratio = current / mid if current is not None and mid > 0 else None
    if ratio is None:
        comparison, label = None, None
    elif ratio <= COMPARISON_BANDS[0]:
        comparison, label = "below_estimated_fair_value", "Below Estimated Fair Value"
    elif ratio <= COMPARISON_BANDS[1]:
        comparison, label = "near_estimated_fair_value", "Near Estimated Fair Value"
    else:
        comparison, label = "above_estimated_fair_value", "Above Estimated Fair Value"
    score_result = calculate_intrinsic_score(
        ratio, confidence, weighted_coverage_raw, disagreement
    )
    difference = price_difference_metadata(current, mid)
    return {"status": "available", "fair_value_low": low, "fair_value_mid": mid,
            "fair_value_high": high, "current_price": current,
            "price_to_fair_value": ratio, "comparison_status": comparison,
            "comparison_label": label, "confidence": confidence,
            "model_disagreement": disagreement, "coverage": coverage,
            "models": models, "version": INTRINSIC_VALUE_VERSION,
            **difference,
            **(score_result or {"score": None, "score_label": "Unavailable"})}
