from __future__ import annotations

import os
from dataclasses import dataclass

from langchain_core.tools import tool


@dataclass(frozen=True)
class ExchangeQuote:
    currency: str
    base_currency: str
    answer: str
    source_url: str | None = None


class ExchangeConfigurationError(RuntimeError):
    """Raised when Tavily cannot be configured."""


class ExchangeLookupError(RuntimeError):
    """Raised when the quote search returns no usable information."""


def build_exchange_query(currency: str, base_currency: str = "BRL") -> str:
    return f"cotacao atual {currency.upper()} para {base_currency.upper()} hoje"


def search_exchange_rate(
    currency: str,
    base_currency: str = "BRL",
    *,
    client=None,
    api_key: str | None = None,
) -> ExchangeQuote:
    tavily_client = client or _build_tavily_client(api_key)
    query = build_exchange_query(currency, base_currency)
    response = tavily_client.search(
        query,
        search_depth="basic",
        max_results=3,
        include_answer="basic",
    )

    answer = response.get("answer")
    results = response.get("results") or []
    source_url = results[0].get("url") if results else None

    if not answer and results:
        answer = results[0].get("content") or results[0].get("title")
    if not answer:
        raise ExchangeLookupError("Nao foi possivel obter cotacao pela Tavily.")

    return ExchangeQuote(
        currency=currency.upper(),
        base_currency=base_currency.upper(),
        answer=answer,
        source_url=source_url,
    )


def _build_tavily_client(api_key: str | None = None):
    resolved_key = api_key or os.getenv("TAVILY_API_KEY")
    if not resolved_key:
        raise ExchangeConfigurationError("Configure TAVILY_API_KEY para usar cambio.")

    from tavily import TavilyClient

    return TavilyClient(api_key=resolved_key)


@tool
def consultar_cotacao(moeda: str, moeda_base: str = "BRL") -> dict:
    """Consulta a cotacao atual de QUALQUER moeda estrangeira em tempo real (via Tavily).

    Chame esta tool sempre que o cliente pedir a cotacao ou o valor de uma moeda.
    Em `moeda`, informe o codigo ISO de 3 letras correspondente ao que o cliente
    citou: dolar -> USD, euro -> EUR, libra -> GBP, iene -> JPY, peso argentino ->
    ARS, franco suico -> CHF, dolar canadense -> CAD. Para qualquer outra moeda, use
    o codigo ISO de 3 letras adequado. Se o cliente nao especificar, use USD.
    Nao invente a cotacao: sempre acione a tool.

    Args:
        moeda: codigo ISO de 3 letras da moeda desejada (ex.: USD, EUR, GBP, JPY, CHF).
        moeda_base: codigo ISO da moeda base da conversao (default BRL).
    """
    quote = search_exchange_rate(moeda, moeda_base)
    return {"answer": quote.answer, "source_url": quote.source_url}
