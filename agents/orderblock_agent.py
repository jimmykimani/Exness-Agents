"""
OrderBlockAgent — Detect and score institutional order blocks.
Uses programmatic skills and Gemini for final analysis.
"""
from typing import Dict, Any
import json
from skills.orderblock_skill import detect_order_blocks
from config.trading_rules import OB_MIN_SCORE
from utils.logger import get_agent_logger
from agents.llm_utils import query_llm_structured, safe_json_dumps
from agents.state import OrderBlockOutput
from utils.session_clock import get_current_session

log = get_agent_logger("ORDER_BLOCK")

PROMPT = """
NAME: OrderBlockAgent
ROLE: Detect and score institutional order blocks

YOU ARE:
An OB specialist. You find where institutions
left unfilled orders behind. These zones are
where price must return and where we enter.
Quality matters more than quantity.

YOUR JOB:
→ Detect bullish and bearish OBs
→ Score each OB quality 1-10
→ Identify breaker blocks
→ Identify mitigation blocks
→ Track virgin vs tested OBs
→ Flag OBs inside OTE zones

SCORING RUBRIC:
Volume > 1.5x average:   +2.5 points
Gap/displacement after:   +2.0 points
Virgin (never retested):  +2.0 points
London/NY formation:      +2.0 points
Inside OTE zone:          +1.5 points
HTF aligned:              +1.0 point
Maximum score:            10 points

Minimum score to flag:    7/10
A+ setup requires:        8.5+/10

Output must strictly follow the Pydantic schema provided.
"""

class OrderBlockAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state

    def run(self) -> Dict[str, Any]:
        data = self.state.get("data", {})
        candles = data.get("candles", {})
        
        # Depending on if state is Pydantic or dict
        struct = self.state.get("structure")
        if isinstance(struct, dict):
            htf_bias = struct.get("bias", {}).get("H1", "NEUTRAL")
        elif struct:
            htf_bias = struct.bias.get("H1", "NEUTRAL")
        else:
            htf_bias = "NEUTRAL"
            
        ote = self.state.get("ote")
        if isinstance(ote, dict):
            ote_zone = ote.get("ote_zone")
        elif ote:
            ote_zone = ote.ote_zone
        else:
            ote_zone = None

        session = get_current_session() or ""

        # 1. Detect OBs programmatically on M5, M15, H1
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

        # 2. Build context
        context = {
            "htf_bias": htf_bias,
            "ote_zone": ote_zone,
            "algorithmic_bullish_obs": bullish_obs,
            "algorithmic_bearish_obs": bearish_obs
        }

        # 3. Query LLM
        try:
            result = query_llm_structured(
                system_prompt=PROMPT,
                user_content=f"Context from programmatic indicators:\n{safe_json_dumps(context)}\n\nPlease finalize the OrderBlockOutput.",
                output_schema=OrderBlockOutput
            )
            
            output = result.model_dump()
            self.state["orderblock"] = output
            
            best_score = output.get("best_ob", {}).get("score") if output.get("best_ob") else 0
            log.info(f"OrderBlocks — Bullish: {len(output.get('bullish_obs', []))} | Bearish: {len(output.get('bearish_obs', []))} | Best: {best_score}")
            return output
            
        except Exception as e:
            log.error(f"LLM OB parsing failed: {e}")
            return self._fallback_algorithmic(bullish_obs, bearish_obs)

    def _fallback_algorithmic(self, bullish_obs, bearish_obs):
        best_ob = None
        all_obs = bullish_obs + bearish_obs
        if all_obs:
            best_ob = max(all_obs, key=lambda x: x["score"])

        ob_in_ote = None
        ote_obs = [ob for ob in all_obs if ob.get("inside_ote")]
        if ote_obs:
            ob_in_ote = max(ote_obs, key=lambda x: x["score"])

        nearest_ob = None
        # Simplified for algorithmic fallback
        if all_obs:
            nearest_ob = all_obs[0]

        output = {
            "bullish_obs": bullish_obs,
            "bearish_obs": bearish_obs,
            "best_ob": best_ob,
            "ob_in_ote": ob_in_ote,
            "nearest_ob": nearest_ob
        }
        self.state["orderblock"] = output
        return output
