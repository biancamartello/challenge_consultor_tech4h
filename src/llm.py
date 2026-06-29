from __future__ import annotations

import os
from functools import lru_cache


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"


class LLMConfigurationError(RuntimeError):
    """Raised when OpenRouter is not configured."""


def get_chat_model(temperature: float = 0):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise LLMConfigurationError("Configure OPENROUTER_API_KEY para usar o LLM.")

    return _get_cached_chat_model(
        model=os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL),
        api_key=api_key,
        temperature=temperature,
    )


def optional_chat_model(temperature: float = 0):
    """Retorna um chat model quando o OpenRouter esta configurado, senao None.

    Permite que os chamadores caiam em logica deterministica (regex/keywords)
    quando nao ha API key ou ocorre falha tecnica, mantendo o sistema testavel
    offline.
    """
    if not os.getenv("OPENROUTER_API_KEY"):
        return None
    try:
        return get_chat_model(temperature=temperature)
    except Exception:
        return None


@lru_cache(maxsize=8)
def _get_cached_chat_model(*, model: str, api_key: str, temperature: float):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        temperature=temperature,
    )
