"""
Execution Skill — Lot size calculation and MT5 order building.
"""
from config.settings import SYMBOL
from config.trading_rules import MAX_LOT_SIZE, RISK_PER_TRADE_PCT


def calculate_lot_size(balance: float, sl_points: float) -> float:
    """
    Calculate position size based on risk.
    Formula: lot = (balance * risk%) / (sl_points * point_value)
    Always capped at MAX_LOT_SIZE.
    """
    if sl_points <= 0:
        return 0.01

    risk_dollars = balance * RISK_PER_TRADE_PCT
    # Gold: 1 lot = 100oz, 1 point = $0.01 per 0.01 lot
    # For 0.01 lot: $0.10 per point on XAUUSDm
    point_value_per_lot = 10.0  # $10 per point for 1.0 lot
    lot = risk_dollars / (sl_points * point_value_per_lot)

    # Round down to nearest 0.01
    lot = int(lot * 100) / 100.0
    lot = max(0.01, min(lot, MAX_LOT_SIZE))

    return lot


def build_order_request(
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    lot: float,
    order_type: str = "MARKET",
) -> dict:
    """
    Build an MT5 order request dictionary.
    """
    try:
        import MetaTrader5 as mt5

        if direction.upper() in ("LONG", "BUY", "BULLISH"):
            trade_type = mt5.ORDER_TYPE_BUY if order_type == "MARKET" else mt5.ORDER_TYPE_BUY_LIMIT
        else:
            trade_type = mt5.ORDER_TYPE_SELL if order_type == "MARKET" else mt5.ORDER_TYPE_SELL_LIMIT

        request = {
            "action": mt5.TRADE_ACTION_DEAL if order_type == "MARKET" else mt5.TRADE_ACTION_PENDING,
            "symbol": SYMBOL,
            "volume": lot,
            "type": trade_type,
            "price": entry,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 234000,
            "comment": "goldbot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        return request
    except ImportError:
        # Simulation mode
        return {
            "action": "DEAL" if order_type == "MARKET" else "PENDING",
            "symbol": SYMBOL,
            "volume": lot,
            "type": f"{'BUY' if direction.upper() in ('LONG', 'BUY', 'BULLISH') else 'SELL'}_{order_type}",
            "price": entry,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 234000,
            "comment": "goldbot_sim",
        }
