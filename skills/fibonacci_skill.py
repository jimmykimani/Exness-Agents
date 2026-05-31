"""
Fibonacci Skill — Calculates all fib levels and OTE zone.
Pure math, no side effects.
"""
from typing import Optional
from config.trading_rules import FIB_LEVELS, OTE_ZONE, SL_BUFFER_POINTS, MIN_SWING_RANGE_POINTS


def calculate_fibonacci(swing_low: float, swing_high: float, direction: str) -> dict:
    """
    Calculate all Fibonacci retracement and extension levels.
    direction: BULLISH (retracement from high) or BEARISH (retracement from low)
    """
    swing_range = abs(swing_high - swing_low)

    levels = {}
    for name, ratio in FIB_LEVELS.items():
        if direction == "BULLISH":
            # Retracement goes DOWN from high
            levels[name] = round(swing_high - (swing_range * ratio), 2)
        else:
            # Retracement goes UP from low
            levels[name] = round(swing_low + (swing_range * ratio), 2)

    # OTE zone boundaries
    ote_start = levels["61.8"]
    ote_end = levels["78.6"]
    ote_zone = (min(ote_start, ote_end), max(ote_start, ote_end))

    return {
        "swing": {"low": swing_low, "high": swing_high, "direction": direction},
        "fib_levels": levels,
        "ote_zone": ote_zone,
        "optimal_entry": levels["70.5"],
        "swing_range": round(swing_range, 2),
    }


def check_ote_zone(
    current_price: float,
    swing_low: float,
    swing_high: float,
    direction: str,
    ob_mid: Optional[float] = None,
) -> dict:
    """
    Full OTE analysis: is price in OTE zone? Calculate entry, SL, TPs.
    """
    fib = calculate_fibonacci(swing_low, swing_high, direction)
    levels = fib["fib_levels"]
    ote = fib["ote_zone"]
    swing_range = fib["swing_range"]

    # Validity checks
    if swing_range < MIN_SWING_RANGE_POINTS:
        return {**fib, "valid": False, "reject_reason": f"Swing too small: {swing_range:.1f}pts < {MIN_SWING_RANGE_POINTS}"}

    price_in_ote = ote[0] <= current_price <= ote[1]

    # Entry: prefer OB mid if available and in zone, else use 70.5%
    entry = fib["optimal_entry"]
    if ob_mid and ote[0] <= ob_mid <= ote[1]:
        entry = ob_mid

    # SL and TPs
    if direction == "BULLISH":
        sl = levels["78.6"] - SL_BUFFER_POINTS
        tp1 = levels["0"]      # back to swing high
        tp2 = swing_high + swing_range * 0.272  # -27.2 extension
        tp3 = swing_high + swing_range * 0.618  # -61.8 extension
    else:
        sl = levels["78.6"] + SL_BUFFER_POINTS
        tp1 = levels["0"]      # back to swing low
        tp2 = swing_low - swing_range * 0.272
        tp3 = swing_low - swing_range * 0.618

    risk_pts = abs(entry - sl)
    rr_tp1 = abs(tp1 - entry) / risk_pts if risk_pts > 0 else 0
    rr_tp2 = abs(tp2 - entry) / risk_pts if risk_pts > 0 else 0
    rr_tp3 = abs(tp3 - entry) / risk_pts if risk_pts > 0 else 0

    valid = price_in_ote and rr_tp2 >= 3.0

    return {
        **fib,
        "price_in_ote": price_in_ote,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "tp3": round(tp3, 2),
        "risk_pts": round(risk_pts, 2),
        "rr_tp1": round(rr_tp1, 2),
        "rr_tp2": round(rr_tp2, 2),
        "rr_tp3": round(rr_tp3, 2),
        "valid": valid,
        "reject_reason": None if valid else (
            "Price not in OTE" if not price_in_ote else f"R:R to TP2 too low: 1:{rr_tp2:.1f}"
        ),
    }
