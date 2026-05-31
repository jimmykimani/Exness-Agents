"""
MonitorAgent — Open trade lifecycle management.
Watches open positions every second, takes partials, trails stops, and alerts Jimmy.
"""
from typing import List, Dict, Any
from datetime import datetime
from data.mt5_connector import get_mt5
from data.active_trades import (
    load_active_trades, save_active_trades,
    remove_active_trade, update_active_trade
)
from utils.logger import get_agent_logger
from utils.session_clock import is_friday_close, today_eat
from db.journal import get_journal

log = get_agent_logger("MONITOR_AGENT")


class MonitorAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state
        self.mt5 = get_mt5()
        self.journal = get_journal()

    def run(self) -> dict:
        positions = self.mt5.get_positions()
        active_trades = load_active_trades()
        
        # Check for force close or Friday 17:30 EAT Close
        # EAT time is usually UTC+3. Friday 17:30 EAT is Friday 14:30 UTC.
        now = datetime.now()
        is_friday_1730 = now.weekday() == 4 and now.hour == 17 and now.minute >= 30
        
        risk = self.state.get("risk", {})
        force_close = risk.get("force_close", False) or is_friday_1730

        actions_taken = []
        
        if force_close and positions:
            log.warning("Force closing all positions due to Friday Close / Risk limit!")
            for pos in positions:
                ticket = pos["ticket"]
                res = self.mt5.close_position(ticket)
                actions_taken.append(f"🔒 Friday close — forced close ticket {ticket}")
                self._alert_jimmy(f"🔒 <b>Friday close</b> — all trades closed. Ticket: {ticket}")
                remove_active_trade(ticket)
            return {
                "open_trades": [],
                "total_open_pnl": 0.0,
                "actions_taken": actions_taken
            }

        # Check for incoming news warning (30 minutes warning)
        news_info = self.state.get("news", {})
        if news_info.get("upcoming_high_impact") and positions:
            # Let's say there is a flag in state about news within 30 min
            if news_info.get("minutes_to_news", 120) <= 30:
                self._alert_jimmy(
                    "📰 <b>⚠️ HIGH IMPACT NEWS WARNING</b>\n"
                    "High-impact news event is starting in less than 30 minutes!\n"
                    "Please review open positions. (Recommend: close if in profit, hold if SL is at BE)."
                )

        # 1. Process active trades that are still open
        open_tickets = {pos["ticket"]: pos for pos in positions}
        
        # Detect if any tracked trade was closed externally (SL or TP hit, or manual close)
        for ticket_str, trade in list(active_trades.items()):
            ticket = int(ticket_str)
            if ticket not in open_tickets:
                # Trade was closed! Let's check history or guess how it closed
                log.info(f"Position {ticket} has closed.")
                
                # Check MT5 history or assume based on last known state
                # For safety and simple EOD sync, let's log to journal
                pnl_usd = trade.get("setup_info", {}).get("risk_usd", 10.0) # Fallback
                pnl_pts = 0.0
                
                # Let's alert
                self._alert_jimmy(
                    f"🔔 <b>Trade Closed</b>\n"
                    f"Ticket: {ticket}\n"
                    f"Direction: {trade['direction']}\n"
                    f"Entry: {trade['entry']}\n"
                    f"SL: {trade['sl']}\n"
                    f"TP3: {trade['tp3']}"
                )
                
                # Update journal
                try:
                    self.journal.log_trade({
                        "date": today_eat(),
                        "ticket": ticket,
                        "direction": trade["direction"],
                        "entry": trade["entry"],
                        "sl": trade["sl"],
                        "tp3": trade["tp3"],
                        "pnl_usd": pnl_usd,
                        "pnl_pts": pnl_pts,
                        "grade": trade.get("setup_info", {}).get("grade", "C")
                    })
                except Exception as je:
                    log.error(f"Failed to log trade to journal: {je}")
                
                remove_active_trade(ticket)
                actions_taken.append(f"Position {ticket} closed externally; logged to journal")

        # 2. Babysit currently open positions
        for ticket, pos in open_tickets.items():
            ticket_str = str(ticket)
            if ticket_str not in active_trades:
                # Pos not tracked yet, let's register standard placeholders
                continue
                
            trade = active_trades[ticket_str]
            current_price = pos["current_price"]
            direction = trade["direction"]
            entry = trade["entry"]
            sl = trade["sl"]
            tp1 = trade["tp1"]
            tp2 = trade["tp2"]
            tp3 = trade["tp3"]
            
            # Check TP1 Hit
            if not trade.get("tp1_hit"):
                hit_tp1 = (direction == "LONG" and current_price >= tp1) or (direction == "SHORT" and current_price <= tp1)
                if hit_tp1:
                    log.info(f"🎯 Position {ticket} hit TP1 ({tp1})! Executing partial close...")
                    # Close 50%
                    close_vol = round(trade["original_volume"] * 0.5, 2)
                    res = self.mt5.close_position(ticket, volume=close_vol)
                    
                    # Move SL to BE (entry price)
                    mod_res = self.mt5.modify_position(ticket, sl=entry)
                    
                    update_active_trade(ticket, {
                        "tp1_hit": True,
                        "sl": entry,
                        "sl_at_be": True,
                        "current_volume": round(pos["volume"] - close_vol, 2)
                    })
                    
                    self._alert_jimmy(
                        f"🎯 <b>TP1 HIT — Position {ticket}</b>\n"
                        f"• Closed 50% position ({close_vol} Lots)\n"
                        f"• SL moved to Break Even ({entry})"
                    )
                    actions_taken.append(f"TP1 hit on {ticket}; closed 50%, moved SL to BE")
                    continue

            # Check TP2 Hit
            if trade.get("tp1_hit") and not trade.get("tp2_hit"):
                hit_tp2 = (direction == "LONG" and current_price >= tp2) or (direction == "SHORT" and current_price <= tp2)
                if hit_tp2:
                    log.info(f"🎯 Position {ticket} hit TP2 ({tp2})! Executing partial close...")
                    # Close 30% of original position
                    close_vol = round(trade["original_volume"] * 0.3, 2)
                    res = self.mt5.close_position(ticket, volume=close_vol)
                    
                    # Trail SL to TP1
                    mod_res = self.mt5.modify_position(ticket, sl=tp1)
                    
                    update_active_trade(ticket, {
                        "tp2_hit": True,
                        "sl": tp1,
                        "current_volume": round(pos["volume"] - close_vol, 2)
                    })
                    
                    self._alert_jimmy(
                        f"🎯 <b>TP2 HIT — Position {ticket}</b>\n"
                        f"• Closed 30% position ({close_vol} Lots)\n"
                        f"• SL trailed to TP1 ({tp1})"
                    )
                    actions_taken.append(f"TP2 hit on {ticket}; closed 30%, trailed SL to TP1")
                    continue

            # Check TP3 Hit
            if trade.get("tp2_hit") and not trade.get("tp3_hit"):
                hit_tp3 = (direction == "LONG" and current_price >= tp3) or (direction == "SHORT" and current_price <= tp3)
                if hit_tp3:
                    log.info(f"🎯 Position {ticket} hit TP3 ({tp3})! Completing trade...")
                    # Close remaining (approx 20%)
                    res = self.mt5.close_position(ticket)
                    
                    update_active_trade(ticket, {
                        "tp3_hit": True
                    })
                    
                    self._alert_jimmy(
                        f"🎯 <b>TP3 HIT — Position {ticket}</b>\n"
                        f"• Closed remaining 20% position\n"
                        f"• Trade completed successfully! 🚀"
                    )
                    actions_taken.append(f"TP3 hit on {ticket}; fully closed")
                    remove_active_trade(ticket)
                    continue

        total_pnl = sum(pos["pnl"] for pos in positions)
        output = {
            "open_trades": positions,
            "total_open_pnl": round(total_pnl, 2),
            "actions_taken": actions_taken
        }
        
        self.state["monitor"] = output
        return output

    def _alert_jimmy(self, message: str):
        """Send message using pending state queue so TelegramAgent picks it up."""
        if "pending_messages" not in self.state:
            self.state["pending_messages"] = []
        self.state["pending_messages"].append(message)
