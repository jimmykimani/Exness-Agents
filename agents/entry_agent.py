"""
EntryAgent — Final entry decision and exact order parameters.
Calculates lot size and produces the final trade payload.
"""
from skills.execution_skill import calculate_lot_size
from utils.logger import get_agent_logger

log = get_agent_logger("ENTRY_AGENT")


class EntryAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state

    def run(self) -> dict:
        bias_out = self.state.get("bias_output", {})
        ote = self.state.get("ote", {})
        risk = self.state.get("risk", {})
        data = self.state.get("data", {})
        price = data.get("current_price", {}).get("mid", 0)

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

        lot = 0.01
        risk_dollars = 0.0

        # Check if entry is allowed
        if bias_out.get("entry_allowed", False) and ote.get("valid", False) and entry > 0 and sl > 0:
            execute = True
            reason = " | ".join(bias_out.get("reasons", ["All conditions met"]))

            # Calculate precise lot size based on account balance and risk limit
            balance = risk.get("account_balance", 192.0)
            sl_points = abs(entry - sl)
            lot = calculate_lot_size(balance, sl_points)
            
            # Gold: $10 per point per 1.0 lot
            risk_dollars = lot * 10.0 * sl_points

        # Determine order type (LIMIT vs MARKET)
        # If price is within 2 points of entry, use MARKET, otherwise LIMIT
        order_type = "LIMIT"
        if execute and price > 0 and abs(price - entry) <= 2.0:
            order_type = "MARKET"

        from utils.session_clock import time_str_eat
        
        output = {
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
            "expiry": "18:25" if session == "LONDON" else "23:55", # EAT EOD
            "time": time_str_eat()
        }

        self.state["trade_params"] = output
        log.info(
            f"Entry params — Exec: {execute} | Dir: {direction} | "
            f"Entry: {entry} | SL: {sl} | Lot: {lot}"
        )
        return output
