"""
StructureAgent — Market structure analysis.
Uses Gemini to analyze programmatic skill outputs and raw data to determine structure.
"""
from typing import Dict, Any
import json
import pandas as pd

from skills.structure_skill import (
    find_swing_points, detect_choch, detect_bos,
    detect_displacement, determine_trend,
)
from utils.logger import get_agent_logger
from agents.llm_utils import query_llm_structured, safe_json_dumps
from agents.state import StructureOutput

log = get_agent_logger("STRUCTURE")

PROMPT = """
NAME: StructureAgent
ROLE: Market structure analysis

YOU ARE:
A pure market structure reader. You identify
where smart money has left footprints through
CHoCH, BOS and MSS patterns. You think like
an institution, not a retail trader.

YOUR JOB:
→ Identify CHoCH on all timeframes
→ Identify BOS on all timeframes
→ Determine trend per timeframe
→ Find swing highs and lows
→ Classify highs/lows as strong or weak
→ Detect displacement candles
→ Identify inducement traps

LOGIC:
CHoCH = first candle closing beyond most recent swing point in opposite direction
BOS = break of swing point in trend direction
Strong High = impulse up + successful retest
Weak High = single push, no retest = TARGET
Displacement = candle body > 1.5x ATR(14)
Inducement = CHoCH on low volume + reversal

IMPORTANT:
→ Never call first CHoCH as confirmed entry signal
→ Always check for inducement before flagging CHoCH
→ Minimum: 3 timeframes must agree for BIAS output

Output must strictly follow the Pydantic schema provided.
"""

class StructureAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state

    def run(self) -> Dict[str, Any]:
        """Analyze market structure using programmatic tools + Gemini."""
        data = self.state.get("data", {})
        candles = data.get("candles", {})

        if not candles:
            log.warning("No candle data available")
            return {}

        # 1. Pre-calculate raw data using algorithmic skills to assist the LLM
        bias = {}
        all_swings = {}
        for tf in ["H4", "H1", "M30", "M15", "M5"]:
            df = candles.get(tf)
            if df is None or df.empty:
                bias[tf] = "NEUTRAL"
                continue
            bias[tf] = determine_trend(df)
            all_swings[tf] = find_swing_points(df)

        m15 = candles.get("M15")
        m5 = candles.get("M5")
        swing_points = all_swings.get("M15", {})

        choch_data = {"confirmed": False}
        if m5 is not None and not m5.empty:
            m5_swings = all_swings.get("M5", find_swing_points(m5))
            choch_data = detect_choch(m5, m5_swings)
            if choch_data.get("confirmed"):
                choch_data["timeframe"] = "M5"

        current_trend = bias.get("M15", "NEUTRAL")
        bos_data = {"confirmed": False}
        if m15 is not None and not m15.empty and swing_points:
            bos_data = detect_bos(m15, swing_points, current_trend)
            if bos_data.get("confirmed"):
                bos_data["timeframe"] = "M15"

        displacement_data = {"detected": False}
        if m15 is not None and not m15.empty:
            displacement_data = detect_displacement(m15)
            
        current_price = data.get("current_price", {}).get("mid", 0)

        # 2. Build context for the LLM
        context = {
            "current_price": current_price,
            "algorithmic_bias_calc": bias,
            "m15_swings": swing_points,
            "m5_choch": choch_data,
            "m15_bos": bos_data,
            "m15_displacement": displacement_data
        }

        # 3. Ask Gemini to finalize the structure analysis
        try:
            result = query_llm_structured(
                system_prompt=PROMPT,
                user_content=f"Context from programmatic indicators:\n{safe_json_dumps(context)}\n\nPlease finalize the StructureOutput.",
                output_schema=StructureOutput
            )
            
            output = result.model_dump()
            self.state["structure"] = output
            
            pd_zone = output.get("premium_discount", "UNKNOWN")
            log.info(
                f"Structure: Bias H4={output.get('bias', {}).get('H4')} | "
                f"CHoCH={output.get('choch', {}).get('confirmed')} | PD={pd_zone}"
            )
            return output
            
        except Exception as e:
            log.error(f"LLM Structure parsing failed: {e}")
            # Fallback to programmatic
            return self._fallback_algorithmic(bias, swing_points, choch_data, bos_data, displacement_data, current_price)
            
    def _fallback_algorithmic(self, bias, swing_points, choch_data, bos_data, displacement_data, current_price):
        inducement_warning = False
        if choch_data.get("confirmed") and not displacement_data.get("detected"):
            inducement_warning = True

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
            "choch": choch_data,
            "bos": bos_data,
            "displacement": displacement_data,
            "inducement_warning": inducement_warning,
            "premium_discount": pd_zone,
            "equilibrium": equilibrium,
        }
        self.state["structure"] = output
        return output
