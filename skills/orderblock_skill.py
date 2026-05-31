"""
Order Block Skill — Detect and score institutional order blocks.
"""
import numpy as np
import pandas as pd
from typing import List, Optional
from config.trading_rules import OB_SCORING, OB_MIN_SCORE, OB_VOLUME_MULTIPLIER


def detect_order_blocks(
    df: pd.DataFrame,
    direction: str,
    timeframe: str = "",
    ote_zone: Optional[tuple] = None,
    htf_bias: str = "NEUTRAL",
    session: str = "",
) -> List[dict]:
    """
    Detect order blocks in candle data.
    Bullish OB = last red candle before significant bullish impulse.
    Bearish OB = last green candle before significant bearish impulse.
    """
    if len(df) < 10:
        return []

    obs = []
    closes = df["close"].values
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    volumes = df["volume"].values if "volume" in df.columns else np.ones(len(df))
    times = df["time"].values

    avg_vol = np.mean(volumes) if np.any(volumes > 0) else 1
    avg_body = np.mean(np.abs(closes - opens))

    for i in range(2, len(df) - 1):
        is_red = closes[i] < opens[i]
        is_green = closes[i] > opens[i]

        # Next candle must be a strong impulse in opposite direction
        next_body = abs(closes[i + 1] - opens[i + 1])
        is_impulse = next_body > avg_body * 1.5

        if not is_impulse:
            continue

        ob = None

        # Bullish OB: red candle → strong green impulse
        if is_red and closes[i + 1] > opens[i + 1]:
            ob = {
                "top": float(opens[i]),     # open of red candle (top)
                "bottom": float(closes[i]),  # close of red candle (bottom)
                "mid": round((opens[i] + closes[i]) / 2, 2),
                "direction": "BULLISH",
                "timeframe": timeframe,
                "time": str(times[i]),
                "index": i,
                "volume_at_creation": float(volumes[i]),
                "impulse_size": float(next_body),
            }

        # Bearish OB: green candle → strong red impulse
        elif is_green and closes[i + 1] < opens[i + 1]:
            ob = {
                "top": float(closes[i]),    # close of green (top)
                "bottom": float(opens[i]),   # open of green (bottom)
                "mid": round((opens[i] + closes[i]) / 2, 2),
                "direction": "BEARISH",
                "timeframe": timeframe,
                "time": str(times[i]),
                "index": i,
                "volume_at_creation": float(volumes[i]),
                "impulse_size": float(next_body),
            }

        if ob:
            # Check if virgin (price hasn't returned to zone since)
            virgin = True
            for j in range(i + 2, len(df)):
                if ob["direction"] == "BULLISH" and lows[j] <= ob["top"]:
                    virgin = False
                    break
                elif ob["direction"] == "BEARISH" and highs[j] >= ob["bottom"]:
                    virgin = False
                    break

            ob["virgin"] = virgin

            # Check if gap/displacement after
            if i + 2 < len(df):
                gap = False
                if ob["direction"] == "BULLISH":
                    gap = lows[i + 2] > highs[i]  # gap up
                else:
                    gap = highs[i + 2] < lows[i]  # gap down
                ob["has_gap"] = gap
            else:
                ob["has_gap"] = False

            # Check if inside OTE zone
            inside_ote = False
            if ote_zone:
                inside_ote = ote_zone[0] <= ob["mid"] <= ote_zone[1]
            ob["inside_ote"] = inside_ote

            # Score the OB
            ob["score"] = score_order_block(ob, avg_vol, htf_bias, session)
            ob["type"] = _classify_ob_type(ob)

            obs.append(ob)

    # Filter by direction requested
    if direction == "BULLISH":
        obs = [o for o in obs if o["direction"] == "BULLISH"]
    elif direction == "BEARISH":
        obs = [o for o in obs if o["direction"] == "BEARISH"]

    return sorted(obs, key=lambda x: x["score"], reverse=True)


def score_order_block(ob: dict, avg_volume: float, htf_bias: str, session: str) -> float:
    """Score an OB on a 0-10 scale using the rubric."""
    score = 0.0

    # Volume above average
    if ob.get("volume_at_creation", 0) > avg_volume * OB_VOLUME_MULTIPLIER:
        score += OB_SCORING["volume_above_avg"]

    # Gap/displacement after
    if ob.get("has_gap", False):
        score += OB_SCORING["gap_displacement"]

    # Virgin
    if ob.get("virgin", False):
        score += OB_SCORING["virgin"]

    # Session formation
    if session.upper() in ("LONDON", "NEW_YORK"):
        score += OB_SCORING["session_formation"]

    # Inside OTE
    if ob.get("inside_ote", False):
        score += OB_SCORING["inside_ote"]

    # HTF aligned
    ob_dir = ob.get("direction", "")
    if (ob_dir == "BULLISH" and htf_bias == "BULLISH") or \
       (ob_dir == "BEARISH" and htf_bias == "BEARISH"):
        score += OB_SCORING["htf_aligned"]

    return round(min(score, 10.0), 1)


def _classify_ob_type(ob: dict) -> str:
    """Classify OB type: STANDARD, BREAKER, PROPULSION, MITIGATION."""
    if ob.get("has_gap", False):
        return "PROPULSION"
    if not ob.get("virgin", True):
        return "MITIGATION"
    return "STANDARD"
