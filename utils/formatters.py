"""
Jimmy's Gold Trading Bot — Formatters
Format prices, messages, and data for display.
"""
from typing import Optional


def fmt_price(price: float) -> str:
    """Format gold price with 2 decimal places."""
    return f"{price:.2f}"


def fmt_pips(points: float) -> str:
    """Format point distance."""
    return f"{points:.1f}pts"


def fmt_rr(rr: float) -> str:
    """Format risk:reward ratio."""
    return f"1:{rr:.1f}"


def fmt_pct(pct: float) -> str:
    """Format percentage."""
    return f"{pct:+.2f}%"


def fmt_usd(amount: float) -> str:
    """Format USD amount."""
    return f"${amount:+.2f}"


def fmt_lot(lot: float) -> str:
    """Format lot size."""
    return f"{lot:.2f}"


def direction_emoji(direction: str) -> str:
    """Get emoji for trade direction."""
    d = direction.upper()
    if d in ("LONG", "BULLISH", "BUY"):
        return "🟢"
    elif d in ("SHORT", "BEARISH", "SELL"):
        return "🔴"
    return "⚪"


def grade_emoji(grade: str) -> str:
    """Get emoji for setup grade."""
    mapping = {
        "A+": "💎",
        "A":  "🎯",
        "B":  "📊",
        "C":  "📝",
    }
    return mapping.get(grade, "❓")


def session_emoji(session: Optional[str]) -> str:
    """Get emoji for session."""
    mapping = {
        "ASIA":     "🌏",
        "LONDON":   "🇬🇧",
        "NEW_YORK": "🇺🇸",
        "DEAD_ZONE": "💤",
    }
    return mapping.get(session, "⏸️") if session else "⏸️"


def format_levels_block(levels: dict) -> str:
    """Format key levels for Telegram message."""
    lines = []
    if "resistance" in levels:
        for i, r in enumerate(levels["resistance"], 1):
            lines.append(f"   R{i}: {fmt_price(r)}")
    if "current" in levels:
        lines.append(f"   NOW: {fmt_price(levels['current'])}")
    if "support" in levels:
        for i, s in enumerate(levels["support"], 1):
            lines.append(f"   S{i}: {fmt_price(s)}")
    return "\n".join(lines)


def format_trade_summary(trade: dict) -> str:
    """Format a single trade for display."""
    d_emoji = direction_emoji(trade.get("direction", ""))
    pnl = trade.get("pnl_dollars", 0)
    pnl_str = fmt_usd(pnl)
    return (
        f"{d_emoji} {trade.get('direction', '?')} | "
        f"Entry: {fmt_price(trade.get('entry', 0))} | "
        f"P&L: {pnl_str}"
    )
