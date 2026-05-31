"""
Structure Skill — CHoCH, BOS, swing points, displacement detection.
Reads candle data and identifies institutional footprints.
"""
import numpy as np
import pandas as pd
from typing import List, Optional
from config.trading_rules import DISPLACEMENT_ATR_MULTIPLIER, ATR_PERIOD


def find_swing_points(df: pd.DataFrame, lookback: int = 5) -> dict:
    """
    Find swing highs and lows using N-bar lookback.
    A swing high = high is highest in lookback bars on both sides.
    """
    highs = df["high"].values
    lows = df["low"].values
    times = df["time"].values

    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(df) - lookback):
        # Swing High
        if highs[i] == max(highs[i - lookback:i + lookback + 1]):
            swing_highs.append({
                "price": float(highs[i]),
                "index": i,
                "time": str(times[i]),
                "type": "STRONG"  # will classify later
            })
        # Swing Low
        if lows[i] == min(lows[i - lookback:i + lookback + 1]):
            swing_lows.append({
                "price": float(lows[i]),
                "index": i,
                "time": str(times[i]),
                "type": "STRONG"
            })

    # Classify strong vs weak
    # Weak high = single push, no retest = TARGET
    # Strong high = impulse up + successful retest
    for i, sh in enumerate(swing_highs):
        if i > 0:
            prev = swing_highs[i - 1]
            # If price came back down and retested near prev high → strong
            retested = any(
                abs(sl["price"] - prev["price"]) < 3.0
                for sl in swing_lows
                if sl["index"] > prev["index"] and sl["index"] < sh["index"]
            )
            if not retested:
                sh["type"] = "WEAK"

    for i, sl in enumerate(swing_lows):
        if i > 0:
            prev = swing_lows[i - 1]
            retested = any(
                abs(sh_inner["price"] - prev["price"]) < 3.0
                for sh_inner in swing_highs
                if sh_inner["index"] > prev["index"] and sh_inner["index"] < sl["index"]
            )
            if not retested:
                sl["type"] = "WEAK"

    last_high = swing_highs[-1] if swing_highs else None
    last_low = swing_lows[-1] if swing_lows else None

    return {
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "last_high": last_high,
        "last_low": last_low,
    }


def detect_choch(df: pd.DataFrame, swing_points: dict) -> dict:
    """
    Detect Change of Character (CHoCH).
    CHoCH = first candle closing beyond most recent swing point in opposite direction.
    """
    if not swing_points["last_high"] or not swing_points["last_low"]:
        return {"confirmed": False}

    last_high = swing_points["last_high"]
    last_low = swing_points["last_low"]
    closes = df["close"].values
    times = df["time"].values

    # Check for bullish CHoCH: price breaks above a significant swing high
    # after a bearish move (break of previous structure to downside)
    bullish_choch = None
    bearish_choch = None

    for i in range(max(last_high["index"], last_low["index"]) + 1, len(df)):
        # Bullish CHoCH: close above last swing high after downtrend
        if closes[i] > last_high["price"] and last_low["index"] > last_high["index"]:
            bullish_choch = {
                "confirmed": True,
                "price": float(closes[i]),
                "level": last_high["price"],
                "direction": "BULLISH",
                "time": str(times[i]),
                "index": i,
            }
            break

        # Bearish CHoCH: close below last swing low after uptrend
        if closes[i] < last_low["price"] and last_high["index"] > last_low["index"]:
            bearish_choch = {
                "confirmed": True,
                "price": float(closes[i]),
                "level": last_low["price"],
                "direction": "BEARISH",
                "time": str(times[i]),
                "index": i,
            }
            break

    result = bullish_choch or bearish_choch
    if result:
        return result
    return {"confirmed": False}


def detect_bos(df: pd.DataFrame, swing_points: dict, current_trend: str) -> dict:
    """
    Detect Break of Structure (BOS).
    BOS = break of swing point in the direction of the current trend.
    """
    if not swing_points["last_high"] or not swing_points["last_low"]:
        return {"confirmed": False}

    closes = df["close"].values
    times = df["time"].values

    if current_trend == "BULLISH":
        target = swing_points["last_high"]
        for i in range(target["index"] + 1, len(df)):
            if closes[i] > target["price"]:
                return {
                    "confirmed": True,
                    "price": float(closes[i]),
                    "level": target["price"],
                    "timeframe": "detected",
                    "direction": "BULLISH",
                    "time": str(times[i]),
                }
    elif current_trend == "BEARISH":
        target = swing_points["last_low"]
        for i in range(target["index"] + 1, len(df)):
            if closes[i] < target["price"]:
                return {
                    "confirmed": True,
                    "price": float(closes[i]),
                    "level": target["price"],
                    "timeframe": "detected",
                    "direction": "BEARISH",
                    "time": str(times[i]),
                }

    return {"confirmed": False}


def detect_displacement(df: pd.DataFrame) -> dict:
    """
    Detect displacement candle (body > 1.5x ATR).
    Sign of institutional aggressive move.
    """
    if len(df) < ATR_PERIOD + 2:
        return {"detected": False}

    # Calculate ATR
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    tr_list = []
    for i in range(1, len(df)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        tr_list.append(tr)

    atr = np.mean(tr_list[-ATR_PERIOD:])

    # Check last candle
    last = df.iloc[-1]
    body = abs(last["close"] - last["open"])
    ratio = body / atr if atr > 0 else 0

    detected = ratio >= DISPLACEMENT_ATR_MULTIPLIER
    direction = "BULLISH" if last["close"] > last["open"] else "BEARISH"

    return {
        "detected": detected,
        "candle_size_vs_atr": round(ratio, 2),
        "direction": direction if detected else "NONE",
        "atr": round(atr, 2),
        "body_size": round(body, 2),
    }


def determine_trend(df: pd.DataFrame) -> str:
    """
    Simple trend determination using swing structure.
    Higher highs + higher lows = BULLISH
    Lower highs + lower lows = BEARISH
    """
    sp = find_swing_points(df, lookback=3)
    highs = sp["swing_highs"]
    lows = sp["swing_lows"]

    if len(highs) < 2 or len(lows) < 2:
        return "NEUTRAL"

    hh = highs[-1]["price"] > highs[-2]["price"]
    hl = lows[-1]["price"] > lows[-2]["price"]
    lh = highs[-1]["price"] < highs[-2]["price"]
    ll = lows[-1]["price"] < lows[-2]["price"]

    if hh and hl:
        return "BULLISH"
    elif lh and ll:
        return "BEARISH"
    return "NEUTRAL"
