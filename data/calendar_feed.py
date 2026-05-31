"""
Jimmy's Gold Trading Bot — Calendar Feed
Fetches economic calendar from Forex Factory for news blocking.
"""
from datetime import datetime, timedelta
from typing import List, Optional
import requests
from utils.logger import get_agent_logger
from utils.session_clock import now_eat, EAT
from config.trading_rules import (
    HIGH_IMPACT_EVENTS, NEWS_BLOCK_BEFORE_MIN,
    NEWS_CLEAR_AFTER_MIN, NEWS_WARNING_BEFORE_MIN,
)

log = get_agent_logger("CALENDAR")

# Forex Factory scraping URL
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


class CalendarFeed:
    def __init__(self):
        self._events: List[dict] = []
        self._last_fetch: Optional[datetime] = None

    def refresh(self) -> List[dict]:
        """Fetch this week's economic calendar."""
        try:
            resp = requests.get(FF_URL, timeout=10)
            resp.raise_for_status()
            raw = resp.json()
            self._events = self._parse_events(raw)
            self._last_fetch = now_eat()
            log.info(f"Calendar refreshed — {len(self._events)} events loaded")
        except Exception as e:
            log.error(f"Calendar fetch failed: {e}")
        return self._events

    def _parse_events(self, raw: list) -> List[dict]:
        events = []
        for ev in raw:
            try:
                impact = ev.get("impact", "").upper()
                if impact not in ("HIGH", "MEDIUM", "LOW"):
                    continue
                currency = ev.get("country", "")
                # Only care about USD events for gold
                if currency != "USD":
                    continue
                title = ev.get("title", "")
                date_str = ev.get("date", "")
                ev_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                ev_time_eat = ev_time.astimezone(EAT)
                events.append({
                    "name": title,
                    "time_eat": ev_time_eat.strftime("%H:%M"),
                    "date": ev_time_eat.strftime("%Y-%m-%d"),
                    "datetime_eat": ev_time_eat,
                    "impact": impact,
                    "currency": currency,
                })
            except Exception:
                continue
        return events

    def get_upcoming(self, hours_ahead: int = 8) -> List[dict]:
        """Get events within the next N hours."""
        if not self._events or self._is_stale():
            self.refresh()
        n = now_eat()
        cutoff = n + timedelta(hours=hours_ahead)
        upcoming = []
        for ev in self._events:
            et = ev["datetime_eat"]
            if n - timedelta(minutes=NEWS_CLEAR_AFTER_MIN) <= et <= cutoff:
                mins_away = int((et - n).total_seconds() / 60)
                upcoming.append({**ev, "mins_away": mins_away})
        return sorted(upcoming, key=lambda x: x["mins_away"])

    def should_block_trading(self) -> dict:
        """Check if trading should be blocked due to news."""
        upcoming = self.get_upcoming(hours_ahead=1)
        for ev in upcoming:
            mins = ev["mins_away"]
            if ev["impact"] == "HIGH":
                is_high = any(kw.lower() in ev["name"].lower() for kw in HIGH_IMPACT_EVENTS)
                if is_high or True:  # block all HIGH impact
                    if -NEWS_CLEAR_AFTER_MIN <= mins <= NEWS_BLOCK_BEFORE_MIN:
                        return {
                            "block_trading": True,
                            "block_reason": f"HIGH impact: {ev['name']} in {mins}min",
                            "event": ev,
                        }
        return {"block_trading": False, "block_reason": None, "event": None}

    def get_next_high_impact(self) -> Optional[dict]:
        upcoming = self.get_upcoming(hours_ahead=24)
        for ev in upcoming:
            if ev["impact"] == "HIGH" and ev["mins_away"] > 0:
                return ev
        return None

    def _is_stale(self) -> bool:
        if self._last_fetch is None:
            return True
        return (now_eat() - self._last_fetch).total_seconds() > 900  # 15 min


_calendar: Optional[CalendarFeed] = None

def get_calendar() -> CalendarFeed:
    global _calendar
    if _calendar is None:
        _calendar = CalendarFeed()
    return _calendar
