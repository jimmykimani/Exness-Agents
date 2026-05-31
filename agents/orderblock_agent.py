"""
OrderBlockAgent — Detect and score institutional order blocks.
"""
from skills.orderblock_skill import detect_order_blocks
from config.trading_rules import OB_MIN_SCORE
from utils.logger import get_agent_logger

log = get_agent_logger("ORDER_BLOCK")


class OrderBlockAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state

    def run(self) -> dict:
        data = self.state.get("data", {})
        candles = data.get("candles", {})
        structure = self.state.get("structure", {})
        ote = self.state.get("ote", {})
        price = data.get("current_price", {}).get("mid", 0)

        htf_bias = structure.get("bias", {}).get("H1", "NEUTRAL")
        ote_zone = ote.get("ote_zone")

        from utils.session_clock import get_current_session
        session = get_current_session() or ""

        # Detect OBs on M5 and M15
        bullish_obs = []
        bearish_obs = []
        for tf in ["M5", "M15", "H1"]:
            df = candles.get(tf)
            if df is None or df.empty:
                continue

            bulls = detect_order_blocks(df, "BULLISH", tf, ote_zone, htf_bias, session)
            bears = detect_order_blocks(df, "BEARISH", tf, ote_zone, htf_bias, session)

            bullish_obs.extend([ob for ob in bulls if ob["score"] >= OB_MIN_SCORE])
            bearish_obs.extend([ob for ob in bears if ob["score"] >= OB_MIN_SCORE])

        # Best OBs
        best_ob = None
        all_obs = bullish_obs + bearish_obs
        if all_obs:
            best_ob = max(all_obs, key=lambda x: x["score"])

        # OB in OTE zone
        ob_in_ote = None
        ote_obs = [ob for ob in all_obs if ob.get("inside_ote")]
        if ote_obs:
            ob_in_ote = max(ote_obs, key=lambda x: x["score"])

        # Nearest to price
        nearest_ob = None
        if all_obs and price > 0:
            nearest_ob = min(all_obs, key=lambda x: abs(x["mid"] - price))

        output = {
            "bullish_obs": sorted(bullish_obs, key=lambda x: x["score"], reverse=True)[:5],
            "bearish_obs": sorted(bearish_obs, key=lambda x: x["score"], reverse=True)[:5],
            "best_ob": best_ob,
            "ob_in_ote": ob_in_ote,
            "nearest_ob": nearest_ob,
        }

        self.state["orderblock"] = output
        log.info(f"OBs found — Bull: {len(bullish_obs)} | Bear: {len(bearish_obs)} | Best: {best_ob['score'] if best_ob else 'N/A'}")
        return output
