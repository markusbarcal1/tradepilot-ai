"""Raw financial metric calculations with defensive missing-data handling."""

import math

from .config import (
    FALLBACK_EFFECTIVE_TAX_RATE,
    MAX_EFFECTIVE_TAX_RATE,
    MIN_EFFECTIVE_TAX_RATE,
    NEAR_ZERO_GROWTH_BASE,
)


def valid_number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_divide(numerator, denominator, *, require_positive_denominator=False):
    numerator = valid_number(numerator)
    denominator = valid_number(denominator)
    if (
        numerator is None or denominator is None or denominator == 0
        or (require_positive_denominator and denominator <= 0)
    ):
        return None
    return numerator / denominator


def calculate_growth(current, previous):
    """Calculate bounded sign-aware growth without near-zero explosions."""
    current = valid_number(current)
    previous = valid_number(previous)
    if current is None or previous is None:
        return None
    scale = max(abs(current), abs(previous), 1.0)
    if abs(previous) <= NEAR_ZERO_GROWTH_BASE * scale:
        return None
    if previous < 0 <= current:
        return 1.0
    if previous >= 0 > current:
        return -1.0
    return max(-1.0, min(1.0, (current - previous) / abs(previous)))


def calculate_effective_tax_rate(tax_provision, pretax_income):
    rate = safe_divide(tax_provision, pretax_income)
    if rate is None or pretax_income <= 0 or not MIN_EFFECTIVE_TAX_RATE <= rate <= MAX_EFFECTIVE_TAX_RATE:
        return FALLBACK_EFFECTIVE_TAX_RATE
    return rate


def calculate_roic(raw):
    operating_income = valid_number(raw.get("operating_income"))
    current_debt = valid_number(raw.get("total_debt"))
    current_equity = valid_number(raw.get("stockholders_equity"))
    current_cash = valid_number(raw.get("cash_and_equivalents"))
    if current_cash is None:
        current_cash = valid_number(raw.get("total_cash"))
    if None in (operating_income, current_debt, current_equity, current_cash):
        return None
    current_capital = current_debt + current_equity - current_cash
    prior_debt = valid_number(raw.get("prior_total_debt"))
    prior_equity = valid_number(raw.get("prior_stockholders_equity"))
    prior_cash = valid_number(raw.get("prior_cash_and_equivalents"))
    capital = current_capital
    if None not in (prior_debt, prior_equity, prior_cash):
        capital = (current_capital + prior_debt + prior_equity - prior_cash) / 2
    if capital <= 0:
        return None
    tax_rate = calculate_effective_tax_rate(raw.get("tax_provision"), raw.get("pretax_income"))
    return safe_divide(operating_income * (1 - tax_rate), capital, require_positive_denominator=True)


def calculate_roe(raw):
    net_income = valid_number(raw.get("net_income"))
    equity = valid_number(raw.get("stockholders_equity"))
    prior_equity = valid_number(raw.get("prior_stockholders_equity"))
    if net_income is None or equity is None or equity <= 0:
        return None
    average_equity = (equity + prior_equity) / 2 if prior_equity is not None and prior_equity > 0 else equity
    return safe_divide(net_income, average_equity, require_positive_denominator=True)


def calculate_gross_margin(raw):
    revenue = valid_number(raw.get("total_revenue"))
    if revenue is None or revenue <= 0:
        return None
    gross_profit = valid_number(raw.get("gross_profit"))
    if gross_profit is None:
        cost = valid_number(raw.get("cost_of_revenue"))
        gross_profit = revenue - cost if cost is not None else None
    return safe_divide(gross_profit, revenue, require_positive_denominator=True)


def calculate_metrics(snapshot):
    raw = snapshot.values
    total_debt = valid_number(raw.get("total_debt"))
    total_cash = valid_number(raw.get("cash_and_equivalents"))
    if total_cash is None:
        total_cash = valid_number(raw.get("total_cash"))
    ebitda = valid_number(raw.get("ebitda"))
    fcf = valid_number(raw.get("free_cash_flow"))
    ocf = valid_number(raw.get("operating_cash_flow"))
    net_income = valid_number(raw.get("net_income"))
    revenue = valid_number(raw.get("total_revenue"))
    ebit = valid_number(raw.get("ebit"))
    interest_expense = valid_number(raw.get("interest_expense"))
    history = [value for value in (valid_number(v) for v in snapshot.annual_free_cash_flow) if value is not None]

    roce = valid_number(raw.get("return_on_capital_employed"))
    if roce is None:
        employed = None
        assets = valid_number(raw.get("total_assets"))
        liabilities = valid_number(raw.get("current_liabilities"))
        if assets is not None and liabilities is not None:
            employed = assets - liabilities
        roce = safe_divide(ebit, employed, require_positive_denominator=True)

    metrics = {
        "roic": calculate_roic(raw),
        "return_on_capital": roce,
        "return_on_equity": calculate_roe(raw),
        "gross_margin": calculate_gross_margin(raw),
        "operating_margin": valid_number(raw.get("operating_margin")),
        "net_margin": valid_number(raw.get("net_margin")),
        "revenue_growth": valid_number(raw.get("revenue_growth")),
        "eps_growth": valid_number(raw.get("eps_growth")),
        "free_cash_flow_growth": calculate_growth(history[0], history[1]) if len(history) >= 2 else None,
        "operating_income_growth": calculate_growth(
            raw.get("operating_income"), raw.get("prior_operating_income")
        ),
        "debt_to_equity": safe_divide(raw.get("debt_to_equity"), 100),
        "current_ratio": valid_number(raw.get("current_ratio")),
        "interest_coverage": safe_divide(ebit, abs(interest_expense)) if interest_expense else None,
        "net_debt_to_ebitda": safe_divide((total_debt or 0) - (total_cash or 0), ebitda),
        "free_cash_flow": fcf,
        "operating_cash_flow_to_net_income": safe_divide(ocf, net_income) if net_income and net_income > 0 else None,
        "free_cash_flow_margin": safe_divide(fcf, revenue, require_positive_denominator=True),
        "positive_cash_flow_consistency": (
            sum(value > 0 for value in history) / len(history) if len(history) >= 2 else None
        ),
        "operating_cash_flow_margin": safe_divide(ocf, revenue, require_positive_denominator=True),
    }

    if (snapshot.sector or "").lower() == "financial services":
        for key in ("debt_to_equity", "current_ratio", "interest_coverage", "net_debt_to_ebitda"):
            metrics[key] = None
    return metrics


def format_metric(key, value):
    if value is None:
        return "N/A"
    percent_metrics = {
        "roic", "return_on_capital", "return_on_equity", "gross_margin",
        "operating_margin", "net_margin", "revenue_growth", "eps_growth",
        "free_cash_flow_growth", "operating_income_growth", "free_cash_flow_margin",
        "positive_cash_flow_consistency", "operating_cash_flow_margin",
    }
    if key in percent_metrics:
        return f"{value * 100:.1f}%"
    if key == "free_cash_flow":
        magnitude = abs(value)
        if magnitude >= 1_000_000_000:
            return f"${value / 1_000_000_000:.1f}B"
        if magnitude >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"
        return f"${value:,.0f}"
    return f"{value:.2f}x"
