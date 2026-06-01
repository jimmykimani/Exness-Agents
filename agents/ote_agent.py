"""
OTEAgent — Fibonacci OTE zone calculator and sniper entry.
Uses pure programmatic math (no LLM) to save API quotas.
"""
from typing import Dict, Any
from skills.fibonacci_skill import check_ote_zone
from skills.structure_skill import find_swing_points
from utils.logger import get_agent_logger

log = get_agent_logger("OTE_AGENT")


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

        self.state["ote"] = alg_result
        
        if alg_result.get("valid"):
            log.info(
                f"OTE VALID — Entry: {alg_result.get('entry')} | SL: {alg_result.get('sl')} | "
                f"TP1: {alg_result.get('tp1')} R:R 1:{alg_result.get('rr_tp1', 0)} | "
                f"TP2: {alg_result.get('tp2')} R:R 1:{alg_result.get('rr_tp2', 0)}"
            )
        else:
            log.info("OTE invalid")
            
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
