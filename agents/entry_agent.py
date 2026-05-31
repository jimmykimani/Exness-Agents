"""
EntryAgent — Final entry decision and exact order parameters.
Calculates lot size and produces the final trade payload using Gemini.
"""
from typing import Dict, Any
import json
from skills.execution_skill import calculate_lot_size
from utils.logger import get_agent_logger
from agents.llm_utils import query_llm_structured, safe_json_dumps
from agents.state import EntryOutput

log = get_agent_logger("ENTRY_AGENT")

PROMPT = """
NAME: EntryAgent
ROLE: Setup confirmation and order parameter generation

YOU ARE:
The execution sniper. You confirm setups, calculate final risk parameters, and generate the final order payload.

YOUR JOB:
→ Verify that a setup is valid and entry is allowed by BiasAgent.
→ Generate precise order parameters: entry price, SL, TP1, TP2, TP3.
→ Verify lot size and risk in dollars.
→ Determine order type (LIMIT vs MARKET).
→ Generate invalidation levels and expiration time.

Output must strictly follow the Pydantic schema provided.
"""

class EntryAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state

    def run(self) -> Dict[str, Any]:
        bias_out = self.state.get("bias_output", {})
        ote = self.state.get("ote", {})
        risk = self.state.get("risk", {})
        data = self.state.get("data", {})
        price = data.get("current_price", {}).get("mid", 0)
        session = self.state.get("session", {}).get("session", "LONDON")

        # Base decision
        execute = False
        reason = bias_out.get("wait_reason", "No setup")
        direction = bias_out.get("direction", "WAIT")

        entry = ote.get("entry", 0)
        sl = ote.get("sl", 0)
        tp1 = ote.get("tp1", 0)
        tp2 = ote.get("tp2", 0)
        tp3 = ote.get("tp3", 0)
        rr_tp1 = ote.get("rr_tp1", 0)
        rr_tp2 = ote.get("rr_tp2", 0)

        lot = 0.02
        risk_dollars = 0.0

        # Check if entry is allowed programmatically first to provide as context
        if bias_out.get("entry_allowed", False) and ote.get("valid", False) and entry > 0 and sl > 0:
            execute = True
            reason = " | ".join(bias_out.get("reasons", ["All conditions met"]))
            balance = risk.get("account_balance", 192.0)
            sl_points = abs(entry - sl)
            lot = calculate_lot_size(balance, sl_points)
            risk_dollars = lot * 10.0 * sl_points
        
        # AGGRESSIVE MODE: also execute if bias has a direction (not WAIT)
        # even without OTE validation — trust the bias + structure confluence
        if not execute and bias_out.get("entry_allowed", False) and direction in ("LONG", "SHORT", "BUY", "SELL"):
            grade = bias_out.get("grade", "C")
            if grade in ("A+", "A", "B"):
                execute = True
                reason = f"Aggressive mode — {grade} setup | " + " | ".join(bias_out.get("reasons", ["Bias aligned"]))
                balance = risk.get("account_balance", 192.0)
                # Use data price as entry if OTE didn't provide one
                if entry <= 0:
                    entry = price
                if sl <= 0:
                    # Emergency SL: 15 points from entry
                    sl = entry - 15.0 if direction in ("LONG", "BUY") else entry + 15.0
                if tp1 <= 0:
                    delta = abs(entry - sl)
                    if direction in ("LONG", "BUY"):
                        tp1 = round(entry + delta * 2, 2)
                        tp2 = round(entry + delta * 3, 2)
                        tp3 = round(entry + delta * 4, 2)
                    else:
                        tp1 = round(entry - delta * 2, 2)
                        tp2 = round(entry - delta * 3, 2)
                        tp3 = round(entry - delta * 4, 2)
                sl_points = abs(entry - sl)
                lot = calculate_lot_size(balance, sl_points)
                risk_dollars = lot * 10.0 * sl_points

        order_type = "LIMIT"
        if execute and price > 0 and abs(price - entry) <= 2.0:
            order_type = "MARKET"

        expiry = "18:25" if session == "LONDON" else "23:55"

        context = {
            "current_price": price,
            "session": session,
            "bias_output": bias_out,
            "ote": ote,
            "programmatic_calculation": {
                "execute": execute,
                "direction": direction,
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp1": round(tp1, 2),
                "tp2": round(tp2, 2),
                "tp3": round(tp3, 2),
                "lot": lot,
                "risk_dollars": round(risk_dollars, 2),
                "rr_tp1": rr_tp1,
                "rr_tp2": rr_tp2,
                "grade": bias_out.get("grade", "C"),
                "reason": reason,
                "invalidation": bias_out.get("invalidation", ""),
                "order_type": order_type,
                "expiry": expiry
            }
        }

        try:
            result = query_llm_structured(
                system_prompt=PROMPT,
                user_content=f"Context from programmatic calculation:\n{safe_json_dumps(context)}\n\nPlease finalize the EntryOutput.",
                output_schema=EntryOutput
            )
            output = result.model_dump()
            self.state["trade_params"] = output
            log.info(
                f"Entry params — Exec: {output['execute']} | Dir: {output['direction']} | "
                f"Entry: {output['entry']} | SL: {output['sl']} | Lot: {output['lot']}"
            )
            return output

        except Exception as e:
            log.error(f"LLM Entry parsing failed: {e}")
            fallback = context["programmatic_calculation"]
            self.state["trade_params"] = fallback
            return fallback

