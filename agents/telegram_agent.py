"""
TelegramAgent — Jimmy's communication interface.
Supports bidirectional communication, alerts, and inline callbacks.
"""
import urllib.request
import json
import os
import requests
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from data.mt5_connector import get_mt5
from db.journal import get_journal
from utils.logger import get_agent_logger
from utils.session_clock import today_eat

log = get_agent_logger("TELEGRAM_AGENT")

# Global variables to retain last setup and offset state
_LAST_SETUP = {}
_LAST_OFFSET = 0

class TelegramAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.mt5 = get_mt5()
        self.journal = get_journal()

    def run(self) -> dict:
        """Process outgoing queued messages and poll for incoming commands."""
        # 1. Send outgoing messages
        messages = self.state.get("pending_messages", [])
        sent = 0
        if messages:
            for msg in messages:
                try:
                    self.send_message(msg)
                    sent += 1
                except Exception as e:
                    log.error(f"Telegram outgoing error: {e}")
            self.state["pending_messages"] = []

        # 2. Check for incoming commands/callbacks from Jimmy
        try:
            self.poll_updates()
        except Exception as e:
            log.error(f"Telegram polling error: {e}")

        return {"sent": sent}

    def queue_message(self, text: str):
        if "pending_messages" not in self.state:
            self.state["pending_messages"] = []
        self.state["pending_messages"].append(text)

    def send_message(self, text: str, reply_markup: dict = None) -> bool:
        """Helper to send a message via requests."""
        if not self.bot_token or not self.chat_id:
            log.warning("Telegram Bot Token or Chat ID not configured.")
            return False
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            log.error(f"Failed to send Telegram message: {e}")
            return False

    def poll_updates(self):
        """Poll the getUpdates API to process commands and callbacks."""
        global _LAST_OFFSET
        if not self.bot_token:
            return
        
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        params = {"timeout": 1}
        if _LAST_OFFSET > 0:
            params["offset"] = _LAST_OFFSET
            
        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code != 200:
                return
            data = response.json()
            if not data.get("ok"):
                return
                
            updates = data.get("result", [])
            for update in updates:
                _LAST_OFFSET = update["update_id"] + 1
                
                # Check for Message Commands
                if "message" in update:
                    msg = update["message"]
                    chat_id = msg.get("chat", {}).get("id")
                    
                    # Security: Only respond to Jimmy's registered Chat ID
                    if str(chat_id) != str(self.chat_id):
                        log.warning(f"Unauthorized access attempt from Chat ID: {chat_id}")
                        continue
                        
                    text = msg.get("text", "").strip()
                    if text.startswith("/"):
                        log.info(f"Received command from Jimmy: {text}")
                        self.handle_command(text)
                        
                # Check for Callback Queries (Button Clicks)
                elif "callback_query" in update:
                    cb = update["callback_query"]
                    cb_id = cb.get("id")
                    chat_id = cb.get("message", {}).get("chat", {}).get("id")
                    
                    if str(chat_id) != str(self.chat_id):
                        continue
                        
                    data_val = cb.get("data")
                    log.info(f"Received callback click from Jimmy: {data_val}")
                    self.handle_callback(cb_id, cb.get("message", {}).get("message_id"), data_val)
                    
        except Exception as e:
            log.error(f"Error pulling updates: {e}")

    def handle_command(self, command: str):
        """Routes slash commands to appropriate handlers."""
        global _LAST_SETUP
        cmd = command.lower().split()[0]
        
        if cmd == "/status":
            positions = self.mt5.get_positions()
            if not positions:
                self.send_message("ℹ️ No open trades found currently.")
                return
            
            msg = "📊 <b>CURRENT POSITIONS</b>\n\n"
            for pos in positions:
                msg += (
                    f"🎫 <b>Ticket:</b> <code>{pos['ticket']}</code>\n"
                    f"• {pos['direction']} {pos['volume']} Lots @ {pos['entry']}\n"
                    f"• SL: {pos['sl']} | TP: {pos['tp']}\n"
                    f"• <b>PnL:</b> ${pos['pnl']:.2f}\n\n"
                )
            self.send_message(msg)

        elif cmd == "/levels":
            # Pull key structure levels from last node run
            struct = self.state.get("structure") or {}
            liqd = self.state.get("liquidity") or {}
            
            asia_high = liqd.get("asia_high", "N/A")
            asia_low = liqd.get("asia_low", "N/A")
            
            msg = (
                f"📍 <b>TODAY'S KEY LEVELS</b>\n\n"
                f"🟡 <b>Asia Range:</b> {asia_high} → {asia_low}\n"
                f"• H4 Swing High: {struct.get('swing_high', 'N/A')}\n"
                f"• H4 Swing Low: {struct.get('swing_low', 'N/A')}\n"
                f"• Premium Level: {struct.get('premium', 'N/A')}\n"
                f"• Discount Level: {struct.get('discount', 'N/A')}"
            )
            self.send_message(msg)

        elif cmd == "/pause":
            # Temporarily disable auto trading
            os.environ["AUTO_EXECUTE"] = "false"
            self.state["risk"]["trading_allowed"] = False
            self.send_message("⏸ <b>Trading Paused</b>. All automatic execution is disabled.")

        elif cmd == "/resume":
            os.environ["AUTO_EXECUTE"] = "true"
            self.state["risk"]["trading_allowed"] = True
            self.send_message("▶️ <b>Trading Resumed</b>. Automatic execution is active.")

        elif cmd == "/stop_bot":
            os.environ["BOT_RUNNING"] = "false"
            self.send_message("🛑 <b>Bot Stopped.</b> All analysis cycles are paused. No API requests will be made.")

        elif cmd == "/start_bot":
            os.environ["BOT_RUNNING"] = "true"
            self.send_message("🟢 <b>Bot Started.</b> Analysis cycles are now running.")

        elif cmd == "/close":
            self.send_message("⚠️ Force-closing all positions now...")
            results = self.mt5.close_all_positions()
            self.send_message(f"🔒 Closed {len(results)} open positions.")

        elif cmd == "/pnl":
            stats = self.journal.get_today_stats()
            msg = (
                f"📊 <b>TODAY'S PERFORMANCE Metrics</b>\n\n"
                f"• Trades taken: {stats.get('trade_count', 0)}\n"
                f"• Wins: {stats.get('wins', 0)} | Losses: {stats.get('losses', 0)}\n"
                f"• <b>Net P&L:</b> ${stats.get('pnl_usd', 0.0):.2f} ({stats.get('pnl_pts', 0.0)} pts)"
            )
            self.send_message(msg)

        elif cmd == "/brief":
            self.send_morning_brief()

        elif cmd == "/grade":
            setup = self.state.get("trade_params") or _LAST_SETUP
            if not setup:
                self.send_message("ℹ️ No setup analyzed recently.")
                return
            
            grade = setup.get("grade", "C")
            reason = setup.get("reason", "No setups matching A/B parameters.")
            score = setup.get("score", 0)
            
            self.send_message(
                f"🎯 <b>LAST SETUP GRADE</b>\n\n"
                f"• <b>Grade:</b> {grade}\n"
                f"• <b>Score:</b> {score}/10\n"
                f"• <b>Reasoning:</b> {reason}"
            )
        else:
            self.send_message(
                "❓ <b>Unknown Command</b>. Available:\n"
                "/status — view open positions\n"
                "/levels — key SMC support/resistances\n"
                "/pause — disable auto trading\n"
                "/resume — enable auto trading\n"
                "/start_bot — start orchestrator loops\n"
                "/stop_bot — pause orchestrator loops\n"
                "/close — close all open trades\n"
                "/pnl — show daily performance\n"
                "/brief — resend morning brief\n"
                "/grade — detail last setup grade"
            )

    def handle_callback(self, cb_id: str, msg_id: int, data: str):
        """Handles inline keyboard button callbacks."""
        url_answer = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
        requests.post(url_answer, json={"callback_query_id": cb_id}, timeout=5)
        
        status_text = ""
        if data == "approve_setup":
            status_text = "✅ Approved by Jimmy! Executing Trade..."
            # Enable Auto execution and queue execution
            self.state["trade_params"]["execute"] = True
            # Let the Execution node run immediately
            from agents.execution_agent import ExecutionAgent
            exec_agent = ExecutionAgent(self.state)
            exec_agent.run()
        elif data == "reject_setup":
            status_text = "❌ Rejected by Jimmy. Setup discarded."
            if "trade_params" in self.state:
                self.state["trade_params"]["execute"] = False
        elif data == "skip_setup":
            status_text = "⏸ Skipped. No actions taken."
            
        # Update the original message text with the status
        url_edit = f"https://api.telegram.org/bot{self.bot_token}/editMessageText"
        payload = {
            "chat_id": self.chat_id,
            "message_id": msg_id,
            "text": f"🎯 <b>SETUP STATUS UPDATE:</b>\n\n{status_text}",
            "parse_mode": "HTML"
        }
        requests.post(url_edit, json=payload, timeout=5)

    def send_morning_brief(self):
        """Generates and sends the beautiful Morning Brief."""
        struct = self.state.get("structure") or {}
        liqd = self.state.get("liquidity") or {}
        bias = self.state.get("bias_output") or {}
        news = self.state.get("news") or {}
        
        bias_h4 = bias.get("bias", "NEUTRAL") if isinstance(bias, dict) else getattr(bias, "bias", "NEUTRAL")
        
        tick = self.mt5.get_tick() or {"mid": "N/A"}
        
        morning_brief_text = (
            f"🌅 <b>BRIEF — {today_eat()}</b>\n\n"
            f"📊 <b>BIAS:</b> H4: {bias_h4} | H1: {struct.get('bias_h1', 'NEUTRAL')}\n"
            f"🟡 <b>ASIA:</b> {liqd.get('asia_high', 'N/A')} → {liqd.get('asia_low', 'N/A')}\n"
            f"📍 <b>LEVELS:</b>\n"
            f"   R: {struct.get('swing_high', 'N/A')} | {struct.get('premium', 'N/A')}\n"
            f"   NOW: {tick['mid']}\n"
            f"   S: {struct.get('swing_low', 'N/A')} | {struct.get('discount', 'N/A')}\n\n"
            f"🎯 <b>LONDON WATCH:</b>\n"
            f"   Waiting for Asia range sweep and H1 displacement.\n\n"
            f"📰 <b>NEWS:</b> {news.get('event_name', 'None upcoming')}"
        )
        self.send_message(morning_brief_text)

    def send_setup_alert(self, setup: dict):
        """Sends a trade setup alert with interactive inline approval buttons."""
        global _LAST_SETUP
        _LAST_SETUP = setup
        
        # Build templates with Approve/Reject inline keyboard
        markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ APPROVE", "callback_data": "approve_setup"},
                    {"text": "❌ REJECT", "callback_data": "reject_setup"},
                    {"text": "⏸ SKIP", "callback_data": "skip_setup"}
                ]
            ]
        }
        
        direction_emoji = "🟢 BUY" if setup.get("direction") == "BUY" else "🔴 SELL"
        risk_usd = setup.get("risk_usd", 10.0)
        
        pts = round(abs(setup["tp3"] - setup["entry"]), 2)
        rr1 = round(abs(setup.get("tp1", 0) - setup["entry"]) / max(0.01, abs(setup["entry"] - setup["sl"])), 1)
        rr2 = round(abs(setup.get("tp2", 0) - setup["entry"]) / max(0.01, abs(setup["entry"] - setup["sl"])), 1)
        rr3 = round(abs(setup.get("tp3", 0) - setup["entry"]) / max(0.01, abs(setup["entry"] - setup["sl"])), 1)
        
        text = (
            f"🎯 <b>{setup.get('grade', 'B')} — {self.state.get('session', {}).get('session', 'LONDON')}</b>\n"
            f"{direction_emoji} | Score: {setup.get('score', 8)}/10\n\n"
            f"Entry: {setup['entry']}\n"
            f"SL: {setup['sl']} (-{setup.get('risk_pts', 20)}pts / -${risk_usd})\n"
            f"TP1: {setup.get('tp1')} R:R 1:{rr1}\n"
            f"TP2: {setup.get('tp2')} R:R 1:{rr2}\n"
            f"TP3: {setup.get('tp3')} R:R 1:{rr3}\n"
            f"Lot: {setup.get('lot', 0.01)}\n\n"
            f"<b>Why:</b> {setup.get('reason', 'SMC alignment')}\n"
            f"❌ Invalid if: {setup.get('invalidation', 'Structure break')}"
        )
        self.send_message(text, reply_markup=markup)
