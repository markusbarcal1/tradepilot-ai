"""Defensive yfinance-backed valuation snapshot retrieval."""

from datetime import datetime, timezone

import yfinance as yf

from .models import ValuationSnapshot

INCOME_ROWS = {
    "revenue": ("Total Revenue", "Operating Revenue"),
    "net_income": ("Net Income Common Stockholders", "Net Income"),
    "ebitda": ("EBITDA", "Normalized EBITDA"),
    "trailing_eps": ("Diluted EPS", "Basic EPS"),
    "operating_income": ("Operating Income",),
    "diluted_shares": ("Diluted Average Shares", "Basic Average Shares"),
    "tax_provision": ("Tax Provision", "Income Tax Expense"),
    "pretax_income": ("Pretax Income", "Income Before Tax"),
}
BALANCE_ROWS = {
    "common_equity": ("Common Stock Equity", "Stockholders Equity"),
    "cash": ("Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"),
    "total_debt": ("Total Debt",),
    "working_capital": ("Working Capital",),
}
CASH_FLOW_ROWS = {
    "operating_cash_flow": ("Operating Cash Flow", "Total Cash From Operating Activities"),
    "capital_expenditure": ("Capital Expenditure", "Capital Expenditures"),
    "free_cash_flow": ("Free Cash Flow",),
    "depreciation_amortization": ("Depreciation And Amortization", "Depreciation"),
}


def _history(statement, aliases):
    result = []
    for period in sorted(_periods(statement)):
        for alias in aliases:
            try:
                value = float(statement.loc[alias, period])
                if value == value and value not in (float("inf"), float("-inf")):
                    label = period.isoformat() if hasattr(period, "isoformat") else str(period)
                    result.append({"period": label, "value": value})
                    break
            except (KeyError, TypeError, ValueError):
                continue
    return result[-5:]


def _periods(statement):
    if statement is None or getattr(statement, "empty", True):
        return []
    try:
        return sorted(statement.columns, reverse=True)
    except (TypeError, ValueError):
        return list(statement.columns)


def _statement_value(statement, aliases):
    periods = _periods(statement)
    if not periods:
        return None
    for alias in aliases:
        try:
            value = float(statement.loc[alias, periods[0]])
            if value == value and value not in (float("inf"), float("-inf")):
                return value
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _first_finite(info, keys):
    for key in keys:
        value = info.get(key)
        try:
            value = float(value)
            if value == value and value not in (float("inf"), float("-inf")):
                return value, key
        except (TypeError, ValueError):
            continue
    return None, None


def _timestamp(value):
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def fetch_valuation_snapshot(ticker):
    symbol = str(ticker).strip().upper()
    stock = yf.Ticker(symbol)
    info = stock.info or {}
    income = stock.income_stmt
    balance = stock.balance_sheet
    cashflow = stock.cash_flow

    price, price_key = _first_finite(
        info, ("regularMarketPrice", "currentPrice", "previousClose")
    )
    price_source = {
        "regularMarketPrice": "regular_market_price",
        "currentPrice": "current_price",
        "previousClose": "previous_close",
    }.get(price_key)
    price_is_fallback = price_key == "previousClose"

    revenue = info.get("totalRevenue")
    net_income = info.get("netIncomeToCommon")
    ebitda = info.get("ebitda")
    common_equity = _statement_value(balance, BALANCE_ROWS["common_equity"])
    operating_cash_flow = info.get("operatingCashflow")
    free_cash_flow = info.get("freeCashflow")
    capital_expenditure = _statement_value(cashflow, CASH_FLOW_ROWS["capital_expenditure"])

    values = {
        "current_price": price,
        "market_cap": info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "trailing_eps": info.get("trailingEps") or _statement_value(income, INCOME_ROWS["trailing_eps"]),
        "forward_eps": info.get("forwardEps"),
        "expected_eps_growth": info.get("earningsGrowth"),
        "revenue": revenue or _statement_value(income, INCOME_ROWS["revenue"]),
        "net_income": net_income or _statement_value(income, INCOME_ROWS["net_income"]),
        "ebitda": ebitda or _statement_value(income, INCOME_ROWS["ebitda"]),
        "common_equity": common_equity,
        "operating_cash_flow": operating_cash_flow or _statement_value(
            cashflow, CASH_FLOW_ROWS["operating_cash_flow"]
        ),
        "capital_expenditure": capital_expenditure,
        "free_cash_flow": free_cash_flow or _statement_value(
            cashflow, CASH_FLOW_ROWS["free_cash_flow"]
        ),
        "provider_trailing_pe": info.get("trailingPE"),
        "provider_forward_pe": info.get("forwardPE"),
        "provider_peg_ratio": info.get("pegRatio"),
        "provider_ev_to_ebitda": info.get("enterpriseToEbitda"),
        "provider_price_to_sales": info.get("priceToSalesTrailing12Months"),
        "provider_price_to_book": info.get("priceToBook"),
        "beta": info.get("beta"),
        "total_debt": info.get("totalDebt") or _statement_value(balance, BALANCE_ROWS["total_debt"]),
        "cash": info.get("totalCash") or _statement_value(balance, BALANCE_ROWS["cash"]),
        # Intrinsic per-share models require statement-reported diluted shares;
        # ordinary shares outstanding is not silently substituted.
        "diluted_shares": _statement_value(income, INCOME_ROWS["diluted_shares"]),
        "forward_revenue_growth": info.get("revenueGrowth"),
        "cost_of_debt": None,
    }
    now = datetime.now(timezone.utc).isoformat()
    return ValuationSnapshot(
        symbol=symbol,
        instrument_type=info.get("quoteType"),
        sector=info.get("sector"),
        industry=info.get("industry"),
        currency=info.get("currency"),
        financial_currency=info.get("financialCurrency"),
        as_of=now,
        price_as_of=_timestamp(info.get("regularMarketTime")) or now,
        price_source=price_source,
        price_is_fallback=price_is_fallback,
        values=values,
        history={
            "revenue": _history(income, INCOME_ROWS["revenue"]),
            "operating_income": _history(income, INCOME_ROWS["operating_income"]),
            "net_income": _history(income, INCOME_ROWS["net_income"]),
            "eps": _history(income, INCOME_ROWS["trailing_eps"]),
            "diluted_shares": _history(income, INCOME_ROWS["diluted_shares"]),
            "operating_cash_flow": _history(cashflow, CASH_FLOW_ROWS["operating_cash_flow"]),
            "capital_expenditure": _history(cashflow, CASH_FLOW_ROWS["capital_expenditure"]),
            "free_cash_flow": _history(cashflow, CASH_FLOW_ROWS["free_cash_flow"]),
            "depreciation_amortization": _history(cashflow, CASH_FLOW_ROWS["depreciation_amortization"]),
            "working_capital": _history(balance, BALANCE_ROWS["working_capital"]),
        },
    )
