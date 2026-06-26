import pytest

from src.tools.exchange import ExchangeConfigurationError, search_exchange_rate


class FakeTavilyClient:
    def __init__(self):
        self.query = None

    def search(self, query, **kwargs):
        self.query = query
        return {
            "answer": "1 USD equivale a aproximadamente 5,40 BRL.",
            "results": [
                {
                    "title": "Cotacao USD BRL",
                    "url": "https://example.com/usd-brl",
                }
            ],
        }


def test_searches_exchange_rate_with_tavily_client():
    client = FakeTavilyClient()

    quote = search_exchange_rate("USD", base_currency="BRL", client=client)

    assert "USD" in client.query
    assert "BRL" in client.query
    assert quote.answer == "1 USD equivale a aproximadamente 5,40 BRL."
    assert quote.source_url == "https://example.com/usd-brl"


def test_requires_tavily_key_when_client_is_not_injected(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with pytest.raises(ExchangeConfigurationError):
        search_exchange_rate("USD")
