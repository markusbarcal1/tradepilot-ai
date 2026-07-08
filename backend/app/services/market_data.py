import yfinance as yf


PRICE_HISTORY_TIMEOUT_SECONDS = 10


def get_price_history(ticker: str, period: str = "max", interval: str = "1d"):
    stock = yf.Ticker(ticker)

    data = stock.history(
        period=period,
        interval=interval,
        timeout=PRICE_HISTORY_TIMEOUT_SECONDS,
    )

    if data.empty:
        raise ValueError(f"No data found for ticker: {ticker}")

    return data
