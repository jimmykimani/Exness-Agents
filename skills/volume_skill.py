"""
Volume Skill — Volume analysis and confirmation.
"""
import numpy as np
import pandas as pd
from typing import Optional


def analyze_volume(df: pd.DataFrame, period: int = 20) -> dict:
    """
    Analyze volume characteristics for confirmation.
    """
    if df is None or len(df) < period + 1:
        return {"confirmation": False, "ratio": 0.0}

    volumes = df["volume"].values
    if not np.any(volumes > 0):
        return {"confirmation": False, "ratio": 0.0, "note": "No volume data"}

    current_vol = float(volumes[-1])
    avg_vol = float(np.mean(volumes[-period - 1:-1]))

    ratio = current_vol / avg_vol if avg_vol > 0 else 0

    return {
        "current_volume": current_vol,
        "avg_volume": round(avg_vol, 0),
        "ratio": round(ratio, 2),
        "confirmation": ratio > 1.5,  # volume spike
        "climax": ratio > 3.0,        # exhaustion/climax volume
    }
