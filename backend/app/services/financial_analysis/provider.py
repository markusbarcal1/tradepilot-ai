import logging
from datetime import date

import yfinance as yf

from .models import FinancialSnapshot

logger = logging.getLogger(__name__)


def _statement_value(statement, row):
    try:
        values = statement.loc[row].dropna()
        return float(values.iloc[0]) if not values.empty else None
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def fetch_financial_snapshot(ticker):
    symbol = str(ticker).strip().upper()
    stock = yf.Ticker(symbol)
    info = stock.info or {}
    cashflow = stock.cash_flow
    income = stock.income_stmt

    annual_fcf = []
    try:
        annual_fcf = [float(value) for value in cashflow.loc["Free Cash Flow"].dropna().iloc[:4]]
    except (KeyError, TypeError, ValueError):
        pass

    values = {
        "return_on_equity": info.get("returnOnEquity"),
        "return_on_assets": info.get("returnOnAssets"),
        "return_on_invested_capital": info.get("returnOnInvestedCapital"),
        "operating_margin": info.get("operatingMargins"),
        "net_margin": info.get("profitMargins"),
        "revenue_growth": info.get("revenueGrowth"),
        "eps_growth": info.get("earningsGrowth"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "free_cash_flow": info.get("freeCashflow"),
        "operating_cash_flow": info.get("operatingCashflow"),
        "total_revenue": info.get("totalRevenue"),
        "net_income": info.get("netIncomeToCommon"),
        "total_cash": info.get("totalCash"),
        "total_debt": info.get("totalDebt"),
        "ebitda": info.get("ebitda"),
        "ebit": _statement_value(income, "EBIT"),
        "interest_expense": _statement_value(income, "Interest Expense"),
    }
    return FinancialSnapshot(
        ticker=symbol,
        instrument_type=info.get("quoteType"),
        sector=info.get("sector"),
        industry=info.get("industry"),
        as_of=date.today().isoformat(),
        values=values,
        annual_free_cash_flow=annual_fcf,
    )
