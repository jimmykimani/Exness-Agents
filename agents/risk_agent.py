"""
RiskAgent — Capital protection. VETO power over all trades.
"""
from config.trading_rules import (
    STARTING_BALANCE, MAX_TRADES_PER_DAY, DAILY_LOSS_LIMIT_PCT,
    WEEKLY_LOSS_LIMIT_PCT, MAX_LOT_SIZE, RISK_PER_TRADE_PCT
)
from data.mt5_connector import get_mt5
from db.journal import get_journal
from utils.logger import get_agent_logger

log = get_agent_logger("RISK_AGENT")


class RiskAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state
        self.journal = get_journal()
        self.mt5 = get_mt5()

    def run(self) -> dict:
        info = self.mt5.get_account_info()
        balance = info.get("balance", STARTING_BALANCE) if info else STARTING_BALANCE
        equity = info.get("equity", balance) if info else balance

        # Get stats from journal
        today_stats = self.journal.get_today_stats()
        weekly_stats = self.journal.get_weekly_metrics()

        daily_pnl = today_stats.get("pnl_usd", 0.0)
        daily_pnl_pct = (daily_pnl / balance) * 100 if balance > 0 else 0
        trade_count_today = today_stats.get("trade_count", 0)
        
        weekly_pnl = weekly_stats.get("pnl_usd", 0.0)
        weekly_pnl_pct = (weekly_pnl / balance) * 100 if balance > 0 else 0

        # Hard limits checks
        trading_allowed = True
        block_reason = None
        force_close = False

        daily_limit_usd = balance * DAILY_LOSS_LIMIT_PCT
        weekly_limit_usd = balance * WEEKLY_LOSS_LIMIT_PCT

        if trade_count_today >= MAX_TRADES_PER_DAY:
            trading_allowed = False
            block_reason = f"Max daily trades reached ({MAX_TRADES_PER_DAY})"
        elif daily_pnl <= -daily_limit_usd:
            trading_allowed = False
            block_reason = f"Daily loss limit hit (${-daily_limit_usd:.2f})"
            force_close = True  # If floating positions push us over
        elif weekly_pnl <= -weekly_limit_usd:
            trading_allowed = False
            block_reason = f"Weekly loss limit hit (${-weekly_limit_usd:.2f})"
        elif not self.mt5.connected:
            trading_allowed = False
            block_reason = "MT5 not connected"

        output = {
            "account_balance": balance,
            "equity": equity,
            "daily_pnl": daily_pnl,
            "daily_pnl_pct": round(daily_pnl_pct, 2),
            "weekly_pnl": weekly_pnl,
            "trade_count_today": trade_count_today,
            "trading_allowed": trading_allowed,
            "block_reason": block_reason,
            "max_lot": MAX_LOT_SIZE,
            "risk_per_trade_dollars": round(balance * RISK_PER_TRADE_PCT, 2),
            "daily_limit_remaining": round(daily_limit_usd + daily_pnl, 2),
            "force_close": force_close
        }

        self.state["risk"] = output
        log.info(
            f"Risk state — Bal: ${balance:.2f} | PnL: ${daily_pnl:.2f} | "
            f"Allowed: {trading_allowed} {f'({block_reason})' if block_reason else ''}"
        )
        return output
