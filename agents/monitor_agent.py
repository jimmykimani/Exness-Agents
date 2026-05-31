"""
MonitorAgent — Open trade lifecycle management.
Moves SL, takes partials.
"""
from typing import List
from data.mt5_connector import get_mt5
from config.trading_rules import TP1_CLOSE_PCT, TP2_CLOSE_PCT
from utils.logger import get_agent_logger
from utils.session_clock import is_friday_close

log = get_agent_logger("MONITOR_AGENT")


class MonitorAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state
        self.mt5 = get_mt5()
        # In a real app we'd track original lot size and tp levels in DB
        # For simplicity we assume state holds the trade params or we read from comment
        self.tracked_trades = {} 

    def run(self) -> dict:
        positions = self.mt5.get_positions()
        
        risk = self.state.get("risk", {})
        force_close = risk.get("force_close", False) or is_friday_close()

        total_pnl = sum(p["pnl"] for p in positions)
        actions_taken = []

        for pos in positions:
            ticket = pos["ticket"]
            
            if force_close:
                res = self.mt5.close_position(ticket)
                actions_taken.append(f"Force closed {ticket}")
                log.info(f"Force closing position {ticket}: {res}")
                continue

            # This is a simplified partials logic.
            # In a full production system, you'd load the original trade_params
            # from the database or the agent state to know exact TP1/TP2 levels.
            # For this MVP, we log the positions and rely on the ExecutionAgent's TP.

        output = {
            "open_trades": positions,
            "total_open_pnl": round(total_pnl, 2),
            "actions_taken": actions_taken
        }
        
        self.state["monitor"] = output
        if positions:
            log.info(f"Monitoring {len(positions)} trades | Total PnL: ${total_pnl:.2f}")
            
        return output
