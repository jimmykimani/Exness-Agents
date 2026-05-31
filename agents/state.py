from typing import TypedDict, Dict, Any, List, Optional
from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════
# LLM Structured Outputs (Pydantic Models)
# ═══════════════════════════════════════════════════════

class SwingPoint(BaseModel):
    price: float
    time: str
    type: str = Field(description="'STRONG' or 'WEAK'")

class StructureOutput(BaseModel):
    bias: Dict[str, str] = Field(description="Bias per timeframe, e.g., H4: BULLISH")
    swing_points: Dict[str, SwingPoint] = Field(description="last_high and last_low")
    choch: Dict[str, Any] = Field(description="CHoCH data")
    bos: Dict[str, Any] = Field(description="BOS data")
    displacement: Dict[str, Any]
    inducement_warning: bool
    premium_discount: str
    equilibrium: float

class LiquidityPool(BaseModel):
    level: float
    type: str
    timeframe: str
    touches: int
    swept: bool
    size: str

class LiquidityOutput(BaseModel):
    asia_range: Dict[str, Any]
    bsl_pools: List[LiquidityPool]
    ssl_pools: List[LiquidityPool]
    nearest_bsl: Optional[Dict[str, float]]
    nearest_ssl: Optional[Dict[str, float]]
    draw_on_liquidity: Dict[str, Any]
    manipulation_detected: bool
    manipulation_direction: str

class OrderBlock(BaseModel):
    top: float
    bottom: float
    mid: float
    timeframe: str
    time: str
    score: float
    type: str
    virgin: bool
    inside_ote: bool
    volume_at_creation: float

class OrderBlockOutput(BaseModel):
    bullish_obs: List[OrderBlock]
    bearish_obs: List[OrderBlock]
    best_ob: Optional[OrderBlock]
    ob_in_ote: Optional[OrderBlock]
    nearest_ob: Optional[OrderBlock]

class OTEOutput(BaseModel):
    swing: Dict[str, Any]
    fib_levels: Dict[str, float]
    ote_zone: List[float]
    price_in_ote: bool
    optimal_entry: float
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    risk_pts: float
    rr_tp1: float
    rr_tp2: float
    rr_tp3: float
    confluence_score: float
    valid: bool

class BiasOutput(BaseModel):
    bias: str = Field(description="LONG, SHORT, or WAIT")
    grade: str = Field(description="A+, A, B, or C")
    score: float
    direction: str = Field(description="BULLISH, BEARISH, or NEUTRAL")
    reasons: List[str]
    invalidation: str
    entry_allowed: bool
    wait_reason: Optional[str]

class EntryOutput(BaseModel):
    execute: bool
    direction: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    lot: float
    risk_dollars: float
    rr_tp1: float
    rr_tp2: float
    grade: str
    reason: str
    invalidation: str
    order_type: str = Field(description="LIMIT or MARKET")
    expiry: str

# ═══════════════════════════════════════════════════════
# Main LangGraph State
# ═══════════════════════════════════════════════════════

class TradingState(TypedDict):
    data: Dict[str, Any]
    structure: StructureOutput
    liquidity: LiquidityOutput
    orderblock: OrderBlockOutput
    ote: OTEOutput
    bias_output: BiasOutput
    trade_params: EntryOutput
    risk: Dict[str, Any]
    session: Dict[str, Any]
    news: Dict[str, Any]
    execution_result: Dict[str, Any]
    monitor: Dict[str, Any]
    pending_messages: List[str]
    errors: List[str]
