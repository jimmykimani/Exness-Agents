"""
Jimmy's Gold Trading Bot — Database Models
Supabase/PostgreSQL trade journal schema and access layer.
"""
from config.settings import SUPABASE_URL, SUPABASE_KEY
from utils.logger import get_agent_logger

log = get_agent_logger("DATABASE")

# SQL to create the trades table (run once on Supabase)
CREATE_TRADES_TABLE = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    session VARCHAR(20),
    direction VARCHAR(10),
    entry_price DECIMAL(10,2),
    exit_price DECIMAL(10,2),
    sl DECIMAL(10,2),
    tp_hit VARCHAR(10),
    lots DECIMAL(5,2),
    pnl_pts DECIMAL(10,2),
    pnl_usd DECIMAL(10,2),
    grade VARCHAR(5),
    score DECIMAL(4,1),
    choch_confirmed BOOLEAN DEFAULT FALSE,
    liquidity_swept BOOLEAN DEFAULT FALSE,
    ote_valid BOOLEAN DEFAULT FALSE,
    ob_present BOOLEAN DEFAULT FALSE,
    news_present BOOLEAN DEFAULT FALSE,
    rr_planned DECIMAL(5,2),
    rr_achieved DECIMAL(5,2),
    mistake TEXT,
    lesson TEXT,
    balance_after DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date);
CREATE INDEX IF NOT EXISTS idx_trades_session ON trades(session);
"""

CREATE_DAILY_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS daily_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE UNIQUE NOT NULL,
    trade_count INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    pnl_pts DECIMAL(10,2) DEFAULT 0,
    pnl_usd DECIMAL(10,2) DEFAULT 0,
    balance DECIMAL(10,2),
    max_drawdown_pct DECIMAL(5,2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""


def get_supabase_client():
    """Get Supabase client. Returns None if not configured."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.warning("Supabase not configured — journal will use local file fallback")
        return None
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        log.info("Supabase client connected")
        return client
    except Exception as e:
        log.error(f"Supabase connection failed: {e}")
        return None
