"""
Jimmy's Gold Trading Bot — Trade Journal
Logs trades and computes performance metrics.
Falls back to local JSON if Supabase unavailable.
"""
import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List

from db.models import get_supabase_client
from utils.logger import get_agent_logger
from utils.session_clock import today_eat

log = get_agent_logger("JOURNAL")

LOCAL_JOURNAL_PATH = Path("data/journal_local.json")


class Journal:
    def __init__(self):
        self._client = get_supabase_client()
        self._local_trades: List[dict] = []
        self._load_local()

    def _load_local(self):
        if LOCAL_JOURNAL_PATH.exists():
            try:
                self._local_trades = json.loads(LOCAL_JOURNAL_PATH.read_text())
            except Exception:
                self._local_trades = []

    def _save_local(self):
        LOCAL_JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_JOURNAL_PATH.write_text(json.dumps(self._local_trades, indent=2, default=str))

    def log_trade(self, trade: dict) -> str:
        """Log a completed trade. Returns trade_id."""
        trade_id = str(uuid.uuid4())
        record = {"trade_id": trade_id, **trade}

        if self._client:
            try:
                self._client.table("trades").insert(record).execute()
                log.info(f"Trade logged to Supabase: {trade_id}")
            except Exception as e:
                log.error(f"Supabase insert failed: {e} — falling back to local")
                self._local_trades.append(record)
                self._save_local()
        else:
            self._local_trades.append(record)
            self._save_local()
            log.info(f"Trade logged locally: {trade_id}")

        return trade_id

    def get_today_trades(self) -> List[dict]:
        today = today_eat()
        if self._client:
            try:
                result = self._client.table("trades").select("*").eq("date", today).execute()
                return result.data
            except Exception:
                pass
        return [t for t in self._local_trades if t.get("date") == today]

    def get_today_stats(self) -> dict:
        trades = self.get_today_trades()
        wins = [t for t in trades if (t.get("pnl_usd") or 0) > 0]
        losses = [t for t in trades if (t.get("pnl_usd") or 0) <= 0]
        total_pnl = sum(t.get("pnl_usd", 0) for t in trades)
        total_pts = sum(t.get("pnl_pts", 0) for t in trades)
        return {
            "date": today_eat(),
            "trade_count": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "pnl_pts": round(total_pts, 2),
            "pnl_usd": round(total_pnl, 2),
        }

    def get_weekly_metrics(self) -> dict:
        """Compute weekly performance metrics."""
        all_trades = self._get_recent_trades(days=7)
        if not all_trades:
            return {"total_trades": 0, "win_rate": 0.0, "avg_rr": 0.0}
        wins = [t for t in all_trades if (t.get("pnl_usd") or 0) > 0]
        rr_vals = [t.get("rr_achieved", 0) for t in all_trades if t.get("rr_achieved")]
        return {
            "total_trades": len(all_trades),
            "win_rate": round(len(wins) / len(all_trades) * 100, 1) if all_trades else 0,
            "avg_rr": round(sum(rr_vals) / len(rr_vals), 2) if rr_vals else 0,
            "pnl_usd": round(sum(t.get("pnl_usd", 0) for t in all_trades), 2),
        }

    def _get_recent_trades(self, days: int = 7) -> List[dict]:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        if self._client:
            try:
                result = self._client.table("trades").select("*").gte("date", cutoff).execute()
                return result.data
            except Exception:
                pass
        return [t for t in self._local_trades if t.get("date", "") >= cutoff]


_journal: Optional[Journal] = None

def get_journal() -> Journal:
    global _journal
    if _journal is None:
        _journal = Journal()
    return _journal
