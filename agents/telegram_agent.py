"""
TelegramAgent — Jimmy's communication interface.
"""
import asyncio
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from utils.logger import get_agent_logger

log = get_agent_logger("TELEGRAM_AGENT")


class TelegramAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID

    def run(self) -> dict:
        """Process messages to send from state."""
        messages = self.state.get("pending_messages", [])
        if not messages:
            return {"sent": 0}

        sent = 0
        for msg in messages:
            try:
                # In production, use python-telegram-bot
                # For this agent shell, we just log it or use requests
                log.info(f"Sending Telegram to Jimmy:\n{msg}")
                # Mock sending
                sent += 1
            except Exception as e:
                log.error(f"Telegram error: {e}")

        # Clear queue
        self.state["pending_messages"] = []
        return {"sent": sent}

    def queue_message(self, text: str):
        if "pending_messages" not in self.state:
            self.state["pending_messages"] = []
        self.state["pending_messages"].append(text)
