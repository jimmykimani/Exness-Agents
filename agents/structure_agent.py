"""
StructureAgent — Market structure analysis.
Identifies CHoCH, BOS, swing points, displacement on all timeframes.
"""
from typing import Dict
import pandas as pd

from skills.structure_skill import (
    find_swing_points, detect_choch, detect_bos,
    detect_displacement, determine_trend,
)
from config.trading_rules import MIN_TF_AGREEMENT
from utils.logger import get_agent_logger

log = get_agent_logger("STRUCTURE")


class StructureAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state

    def run(self) -> dict:
        """Analyze market structure across all timeframes."""
        data = self.state.get("data", {})
        candles = data.get("candles", {})

        if not candles:
            log.warning("No candle data available")
            return {"bias": {}, "error": "No data"}

        # Determine bias per timeframe
        bias = {}
        all_swings = {}
        for tf in ["H4", "H1", "M30", "M15", "M5"]:
            df = candles.get(tf)
            if df is None or df.empty:
                bias[tf] = "NEUTRAL"
                continue
            bias[tf] = determine_trend(df)
            all_swings[tf] = find_swing_points(df)

        # Primary analysis on M15 for entries
        m15 = candles.get("M15")
        m5 = candles.get("M5")

        swing_points = all_swings.get("M15", find_swing_points(m15) if m15 is not None else {})

        # CHoCH detection on M5 (entry TF)
        choch = {"confirmed": False}
        if m5 is not None and not m5.empty:
            m5_swings = all_swings.get("M5", find_swing_points(m5))
            choch = detect_choch(m5, m5_swings)
            if choch.get("confirmed"):
                choch["timeframe"] = "M5"

        # BOS detection on M15
        current_trend = bias.get("M15", "NEUTRAL")
        bos = {"confirmed": False}
        if m15 is not None and not m15.empty and swing_points:
            bos = detect_bos(m15, swing_points, current_trend)
            if bos.get("confirmed"):
                bos["timeframe"] = "M15"

        # Displacement on M15
        displacement = {"detected": False}
        if m15 is not None and not m15.empty:
            displacement = detect_displacement(m15)

        # Inducement warning — CHoCH on low significance
        inducement_warning = False
        if choch.get("confirmed") and not displacement.get("detected"):
            inducement_warning = True

        # Premium/Discount
        current_price = data.get("current_price", {}).get("mid", 0)
        equilibrium = 0.0
        pd_zone = "EQUILIBRIUM"
        if swing_points.get("last_high") and swing_points.get("last_low"):
            h = swing_points["last_high"]["price"]
            l = swing_points["last_low"]["price"]
            equilibrium = round((h + l) / 2, 2)
            if current_price > equilibrium:
                pd_zone = "PREMIUM"
            elif current_price < equilibrium:
                pd_zone = "DISCOUNT"

        output = {
            "bias": bias,
            "swing_points": swing_points,
            "choch": choch,
            "bos": bos,
            "displacement": displacement,
            "inducement_warning": inducement_warning,
            "premium_discount": pd_zone,
            "equilibrium": equilibrium,
        }

        self.state["structure"] = output
        log.info(
            f"Structure: Bias H4={bias.get('H4')} H1={bias.get('H1')} | "
            f"CHoCH={choch.get('confirmed')} | PD={pd_zone}"
        )
        return output
