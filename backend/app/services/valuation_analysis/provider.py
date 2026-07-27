"""Defensive yfinance-backed valuation snapshot retrieval."""

from datetime import datetime, timezone

import yfinance as yf

from .models import ValuationSnapshot

INCOME_ROWS = {
    "revenue": ("Total Revenue", "Operating Revenue"),
    "net_income": ("Net Income Common Stockholders", "Net Income"),
    "ebitda": ("EBITDA", "Normalized EBITDA"),
    "trailing_eps": ("Diluted EPS", "Basic EPS"),
}
BALANCE_ROWS = {
    "common_equity": ("Common Stock Equity", "Stockholders Equity"),
}
CASH_FLOW_ROWS = {
    "operating_cash_flow": ("Operating Cash Flow", "Total Cash From Operating Activities"),
    "capital_expenditure": ("Capital Expenditure", "Capital Expenditures"),
    "free_cash_flow": ("Free Cash Flow",),
}


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
    )
