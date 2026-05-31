"""
Active Trades Persistence — Handles saving and loading trade targets.
Falls back to local active_trades.json storage to preserve state across restarts.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional

ACTIVE_TRADES_PATH = Path("data/active_trades.json")

def load_active_trades() -> Dict[str, Dict[str, Any]]:
    """Load active trades from active_trades.json."""
    if not ACTIVE_TRADES_PATH.exists():
        return {}
    try:
        return json.loads(ACTIVE_TRADES_PATH.read_text())
    except Exception:
        return {}

def save_active_trades(trades: Dict[str, Dict[str, Any]]):
    """Save active trades to active_trades.json."""
    ACTIVE_TRADES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_TRADES_PATH.write_text(json.dumps(trades, indent=2))

def add_active_trade(
    ticket: int,
    direction: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    tp3: float,
    volume: float,
    setup_info: Optional[Dict[str, Any]] = None
):
    """Register an open position ticket with its targets."""
    trades = load_active_trades()
    trades[str(ticket)] = {
        "ticket": ticket,
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "original_volume": volume,
        "current_volume": volume,
        "tp1_hit": False,
        "tp2_hit": False,
        "tp3_hit": False,
        "sl_at_be": False,
        "setup_info": setup_info or {}
    }
    save_active_trades(trades)

def remove_active_trade(ticket: int):
    """Remove a ticket from tracking once closed."""
    trades = load_active_trades()
    ticket_str = str(ticket)
    if ticket_str in trades:
        del trades[ticket_str]
        save_active_trades(trades)

def update_active_trade(ticket: int, updates: Dict[str, Any]):
    """Update tracking info/flags for a specific ticket."""
    trades = load_active_trades()
    ticket_str = str(ticket)
    if ticket_str in trades:
        trades[ticket_str].update(updates)
        save_active_trades(trades)
