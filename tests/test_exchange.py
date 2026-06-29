import pytest

from src.tools.exchange import (
    ExchangeConfigurationError,
    build_conversion_message,
    detect_conversion_direction,
    extract_conversion_amount,
    parse_unit_rate,
    search_exchange_rate,
)


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


def test_extracts_amount_from_mil_reais():
    assert extract_conversion_amount("100 mil reais em euro") == 100_000


def test_parses_unit_rate_from_quote_text():
    answer = "A cotacao atual para 1 EUR e de 5,92 BRL, valida para transacoes comerciais."
    assert parse_unit_rate(answer, "EUR") == pytest.approx(5.92)


def test_detects_brl_to_foreign_conversion():
    direction = detect_conversion_direction("Quanto que e 100 mil reais em euro?", "EUR")
    assert direction == "to_foreign"


def test_builds_conversion_message_for_brl_to_eur():
    message = build_conversion_message(
        amount=100_000,
        direction="to_foreign",
        currency="EUR",
        rate=5.92,
    )

    assert message is not None
    assert "R$ 100.000,00" in message
    assert "EUR" in message
    assert "16.891,89" in message
