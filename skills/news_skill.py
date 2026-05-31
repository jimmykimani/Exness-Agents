"""
News Skill — Check if news blocks trading.
"""
from data.calendar_feed import get_calendar


def check_news_block() -> dict:
    """Check news state for trading decision."""
    cal = get_calendar()
    block = cal.should_block_trading()
    upcoming = cal.get_upcoming(hours_ahead=4)
    next_high = cal.get_next_high_impact()

    return {
        "block_trading": block["block_trading"],
        "block_reason": block["block_reason"],
        "upcoming_events": upcoming[:5],  # top 5
        "next_high_impact": next_high,
        "clear_to_trade_at": None,  # populated when blocking
    }
