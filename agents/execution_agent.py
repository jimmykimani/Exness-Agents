"""
ExecutionAgent — MT5 order placement.
"""
from typing import Optional
from data.mt5_connector import get_mt5
from skills.execution_skill import build_order_request
from config.settings import AUTO_EXECUTE
from utils.logger import get_agent_logger

log = get_agent_logger("EXECUTION_AGENT")


class ExecutionAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state
        self.mt5 = get_mt5()

    def run(self) -> dict:
        params = self.state.get("trade_params", {})
        execute = params.get("execute", False)
        
        if not execute:
            log.debug("Execution not requested")
            return {"executed": False}
            
        if not AUTO_EXECUTE:
            log.info("AUTO_EXECUTE is false — alert generated but order not placed")
            return {"executed": False, "simulated": True, "reason": "Auto-execution disabled"}

        # Build request
        req = build_order_request(
            direction=params["direction"],
            entry=params["entry"],
            sl=params["sl"],
            tp=params["tp3"], # Order placed with final TP
            lot=params["lot"],
            order_type=params["order_type"]
        )

        log.info(f"Sending order to MT5: {req['type']} {req['volume']} @ {req['price']}")
        result = self.mt5.send_order(req)
        
        self.state["execution_result"] = result
        
        if result and result.get("status") == "FILLED":
            log.info(f"Order FILLED — ID: {result.get('order_id')}")
        else:
            log.error(f"Order FAILED — {result.get('error')}")

        return result
