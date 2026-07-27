"""Raw Relative Valuation metric calculation and economic state classification."""

import math

from .config import DISCREPANCY_TOLERANCE


def valid_number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def currency_consistency(currency, financial_currency):
    quote = currency.strip().upper() if isinstance(currency, str) and currency.strip() else None
    financial = (
        financial_currency.strip().upper()
        if isinstance(financial_currency, str) and financial_currency.strip() else None
    )
    if quote and financial:
        return quote == financial
    return None


def _metric(
    state,
    *,
    value=None,
    raw_value=None,
    reason=None,
    source=None,
    method=None,
    provider_value=None,
    calculated_value=None,
):
    result = {
        "support_state": state,
        "value": valid_number(value),
        "raw_value": valid_number(raw_value if raw_value is not None else value),
        "reason": reason,
        "source": source,
        "calculation_method": method,
    }
    provider_value = valid_number(provider_value)
    calculated_value = valid_number(calculated_value)
    if provider_value is not None:
        result["provider_value"] = provider_value
    if calculated_value is not None:
        result["calculated_value"] = calculated_value
    if provider_value is not None and calculated_value not in (None, 0):
        discrepancy = abs(provider_value - calculated_value) / abs(calculated_value)
        result["discrepancy_percentage"] = discrepancy
        result["discrepancy_flag"] = discrepancy > DISCREPANCY_TOLERANCE
    return result


def _unavailable(reason):
    return _metric("unavailable", reason=reason)


def _not_meaningful(raw_value, reason):
    return _metric("not_meaningful", raw_value=raw_value, reason=reason)


def _select_positive_ratio(calculated, provider, method, missing_reason, nonmeaningful_reason):
    calculated = valid_number(calculated)
    provider = valid_number(provider)
    if calculated is not None:
        if calculated <= 0:
            return _not_meaningful(calculated, nonmeaningful_reason)
        return _metric(
            "available", value=calculated, source="calculated", method=method,
            provider_value=provider, calculated_value=calculated,
        )
    if provider is not None:
        if provider <= 0:
            return _not_meaningful(provider, nonmeaningful_reason)
        return _metric("available", value=provider, source="provider", method="provider_reported")
    return _unavailable(missing_reason)


def _currency_allows_calculation(snapshot):
    return currency_consistency(snapshot.currency, snapshot.financial_currency) is not False


def calculate_valuation_metrics(snapshot):
    raw = snapshot.values
    price = valid_number(raw.get("current_price"))
    market_cap = valid_number(raw.get("market_cap"))
    enterprise_value = valid_number(raw.get("enterprise_value"))
    trailing_eps = valid_number(raw.get("trailing_eps"))
    forward_eps = valid_number(raw.get("forward_eps"))
    growth = valid_number(raw.get("expected_eps_growth"))
    consistent = _currency_allows_calculation(snapshot)

    if price is None or price <= 0:
        trailing_pe = _unavailable("Current market price unavailable")
        forward_pe = _unavailable("Current market price unavailable")
    else:
        calculated_trailing = (
            price / trailing_eps if consistent and trailing_eps not in (None, 0)
            else trailing_eps if consistent else None
        )
        trailing_pe = _select_positive_ratio(
            calculated_trailing, raw.get("provider_trailing_pe"),
            "current_price_over_trailing_eps",
            (
                "Quote and financial-statement currencies do not match"
                if not consistent else "Trailing EPS unavailable"
            ),
            "Trailing earnings are zero or negative",
        )
        calculated_forward = (
            price / forward_eps if consistent and forward_eps not in (None, 0)
            else forward_eps if consistent else None
        )
        forward_pe = _select_positive_ratio(
            calculated_forward, raw.get("provider_forward_pe"),
            "current_price_over_forward_eps",
            (
                "Quote and financial-statement currencies do not match"
                if not consistent else "Forward EPS estimate unavailable"
            ),
            "Forward earnings estimate is zero or negative",
        )

    forward_value = forward_pe["value"] if forward_pe["support_state"] == "available" else None
    if growth is not None and growth <= 0:
        peg = _not_meaningful(growth, "Expected EPS growth is zero or negative")
    elif forward_value is not None and growth is not None:
        growth_points = growth * 100 if abs(growth) <= 2 else growth
        calculated_peg = forward_value / growth_points if growth_points > 1e-6 else None
        peg = _select_positive_ratio(
            calculated_peg, raw.get("provider_peg_ratio"),
            "forward_pe_over_expected_eps_growth_percentage",
            "Expected EPS growth unavailable", "PEG inputs are not economically meaningful",
        )
    else:
        peg = _select_positive_ratio(
            None, raw.get("provider_peg_ratio"), "provider_reported",
            "Forward P/E or expected EPS growth unavailable",
            "PEG is not economically meaningful",
        )

    ebitda = valid_number(raw.get("ebitda"))
    calculated_ev = (
        enterprise_value / ebitda
        if consistent and enterprise_value is not None and ebitda not in (None, 0)
        else None
    )
    if enterprise_value is not None and enterprise_value < 0:
        ev_to_ebitda = _not_meaningful(calculated_ev, "Enterprise value is negative")
    elif ebitda is not None and ebitda <= 0:
        ev_to_ebitda = _not_meaningful(calculated_ev, "Trailing EBITDA is zero or negative")
    elif not consistent and raw.get("provider_ev_to_ebitda") is None:
        ev_to_ebitda = _unavailable("Quote and financial-statement currencies do not match")
    else:
        ev_to_ebitda = _select_positive_ratio(
            calculated_ev, raw.get("provider_ev_to_ebitda"),
            "enterprise_value_over_ebitda", "Enterprise value or EBITDA unavailable",
            "EV / EBITDA is not economically meaningful",
        )

    revenue = valid_number(raw.get("revenue"))
    calculated_sales = (
        market_cap / revenue
        if consistent and market_cap is not None and revenue not in (None, 0)
        else None
    )
    if revenue is not None and revenue <= 0:
        price_to_sales = _not_meaningful(calculated_sales, "Trailing revenue is zero or negative")
    elif not consistent and raw.get("provider_price_to_sales") is None:
        price_to_sales = _unavailable("Quote and financial-statement currencies do not match")
    else:
        price_to_sales = _select_positive_ratio(
            calculated_sales, raw.get("provider_price_to_sales"),
            "market_cap_over_trailing_revenue", "Market capitalization or revenue unavailable",
            "Price / Sales is not economically meaningful",
        )

    equity = valid_number(raw.get("common_equity"))
    calculated_book = (
        market_cap / equity
        if consistent and market_cap is not None and equity not in (None, 0)
        else None
    )
    if equity is not None and equity <= 0:
        price_to_book = _not_meaningful(calculated_book, "Common shareholder equity is zero or negative")
    elif not consistent and raw.get("provider_price_to_book") is None:
        price_to_book = _unavailable("Quote and financial-statement currencies do not match")
    else:
        price_to_book = _select_positive_ratio(
            calculated_book, raw.get("provider_price_to_book"),
            "market_cap_over_common_equity", "Market capitalization or common equity unavailable",
            "Price / Book is not economically meaningful",
        )

    fcf = valid_number(raw.get("free_cash_flow"))
    ocf = valid_number(raw.get("operating_cash_flow"))
    capex = valid_number(raw.get("capital_expenditure"))
    fcf_method = "provider_free_cash_flow"
    if fcf is None and ocf is not None and capex is not None:
        fcf = ocf + capex if capex < 0 else ocf - capex
        fcf_method = "operating_cash_flow_less_capital_expenditure"
    if not consistent:
        fcf_yield = _unavailable("Quote and financial-statement currencies do not match")
    elif market_cap is None or market_cap <= 0:
        fcf_yield = _unavailable("Positive market capitalization unavailable")
    elif fcf is None:
        fcf_yield = _unavailable("Free cash flow unavailable")
    else:
        fcf_yield = _metric(
            "available", value=fcf / market_cap, source="calculated",
            method=f"{fcf_method}_over_market_cap",
        )

    net_income = valid_number(raw.get("net_income"))
    if not consistent:
        earnings_yield = _unavailable("Quote and financial-statement currencies do not match")
    elif market_cap is None or market_cap <= 0:
        earnings_yield = _unavailable("Positive market capitalization unavailable")
    elif net_income is None:
        earnings_yield = _unavailable("Trailing net income unavailable")
    else:
        earnings_yield = _metric(
            "available", value=net_income / market_cap, source="calculated",
            method="trailing_net_income_over_market_cap",
        )

    return {
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "peg_ratio": peg,
        "ev_to_ebitda": ev_to_ebitda,
        "price_to_sales": price_to_sales,
        "price_to_book": price_to_book,
        "free_cash_flow_yield": fcf_yield,
        "earnings_yield": earnings_yield,
    }
