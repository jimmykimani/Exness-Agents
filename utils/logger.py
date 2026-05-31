"""
Jimmy's Gold Trading Bot — Structured Logger
Uses loguru for rich, structured logging across all agents.
"""
import sys
from pathlib import Path
from loguru import logger

from config.settings import LOG_LEVEL, LOG_FILE, LOG_ROTATION, LOG_RETENTION


def setup_logger():
    """Configure loguru for the entire application."""
    # Remove default handler
    logger.remove()

    # Console handler — colorized, concise
    logger.add(
        sys.stdout,
        level=LOG_LEVEL,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[agent]: <16}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
        filter=lambda record: record["extra"].get("agent", "SYSTEM"),
    )

    # File handler — full detail, rotated
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_path),
        level="DEBUG",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{extra[agent]: <16} | "
            "{message}"
        ),
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        encoding="utf-8",
    )

    return logger


def get_agent_logger(agent_name: str):
    """Get a logger bound to a specific agent name."""
    return logger.bind(agent=agent_name)


# Initialize on import
setup_logger()
