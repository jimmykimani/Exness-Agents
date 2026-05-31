from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from typing import Type, TypeVar, List
import json
import os

from config.settings import GEMINI_MODEL_ANALYSIS, GEMINI_MODEL_SPEED
from utils.logger import get_agent_logger

log = get_agent_logger("LLM_UTILS")


class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        import numpy as np
        import pandas as pd
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, pd.Timestamp):
            return str(obj)
        return super(NpEncoder, self).default(obj)


def safe_json_dumps(obj) -> str:
    return json.dumps(obj, indent=2, cls=NpEncoder)


# ─── Dual API Key Pool ─────────────────────────────────────────────────────────
# Loads GEMINI_API_KEY (primary) and GEMINI_API_KEY_2 (fallback) from .env.
# On a 429 RESOURCE_EXHAUSTED, automatically retries with the other key.

def _load_api_keys() -> List[str]:
    """Load all configured Gemini API keys (primary + fallbacks)."""
    keys = []
    # Primary key
    k1 = os.getenv("GEMINI_API_KEY", "")
    if k1:
        keys.append(k1)
    # Secondary / fallback key
    k2 = os.getenv("GEMINI_API_KEY_2", "")
    if k2 and k2 != k1:
        keys.append(k2)
    # Tertiary key
    k3 = os.getenv("GEMINI_API_KEY_3", "")
    if k3 and k3 not in keys:
        keys.append(k3)
    if not keys:
        log.warning("No Gemini API keys configured!")
    return keys


_API_KEYS: List[str] = _load_api_keys()
_current_key_index: int = 0


def _get_next_key() -> str:
    """Round-robin through available API keys."""
    global _current_key_index
    if not _API_KEYS:
        return ""
    key = _API_KEYS[_current_key_index % len(_API_KEYS)]
    _current_key_index = (_current_key_index + 1) % len(_API_KEYS)
    return key


T = TypeVar("T", bound=BaseModel)


def get_llm(model_name: str = GEMINI_MODEL_ANALYSIS, temperature: float = 0.0,
            api_key: str = None) -> ChatGoogleGenerativeAI:
    """Returns a configured Gemini Chat model."""
    key = api_key or (_API_KEYS[0] if _API_KEYS else "")
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=key,
        temperature=temperature
    )


def query_llm_structured(
    system_prompt: str,
    user_content: str,
    output_schema: Type[T],
    fast_mode: bool = False
) -> T:
    """
    Queries Gemini and forces the output into the provided Pydantic schema.
    Automatically rotates to fallback API key on 429 RESOURCE_EXHAUSTED.
    """
    model_name = GEMINI_MODEL_SPEED if fast_mode else GEMINI_MODEL_ANALYSIS
    messages = [
        ("system", system_prompt),
        ("human", user_content)
    ]

    last_error = None
    # Try each key in the pool once
    for attempt in range(max(1, len(_API_KEYS))):
        key = _API_KEYS[attempt % len(_API_KEYS)] if _API_KEYS else ""
        try:
            llm = get_llm(model_name=model_name, api_key=key)
            structured_llm = llm.with_structured_output(output_schema)
            response = structured_llm.invoke(messages)
            # Success — note which key worked
            if attempt > 0:
                log.info(f"LLM fallback key #{attempt + 1} succeeded")
            return response
        except Exception as e:
            last_error = e
            err_str = str(e)
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                key_preview = f"...{key[-8:]}" if len(key) > 8 else key
                log.warning(f"Key #{attempt + 1} ({key_preview}) quota exhausted — trying next key")
                continue
            # Non-quota error — re-raise immediately
            raise

    # All keys exhausted
    raise last_error
