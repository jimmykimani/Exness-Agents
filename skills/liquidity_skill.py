"""
Liquidity Skill — BSL/SSL pool mapping, EQH/EQL detection, Asia range.
"""
import pandas as pd
from typing import List, Optional
from config.trading_rules import EQH_EQL_TOLERANCE_POINTS, MIN_POOL_TOUCHES
from skills.structure_skill import find_swing_points


def detect_equal_levels(points: List[dict], tolerance: float = EQH_EQL_TOLERANCE_POINTS) -> List[dict]:
    """
    Find equal highs (EQH) or equal lows (EQL).
    Two+ points within tolerance = equal level = liquidity pool.
    """
    if len(points) < 2:
        return []

    equal_groups = []
    used = set()

    for i, p1 in enumerate(points):
        if i in used:
            continue
        group = [p1]
        for j, p2 in enumerate(points):
            if j <= i or j in used:
                continue
            if abs(p1["price"] - p2["price"]) <= tolerance:
                group.append(p2)
                used.add(j)
        if len(group) >= MIN_POOL_TOUCHES:
            avg_price = sum(p["price"] for p in group) / len(group)
            equal_groups.append({
                "level": round(avg_price, 2),
                "touches": len(group),
                "points": group,
            })
            used.add(i)

    return equal_groups


def map_liquidity_pools(df: pd.DataFrame, current_price: float, timeframe: str = "") -> dict:
    """
    Map all BSL (buyside) and SSL (sellside) liquidity pools.
    """
    sp = find_swing_points(df)
    highs = sp["swing_highs"]
    lows = sp["swing_lows"]

    # BSL pools (above price) — swing highs, EQH
    bsl_pools = []
    eqh = detect_equal_levels(highs)
    for h in highs:
        pool_type = "SWING_HIGH"
        for eq in eqh:
            if abs(h["price"] - eq["level"]) <= EQH_EQL_TOLERANCE_POINTS:
                pool_type = "EQH"
                break
        swept = current_price > h["price"]
        bsl_pools.append({
            "level": h["price"],
            "type": pool_type,
            "timeframe": timeframe,
            "touches": 1,
            "swept": swept,
            "size": "LARGE" if pool_type == "EQH" else "MEDIUM",
        })

    # SSL pools (below price) — swing lows, EQL
    ssl_pools = []
    eql = detect_equal_levels(lows)
    for l in lows:
        pool_type = "SWING_LOW"
        for eq in eql:
            if abs(l["price"] - eq["level"]) <= EQH_EQL_TOLERANCE_POINTS:
                pool_type = "EQL"
                break
        swept = current_price < l["price"]
        ssl_pools.append({
            "level": l["price"],
            "type": pool_type,
            "timeframe": timeframe,
            "touches": 1,
            "swept": swept,
            "size": "LARGE" if pool_type == "EQL" else "MEDIUM",
        })

    # Merge EQH/EQL touches
    for eq in eqh:
        for pool in bsl_pools:
            if abs(pool["level"] - eq["level"]) <= EQH_EQL_TOLERANCE_POINTS:
                pool["touches"] = eq["touches"]
    for eq in eql:
        for pool in ssl_pools:
            if abs(pool["level"] - eq["level"]) <= EQH_EQL_TOLERANCE_POINTS:
                pool["touches"] = eq["touches"]

    # Nearest pools
    unswept_bsl = [p for p in bsl_pools if not p["swept"] and p["level"] > current_price]
    unswept_ssl = [p for p in ssl_pools if not p["swept"] and p["level"] < current_price]

    nearest_bsl = min(unswept_bsl, key=lambda p: abs(p["level"] - current_price)) if unswept_bsl else None
    nearest_ssl = min(unswept_ssl, key=lambda p: abs(p["level"] - current_price)) if unswept_ssl else None

    return {
        "bsl_pools": sorted(bsl_pools, key=lambda p: p["level"]),
        "ssl_pools": sorted(ssl_pools, key=lambda p: p["level"], reverse=True),
        "nearest_bsl": {
            "level": nearest_bsl["level"],
            "distance": round(abs(nearest_bsl["level"] - current_price), 2),
        } if nearest_bsl else None,
        "nearest_ssl": {
            "level": nearest_ssl["level"],
            "distance": round(abs(nearest_ssl["level"] - current_price), 2),
        } if nearest_ssl else None,
    }


def check_asia_range(df_h1: pd.DataFrame, lock_hour: int = 9) -> dict:
    """
    Calculate Asia session range (01:00-09:00 EAT).
    Should be locked at 09:00 EAT.
    """
    if df_h1 is None or df_h1.empty:
        return {"high": 0, "low": 0, "mid": 0, "high_swept": False, "low_swept": False}

    # Filter for Asia hours (1-9 EAT in today's data)
    asia = df_h1[
        (df_h1["time"].dt.hour >= 1) & (df_h1["time"].dt.hour < lock_hour)
    ]

    if asia.empty:
        return {"high": 0, "low": 0, "mid": 0, "high_swept": False, "low_swept": False}

    high = float(asia["high"].max())
    low = float(asia["low"].min())
    mid = round((high + low) / 2, 2)

    # Check if swept after Asia close
    post_asia = df_h1[df_h1["time"].dt.hour >= lock_hour]
    high_swept = False
    low_swept = False
    if not post_asia.empty:
        high_swept = float(post_asia["high"].max()) > high
        low_swept = float(post_asia["low"].min()) < low

    return {
        "high": high,
        "low": low,
        "mid": mid,
        "high_swept": high_swept,
        "low_swept": low_swept,
    }
