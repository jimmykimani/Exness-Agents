"""
OrchestratorAgent — Master controller using LangGraph.
"""
from typing import Dict, Any, TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

from utils.logger import get_agent_logger
from utils.session_clock import get_current_session, is_session_tradeable

# Import all agents
from agents.data_agent import DataAgent
from agents.structure_agent import StructureAgent
from agents.liquidity_agent import LiquidityAgent
from agents.orderblock_agent import OrderBlockAgent
from agents.ote_agent import OTEAgent
from agents.bias_agent import BiasAgent
from agents.entry_agent import EntryAgent
from agents.risk_agent import RiskAgent
from agents.execution_agent import ExecutionAgent
from agents.monitor_agent import MonitorAgent
from agents.news_agent import NewsAgent

log = get_agent_logger("ORCHESTRATOR")


# Define the shared state type
class State(TypedDict):
    data: Dict[str, Any]
    structure: Dict[str, Any]
    liquidity: Dict[str, Any]
    orderblock: Dict[str, Any]
    ote: Dict[str, Any]
    bias_output: Dict[str, Any]
    trade_params: Dict[str, Any]
    risk: Dict[str, Any]
    session: Dict[str, Any]
    news: Dict[str, Any]
    execution_result: Dict[str, Any]
    monitor: Dict[str, Any]
    pending_messages: list
    errors: list


class OrchestratorAgent:
    def __init__(self):
        self.state = {
            "data": {}, "structure": {}, "liquidity": {}, "orderblock": {},
            "ote": {}, "bias_output": {}, "trade_params": {}, "risk": {},
            "session": {}, "news": {}, "execution_result": {}, "monitor": {},
            "pending_messages": [], "errors": []
        }
        
        # Initialize agents
        self.data_agent = DataAgent(self.state)
        self.structure_agent = StructureAgent(self.state)
        self.liquidity_agent = LiquidityAgent(self.state)
        self.ob_agent = OrderBlockAgent(self.state)
        self.ote_agent = OTEAgent(self.state)
        self.bias_agent = BiasAgent(self.state)
        self.entry_agent = EntryAgent(self.state)
        self.risk_agent = RiskAgent(self.state)
        self.execution_agent = ExecutionAgent(self.state)
        self.monitor_agent = MonitorAgent(self.state)
        self.news_agent = NewsAgent(self.state)

    def run_cycle(self):
        """Run one complete 5-minute analysis cycle."""
        log.info("=== STARTING ANALYSIS CYCLE ===")
        
        # 1. Update session
        session_name = get_current_session()
        self.state["session"] = {
            "session": session_name,
            "tradeable": is_session_tradeable()
        }
        
        # 2. Pre-checks (News & Risk)
        self.news_agent.run()
        self.risk_agent.run()
        
        if not self.state["session"]["tradeable"]:
            log.info("Outside tradeable session. Stopping cycle.")
            return
            
        if self.state["news"].get("block_trading"):
            log.info("News block active. Stopping cycle.")
            return
            
        if not self.state["risk"].get("trading_allowed"):
            log.info("Risk limit reached. Stopping cycle.")
            return

        # 3. Data pipeline
        data_ok = self.data_agent.run()
        if not data_ok.get("connection_ok") or not data_ok.get("spread_ok"):
            log.warning("Data not OK (Connection/Spread). Stopping cycle.")
            return

        # 4. Analysis pipeline
        self.structure_agent.run()
        self.liquidity_agent.run()
        self.ote_agent.run()
        self.ob_agent.run()
        
        # 5. Bias & Decision
        self.bias_agent.run()
        self.entry_agent.run()
        
        # 6. Execution (if applicable)
        params = self.state.get("trade_params", {})
        if params.get("execute"):
            log.info("🔥 Valid setup found! Routing to execution...")
            self.execution_agent.run()
            
            # Format alert for Telegram
            grade = params.get("grade")
            d = params.get("direction")
            msg = f"🎯 SETUP {grade} - {d}\nEntry: {params['entry']}\nSL: {params['sl']}\nTP1: {params['tp1']}\nReason: {params['reason']}"
            self.state["pending_messages"].append(msg)
            
        # 7. Post-execution Monitor
        self.monitor_agent.run()
        
        log.info("=== CYCLE COMPLETE ===")
