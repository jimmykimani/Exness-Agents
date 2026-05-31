"""
OrchestratorAgent — Master controller using LangGraph.
"""
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from utils.logger import get_agent_logger
from utils.session_clock import get_current_session, is_session_tradeable
from agents.state import TradingState

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
from agents.telegram_agent import TelegramAgent
from agents.journal_agent import JournalAgent

log = get_agent_logger("ORCHESTRATOR")

class OrchestratorAgent:
    def __init__(self):
        # We initialize the agents. For LangGraph, we'll wrap their run methods.
        self.state = {
            "data": {}, "structure": None, "liquidity": None, "orderblock": None,
            "ote": None, "bias_output": None, "trade_params": None, "risk": {},
            "session": {}, "news": {}, "execution_result": {}, "monitor": {},
            "pending_messages": [], "errors": []
        }
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
        
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(TradingState)
        
        # Add nodes
        workflow.add_node("pre_checks", self._node_pre_checks)
        workflow.add_node("data", self._node_data)
        workflow.add_node("analysis", self._node_analysis)
        workflow.add_node("decision", self._node_decision)
        workflow.add_node("execution", self._node_execution)
        workflow.add_node("monitor", self._node_monitor)
        
        # Add edges
        workflow.add_edge(START, "pre_checks")
        
        # Conditional routing after pre_checks
        workflow.add_conditional_edges(
            "pre_checks",
            self._route_pre_checks,
            {
                "continue": "data",
                "stop": END
            }
        )
        
        # Conditional routing after data
        workflow.add_conditional_edges(
            "data",
            self._route_data,
            {
                "continue": "analysis",
                "stop": END
            }
        )
        
        workflow.add_edge("analysis", "decision")
        
        # Conditional routing after decision
        workflow.add_conditional_edges(
            "decision",
            self._route_decision,
            {
                "execute": "execution",
                "monitor_only": "monitor"
            }
        )
        
        workflow.add_edge("execution", "monitor")
        workflow.add_edge("monitor", END)
        
        # Compile
        return workflow.compile()

    # ─── Node Wrappers ──────────────────────────────────────────

    def _node_pre_checks(self, state: TradingState) -> Dict[str, Any]:
        """Runs news and risk checks."""
        # Setup temporary state for old agent compatibility
        self.news_agent.state = dict(state)
        self.risk_agent.state = dict(state)
        
        self.news_agent.run()
        self.risk_agent.run()
        
        return {
            "news": self.news_agent.state.get("news", {}),
            "risk": self.risk_agent.state.get("risk", {}),
            "session": {
                "session": get_current_session(),
                "tradeable": is_session_tradeable()
            }
        }

    def _route_pre_checks(self, state: TradingState) -> str:
        if not state.get("session", {}).get("tradeable"):
            log.info("Outside tradeable session. Stopping cycle.")
            return "stop"
        if state.get("news", {}).get("block_trading"):
            log.info("News block active. Stopping cycle.")
            return "stop"
        if not state.get("risk", {}).get("trading_allowed", True):
            log.info("Risk limit reached. Stopping cycle.")
            return "stop"
        return "continue"

    def _node_data(self, state: TradingState) -> Dict[str, Any]:
        self.data_agent.state = dict(state)
        data_out = self.data_agent.run()
        return {"data": data_out}

    def _route_data(self, state: TradingState) -> str:
        data_ok = state.get("data", {})
        if not data_ok.get("connection_ok") or not data_ok.get("spread_ok"):
            log.warning("Data not OK (Connection/Spread). Stopping cycle.")
            return "stop"
        return "continue"

    def _node_analysis(self, state: TradingState) -> Dict[str, Any]:
        # Pass state down
        shared = dict(state)
        
        self.structure_agent.state = shared
        self.structure_agent.run()
        
        self.liquidity_agent.state = shared
        self.liquidity_agent.run()
        
        self.ob_agent.state = shared
        self.ob_agent.run()
        
        self.ote_agent.state = shared
        self.ote_agent.run()
        
        return {
            "structure": shared.get("structure"),
            "liquidity": shared.get("liquidity"),
            "ote": shared.get("ote"),
            "orderblock": shared.get("orderblock")
        }

    def _node_decision(self, state: TradingState) -> Dict[str, Any]:
        shared = dict(state)
        self.bias_agent.state = shared
        self.bias_agent.run()
        
        self.entry_agent.state = shared
        self.entry_agent.run()
        
        return {
            "bias_output": shared.get("bias_output"),
            "trade_params": shared.get("trade_params"),
            "pending_messages": shared.get("pending_messages", [])
        }

    def _route_decision(self, state: TradingState) -> str:
        params = state.get("trade_params", {})
        # Depending if it's a dict or Pydantic model
        execute = False
        if isinstance(params, dict):
            execute = params.get("execute", False)
        elif hasattr(params, "execute"):
            execute = params.execute
            
        if execute:
            log.info("🔥 Valid setup found! Routing to execution...")
            return "execute"
        return "monitor_only"

    def _node_execution(self, state: TradingState) -> Dict[str, Any]:
        shared = dict(state)
        self.execution_agent.state = shared
        self.execution_agent.run()
        
        # Format alert for Telegram
        params = state.get("trade_params", {})
        if isinstance(params, dict):
            grade = params.get("grade")
            d = params.get("direction")
            msg = f"🎯 SETUP {grade} - {d}\nEntry: {params.get('entry')}\nSL: {params.get('sl')}\nTP1: {params.get('tp1')}\nReason: {params.get('reason')}"
        else:
            msg = f"🎯 SETUP {params.grade} - {params.direction}\nEntry: {params.entry}\nSL: {params.sl}\nTP1: {params.tp1}\nReason: {params.reason}"
            
        msgs = state.get("pending_messages", [])
        msgs.append(msg)
        
        return {
            "execution_result": shared.get("execution_result"),
            "pending_messages": msgs
        }

    def _node_monitor(self, state: TradingState) -> Dict[str, Any]:
        shared = dict(state)
        self.monitor_agent.state = shared
        self.monitor_agent.run()
        return {"monitor": shared.get("monitor")}

    def run_cycle(self):
        """Run one complete 5-minute analysis cycle."""
        import os
        if os.getenv("BOT_RUNNING", "true").lower() != "true":
            log.info("BOT_RUNNING is false — skipping analysis cycle to save API quota.")
            return {"status": "paused"}
            
        log.info("=== STARTING ANALYSIS CYCLE ===")
        
        # Thread ID for memory
        config = {"configurable": {"thread_id": "goldbot_1"}}
        
        current_state = self.state
            
        # Ensure any pending messages queued externally (like startup message) are included
        if "pending_messages" in self.state and self.state["pending_messages"]:
            if "pending_messages" not in current_state:
                current_state["pending_messages"] = []
            current_state["pending_messages"].extend(self.state["pending_messages"])
            self.state["pending_messages"] = []
            
        # Execute the graph
        result = self.graph.invoke(current_state, config=config)
        
        # Sync back the state so other agents (like TelegramAgent) can access it
        self.state.update(result)
        
        log.info("=== CYCLE COMPLETE ===")
        return result
