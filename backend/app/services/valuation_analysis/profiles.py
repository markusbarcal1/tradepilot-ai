"""Immutable sector-aware valuation profile resolution and validation."""

import math
from copy import deepcopy
from types import MappingProxyType

from app.services.financial_analysis.profiles import (
    PROFILE_LABELS,
    SectorProfile,
    normalize_sector,
)

from .config import DEFAULT_VALUATION_PROFILE, higher, lower

VALUATION_PROFILE_OVERRIDES = {
    "default": {},
    "technology": {
        "unsupported_metrics": {"price_to_book"},
        "metric_weights": {
            "forward_pe": 24, "trailing_pe": 12, "peg_ratio": 15,
            "ev_to_ebitda": 20, "price_to_sales": 12,
            "free_cash_flow_yield": 12, "earnings_yield": 5,
        },
        "thresholds": {
            "forward_pe": lower(15, 24, 35, 60),
            "trailing_pe": lower(16, 26, 40, 70),
            "peg_ratio": lower(0.8, 1.3, 2.0, 3.5),
            "ev_to_ebitda": lower(10, 17, 25, 40),
            "price_to_sales": lower(2, 5, 10, 20),
        },
    },
    "communication_services": {
        "metric_weights": {"forward_pe": 22, "price_to_sales": 12, "price_to_book": 4},
        "thresholds": {
            "forward_pe": lower(12, 20, 30, 50),
            "trailing_pe": lower(12, 21, 32, 55),
            "price_to_sales": lower(1.5, 4, 8, 15),
        },
    },
    "healthcare": {
        "metric_weights": {"forward_pe": 22, "ev_to_ebitda": 20, "price_to_book": 4},
        "thresholds": {
            "forward_pe": lower(12, 20, 30, 50),
            "trailing_pe": lower(12, 21, 32, 55),
        },
    },
    "financials": {
        "unsupported_metrics": {"ev_to_ebitda", "price_to_sales", "free_cash_flow_yield"},
        "metric_weights": {
            "forward_pe": 25, "trailing_pe": 18, "peg_ratio": 10,
            "price_to_book": 27, "earnings_yield": 20,
        },
        "thresholds": {"price_to_book": lower(0.7, 1.1, 1.8, 3.0)},
    },
    "consumer_discretionary": {
        "metric_weights": {"forward_pe": 22, "ev_to_ebitda": 20, "price_to_book": 4},
        "thresholds": {
            "forward_pe": lower(12, 19, 28, 48),
            "ev_to_ebitda": lower(7, 12, 18, 28),
        },
    },
    "consumer_staples": {
        "metric_weights": {
            "forward_pe": 23, "peg_ratio": 10, "ev_to_ebitda": 20,
            "price_to_sales": 7, "free_cash_flow_yield": 15,
        },
        "thresholds": {
            "forward_pe": lower(12, 20, 29, 48),
            "ev_to_ebitda": lower(7, 12, 18, 28),
        },
    },
    "industrials": {
        "metric_weights": {
            "forward_pe": 18, "trailing_pe": 12, "peg_ratio": 10,
            "ev_to_ebitda": 25, "price_to_sales": 7, "price_to_book": 6,
            "free_cash_flow_yield": 17, "earnings_yield": 5,
        },
    },
    "energy": {
        "metric_weights": {
            "forward_pe": 12, "trailing_pe": 12, "peg_ratio": 5,
            "ev_to_ebitda": 25, "price_to_sales": 8, "price_to_book": 8,
            "free_cash_flow_yield": 25, "earnings_yield": 5,
        },
        "thresholds": {
            "forward_pe": lower(7, 13, 22, 38),
            "trailing_pe": lower(6, 12, 22, 40),
            "ev_to_ebitda": lower(4, 7, 12, 20),
        },
    },
    "materials": {
        "metric_weights": {
            "forward_pe": 15, "trailing_pe": 12, "peg_ratio": 7,
            "ev_to_ebitda": 25, "price_to_sales": 8, "price_to_book": 10,
            "free_cash_flow_yield": 18, "earnings_yield": 5,
        },
        "thresholds": {
            "forward_pe": lower(8, 14, 24, 42),
            "ev_to_ebitda": lower(5, 8, 13, 22),
        },
    },
    "utilities": {
        "metric_weights": {
            "forward_pe": 25, "trailing_pe": 18, "peg_ratio": 8,
            "ev_to_ebitda": 22, "price_to_sales": 8, "price_to_book": 10,
            "free_cash_flow_yield": 4, "earnings_yield": 5,
        },
        "thresholds": {
            "forward_pe": lower(12, 19, 28, 45),
            "ev_to_ebitda": lower(8, 13, 19, 30),
            "price_to_book": lower(1.2, 2.2, 4.5, 8.5),
        },
    },
    "real_estate": {
        "unsupported_metrics": {
            "trailing_pe", "peg_ratio", "free_cash_flow_yield", "earnings_yield",
        },
        "metric_weights": {
            "forward_pe": 15, "ev_to_ebitda": 30,
            "price_to_sales": 20, "price_to_book": 35,
        },
        "thresholds": {
            "forward_pe": lower(15, 25, 40, 70),
            "ev_to_ebitda": lower(10, 16, 24, 38),
            "price_to_sales": lower(3, 6, 10, 18),
            "price_to_book": lower(1, 2, 4, 7),
        },
    },
}


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, set):
        return frozenset(value)
    return value


def resolve_valuation_profile(profile):
    profile = SectorProfile(profile)
    resolved = deepcopy(DEFAULT_VALUATION_PROFILE)
    category = resolved["relative_valuation"]
    overrides = VALUATION_PROFILE_OVERRIDES[profile.value]
    unsupported = overrides.get("unsupported_metrics", set())
    for key, weight in overrides.get("metric_weights", {}).items():
        category["metrics"][key]["weight"] = weight
    for key in unsupported:
        metric = category["metrics"][key]
        metric["weight"] = 0
        metric["unsupported"] = True
        metric["unsupported_reason"] = (
            f"Excluded from the {PROFILE_LABELS[profile.value]} valuation profile"
        )
    for key, thresholds in overrides.get("thresholds", {}).items():
        category["metrics"][key]["thresholds"] = deepcopy(thresholds)
    return _freeze(resolved)


def validate_valuation_profile(profile):
    resolved = resolve_valuation_profile(profile)
    category_total = sum(category["weight"] for category in resolved.values())
    if not math.isclose(category_total, 100):
        raise ValueError(f"{profile}: active categories must total 100")
    seen = set()
    for category_name, category in resolved.items():
        metric_total = 0
        for key, metric in category["metrics"].items():
            if key in seen:
                raise ValueError(f"{profile}: duplicate metric {key}")
            seen.add(key)
            weight = metric["weight"]
            if not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight < 0:
                raise ValueError(f"{profile}.{key}: invalid weight")
            metric_total += weight
            if metric["direction"] not in {"higher", "lower"}:
                raise ValueError(f"{profile}.{key}: invalid direction")
            anchors = metric["thresholds"]
            values = [anchors[name] for name in ("poor", "acceptable", "good", "excellent")]
            expected = sorted(values) if metric["direction"] == "higher" else sorted(values, reverse=True)
            if values != expected or not all(math.isfinite(value) for value in values):
                raise ValueError(f"{profile}.{key}: non-monotonic thresholds")
        if not math.isclose(metric_total, category["weight"]):
            raise ValueError(f"{profile}.{category_name}: metric weights must total category")
    return True


def validate_all_valuation_profiles():
    for profile in SectorProfile:
        validate_valuation_profile(profile)
    return True


validate_all_valuation_profiles()

__all__ = [
    "PROFILE_LABELS", "SectorProfile", "normalize_sector",
    "resolve_valuation_profile", "validate_all_valuation_profiles",
]
