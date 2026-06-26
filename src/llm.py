from __future__ import annotations

import os


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-chat"


class LLMConfigurationError(RuntimeError):
    """Raised when OpenRouter is not configured."""


def get_chat_model():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise LLMConfigurationError("Configure OPENROUTER_API_KEY para usar o LLM.")

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL),
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        temperature=0,
    )
