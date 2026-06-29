from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from langchain_core.tools import tool


ConversionDirection = Literal["quote_only", "to_foreign", "to_base"]

_CURRENCY_TERMS: dict[str, tuple[str, ...]] = {
    "USD": ("dolar", "dólar", "usd"),
    "EUR": ("euro", "eur"),
    "GBP": ("libra", "esterlina", "gbp"),
    "JPY": ("iene", "yen", "jpy"),
    "CHF": ("franco", "suico", "suíço", "chf"),
    "ARS": ("peso argentino", "ars"),
    "CAD": ("dolar canadense", "dólar canadense", "cad"),
}


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


def extract_conversion_amount(text: str) -> float | None:
    normalized = text.lower()
    match = re.search(r"(?:r\$\s*)?(\d+(?:[.,]\d{1,2})?)\s*k\b", normalized)
    if match:
        return float(match.group(1).replace(",", ".")) * 1000

    match = re.search(r"(?:r\$\s*)?(\d+(?:[.,]\d{1,2})?)\s*mil\b", normalized)
    if match:
        return float(match.group(1).replace(",", ".")) * 1000

    match = re.search(r"(?:r\$\s*)?(\d+(?:[.,]\d{2})?)", normalized)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def parse_unit_rate(answer: str, currency: str, base_currency: str = "BRL") -> float | None:
    text = answer.replace(",", ".")
    curr = re.escape(currency.upper())
    base = re.escape(base_currency.upper())
    patterns = (
        rf"1\s*{curr}\s*(?:=|equivale?\s*a?|is|:)\s*([\d.]+)\s*{base}",
        rf"1\s*{curr}\s*(?:=|equivale?\s*a?|is|:)\s*([\d.]+)",
        rf"{curr}[^\d]*([\d.]+)\s*{base}",
        rf"([\d.]+)\s*{base}[^\d]*{curr}",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            rate = float(match.group(1))
        except ValueError:
            continue
        if rate > 0:
            return rate
    return None


def detect_conversion_direction(text: str, currency: str) -> ConversionDirection:
    if extract_conversion_amount(text) is None:
        return "quote_only"

    normalized = text.lower()
    foreign_terms = _CURRENCY_TERMS.get(currency.upper(), (currency.lower(),))
    brl_terms = ("reais", "real", "brl", "r$")
    has_brl = any(term in normalized for term in brl_terms)
    has_foreign = any(term in normalized for term in foreign_terms)

    to_foreign_patterns = (
        r"(reais?|r\$|brl).*(?:em|para|pra)\s*(?:o\s+|a\s+)?(" + "|".join(map(re.escape, foreign_terms)) + r")",
        r"(\d[\d.,]*\s*(?:mil|k)?).*(?:em|para|pra)\s*(?:o\s+|a\s+)?(" + "|".join(map(re.escape, foreign_terms)) + r")",
    )
    to_base_patterns = (
        r"(" + "|".join(map(re.escape, foreign_terms)) + r").*(?:em|para|pra)\s*(?:o\s+|os\s+)?(reais?|r\$|brl)",
    )

    if has_brl and has_foreign:
        brl_pos = min(normalized.find(term) for term in brl_terms if term in normalized)
        foreign_pos = min(normalized.find(term) for term in foreign_terms if term in normalized)
        return "to_foreign" if brl_pos < foreign_pos else "to_base"

    if any(re.search(pattern, normalized) for pattern in to_foreign_patterns):
        return "to_foreign"
    if any(re.search(pattern, normalized) for pattern in to_base_patterns):
        return "to_base"
    if has_foreign:
        return "to_foreign"
    return "quote_only"


def format_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_foreign(value: float, currency: str) -> str:
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} {currency.upper()}"


def build_conversion_message(
    *,
    amount: float,
    direction: ConversionDirection,
    currency: str,
    rate: float,
) -> str | None:
    if direction == "quote_only":
        return None
    if direction == "to_foreign":
        converted = amount / rate
        return (
            f"Com essa cotacao, {format_brl(amount)} equivalem a aproximadamente "
            f"{format_foreign(converted, currency)}."
        )
    converted = amount * rate
    return (
        f"Com essa cotacao, {format_foreign(amount, currency)} equivalem a aproximadamente "
        f"{format_brl(converted)}."
    )
