"""
Jimmy's Gold Trading Bot — Session Clock
Handles all time-related logic in EAT (UTC+3).
"""
from datetime import datetime, time
from typing import Optional

import pytz

from config.settings import TIMEZONE
from config.trading_rules import SESSIONS, FRIDAY_CLOSE_TIME, SCHEDULE


EAT = pytz.timezone(TIMEZONE)


def now_eat() -> datetime:
    """Get current time in EAT."""
    return datetime.now(EAT)


def today_eat() -> str:
    """Get today's date string in EAT."""
    return now_eat().strftime("%Y-%m-%d")


def time_str_eat() -> str:
    """Get current time as HH:MM string in EAT."""
    return now_eat().strftime("%H:%M")


def parse_time(t: str) -> time:
    """Parse 'HH:MM' string to time object."""
    parts = t.split(":")
    return time(int(parts[0]), int(parts[1]))


def is_within(current: time, start: str, end: str) -> bool:
    """Check if current time is within start-end window."""
    s = parse_time(start)
    e = parse_time(end)
    return s <= current <= e


def get_current_session() -> Optional[str]:
    """
    Determine which session we are in right now.
    Returns session name or None if outside all sessions.
    """
    ct = now_eat().time()
    for name, cfg in SESSIONS.items():
        if is_within(ct, cfg["start"], cfg["end"]):
            return name
    return None


def is_session_tradeable() -> bool:
    """Check if current session allows trading."""
    session = get_current_session()
    if session is None:
        return False
    return SESSIONS[session]["tradeable"]


def is_friday_close() -> bool:
    """Check if it's Friday past close time."""
    n = now_eat()
    if n.weekday() != 4:  # 0=Mon, 4=Fri
        return False
    return n.time() >= parse_time(FRIDAY_CLOSE_TIME)


def minutes_until(target_time: str) -> int:
    """Calculate minutes from now until target_time (EAT)."""
    n = now_eat()
    target = parse_time(target_time)
    target_dt = n.replace(
        hour=target.hour, minute=target.minute, second=0, microsecond=0
    )
    if target_dt < n:
        # Target is tomorrow
        from datetime import timedelta
        target_dt += timedelta(days=1)
    delta = target_dt - n
    return int(delta.total_seconds() / 60)


def session_info() -> dict:
    """Get comprehensive session state."""
    n = now_eat()
    session = get_current_session()
    return {
        "current_time_eat": n.strftime("%H:%M:%S"),
        "date": n.strftime("%Y-%m-%d"),
        "day_of_week": n.strftime("%A"),
        "session": session,
        "tradeable": is_session_tradeable(),
        "is_friday_close": is_friday_close(),
    }


def get_schedule_event(event_name: str) -> Optional[str]:
    """Get scheduled time for a named event."""
    return SCHEDULE.get(event_name)
