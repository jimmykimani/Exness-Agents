"""
ExecutionAgent — MT5 order placement.
Auto-executes trades and alerts Jimmy via Telegram.
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
            # Still send a Telegram alert so Jimmy can approve manually
            self._alert(
                f"🎯 <b>SETUP FOUND (Manual Mode)</b>\n\n"
                f"Direction: {params.get('direction')}\n"
                f"Entry: {params.get('entry')}\n"
                f"SL: {params.get('sl')}\n"
                f"Grade: {params.get('grade', 'B')}\n\n"
                f"<i>AUTO_EXECUTE is off. Approve via Telegram.</i>"
            )
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
            
            # Alert Jimmy about the executed trade
            self._alert(
                f"🚀 <b>TRADE EXECUTED</b>\n\n"
                f"🎫 Ticket: <code>{result.get('order_id')}</code>\n"
                f"Direction: {params['direction']}\n"
                f"Entry: {result.get('fill_price', params['entry'])}\n"
                f"SL: {params['sl']}\n"
                f"TP1: {params.get('tp1')}\n"
                f"TP2: {params.get('tp2')}\n"
                f"TP3: {params.get('tp3')}\n"
                f"Lot: {params['lot']}\n"
                f"Grade: {params.get('grade', 'B')}\n"
                f"Reason: {params.get('reason', 'SMC alignment')}"
            )
            
            try:
                from data.active_trades import add_active_trade
                tp1 = params.get("tp1") or (params["entry"] + (params["tp3"] - params["entry"]) * 0.33)
                tp2 = params.get("tp2") or (params["entry"] + (params["tp3"] - params["entry"]) * 0.66)
                tp3 = params["tp3"]
                
                add_active_trade(
                    ticket=result["order_id"],
                    direction=params["direction"],
                    entry=result.get("fill_price") or params["entry"],
                    sl=params["sl"],
                    tp1=round(tp1, 2),
                    tp2=round(tp2, 2),
                    tp3=round(tp3, 2),
                    volume=params["lot"],
                    setup_info=params
                )
                log.info(f"Position {result['order_id']} successfully registered in active trades tracking.")
            except Exception as ex:
                log.error(f"Failed to register position in active trades: {ex}")
        else:
            error_msg = result.get('error', 'Unknown') if result else 'No response'
            log.error(f"Order FAILED — {error_msg}")
            self._alert(
                f"❌ <b>ORDER FAILED</b>\n\n"
                f"Direction: {params['direction']}\n"
                f"Entry: {params['entry']}\n"
                f"Error: {error_msg}"
            )

        return result

    def _alert(self, message: str):
        """Queue a Telegram message."""
        if "pending_messages" not in self.state:
            self.state["pending_messages"] = []
        self.state["pending_messages"].append(message)

