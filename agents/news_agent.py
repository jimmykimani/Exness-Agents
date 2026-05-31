"""
NewsAgent — Economic calendar watchdog.
"""
from skills.news_skill import check_news_block
from utils.logger import get_agent_logger

log = get_agent_logger("NEWS_AGENT")


class NewsAgent:
    def __init__(self, shared_state: dict):
        self.state = shared_state

    def run(self) -> dict:
        news_state = check_news_block()
        
        self.state["news"] = news_state
        
        if news_state.get("block_trading"):
            log.warning(f"TRADING BLOCKED by news: {news_state.get('block_reason')}")
        else:
            nxt = news_state.get("next_high_impact")
            if nxt:
                log.info(f"Next high impact: {nxt['name']} in {nxt['mins_away']}m")
            else:
                log.info("No high impact news upcoming")
                
        return news_state
