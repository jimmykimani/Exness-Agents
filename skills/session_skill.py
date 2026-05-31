"""
Session Skill — Session window detection and state.
"""
from utils.session_clock import (
    get_current_session, is_session_tradeable,
    is_friday_close, session_info, now_eat,
)


def get_session_state() -> dict:
    """Get full session state for agent consumption."""
    info = session_info()
    return {
        **info,
        "is_weekend": now_eat().weekday() >= 5,
        "friday_close": is_friday_close(),
    }
