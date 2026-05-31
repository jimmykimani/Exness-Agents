"""
DataAgent — Live market data provider.
The eyes of the system. Fetches, cleans and distributes all price data.
"""
from typing import Optional, Dict
import pandas as pd

from data.price_feed import get_price_feed
from data.mt5_connector import get_mt5
from utils.logger import get_agent_logger

log = get_agent_logger("DATA_AGENT")


class DataAgent:
    """Provides all price data to the system."""

    def __init__(self, shared_state: dict):
        self.state = shared_state
        self.feed = get_price_feed()
        self.mt5 = get_mt5()

    def run(self) -> dict:
        """Execute data collection cycle."""
        log.info("Refreshing market data...")

        # Refresh tick
        price = self.feed.get_current_price()
        if price is None:
            log.error("Failed to get current price")
            self.state["data"] = {"connection_ok": False, "spread_ok": False}
            return self.state["data"]

        # Refresh candles
        candles = self.feed.get_all_candles()

        # ATR for displacement detection
        atr_m15 = self.feed.get_atr("M15", 14)
        atr_h1 = self.feed.get_atr("H1", 14)

        # PDH/PDL
        pdh_pdl = self.feed.get_pdh_pdl()

        output = {
            "symbol": price["symbol"],
            "current_price": price,
            "candles": candles,
            "spread_ok": price["spread_ok"],
            "connection_ok": price["connection_ok"],
            "atr": {"M15": atr_m15, "H1": atr_h1},
            "pdh_pdl": pdh_pdl,
        }

        self.state["data"] = output
        log.info(
            f"Data refreshed — Price: {price['mid']} | "
            f"Spread: {price['spread']} | "
            f"TFs loaded: {list(candles.keys())}"
        )
        return output

    def get_candles(self, timeframe: str) -> Optional[pd.DataFrame]:
        """Get candles for a specific timeframe."""
        return self.feed.get_candles(timeframe)

    def get_price(self) -> Optional[dict]:
        """Get current price."""
        return self.feed.get_current_price()
