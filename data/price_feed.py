"""
Jimmy's Gold Trading Bot — Price Feed
Builds and caches OHLCV data from MT5.
"""
import time as _time
from typing import Optional, Dict
import pandas as pd
from config.settings import SYMBOL, TIMEFRAMES, MAX_DATA_AGE_SECONDS
from config.trading_rules import MAX_SPREAD_POINTS
from data.mt5_connector import get_mt5
from utils.logger import get_agent_logger
from utils.session_clock import now_eat

log = get_agent_logger("PRICE_FEED")


class PriceFeed:
    def __init__(self):
        self._tick: Optional[dict] = None
        self._candles: Dict[str, pd.DataFrame] = {}
        self._last_tick_time: float = 0.0
        self._last_candle_time: float = 0.0

    def refresh_tick(self) -> Optional[dict]:
        connector = get_mt5()
        tick = connector.get_tick()
        if tick is not None:
            self._tick = tick
            self._tick["fetch_time"] = _time.time()
            self._last_tick_time = _time.time()
        return self._tick

    def get_current_price(self) -> Optional[dict]:
        if self._tick is None or self._is_tick_stale():
            self.refresh_tick()
        if self._tick is None:
            return None
        return {
            "symbol": SYMBOL,
            "bid": self._tick["bid"],
            "ask": self._tick["ask"],
            "mid": self._tick["mid"],
            "spread": self._tick["spread"],
            "time": self._tick["time"],
            "spread_ok": self._tick["spread"] <= MAX_SPREAD_POINTS,
            "connection_ok": get_mt5().connected,
        }

    def _is_tick_stale(self) -> bool:
        return (_time.time() - self._last_tick_time) > MAX_DATA_AGE_SECONDS

    def refresh_candles(self, timeframe: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        connector = get_mt5()
        if timeframe:
            df = connector.get_candles(timeframe)
            if df is not None:
                self._candles[timeframe] = df
        else:
            self._candles = connector.get_all_candles()
            self._last_candle_time = _time.time()
        return self._candles

    def get_candles(self, timeframe: str) -> Optional[pd.DataFrame]:
        if timeframe not in self._candles or self._are_candles_stale():
            self.refresh_candles(timeframe)
        return self._candles.get(timeframe)

    def get_all_candles(self) -> Dict[str, pd.DataFrame]:
        if not self._candles or self._are_candles_stale():
            self.refresh_candles()
        return self._candles

    def _are_candles_stale(self) -> bool:
        return (_time.time() - self._last_candle_time) > MAX_DATA_AGE_SECONDS

    def get_last_close(self, timeframe: str = "M5") -> Optional[float]:
        df = self.get_candles(timeframe)
        if df is None or df.empty:
            return None
        return float(df.iloc[-1]["close"])

    def get_atr(self, timeframe: str = "M15", period: int = 14) -> Optional[float]:
        df = self.get_candles(timeframe)
        if df is None or len(df) < period + 1:
            return None
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        tr_list = []
        for i in range(1, len(high)):
            tr = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
            tr_list.append(tr)
        if len(tr_list) < period:
            return None
        atr = sum(tr_list[-period:]) / period
        return round(atr, 2)

    def get_pdh_pdl(self) -> Optional[dict]:
        df = self.get_candles("H1")
        if df is None or len(df) < 24:
            return None
        today = now_eat().date()
        prev_day = df[df["time"].dt.date < today]
        if prev_day.empty:
            return None
        last_day = prev_day["time"].dt.date.max()
        day_candles = prev_day[prev_day["time"].dt.date == last_day]
        return {"pdh": float(day_candles["high"].max()), "pdl": float(day_candles["low"].min())}

    def get_full_state(self) -> dict:
        price = self.get_current_price()
        candles = self.get_all_candles()
        return {
            "symbol": SYMBOL,
            "current_price": price,
            "candles": {tf: df for tf, df in candles.items()},
            "spread_ok": price["spread_ok"] if price else False,
            "connection_ok": price["connection_ok"] if price else False,
        }


_feed: Optional[PriceFeed] = None

def get_price_feed() -> PriceFeed:
    global _feed
    if _feed is None:
        _feed = PriceFeed()
    return _feed
