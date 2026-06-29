import sys
from types import SimpleNamespace

from src import llm


def test_get_chat_model_reuses_cached_client(monkeypatch):
    class FakeChatOpenAI:
        calls = 0

        def __init__(self, **_kwargs):
            FakeChatOpenAI.calls += 1

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
    monkeypatch.setitem(sys.modules, "langchain_openai", SimpleNamespace(ChatOpenAI=FakeChatOpenAI))

    llm._get_cached_chat_model.cache_clear()

    first = llm.get_chat_model(temperature=0.7)
    second = llm.get_chat_model(temperature=0.7)

    assert first is second
    assert FakeChatOpenAI.calls == 1
