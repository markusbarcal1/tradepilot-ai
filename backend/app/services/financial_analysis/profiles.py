"""Canonical sector mapping and immutable scoring-profile resolution."""

import math
from copy import deepcopy
from enum import Enum
from types import MappingProxyType

from .config import DEFAULT_SCORING_PROFILE

PROFILE_VERSION = "1.0"


class SectorProfile(str, Enum):
    DEFAULT = "default"
    TECHNOLOGY = "technology"
    COMMUNICATION_SERVICES = "communication_services"
    HEALTHCARE = "healthcare"
    FINANCIALS = "financials"
    CONSUMER_DISCRETIONARY = "consumer_discretionary"
    CONSUMER_STAPLES = "consumer_staples"
    INDUSTRIALS = "industrials"
    ENERGY = "energy"
    MATERIALS = "materials"
    UTILITIES = "utilities"
    REAL_ESTATE = "real_estate"


PROFILE_LABELS = {
    profile.value: profile.value.replace("_", " ").title() for profile in SectorProfile
}
PROFILE_LABELS[SectorProfile.DEFAULT.value] = "General Company"

SECTOR_ALIASES = {
    "technology": SectorProfile.TECHNOLOGY,
    "information technology": SectorProfile.TECHNOLOGY,
    "communication services": SectorProfile.COMMUNICATION_SERVICES,
    "communications": SectorProfile.COMMUNICATION_SERVICES,
    "healthcare": SectorProfile.HEALTHCARE,
    "health care": SectorProfile.HEALTHCARE,
    "financial services": SectorProfile.FINANCIALS,
    "financials": SectorProfile.FINANCIALS,
    "consumer cyclical": SectorProfile.CONSUMER_DISCRETIONARY,
    "consumer discretionary": SectorProfile.CONSUMER_DISCRETIONARY,
    "consumer defensive": SectorProfile.CONSUMER_STAPLES,
    "consumer staples": SectorProfile.CONSUMER_STAPLES,
    "industrials": SectorProfile.INDUSTRIALS,
    "energy": SectorProfile.ENERGY,
    "basic materials": SectorProfile.MATERIALS,
    "materials": SectorProfile.MATERIALS,
    "utilities": SectorProfile.UTILITIES,
    "real estate": SectorProfile.REAL_ESTATE,
}


def _thresholds(poor, acceptable, good, excellent):
    return {"poor": poor, "acceptable": acceptable, "good": good, "excellent": excellent}


SECTOR_PROFILE_OVERRIDES = {
    SectorProfile.DEFAULT.value: {},
    SectorProfile.TECHNOLOGY.value: {
        "metric_overrides": {
            "roic": {"thresholds": _thresholds(0.00, 0.10, 0.18, 0.30)},
            "gross_margin": {"thresholds": _thresholds(0.20, 0.40, 0.60, 0.75)},
            "operating_margin": {"thresholds": _thresholds(0.00, 0.10, 0.22, 0.35)},
            "revenue_growth": {"thresholds": _thresholds(-0.10, 0.05, 0.15, 0.30)},
            "eps_growth": {"thresholds": _thresholds(-0.20, 0.05, 0.18, 0.35)},
            "free_cash_flow_growth": {"thresholds": _thresholds(-0.20, 0.05, 0.15, 0.30)},
            "operating_income_growth": {"thresholds": _thresholds(-0.15, 0.05, 0.15, 0.30)},
            "free_cash_flow_margin": {"thresholds": _thresholds(0.00, 0.08, 0.18, 0.30)},
            "operating_cash_flow_margin": {"thresholds": _thresholds(0.00, 0.10, 0.20, 0.32)},
        },
    },
    SectorProfile.COMMUNICATION_SERVICES.value: {
        "metric_overrides": {
            "gross_margin": {"thresholds": _thresholds(0.15, 0.25, 0.45, 0.65)},
            "operating_margin": {"thresholds": _thresholds(0.00, 0.09, 0.18, 0.28)},
            "revenue_growth": {"thresholds": _thresholds(-0.10, 0.02, 0.12, 0.25)},
            "debt_to_equity": {"thresholds": {"excellent": 0.40, "good": 1.20, "acceptable": 2.30, "poor": 3.50}},
        },
    },
    SectorProfile.HEALTHCARE.value: {
        "metric_overrides": {
            "gross_margin": {"thresholds": _thresholds(0.10, 0.25, 0.45, 0.65)},
            "revenue_growth": {"thresholds": _thresholds(-0.10, 0.00, 0.08, 0.20)},
            "eps_growth": {"thresholds": _thresholds(-0.20, 0.00, 0.10, 0.25)},
        },
    },
    SectorProfile.FINANCIALS.value: {
        "category_weights": {"profitability": 40, "growth": 30, "financial_health": 0, "cash_flow_quality": 30},
        "unsupported_metrics": {
            "return_on_capital", "gross_margin", "debt_to_equity", "current_ratio",
            "interest_coverage", "net_debt_to_ebitda",
        },
        "metric_weights": {
            "profitability": {"roic": 8, "return_on_equity": 17, "operating_margin": 7, "net_margin": 8},
            "growth": {"revenue_growth": 8, "eps_growth": 8, "free_cash_flow_growth": 6, "operating_income_growth": 8},
            "cash_flow_quality": {
                "free_cash_flow": 6, "operating_cash_flow_to_net_income": 8,
                "free_cash_flow_margin": 6, "positive_cash_flow_consistency": 4,
                "operating_cash_flow_margin": 6,
            },
        },
        "metric_overrides": {
            "return_on_equity": {"thresholds": _thresholds(0.00, 0.08, 0.14, 0.22)},
            "net_margin": {"thresholds": _thresholds(0.00, 0.08, 0.16, 0.25)},
        },
    },
    SectorProfile.CONSUMER_DISCRETIONARY.value: {
        "metric_overrides": {
            "roic": {"thresholds": _thresholds(0.00, 0.07, 0.13, 0.22)},
            "gross_margin": {"thresholds": _thresholds(0.08, 0.18, 0.35, 0.55)},
            "operating_margin": {"thresholds": _thresholds(0.00, 0.06, 0.12, 0.20)},
        },
    },
    SectorProfile.CONSUMER_STAPLES.value: {
        "metric_overrides": {
            "revenue_growth": {"thresholds": _thresholds(-0.05, 0.00, 0.05, 0.10)},
            "eps_growth": {"thresholds": _thresholds(-0.10, 0.00, 0.08, 0.15)},
            "operating_income_growth": {"thresholds": _thresholds(-0.08, 0.00, 0.06, 0.12)},
        },
        "metric_weights": {
            "cash_flow_quality": {
                "free_cash_flow": 3, "operating_cash_flow_to_net_income": 4,
                "free_cash_flow_margin": 4, "positive_cash_flow_consistency": 5,
                "operating_cash_flow_margin": 4,
            },
        },
    },
    SectorProfile.INDUSTRIALS.value: {
        "metric_overrides": {
            "gross_margin": {"thresholds": _thresholds(0.08, 0.18, 0.30, 0.45)},
            "operating_margin": {"thresholds": _thresholds(0.00, 0.06, 0.12, 0.20)},
            "revenue_growth": {"thresholds": _thresholds(-0.10, 0.00, 0.08, 0.18)},
        },
    },
    SectorProfile.ENERGY.value: {
        "category_weights": {"profitability": 25, "growth": 15, "financial_health": 30, "cash_flow_quality": 30},
        "metric_weights": {
            "profitability": {
                "roic": 7, "return_on_capital": 6, "return_on_equity": 4,
                "gross_margin": 3, "operating_margin": 3, "net_margin": 2,
            },
            "growth": {"revenue_growth": 3, "eps_growth": 3, "free_cash_flow_growth": 4, "operating_income_growth": 5},
            "financial_health": {"debt_to_equity": 10, "current_ratio": 6, "interest_coverage": 7, "net_debt_to_ebitda": 7},
            "cash_flow_quality": {
                "free_cash_flow": 6, "operating_cash_flow_to_net_income": 6,
                "free_cash_flow_margin": 6, "positive_cash_flow_consistency": 6,
                "operating_cash_flow_margin": 6,
            },
        },
        "metric_overrides": {
            "revenue_growth": {"thresholds": _thresholds(-0.30, -0.05, 0.15, 0.40)},
            "eps_growth": {"thresholds": _thresholds(-0.50, -0.10, 0.20, 0.60)},
            "operating_income_growth": {"thresholds": _thresholds(-0.40, -0.05, 0.20, 0.50)},
        },
    },
    SectorProfile.MATERIALS.value: {
        "metric_overrides": {
            "gross_margin": {"thresholds": _thresholds(0.05, 0.15, 0.28, 0.42)},
            "operating_margin": {"thresholds": _thresholds(0.00, 0.05, 0.11, 0.18)},
            "revenue_growth": {"thresholds": _thresholds(-0.20, -0.02, 0.08, 0.20)},
            "operating_income_growth": {"thresholds": _thresholds(-0.25, -0.02, 0.10, 0.25)},
        },
        "metric_weights": {
            "cash_flow_quality": {
                "free_cash_flow": 4, "operating_cash_flow_to_net_income": 4,
                "free_cash_flow_margin": 4, "positive_cash_flow_consistency": 5,
                "operating_cash_flow_margin": 3,
            },
        },
    },
    SectorProfile.UTILITIES.value: {
        "metric_overrides": {
            "roic": {"thresholds": _thresholds(0.00, 0.04, 0.07, 0.11)},
            "operating_margin": {"thresholds": _thresholds(0.00, 0.06, 0.12, 0.20)},
            "revenue_growth": {"thresholds": _thresholds(-0.05, 0.00, 0.04, 0.08)},
            "eps_growth": {"thresholds": _thresholds(-0.10, 0.00, 0.05, 0.12)},
            "debt_to_equity": {"thresholds": {"excellent": 0.50, "good": 1.20, "acceptable": 2.00, "poor": 3.50}},
            "net_debt_to_ebitda": {"thresholds": {"excellent": 1.50, "good": 3.00, "acceptable": 4.50, "poor": 6.00}},
        },
        "metric_weights": {
            "growth": {"revenue_growth": 9, "eps_growth": 7, "free_cash_flow_growth": 2, "operating_income_growth": 7},
            "cash_flow_quality": {
                "free_cash_flow": 2, "operating_cash_flow_to_net_income": 4,
                "free_cash_flow_margin": 3, "positive_cash_flow_consistency": 7,
                "operating_cash_flow_margin": 4,
            },
        },
    },
    SectorProfile.REAL_ESTATE.value: {
        "unsupported_metrics": {
            "net_margin", "eps_growth", "free_cash_flow_growth",
            "operating_cash_flow_to_net_income", "free_cash_flow_margin",
        },
        "metric_weights": {
            "profitability": {
                "roic": 8, "return_on_capital": 6, "return_on_equity": 5,
                "gross_margin": 5, "operating_margin": 6,
            },
            "growth": {"revenue_growth": 12, "operating_income_growth": 13},
            "cash_flow_quality": {
                "free_cash_flow": 4, "positive_cash_flow_consistency": 7,
                "operating_cash_flow_margin": 9,
            },
        },
        "metric_overrides": {
            "revenue_growth": {"thresholds": _thresholds(-0.10, 0.00, 0.07, 0.15)},
            "operating_income_growth": {"thresholds": _thresholds(-0.15, 0.00, 0.08, 0.18)},
        },
    },
}


def normalize_sector(raw_sector):
    """Return a canonical profile while preserving an honest default fallback."""
    if not isinstance(raw_sector, str):
        return SectorProfile.DEFAULT
    normalized = " ".join(raw_sector.strip().casefold().split())
    return SECTOR_ALIASES.get(normalized, SectorProfile.DEFAULT)


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, set):
        return frozenset(value)
    return value


def resolve_profile(profile):
    """Resolve default plus sector overrides without mutating global configuration."""
    profile = SectorProfile(profile)
    resolved = deepcopy(DEFAULT_SCORING_PROFILE)
    overrides = SECTOR_PROFILE_OVERRIDES[profile.value]
    category_weights = overrides.get("category_weights", {})
    metric_weights = overrides.get("metric_weights", {})
    unsupported = overrides.get("unsupported_metrics", set())

    for category, weight in category_weights.items():
        resolved[category]["weight"] = weight
    for category, weights in metric_weights.items():
        for metric, weight in weights.items():
            resolved[category]["metrics"][metric]["weight"] = weight
    for category in resolved.values():
        for key, metric in category["metrics"].items():
            if key in unsupported:
                metric["weight"] = 0
                metric["unsupported"] = True
                metric["unsupported_reason"] = f"Not used for the {PROFILE_LABELS[profile.value]} sector profile"
    for key, settings in overrides.get("metric_overrides", {}).items():
        for category in resolved.values():
            if key in category["metrics"]:
                category["metrics"][key].update(deepcopy(settings))
                break
    return _freeze(resolved)


def validate_profile(profile):
    resolved = resolve_profile(profile)
    if not math.isclose(sum(category["weight"] for category in resolved.values()), 100):
        raise ValueError(f"{profile}: category weights must total 100")
    valid_directions = {"higher", "lower", "positive"}
    base_metrics = {
        key for category in DEFAULT_SCORING_PROFILE.values() for key in category["metrics"]
    }
    seen = set()
    for category_name, category in resolved.items():
        weight = category["weight"]
        if not isinstance(weight, (int, float)) or not math.isfinite(weight) or weight < 0:
            raise ValueError(f"{profile}.{category_name}: invalid category weight")
        active_weight = 0
        for key, metric in category["metrics"].items():
            if key in seen or key not in base_metrics:
                raise ValueError(f"{profile}: invalid or duplicate metric {key}")
            seen.add(key)
            metric_weight = metric["weight"]
            if not isinstance(metric_weight, (int, float)) or not math.isfinite(metric_weight) or metric_weight < 0:
                raise ValueError(f"{profile}.{key}: invalid metric weight")
            active_weight += metric_weight
            if metric["direction"] not in valid_directions:
                raise ValueError(f"{profile}.{key}: invalid direction")
            if metric["direction"] != "positive":
                thresholds = metric["thresholds"]
                ordered = [thresholds[name] for name in ("poor", "acceptable", "good", "excellent")]
                if metric["direction"] == "higher" and ordered != sorted(ordered):
                    raise ValueError(f"{profile}.{key}: thresholds must increase")
                if metric["direction"] == "lower" and ordered != sorted(ordered, reverse=True):
                    raise ValueError(f"{profile}.{key}: thresholds must decrease")
        if not math.isclose(active_weight, weight):
            raise ValueError(f"{profile}.{category_name}: metric weights must total {weight}")
    return True


def validate_all_profiles():
    for profile in SectorProfile:
        validate_profile(profile)
    return True


validate_all_profiles()
