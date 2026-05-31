"""
OTEAgent — Fibonacci OTE zone calculator and sniper entry.
Uses programmatic skills and Gemini for final analysis.
"""
from typing import Dict, Any
import json
from skills.fibonacci_skill import check_ote_zone
from skills.structure_skill import find_swing_points
from utils.logger import get_agent_logger
from agents.llm_utils import query_llm_structured, safe_json_dumps
from agents.state import OTEOutput

log = get_agent_logger("OTE_AGENT")

PROMPT = """
NAME: OTEAgent
ROLE: Fibonacci OTE zone calculator + sniper entry

YOU ARE:
A precision entry specialist. You use
Fibonacci retracement to identify exactly
where institutions re-enter after creating
an impulse. Your entries have the tightest
SLs and highest R:R in the system.

YOUR JOB:
→ Identify impulse swings
→ Calculate all Fibonacci levels
→ Define OTE zone (61.8-78.6%)
→ Check if price is in OTE
→ Calculate sniper entry within OTE
→ Calculate precise SL and TPs
→ Score confluence

SNIPER PROCESS:
1. Find last impulse on H1
2. Calculate all fib levels
3. Check if current price in 61.8-78.6%
4. If OB exists in zone → use OB mid as entry
5. If FVG exists in zone → use FVG mid as entry
6. SL = 78.6% level - 5pts buffer
7. TP1 = 100% (swing origin)
8. TP2 = 127.2% extension
9. TP3 = 161.8% extension
10. R:R check: TP2 must be minimum 1:3

REJECT if:
→ R:R to TP2 < 1:3
→ Price not in OTE zone
→ Swing too small (< 20pts range)

Output must strictly follow the Pydantic schema provided.
"""

class OTEAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state

    def run(self) -> Dict[str, Any]:
        data = self.state.get("data", {})
        candles = data.get("candles", {})
        structure = self.state.get("structure", {})
        price = data.get("current_price", {}).get("mid", 0)

        if price == 0:
            log.warning("No price data for OTE calculation")
            return self._empty_result()

        # 1. Programmatic math
        swing = self._find_impulse_swing(candles, structure)
        if swing is None:
            log.info("No valid impulse swing found")
            res = self._empty_result()
            self.state["ote"] = res
            return res

        ob_in_ote = None
        ob = self.state.get("orderblock")
        if isinstance(ob, dict):
            ob_in_ote = ob.get("ob_in_ote")
        elif ob:
            ob_in_ote = ob.ob_in_ote
            
        ob_mid = ob_in_ote.get("mid") if isinstance(ob_in_ote, dict) and ob_in_ote else (ob_in_ote.mid if ob_in_ote else None)

        alg_result = check_ote_zone(
            current_price=price,
            swing_low=swing["low"],
            swing_high=swing["high"],
            direction=swing["direction"],
            ob_mid=ob_mid,
        )

        context = {
            "current_price": price,
            "impulse_swing": swing,
            "ob_in_zone_mid": ob_mid,
            "algorithmic_calculation": alg_result
        }

        # 2. Ask Gemini for final mapping
        try:
            result = query_llm_structured(
                system_prompt=PROMPT,
                user_content=f"Context from programmatic indicators:\n{safe_json_dumps(context)}\n\nPlease finalize the OTEOutput.",
                output_schema=OTEOutput
            )
            
            output = result.model_dump()
            self.state["ote"] = output
            
            if output.get("valid"):
                log.info(
                    f"OTE VALID — Entry: {output['entry']} | SL: {output['sl']} | "
                    f"TP1: {output['tp1']} R:R 1:{output['rr_tp1']} | "
                    f"TP2: {output['tp2']} R:R 1:{output['rr_tp2']}"
                )
            else:
                log.info(f"OTE invalid")
                
            return output
            
        except Exception as e:
            log.error(f"LLM OTE parsing failed: {e}")
            self.state["ote"] = alg_result
            return alg_result

    def _empty_result(self):
        return {
            "valid": False, "swing": {}, "fib_levels": {}, "ote_zone": [], 
            "price_in_ote": False, "optimal_entry": 0, "entry": 0, "sl": 0, 
            "tp1": 0, "tp2": 0, "tp3": 0, "risk_pts": 0, "rr_tp1": 0, "rr_tp2": 0, "rr_tp3": 0, "confluence_score": 0
        }

    def _find_impulse_swing(self, candles, structure):
        bias = structure.get("bias", {}) if isinstance(structure, dict) else (structure.bias if structure else {})
        direction = bias.get("H1", bias.get("M15", "NEUTRAL"))

        if direction == "NEUTRAL":
            return None

        for tf in ["H1", "M15"]:
            df = candles.get(tf)
            if df is None or df.empty:
                continue

            sp = find_swing_points(df, lookback=5)
            last_high = sp.get("last_high")
            last_low = sp.get("last_low")

            if last_high and last_low:
                return {
                    "high": last_high["price"],
                    "low": last_low["price"],
                    "direction": "BULLISH" if direction == "BULLISH" else "BEARISH",
                }

        return None
