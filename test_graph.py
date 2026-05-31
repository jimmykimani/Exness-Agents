"""
Quick test: verify all imports resolve, graph compiles, and run one cycle.
"""
import sys
import traceback

print("[1/4] Importing modules...")
try:
    from agents.orchestrator import OrchestratorAgent
    print("  OK - OrchestratorAgent imported")
except Exception as e:
    print(f"  FAIL - {e}")
    traceback.print_exc()
    sys.exit(1)

print("[2/4] Instantiating OrchestratorAgent (builds graph)...")
try:
    orch = OrchestratorAgent()
    print("  OK - OrchestratorAgent created, graph compiled")
except Exception as e:
    print(f"  FAIL - {e}")
    traceback.print_exc()
    sys.exit(1)

print("[3/4] Checking graph nodes and edges...")
try:
    graph = orch.graph
    print(f"  Nodes: {list(graph.nodes.keys()) if hasattr(graph, 'nodes') else 'N/A'}")
    print("  OK - Graph structure looks good")
except Exception as e:
    print(f"  FAIL - {e}")
    traceback.print_exc()

print("[4/4] Running one analysis cycle...")
try:
    result = orch.run_cycle()
    print("  OK - Cycle completed!")
    print(f"  Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
    
    # Show key outputs
    if isinstance(result, dict):
        session = result.get("session", {})
        print(f"  Session: {session.get('session', 'N/A')}")
        print(f"  Tradeable: {session.get('tradeable', 'N/A')}")
        
        data = result.get("data", {})
        if data:
            print(f"  Price: {data.get('current_price', {}).get('mid', 'N/A')}")
            print(f"  Connection OK: {data.get('connection_ok', 'N/A')}")
            print(f"  Spread OK: {data.get('spread_ok', 'N/A')}")
        
        bias = result.get("bias_output")
        if bias:
            if isinstance(bias, dict):
                print(f"  Bias: {bias.get('bias', 'N/A')} | Grade: {bias.get('grade', 'N/A')}")
            else:
                print(f"  Bias: {bias.bias} | Grade: {bias.grade}")
        
        trade = result.get("trade_params")
        if trade:
            if isinstance(trade, dict):
                print(f"  Execute: {trade.get('execute', False)}")
            else:
                print(f"  Execute: {trade.execute}")
                
except Exception as e:
    print(f"  FAIL - {e}")
    traceback.print_exc()

print("\nDone.")
