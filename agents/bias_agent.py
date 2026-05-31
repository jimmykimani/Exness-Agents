"""
BiasAgent — Aggregates all signals into final directional bias.
Produces LONG, SHORT, or WAIT with a grade (A+/A/B/C).
"""
from config.trading_rules import CONFLUENCE_SCORING, GRADE_THRESHOLDS
from utils.logger import get_agent_logger

log = get_agent_logger("BIAS_AGENT")


class BiasAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state

    def run(self) -> dict:
        structure = self.state.get("structure", {})
        liquidity = self.state.get("liquidity", {})
        ote = self.state.get("ote", {})
        ob = self.state.get("orderblock", {})
        news = self.state.get("news", {})
        risk = self.state.get("risk", {})
        session = self.state.get("session", {})

        score = 0.0
        reasons = []

        # 1. HTF alignment (+2)
        h4_bias = structure.get("bias", {}).get("H4", "NEUTRAL")
        h1_bias = structure.get("bias", {}).get("H1", "NEUTRAL")
        if h4_bias == h1_bias and h4_bias != "NEUTRAL":
            score += CONFLUENCE_SCORING["htf_aligned"]
            reasons.append(f"HTF aligned: {h4_bias}")

        # Determine direction from HTF
        direction = h4_bias if h4_bias != "NEUTRAL" else h1_bias
        bias = "WAIT"
        if direction == "BULLISH":
            bias = "LONG"
        elif direction == "BEARISH":
            bias = "SHORT"

        # 2. Liquidity swept (+2)
        manip = liquidity.get("manipulation_detected", False)
        asia = liquidity.get("asia_range", {})
        swept = asia.get("high_swept", False) or asia.get("low_swept", False)
        if manip or swept:
            score += CONFLUENCE_SCORING["liquidity_swept"]
            reasons.append("Liquidity swept")

        # 3. Price in OTE (+2)
        if ote.get("price_in_ote", False):
            score += CONFLUENCE_SCORING["price_in_ote"]
            reasons.append(f"Price in OTE zone")

        # 4. OB in zone (+1)
        ob_in_ote = ob.get("ob_in_ote")
        if ob_in_ote and ob_in_ote.get("score", 0) >= 7:
            score += CONFLUENCE_SCORING["ob_in_zone"]
            reasons.append(f"OB in zone (score: {ob_in_ote['score']})")

        # 5. FVG check (+1) — simplified, check displacement as proxy
        displacement = structure.get("displacement", {})
        if displacement.get("detected", False):
            score += CONFLUENCE_SCORING["fvg_in_zone"]
            reasons.append("Displacement/FVG detected")

        # 6. Volume confirmation (+1)
        # Would come from volume_skill analysis
        score += 0  # placeholder — added when volume data available

        # 7. M1/M5 CHoCH (+1)
        choch = structure.get("choch", {})
        if choch.get("confirmed", False):
            score += CONFLUENCE_SCORING["m1_choch"]
            reasons.append(f"CHoCH confirmed ({choch.get('direction')})")

        # Grade
        grade = "C"
        for g, threshold in sorted(GRADE_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
            if score >= threshold:
                grade = g
                break

        # Wait conditions
        entry_allowed = True
        wait_reason = None

        if not session.get("tradeable", False):
            entry_allowed = False
            wait_reason = f"Session not tradeable: {session.get('session', 'N/A')}"
        elif news.get("block_trading", False):
            entry_allowed = False
            wait_reason = news.get("block_reason", "News block")
        elif not risk.get("trading_allowed", True):
            entry_allowed = False
            wait_reason = risk.get("block_reason", "Risk limit")
        elif score < GRADE_THRESHOLDS["B"]:
            entry_allowed = False
            wait_reason = f"Low confluence score: {score}/10"

        if not entry_allowed:
            bias = "WAIT"

        # Invalidation
        invalidation = ""
        if ote.get("valid"):
            if direction == "BULLISH":
                invalidation = f"Below {ote.get('sl', 'N/A')}"
            else:
                invalidation = f"Above {ote.get('sl', 'N/A')}"

        output = {
            "bias": bias,
            "grade": grade,
            "score": round(score, 1),
            "direction": direction,
            "reasons": reasons,
            "invalidation": invalidation,
            "entry_allowed": entry_allowed,
            "wait_reason": wait_reason,
        }

        self.state["bias_output"] = output
        log.info(f"Bias: {bias} | Grade: {grade} | Score: {score}/10 | Allowed: {entry_allowed}")
        return output
