"""
Jimmy's Gold Trading Bot — Central Configuration
All settings, constants, and environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# ─── Load .env ─────────────────────────────────────────
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# ═══════════════════════════════════════════════════════
# BROKER / MT5
# ═══════════════════════════════════════════════════════
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "Exness-MT5Trial")
SYMBOL = "XAUUSD"

# ═══════════════════════════════════════════════════════
# LLM API KEYS
# ═══════════════════════════════════════════════════════
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# LLM Models
GEMINI_MODEL_ANALYSIS = "gemini-2.5-flash"
GEMINI_MODEL_SPEED = "gemini-2.5-flash"

# ═══════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ═══════════════════════════════════════════════════════
# REDIS / CACHE
# ═══════════════════════════════════════════════════════
REDIS_URL = os.getenv("REDIS_URL", "")

# ═══════════════════════════════════════════════════════
# DATABASE (Supabase / PostgreSQL)
# ═══════════════════════════════════════════════════════
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ═══════════════════════════════════════════════════════
# SENTRY
# ═══════════════════════════════════════════════════════
SENTRY_DSN = os.getenv("SENTRY_DSN", "")

# ═══════════════════════════════════════════════════════
# TRADING MODE
# ═══════════════════════════════════════════════════════
TRADING_MODE = os.getenv("TRADING_MODE", "demo")  # "demo" | "live"
AUTO_EXECUTE = os.getenv("AUTO_EXECUTE", "false").lower() == "true"

# ═══════════════════════════════════════════════════════
# TIMEZONE
# ═══════════════════════════════════════════════════════
TIMEZONE = "Africa/Nairobi"  # EAT = UTC+3

# ═══════════════════════════════════════════════════════
# TIMEFRAMES
# ═══════════════════════════════════════════════════════
TIMEFRAMES = {
    "M1":  {"mt5": "TIMEFRAME_M1",  "minutes": 1,   "candle_count": 100},
    "M5":  {"mt5": "TIMEFRAME_M5",  "minutes": 5,   "candle_count": 100},
    "M15": {"mt5": "TIMEFRAME_M15", "minutes": 15,  "candle_count": 100},
    "M30": {"mt5": "TIMEFRAME_M30", "minutes": 30,  "candle_count": 100},
    "H1":  {"mt5": "TIMEFRAME_H1",  "minutes": 60,  "candle_count": 100},
    "H4":  {"mt5": "TIMEFRAME_H4",  "minutes": 240, "candle_count": 50},
}

# ═══════════════════════════════════════════════════════
# NEWS SOURCE
# ═══════════════════════════════════════════════════════
FOREX_FACTORY_RSS = "https://www.forexfactory.com/calendar.xml"
NEWS_REFRESH_INTERVAL_MIN = 15

# ═══════════════════════════════════════════════════════
# DATA REFRESH
# ═══════════════════════════════════════════════════════
TICK_REFRESH_SECONDS = 1
CANDLE_REFRESH_SECONDS = 5
MAX_DATA_AGE_SECONDS = 60

# ═══════════════════════════════════════════════════════
# FASTAPI
# ═══════════════════════════════════════════════════════
API_HOST = "0.0.0.0"
API_PORT = int(os.getenv("PORT", "8000"))

# ═══════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "logs/goldbot.log"
LOG_ROTATION = "10 MB"
LOG_RETENTION = "7 days"
