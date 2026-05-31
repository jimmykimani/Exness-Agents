"""
LiquidityAgent — Maps all institutional liquidity pools.
Uses programmatic skills and Gemini for final analysis.
"""
from typing import Dict, Any
import json
from skills.liquidity_skill import map_liquidity_pools, check_asia_range
from utils.logger import get_agent_logger
from agents.llm_utils import query_llm_structured, safe_json_dumps
from agents.state import LiquidityOutput

log = get_agent_logger("LIQUIDITY")

PROMPT = """
NAME: LiquidityAgent
ROLE: Map all institutional liquidity pools

YOU ARE:
A liquidity hunter. You see the market as
pools of stop losses waiting to be raided
by institutions. You predict where price
goes next by finding the nearest unswept
liquidity.

YOUR JOB:
→ Map all BSL and SSL pools
→ Identify EQH and EQL
→ Track PDH/PDL/PWH/PWL
→ Mark Asia High/Low at 09:00 EAT
→ Track which pools are swept vs unswept
→ Predict next liquidity target

LOGIC:
EQH = two+ highs within 2pts of each other
EQL = two+ lows within 2pts of each other
Pool size = number of touches at same level
Swept = price traded through the level
Draw on liquidity = largest unswept pool in direction of HTF bias

Asia range:
→ Lock at exactly 09:00 EAT
→ London sweeps one side = manipulation
→ Opposite side = real direction

Output must strictly follow the Pydantic schema provided.
"""

class LiquidityAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state
        self.asia_range = None  # Locked at 09:00 EAT

    def run(self) -> Dict[str, Any]:
        data = self.state.get("data", {})
        candles = data.get("candles", {})
        price = data.get("current_price", {}).get("mid", 0)

        if not candles or price == 0:
            log.warning("No data for liquidity mapping")
            return {}

        # 1. Map pools programmatically
        all_bsl = []
        all_ssl = []
        for tf in ["H1", "M15", "M5"]:
            df = candles.get(tf)
            if df is None or df.empty:
                continue
            pools = map_liquidity_pools(df, price, tf)
            all_bsl.extend(pools["bsl_pools"])
            all_ssl.extend(pools["ssl_pools"])

        bsl_pools = self._deduplicate(all_bsl)
        ssl_pools = self._deduplicate(all_ssl)

        unswept_bsl = [p for p in bsl_pools if not p["swept"] and p["level"] > price]
        unswept_ssl = [p for p in ssl_pools if not p["swept"] and p["level"] < price]
        nearest_bsl = min(unswept_bsl, key=lambda p: abs(p["level"] - price)) if unswept_bsl else None
        nearest_ssl = min(unswept_ssl, key=lambda p: abs(p["level"] - price)) if unswept_ssl else None

        if self.asia_range is None:
            h1 = candles.get("H1")
            if h1 is not None:
                self.asia_range = check_asia_range(h1)

        asia = self.asia_range or {"high": 0, "low": 0, "mid": 0, "high_swept": False, "low_swept": False}
        if asia["high"] > 0:
            asia["high_swept"] = price > asia["high"]
            asia["low_swept"] = price < asia["low"]

        # 2. Build Context for LLM
        htf_bias = ""
        # Accessing nested structures differently depending on if it's Pydantic or dict
        struct = self.state.get("structure")
        if isinstance(struct, dict):
            htf_bias = struct.get("bias", {}).get("H4", "NEUTRAL")
        elif struct:
            htf_bias = struct.bias.get("H4", "NEUTRAL")

        context = {
            "current_price": price,
            "htf_bias": htf_bias,
            "asia_range": asia,
            "algorithmic_bsl_pools": bsl_pools[:10],
            "algorithmic_ssl_pools": ssl_pools[:10],
            "nearest_unswept_bsl": nearest_bsl,
            "nearest_unswept_ssl": nearest_ssl
        }

        # 3. Ask Gemini for final mapping
        try:
            result = query_llm_structured(
                system_prompt=PROMPT,
                user_content=f"Context from programmatic indicators:\n{safe_json_dumps(context)}\n\nPlease finalize the LiquidityOutput.",
                output_schema=LiquidityOutput
            )
            
            output = result.model_dump()
            self.state["liquidity"] = output
            
            dol_dir = output.get('draw_on_liquidity', {}).get('direction', 'N/A')
            log.info(f"Liquidity mapped — BSL: {len(output.get('bsl_pools', []))} | SSL: {len(output.get('ssl_pools', []))} | DOL: {dol_dir}")
            return output
            
        except Exception as e:
            log.error(f"LLM Liquidity parsing failed: {e}")
            return self._fallback_algorithmic(asia, bsl_pools, ssl_pools, nearest_bsl, nearest_ssl, htf_bias, price)

    def lock_asia_range(self):
        """Lock Asia range at 09:00 EAT."""
        data = self.state.get("data", {})
        h1 = data.get("candles", {}).get("H1")
        if h1 is not None:
            self.asia_range = check_asia_range(h1)
            log.info(f"Asia range locked — H: {self.asia_range['high']} L: {self.asia_range['low']}")

    def _deduplicate(self, pools: list, tolerance: float = 3.0) -> list:
        if not pools:
            return []
        pools = sorted(pools, key=lambda p: p["level"])
        deduped = [pools[0]]
        for p in pools[1:]:
            if abs(p["level"] - deduped[-1]["level"]) > tolerance:
                deduped.append(p)
            else:
                if p["touches"] > deduped[-1]["touches"]:
                    deduped[-1] = p
        return deduped

    def _fallback_algorithmic(self, asia, bsl_pools, ssl_pools, nearest_bsl, nearest_ssl, htf_bias, price):
        dol = self._calc_draw_on_liquidity(htf_bias, [p for p in bsl_pools if not p["swept"] and p["level"] > price], [p for p in ssl_pools if not p["swept"] and p["level"] < price], price)
        manip = self._detect_manipulation(asia, price)

        output = {
            "asia_range": asia,
            "bsl_pools": bsl_pools[:10],
            "ssl_pools": ssl_pools[:10],
            "nearest_bsl": {"level": nearest_bsl["level"], "distance": round(abs(nearest_bsl["level"] - price), 2)} if nearest_bsl else None,
            "nearest_ssl": {"level": nearest_ssl["level"], "distance": round(abs(nearest_ssl["level"] - price), 2)} if nearest_ssl else None,
            "draw_on_liquidity": dol,
            "manipulation_detected": manip["detected"],
            "manipulation_direction": manip["direction"],
        }
        self.state["liquidity"] = output
        return output
        
    def _calc_draw_on_liquidity(self, bias, unswept_bsl, unswept_ssl, price):
        if bias == "BULLISH" and unswept_bsl:
            target = max(unswept_bsl, key=lambda p: p.get("touches", 1))
            return {"direction": "UP", "target": target["level"], "confidence": min(target.get("touches", 1) * 25, 100)}
        elif bias == "BEARISH" and unswept_ssl:
            target = max(unswept_ssl, key=lambda p: p.get("touches", 1))
            return {"direction": "DOWN", "target": target["level"], "confidence": min(target.get("touches", 1) * 25, 100)}
        return {"direction": "NONE", "target": 0, "confidence": 0}

    def _detect_manipulation(self, asia, price):
        if asia["high"] == 0:
            return {"detected": False, "direction": "NONE"}
        if asia["high_swept"] and not asia["low_swept"]:
            return {"detected": True, "direction": "DOWN"}
        elif asia["low_swept"] and not asia["high_swept"]:
            return {"detected": True, "direction": "UP"}
        return {"detected": False, "direction": "NONE"}
