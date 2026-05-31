"""
JournalAgent — Performance tracking and logging.
"""
from db.journal import get_journal
from utils.logger import get_agent_logger

log = get_agent_logger("JOURNAL_AGENT")


class JournalAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state
        self.journal = get_journal()

    def run(self) -> dict:
        """Run EOD journaling tasks."""
        stats = self.journal.get_today_stats()
        weekly = self.journal.get_weekly_metrics()
        
        output = {
            "today": stats,
            "weekly": weekly
        }
        
        self.state["journal_stats"] = output
        log.info(f"Journal stats — Today: {stats.get('trade_count')} trades, PnL: ${stats.get('pnl_usd')}")
        
        return output
