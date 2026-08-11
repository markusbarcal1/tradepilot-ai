"""Deterministic, sector-aware assumptions for Phase 2B intrinsic valuation."""

import math
from statistics import median

from .config import (
    BETA_CALCULATION_BOUNDS, DEFAULT_COST_OF_DEBT, DEFAULT_EQUITY_RISK_PREMIUM,
    DEFAULT_RISK_FREE_RATE, DEFAULT_TAX_RATE, DISCOUNT_RATE_BOUNDS,
    INITIAL_GROWTH_BOUNDS, SECTOR_TERMINAL_GROWTH, TERMINAL_GROWTH_BOUNDS,
)
from .metrics import valid_number


def history_values(snapshot, key):
    rows = snapshot.history.get(key, []) if isinstance(snapshot.history, dict) else []
    ordered = sorted(
        (row for row in rows if isinstance(row, dict)), key=lambda row: str(row.get("period", ""))
    )
    values = []
    for row in ordered:
        value = valid_number(row.get("value"))
        if value is not None:
            values.append(value)
    return values[-5:]


def sign_aware_growth(previous, current, near_zero=1e-9):
    previous, current = valid_number(previous), valid_number(current)
    if previous is None or current is None or abs(previous) <= near_zero:
        return None
    if previous <= 0 or current <= 0:
        return None
    return current / previous - 1


def annual_growth_rates(values):
    return [rate for rate in (sign_aware_growth(a, b) for a, b in zip(values, values[1:]))
            if rate is not None]


def median_growth(values):
    rates = annual_growth_rates(values)
    return median(rates) if rates else None


def cagr(values):
    finite = [valid_number(value) for value in values]
    if len(finite) < 2 or any(value is None or value <= 0 for value in finite):
        return None
    return (finite[-1] / finite[0]) ** (1 / (len(finite) - 1)) - 1


def _clamp(value, bounds):
    return min(bounds[1], max(bounds[0], value))


def resolve_assumptions(snapshot, sector_profile):
    raw = snapshot.values
    fallbacks = []
    candidates = []
    for key in ("free_cash_flow", "revenue", "operating_income"):
        value = median_growth(history_values(snapshot, key))
        if value is not None and math.isfinite(value):
            candidates.append(value)
    for key in ("forward_revenue_growth", "expected_eps_growth"):
        value = valid_number(raw.get(key))
        if value is not None:
            candidates.append(value / 100 if abs(value) > 2 else value)
    if candidates:
        raw_growth = median(candidates)
        spread = max(candidates) - min(candidates) if len(candidates) > 1 else 0
        growth_source = "blended_historical_forward" if len(candidates) > 1 else "single_available_estimate"
    else:
        raw_growth, spread, growth_source = 0.03, 0, "sector_neutral_fallback"
        fallbacks.append("fallback_initial_growth")
    growth_bounds = INITIAL_GROWTH_BOUNDS.get(sector_profile, INITIAL_GROWTH_BOUNDS["default"])
    initial_growth = _clamp(raw_growth, growth_bounds)

    terminal_growth = _clamp(
        SECTOR_TERMINAL_GROWTH.get(sector_profile, 0.025), TERMINAL_GROWTH_BOUNDS
    )
    beta_raw = valid_number(raw.get("beta"))
    if beta_raw is None:
        beta, beta_source = 1.0, "fallback_beta"
        fallbacks.append("fallback_beta")
    else:
        beta, beta_source = _clamp(beta_raw, BETA_CALCULATION_BOUNDS), "provider_beta"
        if beta != beta_raw:
            fallbacks.append("beta_clamped_for_calculation")
    tax_rate = valid_number(raw.get("tax_rate"))
    if tax_rate is None or not 0 <= tax_rate <= 0.5:
        tax_rate = DEFAULT_TAX_RATE
        fallbacks.append("default_tax_rate")
    cost_of_debt = valid_number(raw.get("cost_of_debt"))
    if cost_of_debt is None or cost_of_debt < 0:
        cost_of_debt = DEFAULT_COST_OF_DEBT
        fallbacks.append("fallback_cost_of_debt")
    equity = valid_number(raw.get("market_cap"))
    debt = valid_number(raw.get("total_debt"))
    if equity is None or equity <= 0:
        equity_weight, debt_weight = 1.0, 0.0
        fallbacks.append("equity_only_capital_weights")
    else:
        debt = max(0, debt or 0)
        equity_weight = equity / (equity + debt)
        debt_weight = debt / (equity + debt)
    cost_of_equity = DEFAULT_RISK_FREE_RATE + beta * DEFAULT_EQUITY_RISK_PREMIUM
    raw_wacc = equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)
    discount_rate = _clamp(raw_wacc, DISCOUNT_RATE_BOUNDS)
    if discount_rate != raw_wacc:
        fallbacks.append("wacc_clamped_for_calculation")
    return {
        "initial_growth_rate": initial_growth, "raw_growth_estimate": raw_growth,
        "growth_estimate_spread": spread, "terminal_growth_rate": terminal_growth,
        "discount_rate": discount_rate, "raw_wacc": raw_wacc,
        "risk_free_rate": DEFAULT_RISK_FREE_RATE,
        "equity_risk_premium": DEFAULT_EQUITY_RISK_PREMIUM,
        "cost_of_equity": cost_of_equity, "cost_of_debt": cost_of_debt,
        "tax_rate": tax_rate, "beta": beta, "raw_beta": beta_raw,
        "equity_weight": equity_weight, "debt_weight": debt_weight,
        "growth_source": growth_source, "discount_rate_source": "calculated_wacc",
        "beta_source": beta_source, "fallbacks_used": fallbacks,
    }
