"""
Skills Registry — maps skill names to callable functions for LangGraph tool use.
"""
from skills.fibonacci_skill import calculate_fibonacci, check_ote_zone
from skills.structure_skill import detect_choch, detect_bos, find_swing_points, detect_displacement
from skills.liquidity_skill import map_liquidity_pools, detect_equal_levels, check_asia_range
from skills.orderblock_skill import detect_order_blocks, score_order_block
from skills.session_skill import get_session_state
from skills.news_skill import check_news_block
from skills.volume_skill import analyze_volume
from skills.execution_skill import calculate_lot_size, build_order_request

SKILL_REGISTRY = {
    # Fibonacci / OTE
    "calculate_fibonacci": calculate_fibonacci,
    "check_ote_zone": check_ote_zone,
    # Structure
    "detect_choch": detect_choch,
    "detect_bos": detect_bos,
    "find_swing_points": find_swing_points,
    "detect_displacement": detect_displacement,
    # Liquidity
    "map_liquidity_pools": map_liquidity_pools,
    "detect_equal_levels": detect_equal_levels,
    "check_asia_range": check_asia_range,
    # Order Blocks
    "detect_order_blocks": detect_order_blocks,
    "score_order_block": score_order_block,
    # Session
    "get_session_state": get_session_state,
    # News
    "check_news_block": check_news_block,
    # Volume
    "analyze_volume": analyze_volume,
    # Execution
    "calculate_lot_size": calculate_lot_size,
    "build_order_request": build_order_request,
}


def get_skill(name: str):
    """Get a skill function by name."""
    return SKILL_REGISTRY.get(name)
