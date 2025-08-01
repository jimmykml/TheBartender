import yfinance as yf

def get_fundamental_metrics(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        return {
            "revenue_growth_5y": info.get("fiveYearAvgDividendYield", "N/A"),
            "net_margin": info.get("netMargins", "N/A"),
            "roe": info.get("returnOnEquity", "N/A"),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "de_ratio": info.get("debtToEquity", "N/A"),
            "free_cash_flow": info.get("freeCashflow", "N/A"),
            "dcf_value": "N/A",  # Add from FMP if needed
            "current_price": info.get("currentPrice", "N/A"),
        }
    except Exception as e:
        print(f"Error fetching fundamentals: {e}")
        return None
