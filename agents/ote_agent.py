"""
OTEAgent — Fibonacci OTE zone calculator and sniper entry.
"""
from skills.fibonacci_skill import check_ote_zone
from skills.structure_skill import find_swing_points
from utils.logger import get_agent_logger

log = get_agent_logger("OTE_AGENT")


class OTEAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state

    def run(self) -> dict:
        data = self.state.get("data", {})
        candles = data.get("candles", {})
        structure = self.state.get("structure", {})
        price = data.get("current_price", {}).get("mid", 0)

        if price == 0:
            log.warning("No price data for OTE calculation")
            return {"valid": False}

        # Find the last impulse swing on H1 (primary) or M15 (secondary)
        swing = self._find_impulse_swing(candles, structure)
        if swing is None:
            log.info("No valid impulse swing found")
            self.state["ote"] = {"valid": False, "reject_reason": "No impulse swing"}
            return self.state["ote"]

        # Check for OB in zone to refine entry
        ob_in_ote = self.state.get("orderblock", {}).get("ob_in_ote")
        ob_mid = ob_in_ote["mid"] if ob_in_ote else None

        # Calculate full OTE
        result = check_ote_zone(
            current_price=price,
            swing_low=swing["low"],
            swing_high=swing["high"],
            direction=swing["direction"],
            ob_mid=ob_mid,
        )

        self.state["ote"] = result
        if result["valid"]:
            log.info(
                f"OTE VALID — Entry: {result['entry']} | SL: {result['sl']} | "
                f"TP1: {result['tp1']} R:R 1:{result['rr_tp1']} | "
                f"TP2: {result['tp2']} R:R 1:{result['rr_tp2']}"
            )
        else:
            log.info(f"OTE invalid: {result.get('reject_reason')}")

        return result

    def _find_impulse_swing(self, candles, structure):
        """Find the most recent impulse swing for OTE calculation."""
        bias = structure.get("bias", {})
        direction = bias.get("H1", bias.get("M15", "NEUTRAL"))

        if direction == "NEUTRAL":
            return None

        # Try H1 first, then M15
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
