from datetime import date

import yfinance as yf

from .models import FinancialSnapshot

INCOME_ROWS = {
    "total_revenue": ("Total Revenue", "Operating Revenue"),
    "gross_profit": ("Gross Profit",),
    "cost_of_revenue": ("Cost Of Revenue", "Reconciled Cost Of Revenue"),
    "operating_income": ("Operating Income", "Total Operating Income As Reported"),
    "net_income": ("Net Income", "Net Income Common Stockholders"),
    "tax_provision": ("Tax Provision", "Income Tax Expense"),
    "pretax_income": ("Pretax Income", "Income Before Tax"),
    "ebit": ("EBIT", "Operating Income"),
    "interest_expense": ("Interest Expense", "Interest Expense Non Operating"),
}
BALANCE_ROWS = {
    "cash_and_equivalents": ("Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"),
    "total_debt": ("Total Debt",),
    "stockholders_equity": ("Stockholders Equity", "Total Equity Gross Minority Interest"),
    "total_assets": ("Total Assets",),
    "current_liabilities": ("Current Liabilities", "Total Current Liabilities"),
}
CASH_FLOW_ROWS = {
    "operating_cash_flow": ("Operating Cash Flow", "Total Cash From Operating Activities"),
    "free_cash_flow": ("Free Cash Flow",),
}


def _ordered_periods(statement):
    if statement is None or getattr(statement, "empty", True):
        return []
    try:
        return sorted(statement.columns, reverse=True)
    except (TypeError, ValueError):
        return list(statement.columns)


def _statement_value(statement, rows, period_index=0):
    periods = _ordered_periods(statement)
    if period_index >= len(periods):
        return None
    for row in rows:
        try:
            value = float(statement.loc[row, periods[period_index]])
            if value == value and value not in (float("inf"), float("-inf")):
                return value
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return None


def fetch_financial_snapshot(ticker):
    symbol = str(ticker).strip().upper()
    stock = yf.Ticker(symbol)
    info = stock.info or {}
    cashflow = stock.cash_flow
    income = stock.income_stmt
    balance = stock.balance_sheet

    annual_fcf = [
        value for index in range(min(4, len(_ordered_periods(cashflow))))
        if (value := _statement_value(cashflow, CASH_FLOW_ROWS["free_cash_flow"], index)) is not None
    ]

    values = {
        "return_on_capital_employed": info.get("returnOnCapitalEmployed"),
        "operating_margin": info.get("operatingMargins"),
        "net_margin": info.get("profitMargins"),
        "revenue_growth": info.get("revenueGrowth"),
        "eps_growth": info.get("earningsGrowth"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "free_cash_flow": info.get("freeCashflow") or _statement_value(cashflow, CASH_FLOW_ROWS["free_cash_flow"]),
        "operating_cash_flow": info.get("operatingCashflow") or _statement_value(cashflow, CASH_FLOW_ROWS["operating_cash_flow"]),
        "total_revenue": info.get("totalRevenue") or _statement_value(income, INCOME_ROWS["total_revenue"]),
        "net_income": info.get("netIncomeToCommon") or _statement_value(income, INCOME_ROWS["net_income"]),
        "total_cash": info.get("totalCash"),
        "ebitda": info.get("ebitda"),
        **{key: _statement_value(income, rows) for key, rows in INCOME_ROWS.items()},
        **{key: _statement_value(balance, rows) for key, rows in BALANCE_ROWS.items()},
        "prior_operating_income": _statement_value(income, INCOME_ROWS["operating_income"], 1),
        **{f"prior_{key}": _statement_value(balance, rows, 1) for key, rows in BALANCE_ROWS.items()
           if key in {"cash_and_equivalents", "total_debt", "stockholders_equity"}},
    }
    values["total_debt"] = values.get("total_debt") or info.get("totalDebt")
    return FinancialSnapshot(
        ticker=symbol,
        instrument_type=info.get("quoteType"),
        sector=info.get("sector"),
        industry=info.get("industry"),
        as_of=date.today().isoformat(),
        values=values,
        annual_free_cash_flow=annual_fcf,
    )
