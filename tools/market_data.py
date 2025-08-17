import yfinance as yf


def get_price_history(ticker, period="3mo", interval="1d"):
    df = yf.Ticker(ticker).history(period=period, interval=interval)
    return df["Close"]
