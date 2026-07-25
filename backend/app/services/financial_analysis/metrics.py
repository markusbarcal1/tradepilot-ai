import math


def valid_number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_divide(numerator, denominator):
    numerator = valid_number(numerator)
    denominator = valid_number(denominator)
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _growth(current, previous):
    current = valid_number(current)
    previous = valid_number(previous)
    if current is None or previous is None or previous <= 0:
        return None
    return (current - previous) / previous


def calculate_metrics(snapshot):
    raw = snapshot.values
    roe = valid_number(raw.get("return_on_equity"))
    roa = valid_number(raw.get("return_on_assets"))
    roic = valid_number(raw.get("return_on_invested_capital"))
    return_metric = roic if roic is not None else roe if roe is not None and roe >= 0 else roa

    total_debt = valid_number(raw.get("total_debt"))
    total_cash = valid_number(raw.get("total_cash"))
    ebitda = valid_number(raw.get("ebitda"))
    fcf = valid_number(raw.get("free_cash_flow"))
    ocf = valid_number(raw.get("operating_cash_flow"))
    net_income = valid_number(raw.get("net_income"))
    revenue = valid_number(raw.get("total_revenue"))
    ebit = valid_number(raw.get("ebit"))
    interest_expense = valid_number(raw.get("interest_expense"))
    history = [value for value in (valid_number(v) for v in snapshot.annual_free_cash_flow) if value is not None]

    metrics = {
        "return_on_capital": return_metric,
        "operating_margin": valid_number(raw.get("operating_margin")),
        "net_margin": valid_number(raw.get("net_margin")),
        "revenue_growth": valid_number(raw.get("revenue_growth")),
        "eps_growth": valid_number(raw.get("eps_growth")),
        "free_cash_flow_growth": _growth(history[0], history[1]) if len(history) >= 2 else None,
        # yfinance reports debtToEquity as a percentage (e.g. 150 == 1.5x).
        "debt_to_equity": safe_divide(raw.get("debt_to_equity"), 100),
        "current_ratio": valid_number(raw.get("current_ratio")),
        "interest_coverage": safe_divide(ebit, abs(interest_expense)) if interest_expense else None,
        "net_debt_to_ebitda": safe_divide((total_debt or 0) - (total_cash or 0), ebitda),
        "free_cash_flow": fcf,
        "operating_cash_flow_to_net_income": safe_divide(ocf, net_income) if net_income and net_income > 0 else None,
        "free_cash_flow_margin": safe_divide(fcf, revenue),
        "positive_cash_flow_consistency": (
            sum(value > 0 for value in history) / len(history) if len(history) >= 2 else None
        ),
    }

    # Bank and insurer liabilities are operating inputs, so conventional
    # corporate leverage ratios are not comparable and are explicitly omitted.
    if (snapshot.sector or "").lower() == "financial services":
        for key in ("debt_to_equity", "current_ratio", "interest_coverage", "net_debt_to_ebitda"):
            metrics[key] = None

    return metrics


def format_metric(key, value):
    if value is None:
        return None
    if key in {
        "return_on_capital", "operating_margin", "net_margin", "revenue_growth",
        "eps_growth", "free_cash_flow_growth", "free_cash_flow_margin",
        "positive_cash_flow_consistency",
    }:
        return f"{value * 100:.1f}%"
    if key == "free_cash_flow":
        magnitude = abs(value)
        if magnitude >= 1_000_000_000:
            return f"${value / 1_000_000_000:.1f}B"
        if magnitude >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"
        return f"${value:,.0f}"
    return f"{value:.2f}x"
