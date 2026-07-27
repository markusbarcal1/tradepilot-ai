"""Graduated scoring and weight-based normalization for Relative Valuation."""

from .config import METRIC_EXPLANATIONS, MINIMUM_COVERAGE_PERCENT, VALUATION_SCORING_VERSION
from .metrics import valid_number

ANCHOR_QUALITY = {"poor": 0.0, "acceptable": 0.4, "good": 0.7, "excellent": 1.0}


def valuation_classification(score):
    if score >= 85:
        return "deeply_undervalued", "Deeply Undervalued"
    if score >= 70:
        return "undervalued", "Undervalued"
    if score >= 45:
        return "fairly_valued", "Fairly Valued"
    if score >= 25:
        return "expensive", "Expensive"
    return "very_expensive", "Very Expensive"


def _quality(value, thresholds, direction):
    value = valid_number(value)
    if value is None:
        return None
    anchors = [
        (thresholds[name], ANCHOR_QUALITY[name])
        for name in ("poor", "acceptable", "good", "excellent")
    ]
    if direction == "lower":
        anchors.sort(key=lambda item: item[0])
    if value <= anchors[0][0]:
        return anchors[0][1]
    if value >= anchors[-1][0]:
        return anchors[-1][1]
    for (left_value, left_score), (right_value, right_score) in zip(anchors, anchors[1:]):
        if left_value <= value <= right_value:
            position = (value - left_value) / (right_value - left_value)
            return left_score + position * (right_score - left_score)
    return None


def score_lower_is_better(value, excellent, good, acceptable, poor, max_points):
    quality = _quality(
        value,
        {"excellent": excellent, "good": good, "acceptable": acceptable, "poor": poor},
        "lower",
    )
    return None if quality is None else max(0.0, min(max_points, quality * max_points))


def score_higher_is_better(value, poor, acceptable, good, excellent, max_points):
    quality = _quality(
        value,
        {"poor": poor, "acceptable": acceptable, "good": good, "excellent": excellent},
        "higher",
    )
    return None if quality is None else max(0.0, min(max_points, quality * max_points))


def _points(value, settings):
    if settings["direction"] == "lower":
        return score_lower_is_better(value, max_points=settings["weight"], **settings["thresholds"])
    return score_higher_is_better(value, max_points=settings["weight"], **settings["thresholds"])


def _format_value(settings, metric):
    state = metric["support_state"]
    if state == "not_meaningful":
        return "N/M"
    value = valid_number(metric.get("value"))
    if value is None:
        return "N/A"
    if settings["unit"] == "percent":
        return f"{value * 100:.1f}%"
    return f"{value:.2f}×"


def _metric_status(points, max_score):
    quality = points / max_score * 100
    if quality >= 85:
        return "excellent"
    if quality >= 70:
        return "good"
    if quality >= 45:
        return "fair"
    if quality >= 25:
        return "expensive"
    return "very_expensive"


def score_valuation_metrics(metrics, profile):
    category_settings = profile["relative_valuation"]
    category_weight = category_settings["weight"]
    configured_count = len(category_settings["metrics"])
    supported_count = 0
    available_count = 0
    unsupported_count = 0
    available_weight = 0
    supported_weight = 0
    earned_points = 0.0
    details = []

    for key, settings in category_settings["metrics"].items():
        if settings.get("unsupported"):
            unsupported_count += 1
            details.append({
                "key": key, "label": settings["label"], "value": None,
                "raw_value": None, "formatted_value": "N/A", "display_value": "N/A",
                "score": None, "max_score": 0, "status": "unsupported_for_sector",
                "support_state": "unsupported_for_sector",
                "availability": "unsupported_for_sector", "available": False,
                "direction": settings["direction"],
                "reason": settings["unsupported_reason"],
                "explanation": METRIC_EXPLANATIONS[key],
                "reference": settings["unsupported_reason"],
            })
            continue

        supported_count += 1
        supported_weight += settings["weight"]
        metric = metrics.get(key) or {"support_state": "unavailable", "reason": "Metric unavailable"}
        state = metric["support_state"]
        common = {
            "key": key, "label": settings["label"],
            "value": metric.get("value"), "raw_value": metric.get("raw_value"),
            "formatted_value": _format_value(settings, metric),
            "display_value": _format_value(settings, metric),
            "max_score": settings["weight"], "direction": settings["direction"],
            "calculation_method": metric.get("calculation_method"),
            "source": metric.get("source"), "reason": metric.get("reason"),
            "explanation": METRIC_EXPLANATIONS[key],
        }
        for diagnostic in (
            "provider_value", "calculated_value",
            "discrepancy_percentage", "discrepancy_flag",
        ):
            if diagnostic in metric:
                common[diagnostic] = metric[diagnostic]

        if state != "available":
            details.append({
                **common, "score": None, "status": state, "support_state": state,
                "availability": state, "available": False,
                "reference": "Excluded from score normalization",
            })
            continue

        points = _points(metric["value"], settings)
        if points is None:
            details.append({
                **common, "score": None, "status": "invalid", "support_state": "invalid",
                "availability": "invalid", "available": False,
                "reason": "Metric could not be scored safely",
                "reference": "Excluded from score normalization",
            })
            continue
        available_count += 1
        available_weight += settings["weight"]
        earned_points += points
        details.append({
            **common, "score": round(points, 1),
            "status": _metric_status(points, settings["weight"]),
            "support_state": "available", "availability": "available", "available": True,
            "reference": (
                f"{'Lower' if settings['direction'] == 'lower' else 'Higher'} is more attractive"
            ),
        })

    missing_count = supported_count - available_count
    weighted_coverage = available_weight / supported_weight if supported_weight else 0
    count_coverage = available_count / supported_count if supported_count else 0
    coverage = {
        "configured_metrics": configured_count, "supported_metrics": supported_count,
        "available_metrics": available_count, "missing_supported_metrics": missing_count,
        "unsupported_metrics": unsupported_count, "available_weight": available_weight,
        "supported_weight": supported_weight, "configured_weight": category_weight,
        "weighted_coverage": round(weighted_coverage, 4),
        "metric_count_coverage": round(count_coverage, 4),
        "percentage": round(weighted_coverage * 100),
        "ratio": round(weighted_coverage, 4), "coverage_method": "weighted",
    }
    category_score = (
        earned_points / available_weight * category_weight if available_weight else None
    )
    normalized_score = (
        max(0.0, min(100.0, category_score)) if category_score is not None else None
    )
    category = {
        "key": "relative_valuation", "label": category_settings["label"],
        "score": round(normalized_score, 1) if normalized_score is not None else None,
        "max_score": category_weight, "coverage": coverage,
        **coverage, "metrics": details, "details": details,
        "normalization_note": (
            f"Score normalized using {available_count} of {supported_count} supported metrics."
            if available_count < supported_count else None
        ),
    }
    common_result = {
        "coverage": coverage, **{
            key: coverage[key] for key in (
                "configured_metrics", "supported_metrics", "available_metrics",
                "missing_supported_metrics", "unsupported_metrics",
            )
        },
        "categories": {"relative_valuation": category},
        "scoring_version": VALUATION_SCORING_VERSION,
    }
    if (
        normalized_score is None
        or coverage["percentage"] < MINIMUM_COVERAGE_PERCENT
    ):
        return {
            **common_result, "score": None, "status": "unavailable",
            "status_label": "Unavailable", "availability": "unavailable",
            "reason_code": "insufficient_valuation_data",
            "message": "Not enough reliable valuation data is available.",
        }
    status, label = valuation_classification(normalized_score)
    return {
        **common_result, "score": round(normalized_score, 1),
        "status": status, "status_label": label,
        "availability": "available" if coverage["percentage"] == 100 else "partial",
        "message": (
            "Valuation score is based on limited available data."
            if coverage["percentage"] < 100 else None
        ),
    }
