from src.exchange_subgraph import _responder_pt_br, busca_cotacao, exchange_app, extrai_moeda
from src.tools.exchange import ExchangeLookupError, ExchangeQuote, consultar_cotacao


class FakeToolCallLLM:
    """LLM fake que emite um tool_call de consultar_cotacao com a moeda dada."""

    def __init__(self, moeda):
        self.moeda = moeda
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def invoke(self, _messages):
        return type(
            "Response",
            (),
            {"tool_calls": [{"name": "consultar_cotacao", "args": {"moeda": self.moeda}, "id": "1"}]},
        )()


def _fake_quote(answer="1 USD equivale a 5,40 BRL.", source_url="https://example.com/usd"):
    def fake_search(moeda, moeda_base="BRL", **_kwargs):
        return ExchangeQuote(
            currency=moeda.upper(),
            base_currency=moeda_base.upper(),
            answer=answer,
            source_url=source_url,
        )

    return fake_search


def test_consultar_cotacao_tool_wraps_search(monkeypatch):
    captured = {}

    def fake_search(moeda, moeda_base="BRL", **_kwargs):
        captured["moeda"] = moeda
        return ExchangeQuote(currency=moeda, base_currency=moeda_base, answer="ok", source_url="https://x")

    monkeypatch.setattr("src.tools.exchange.search_exchange_rate", fake_search)

    result = consultar_cotacao.invoke({"moeda": "USD"})

    assert result == {"answer": "ok", "source_url": "https://x"}
    assert captured["moeda"] == "USD"
    assert consultar_cotacao.name == "consultar_cotacao"


def test_extrai_moeda_uses_tool_call_when_llm_available(monkeypatch):
    monkeypatch.setattr("src.exchange_subgraph.optional_chat_model", lambda *a, **k: FakeToolCallLLM("EUR"))

    out = extrai_moeda({"user_input": "qual a cotacao do euro?"})

    assert out["currency"] == "EUR"


def test_extrai_moeda_falls_back_to_regex_without_llm(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    out = extrai_moeda({"user_input": "queria saber do euro hoje"})

    assert out["currency"] == "EUR"


def test_busca_cotacao_returns_quote(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(
        "src.tools.exchange.search_exchange_rate",
        _fake_quote(answer="1 EUR equivale a 6,00 BRL.", source_url="https://example.com/eur"),
    )

    out = busca_cotacao({"currency": "EUR"})

    assert "1 EUR equivale a 6,00 BRL." in out["response"]
    assert "https://example.com/eur" in out["response"]


def test_busca_cotacao_handles_lookup_error(monkeypatch):
    def fake_search(*_args, **_kwargs):
        raise ExchangeLookupError("sem dados")

    monkeypatch.setattr("src.tools.exchange.search_exchange_rate", fake_search)

    out = busca_cotacao({"currency": "USD"})

    assert "Nao consegui consultar o cambio" in out["response"]


def test_exchange_app_end_to_end_offline(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("src.tools.exchange.search_exchange_rate", _fake_quote())

    out = exchange_app.invoke({"user_input": "qual a cotacao do dolar hoje?"})

    assert "5,40" in out["response"]


def test_extrai_moeda_fallback_maps_extra_currencies(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    assert extrai_moeda({"user_input": "cotacao do iene"})["currency"] == "JPY"
    assert extrai_moeda({"user_input": "quanto esta o franco suico?"})["currency"] == "CHF"
    assert extrai_moeda({"user_input": "valor do peso argentino"})["currency"] == "ARS"


def test_responder_pt_br_translates_with_llm(monkeypatch):
    class FakeLLM:
        def invoke(self, _messages):
            return type("R", (), {"content": "1 EUR equivale a 6,00 BRL hoje."})()

    monkeypatch.setattr("src.exchange_subgraph.optional_chat_model", lambda *a, **k: FakeLLM())

    assert _responder_pt_br("1 EUR equals 6.00 BRL") == "1 EUR equivale a 6,00 BRL hoje."


def test_responder_pt_br_keeps_original_without_llm(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    assert _responder_pt_br("1 EUR equals 6.00 BRL") == "1 EUR equals 6.00 BRL"
