import json
import os
from tools.market_data import get_price_history

WATCHLIST_PATH = os.path.join("data", "watchlist.json")


class WatchlistAgent:
    def __init__(self):
        self.watchlist = self.load_watchlist()

    def load_watchlist(self):
        if os.path.exists(WATCHLIST_PATH):
            with open(WATCHLIST_PATH, "r") as f:
                return json.load(f)
        return []

    def save_watchlist(self):
        with open(WATCHLIST_PATH, "w") as f:
            json.dump(self.watchlist, f, indent=2)

    def add(self, ticker: str, alert_price: float):
        for item in self.watchlist:
            if item["ticker"] == ticker:
                item["alert_price"] = alert_price
                break
        else:
            self.watchlist.append(
                {
                    "ticker": ticker,
                    "alert_price": alert_price,
                    "last_recommendation": None,
                }
            )
        self.save_watchlist()

    def remove(self, ticker: str):
        self.watchlist = [item for item in self.watchlist if item["ticker"] != ticker]
        self.save_watchlist()

    def check_alerts(self):
        alerts = []
        for item in self.watchlist:
            ticker = item["ticker"]
            alert_price = item["alert_price"]
            prices = get_price_history(ticker, period="5d")
            if prices.empty:
                continue
            latest_price = prices.iloc[-1]

            if latest_price >= alert_price:
                alerts.append(
                    {
                        "ticker": ticker,
                        "current_price": latest_price,
                        "alert_price": alert_price,
                        "message": f"{ticker} has crossed your alert price (${alert_price}). Now at ${latest_price:.2f}.",
                    }
                )

        return alerts
