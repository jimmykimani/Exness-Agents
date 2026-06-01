"""
Jimmy's Gold Trading Bot — Trading Rules
All risk parameters, session windows, scoring rubrics.
These are the HARD RULES that protect Jimmy's capital.
"""

# ═══════════════════════════════════════════════════════
# ACCOUNT PARAMETERS
# ═══════════════════════════════════════════════════════
STARTING_BALANCE = 192.0  # USD

# ═══════════════════════════════════════════════════════
# RISK MANAGEMENT — AGGRESSIVE MODE
# ═══════════════════════════════════════════════════════
RISK_PER_TRADE_PCT = 0.05        # 5% per trade (aggressive)
MAX_LOT_SIZE = 0.10              # allow up to 0.10 lots
MAX_TRADES_PER_DAY = 6
DAILY_LOSS_LIMIT_PCT = 0.10      # 10% daily loss limit
WEEKLY_LOSS_LIMIT_PCT = 0.15     # 15% weekly loss limit
MAX_SPREAD_POINTS = 5.0          # reject if spread > 5
MIN_VOLATILITY_POINTS = 2.0      # minimum movement to trigger LLM analysis

# ═══════════════════════════════════════════════════════
# SESSION WINDOWS (EAT = UTC+3)
# ═══════════════════════════════════════════════════════
SESSIONS = {
    "ASIA": {
        "start": "01:00",
        "end": "09:59",
        "tradeable": False,
    },
    "LONDON": {
        "start": "10:00",
        "end": "15:59",
        "tradeable": True,
    },
    "NEW_YORK": {
        "start": "16:00",
        "end": "23:59",
        "tradeable": True,
    },
    "LATE_NY": {
        "start": "00:00",
        "end": "00:59",
        "tradeable": True,
    },
}

# Friday close time
FRIDAY_CLOSE_TIME = "17:30"  # EAT

# ═══════════════════════════════════════════════════════
# WORKFLOW SCHEDULE (EAT times)
# ═══════════════════════════════════════════════════════
SCHEDULE = {
    "news_start":           "00:59",
    "asia_data_start":      "01:00",
    "asia_range_lock":      "09:00",
    "morning_brief":        "09:45",
    "london_prep":          "09:58",
    "london_open":          "10:00",
    "london_close":         "12:00",
    "ny_prep":              "16:28",
    "ny_open":              "16:30",
    "ny_close":             "18:30",
    "daily_summary":        "18:31",
}

# ═══════════════════════════════════════════════════════
# STRUCTURE ANALYSIS
# ═══════════════════════════════════════════════════════
DISPLACEMENT_ATR_MULTIPLIER = 1.5  # candle body > 1.5x ATR = displacement
ATR_PERIOD = 14
MIN_TF_AGREEMENT = 3  # minimum timeframes that must agree for bias

# ═══════════════════════════════════════════════════════
# LIQUIDITY
# ═══════════════════════════════════════════════════════
EQH_EQL_TOLERANCE_POINTS = 2.0  # two highs/lows within 2pts = equal
MIN_POOL_TOUCHES = 2

# ═══════════════════════════════════════════════════════
# ORDER BLOCK SCORING RUBRIC
# ═══════════════════════════════════════════════════════
OB_SCORING = {
    "volume_above_avg":     2.5,  # volume > 1.5x average
    "gap_displacement":     2.0,  # gap or displacement after OB
    "virgin":               2.0,  # never retested
    "session_formation":    2.0,  # formed in London/NY
    "inside_ote":           1.5,  # inside OTE zone
    "htf_aligned":          1.0,  # aligned with HTF bias
}
OB_MIN_SCORE = 7.0        # minimum to flag
OB_APLUS_SCORE = 8.5      # A+ setup threshold
OB_VOLUME_MULTIPLIER = 1.5  # volume must be > 1.5x avg

# ═══════════════════════════════════════════════════════
# OTE / FIBONACCI
# ═══════════════════════════════════════════════════════
FIB_LEVELS = {
    "0":     0.0,
    "23.6":  0.236,
    "38.2":  0.382,
    "50.0":  0.5,     # equilibrium — avoid
    "61.8":  0.618,   # OTE zone start
    "70.5":  0.705,   # optimal entry
    "78.6":  0.786,   # OTE zone end
    "100":   1.0,     # invalidation / TP1
    "127.2": 1.272,   # TP extension
    "161.8": 1.618,   # TP extension
    "200.0": 2.0,     # TP extension
}
OTE_ZONE = (0.618, 0.786)
SL_BUFFER_POINTS = 5.0       # SL below 78.6% + buffer
MIN_RR_TP2 = 3.0             # R:R to TP2 must be >= 1:3
MIN_SWING_RANGE_POINTS = 20  # reject if swing < 20pts

# ═══════════════════════════════════════════════════════
# BIAS / CONFLUENCE SCORING
# ═══════════════════════════════════════════════════════
CONFLUENCE_SCORING = {
    "htf_aligned":          2,  # H4+H1 same direction
    "liquidity_swept":      2,  # BSL/SSL swept
    "price_in_ote":         2,  # in OTE zone
    "ob_in_zone":           1,  # OB score > 7 in zone
    "fvg_in_zone":          1,  # FVG present in zone
    "volume_confirmation":  1,  # volume spike
    "m1_choch":             1,  # 1m CHoCH confirmed
}

# ═══════════════════════════════════════════════════════
# SETUP GRADING
# ═══════════════════════════════════════════════════════
GRADE_THRESHOLDS = {
    "A+": 9,   # auto-execute immediately
    "A":  7,   # auto-execute (aggressive mode)
    "B":  5,   # auto-execute + alert Jimmy
    "C":  0,   # alert only, no execution
}

# ═══════════════════════════════════════════════════════
# PARTIAL CLOSE / TRADE MANAGEMENT
# ═══════════════════════════════════════════════════════
TP1_CLOSE_PCT = 0.50   # close 50% at TP1
TP2_CLOSE_PCT = 0.30   # close 30% of original at TP2
TP3_CLOSE_PCT = 0.20   # close remaining 20% at TP3

# ═══════════════════════════════════════════════════════
# NEWS BLOCKING
# ═══════════════════════════════════════════════════════
NEWS_BLOCK_BEFORE_MIN = 30  # block 30min before HIGH impact
NEWS_CLEAR_AFTER_MIN = 15   # clear 15min after event
NEWS_WARNING_BEFORE_MIN = 15  # warning for MEDIUM impact

HIGH_IMPACT_EVENTS = [
    "NFP", "Non-Farm Payrolls",
    "CPI", "Consumer Price Index",
    "FOMC", "FOMC Minutes",
    "Fed Rate Decision", "Interest Rate Decision",
    "GDP", "Gross Domestic Product",
    "PCE", "Core PCE",
    "Fed Chair Speech", "Fed Chair Powell",
    "PMI", "ISM Manufacturing PMI", "ISM Services PMI",
    "UMich", "Michigan Consumer Sentiment",
    "Jobless Claims", "Initial Jobless Claims",
    "US Unemployment", "Unemployment Rate",
]

# ═══════════════════════════════════════════════════════
# FTMO TARGETS
# ═══════════════════════════════════════════════════════
FTMO = {
    "target_pct":       10.0,    # +10% in 30 days
    "max_daily_loss":   5.0,     # 5% daily loss limit
    "max_drawdown":     10.0,    # 10% max drawdown
    "min_trading_days": 4,       # minimum 4 trading days
    "phase1_days":      30,      # 30 day challenge
}

# ═══════════════════════════════════════════════════════
# EXECUTION
# ═══════════════════════════════════════════════════════
MAX_SLIPPAGE_POINTS = 2.0   # reject if price moved > 2pts
ORDER_RETRY_DELAY_SEC = 2   # wait before retry
MAX_ORDER_RETRIES = 1
MT5_RECONNECT_INTERVAL_SEC = 30
MT5_ALERT_AFTER_SEC = 300   # alert Jimmy after 5min disconnect
