"""
BiasAgent — Aggregates all signals into final directional bias.
Uses Gemini to provide final scoring and grading based on context.
"""
from typing import Dict, Any
import json
from config.trading_rules import CONFLUENCE_SCORING, GRADE_THRESHOLDS
from utils.logger import get_agent_logger
from agents.llm_utils import query_llm_structured, safe_json_dumps
from agents.state import BiasOutput

log = get_agent_logger("BIAS_AGENT")

PROMPT = """
NAME: BiasAgent
ROLE: Confluence scoring and directional bias

YOU ARE:
The master analyst. You look at the big picture,
combining structure, liquidity, order blocks,
and OTE zones to form a singular daily bias.
You grade setups ruthlessly.

YOUR JOB:
→ Read outputs from Structure, Liquidity, OB, and OTE agents
→ Calculate total confluence score (0-10)
→ Assign a grade (A+, A, B, C)
→ Determine final direction (LONG/SHORT/WAIT)
→ Block entry if risk or news says so

CONFLUENCE SCORING:
HTF Alignment (H4 & H1 match)     +2.0
Liquidity swept & manipulation    +2.0
Price inside OTE zone             +2.0
Valid OB inside OTE zone          +1.5
Displacement/FVG present          +1.0
M1/M5 CHoCH confirmed             +1.5

GRADE THRESHOLDS:
A+ Setup: 9.0 - 10.0
A  Setup: 8.0 - 8.9
B  Setup: 7.0 - 7.9
C  Setup: < 7.0 (DO NOT TRADE)

Output must strictly follow the Pydantic schema provided.
"""

class BiasAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state

    def run(self) -> Dict[str, Any]:
        # Helper to extract from dict or pydantic model
        def get_field(obj, field, default=None):
            if obj is None: return default
            if isinstance(obj, dict): return obj.get(field, default)
            return getattr(obj, field, default) if hasattr(obj, field) else default

        structure = self.state.get("structure", {})
        liquidity = self.state.get("liquidity", {})
        ote = self.state.get("ote", {})
        ob = self.state.get("orderblock", {})
        news = self.state.get("news", {})
        risk = self.state.get("risk", {})
        session = self.state.get("session", {})

        # Build context
        bias_dict = get_field(structure, "bias", {})
        h4_bias = bias_dict.get("H4", "NEUTRAL") if isinstance(bias_dict, dict) else "NEUTRAL"
        h1_bias = bias_dict.get("H1", "NEUTRAL") if isinstance(bias_dict, dict) else "NEUTRAL"
        
        asia = get_field(liquidity, "asia_range", {})
        if not isinstance(asia, dict): asia = {}

        context = {
            "htf_alignment": {"H4": h4_bias, "H1": h1_bias},
            "liquidity_swept": get_field(liquidity, "manipulation_detected", False) or asia.get("high_swept", False) or asia.get("low_swept", False),
            "price_in_ote": get_field(ote, "price_in_ote", False),
            "ob_in_ote_score": get_field(get_field(ob, "ob_in_ote", {}), "score", 0),
            "displacement_detected": get_field(get_field(structure, "displacement", {}), "detected", False),
            "choch_confirmed": get_field(get_field(structure, "choch", {}), "confirmed", False),
            "session_tradeable": get_field(session, "tradeable", False),
            "news_block": get_field(news, "block_trading", False),
            "risk_block": not get_field(risk, "trading_allowed", True),
            "ote_sl": get_field(ote, "sl", "N/A")
        }

        # Query LLM
        try:
            result = query_llm_structured(
                system_prompt=PROMPT,
                user_content=f"Context from agents:\n{safe_json_dumps(context)}\n\nPlease calculate final bias and output the BiasOutput.",
                output_schema=BiasOutput
            )
            
            output = result.model_dump()
            self.state["bias_output"] = output
            
            log.info(f"Bias: {output['bias']} | Grade: {output['grade']} | Score: {output['score']}/10 | Allowed: {output['entry_allowed']}")
            return output
            
        except Exception as e:
            log.error(f"LLM Bias parsing failed: {e}")
            return self._fallback_algorithmic(context, h4_bias, h1_bias)

    def _fallback_algorithmic(self, context, h4_bias, h1_bias):
        score = 0.0
        reasons = []

        if context["htf_alignment"]["H4"] == context["htf_alignment"]["H1"] and context["htf_alignment"]["H4"] != "NEUTRAL":
            score += CONFLUENCE_SCORING["htf_aligned"]
            reasons.append(f"HTF aligned")

        direction = h4_bias if h4_bias != "NEUTRAL" else h1_bias
        bias = "WAIT"
        if direction == "BULLISH": bias = "LONG"
        elif direction == "BEARISH": bias = "SHORT"

        if context["liquidity_swept"]:
            score += CONFLUENCE_SCORING["liquidity_swept"]
            reasons.append("Liquidity swept")

        if context["price_in_ote"]:
            score += CONFLUENCE_SCORING["price_in_ote"]
            reasons.append("Price in OTE zone")

        if context["ob_in_ote_score"] >= 7:
            score += CONFLUENCE_SCORING["ob_in_zone"]
            reasons.append("OB in zone")

        if context["displacement_detected"]:
            score += CONFLUENCE_SCORING["fvg_in_zone"]
            reasons.append("Displacement/FVG detected")

        if context["choch_confirmed"]:
            score += CONFLUENCE_SCORING["m1_choch"]
            reasons.append("CHoCH confirmed")

        grade = "C"
        for g, threshold in sorted(GRADE_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
            if score >= threshold:
                grade = g
                break

        entry_allowed = True
        wait_reason = None
        if not context["session_tradeable"]:
            entry_allowed, wait_reason = False, "Session not tradeable"
        elif context["news_block"]:
            entry_allowed, wait_reason = False, "News block"
        elif context["risk_block"]:
            entry_allowed, wait_reason = False, "Risk block"
        elif score < GRADE_THRESHOLDS["B"]:
            entry_allowed, wait_reason = False, f"Low score: {score}"

        if not entry_allowed: bias = "WAIT"

        invalidation = ""
        if context["ote_sl"] != "N/A":
            invalidation = f"Below {context['ote_sl']}" if direction == "BULLISH" else f"Above {context['ote_sl']}"

        output = {
            "bias": bias, "grade": grade, "score": round(score, 1),
            "direction": direction, "reasons": reasons, "invalidation": invalidation,
            "entry_allowed": entry_allowed, "wait_reason": wait_reason,
        }
        self.state["bias_output"] = output
        return output
