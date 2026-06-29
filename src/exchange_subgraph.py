"""Subgrafo de cambio do Banco Agil.

Modela o "Agente de Cambio" como um subgrafo LangGraph composto de dois nos:

- ``extrai_moeda``: usa tool-calling (``bind_tools``) para o LLM decidir a moeda
  que o cliente quer; cai num fallback deterministico por regex quando nao ha
  LLM configurado (ou quando o modelo nao emite ``tool_calls``).
- ``busca_cotacao``: executa a tool ``consultar_cotacao`` (Tavily por baixo) sob
  ``try/except``, mantendo a regra deterministica e o tratamento de erro no Python.
"""

from __future__ import annotations

import logging
import re
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from src.conversation import exchange_response
from src.llm import optional_chat_model
from src.tools.exchange import (
    ExchangeConfigurationError,
    ExchangeLookupError,
    consultar_cotacao,
)


logger = logging.getLogger("banco_agil")


CURRENCY_TOOL_PROMPT = (
    "Voce e o agente de cambio do Banco Agil. Quando o cliente perguntar sobre a "
    "cotacao de qualquer moeda, chame a tool consultar_cotacao informando o codigo "
    "ISO de 3 letras da moeda citada (ex.: dolar=USD, euro=EUR, libra=GBP, iene=JPY, "
    "peso argentino=ARS, franco suico=CHF, dolar canadense=CAD). Para qualquer outra "
    "moeda, use o codigo ISO de 3 letras correspondente. Se nenhuma moeda for citada, "
    "use USD. Nao invente a cotacao: sempre acione a tool."
)

# Reescreve a resposta da Tavily (que vem em ingles) para pt-BR, preservando numeros.
RESPONSE_PT_PROMPT = (
    "Voce e a atendente de cambio do Banco Agil. Reescreva em portugues do Brasil, de "
    "forma curta e cordial, a informacao de cotacao a seguir. PRESERVE exatamente os "
    "valores numericos, as moedas e as taxas como aparecem no texto original: nao "
    "recalcule, nao arredonde e nao invente numeros. Responda apenas com a frase final, "
    "sem listas nem formatacao."
)


class ExchangeState(TypedDict, total=False):
    user_input: str
    currency: str
    response: str


_CURRENCY_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("euro", "eur"), "EUR"),
    (("libra", "esterlina", "gbp"), "GBP"),
    (("iene", "yen", "jpy"), "JPY"),
    (("franco", "suico", "suíço", "chf"), "CHF"),
    (("peso argentino", "ars"), "ARS"),
    (("dolar canadense", "dólar canadense", "cad"), "CAD"),
    (("dolar", "dólar", "usd"), "USD"),
)


def _extract_currency(text: str) -> str:
    normalized = text.lower()
    for terms, code in _CURRENCY_KEYWORDS:
        if any(term in normalized for term in terms):
            return code
    match = re.search(r"\b[A-Z]{3}\b", text.upper())
    return match.group(0) if match else "USD"


def _currency_from_tool_call(user_input: str, model) -> str | None:
    try:
        bound = model.bind_tools([consultar_cotacao])
        response = bound.invoke([("system", CURRENCY_TOOL_PROMPT), ("human", user_input)])
    except Exception:
        return None
    tool_calls = getattr(response, "tool_calls", None) or []
    if not tool_calls:
        return None
    moeda = (tool_calls[0].get("args") or {}).get("moeda")
    return str(moeda).upper() if moeda else None


def extrai_moeda(state: ExchangeState) -> ExchangeState:
    user_input = state.get("user_input", "")
    model = optional_chat_model()
    if model is not None:
        currency = _currency_from_tool_call(user_input, model)
        if currency is not None:
            return {"currency": currency}
    return {"currency": _extract_currency(user_input)}


def _responder_pt_br(answer: str) -> str:
    """Reescreve o texto da cotacao (em ingles) para pt-BR preservando os numeros.

    Usa temperatura 0 e instrucao explicita de nao alterar valores. Se nao houver LLM
    configurado (offline/testes) ou ocorrer falha, retorna o texto original intacto.
    """
    model = optional_chat_model()
    if model is None:
        return answer
    try:
        response = model.invoke([("system", RESPONSE_PT_PROMPT), ("human", answer)])
    except Exception:
        return answer
    text = str(getattr(response, "content", "")).strip()
    return text or answer


def busca_cotacao(state: ExchangeState) -> ExchangeState:
    currency = state.get("currency") or "USD"
    try:
        result = consultar_cotacao.invoke({"moeda": currency})
    except (ExchangeConfigurationError, ExchangeLookupError) as exc:
        logger.warning("exchange lookup failed: %s", exc)
        return {"response": f"Nao consegui consultar o cambio agora: {exc}"}
    except Exception:
        logger.exception("exchange subgraph failure")
        return {"response": "Tive um problema ao consultar a cotacao agora. Pode tentar novamente em instantes?"}
    return {"response": exchange_response(answer=_responder_pt_br(result["answer"]), source=result["source_url"] or "Tavily")}


def _build_exchange_app():
    graph = StateGraph(ExchangeState)
    graph.add_node("extrai_moeda", extrai_moeda)
    graph.add_node("busca_cotacao", busca_cotacao)
    graph.add_edge(START, "extrai_moeda")
    graph.add_edge("extrai_moeda", "busca_cotacao")
    graph.add_edge("busca_cotacao", END)
    return graph.compile()


exchange_app = _build_exchange_app()
