"""
Jimmy's Gold Trading Bot — MT5 Connector
Handles MetaTrader5 connection, reconnection, and raw data access.
"""
import time as _time
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import pandas as pd

from config.settings import (
    MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, SYMBOL, TIMEFRAMES
)
from config.trading_rules import MT5_RECONNECT_INTERVAL_SEC, MT5_ALERT_AFTER_SEC
from utils.logger import get_agent_logger

log = get_agent_logger("MT5_CONNECTOR")

# ─── MT5 import with graceful fallback ──────────────────
try:
    import MetaTrader5 as mt5

    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None
    log.warning("MetaTrader5 not installed — running in SIMULATION mode")

# ─── MT5 timeframe mapping ──────────────────────────────
_TF_MAP = {}
if MT5_AVAILABLE:
    _TF_MAP = {
        "M1":  mt5.TIMEFRAME_M1,
        "M5":  mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1":  mt5.TIMEFRAME_H1,
        "H4":  mt5.TIMEFRAME_H4,
        "D1":  mt5.TIMEFRAME_D1,
        "W1":  mt5.TIMEFRAME_W1,
    }


class MT5Connector:
    """Manages the MetaTrader5 connection lifecycle."""

    def __init__(self):
        self.connected = False
        self._last_connect_attempt = 0.0
        self._disconnect_since: Optional[float] = None

    # ─── Connection ────────────────────────────────────
    def connect(self) -> bool:
        """Initialize MT5 and log in."""
        if not MT5_AVAILABLE:
            log.warning("MT5 not available — simulation mode")
            self.connected = False
            return False

        now = _time.time()
        if now - self._last_connect_attempt < MT5_RECONNECT_INTERVAL_SEC:
            return self.connected
        self._last_connect_attempt = now

        if not mt5.initialize():
            log.error(f"MT5 initialize failed: {mt5.last_error()}")
            self._mark_disconnected()
            return False

        authorized = mt5.login(
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )
        if not authorized:
            log.error(f"MT5 login failed: {mt5.last_error()}")
            self._mark_disconnected()
            return False

        self.connected = True
        self._disconnect_since = None
        log.info(f"MT5 connected — Account #{MT5_LOGIN} on {MT5_SERVER}")
        return True

    def disconnect(self):
        """Shutdown MT5."""
        if MT5_AVAILABLE and self.connected:
            mt5.shutdown()
        self.connected = False
        log.info("MT5 disconnected")

    def ensure_connected(self) -> bool:
        """Ensure we have an active connection, attempt reconnect if not."""
        if self.connected and MT5_AVAILABLE:
            # Quick health check
            info = mt5.account_info()
            if info is not None:
                return True
            log.warning("MT5 connection lost — reconnecting...")
        return self.connect()

    def _mark_disconnected(self):
        """Track when disconnection started."""
        self.connected = False
        if self._disconnect_since is None:
            self._disconnect_since = _time.time()

    def disconnected_seconds(self) -> float:
        """How long we've been disconnected."""
        if self._disconnect_since is None:
            return 0.0
        return _time.time() - self._disconnect_since

    def should_alert_disconnect(self) -> bool:
        """True if disconnected longer than alert threshold."""
        return self.disconnected_seconds() > MT5_ALERT_AFTER_SEC

    # ─── Account Info ──────────────────────────────────
    def get_account_info(self) -> Optional[dict]:
        """Get account balance, equity, margin info."""
        if not self.ensure_connected():
            return None
        info = mt5.account_info()
        if info is None:
            return None
        return {
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "profit": info.profit,
            "leverage": info.leverage,
            "currency": info.currency,
        }

    # ─── Price Data ────────────────────────────────────
    def get_tick(self) -> Optional[dict]:
        """Get latest tick for XAUUSD."""
        if not self.ensure_connected():
            return None
        tick = mt5.symbol_info_tick(SYMBOL)
        if tick is None:
            log.error(f"Failed to get tick for {SYMBOL}")
            return None
        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "mid": round((tick.bid + tick.ask) / 2, 2),
            "spread": round((tick.ask - tick.bid) * 10, 1),  # in points
            "time": datetime.fromtimestamp(tick.time).strftime("%H:%M:%S"),
            "volume": tick.volume,
        }

    def get_candles(
        self, timeframe: str, count: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV candles for a given timeframe.
        Returns DataFrame with columns: time, open, high, low, close, volume
        """
        if not self.ensure_connected():
            return None

        tf = _TF_MAP.get(timeframe)
        if tf is None:
            log.error(f"Unknown timeframe: {timeframe}")
            return None

        if count is None:
            count = TIMEFRAMES.get(timeframe, {}).get("candle_count", 100)

        rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, count)
        if rates is None or len(rates) == 0:
            log.error(f"No candle data for {SYMBOL} {timeframe}")
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df[["time", "open", "high", "low", "close", "tick_volume"]]
        df = df.rename(columns={"tick_volume": "volume"})
        df = df.reset_index(drop=True)
        return df

    def get_all_candles(self) -> Dict[str, pd.DataFrame]:
        """Fetch candles for all configured timeframes."""
        candles = {}
        for tf_name in TIMEFRAMES:
            df = self.get_candles(tf_name)
            if df is not None:
                candles[tf_name] = df
        return candles

    # ─── Order Execution ──────────────────────────────
    def send_order(self, request: dict) -> Optional[dict]:
        """Send an order to MT5. Returns result dict."""
        if not self.ensure_connected():
            return {"status": "ERROR", "error": "MT5 not connected"}

        result = mt5.order_send(request)
        if result is None:
            return {
                "status": "ERROR",
                "error": str(mt5.last_error()),
                "mt5_retcode": -1,
            }

        return {
            "order_id": result.order,
            "status": "FILLED" if result.retcode == mt5.TRADE_RETCODE_DONE else "REJECTED",
            "fill_price": result.price,
            "mt5_retcode": result.retcode,
            "comment": result.comment,
            "error": None if result.retcode == mt5.TRADE_RETCODE_DONE else result.comment,
        }

    def get_positions(self) -> List[dict]:
        """Get all open positions."""
        if not self.ensure_connected():
            return []

        positions = mt5.positions_get(symbol=SYMBOL)
        if positions is None:
            return []

        result = []
        for pos in positions:
            result.append({
                "ticket": pos.ticket,
                "direction": "LONG" if pos.type == mt5.ORDER_TYPE_BUY else "SHORT",
                "volume": pos.volume,
                "entry": pos.price_open,
                "current_price": pos.price_current,
                "sl": pos.sl,
                "tp": pos.tp,
                "pnl": pos.profit,
                "swap": pos.swap,
                "time": datetime.fromtimestamp(pos.time).strftime("%H:%M:%S"),
                "magic": pos.magic,
                "comment": pos.comment,
            })
        return result

    def close_position(self, ticket: int) -> Optional[dict]:
        """Close a specific position by ticket."""
        if not self.ensure_connected():
            return {"status": "ERROR", "error": "MT5 not connected"}

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return {"status": "ERROR", "error": f"Position {ticket} not found"}

        pos = positions[0]
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(SYMBOL).bid if pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(SYMBOL).ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": SYMBOL,
            "volume": pos.volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "goldbot_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        return self.send_order(request)

    def close_all_positions(self) -> List[dict]:
        """Close all open positions on XAUUSD."""
        positions = self.get_positions()
        results = []
        for pos in positions:
            result = self.close_position(pos["ticket"])
            results.append(result)
        return results

    def modify_position(
        self, ticket: int, sl: Optional[float] = None, tp: Optional[float] = None
    ) -> Optional[dict]:
        """Modify SL/TP on an open position."""
        if not self.ensure_connected():
            return {"status": "ERROR", "error": "MT5 not connected"}

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return {"status": "ERROR", "error": f"Position {ticket} not found"}

        pos = positions[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": SYMBOL,
            "position": ticket,
            "sl": sl if sl is not None else pos.sl,
            "tp": tp if tp is not None else pos.tp,
        }
        return self.send_order(request)

    def get_symbol_info(self) -> Optional[dict]:
        """Get symbol details (point size, min lot, etc)."""
        if not self.ensure_connected():
            return None
        info = mt5.symbol_info(SYMBOL)
        if info is None:
            return None
        return {
            "point": info.point,
            "digits": info.digits,
            "trade_contract_size": info.trade_contract_size,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
        }


# ─── Singleton ─────────────────────────────────────────
_connector: Optional[MT5Connector] = None


def get_mt5() -> MT5Connector:
    """Get or create the MT5 connector singleton."""
    global _connector
    if _connector is None:
        _connector = MT5Connector()
    return _connector
