from __future__ import annotations

import json
import os
import re
from pathlib import Path

from src.llm import get_chat_model
from src.schemas import IntentResult
from src.state import AgentState, Intent
from src.tools.auth import authenticate_client
from src.tools.credit import get_current_limit, request_credit_increase
from src.tools.exchange import ExchangeConfigurationError, ExchangeLookupError, search_exchange_rate
from src.tools.scoring import calculate_credit_score, update_client_score


CLIENTS_PATH = Path("data/clientes.csv")
SCORE_LIMIT_PATH = Path("data/score_limite.csv")
REQUESTS_PATH = Path("data/solicitacoes_aumento_limite.csv")


VALID_INTENTS: tuple[Intent, ...] = ("credit_interview", "exchange", "credit", "end", "unknown")
INTENT_CLASSIFIER_PROMPT = """Voce e o agente de triagem do Banco Agil.
Classifique a intencao do cliente em exatamente uma das opcoes:

- credit: consultar limite, pedir aumento de limite, cartao, poder de compra, credito.
- credit_interview: recalcular score, atualizar dados financeiros, fazer entrevista de credito.
- exchange: cotacao de moeda, dolar, euro, cambio.
- end: encerrar, sair, finalizar atendimento.
- unknown: fora do escopo ou insuficiente.

Responda somente com um JSON valido neste formato:
{"intent": "credit|credit_interview|exchange|end|unknown", "confidence": 0.0}
Nao inclua texto fora do JSON."""


def classify_intent(text: str, llm=None) -> Intent:
    model = llm or _optional_runtime_llm()
    if model:
        intent = _classify_intent_with_llm(text, model)
        if intent is not None:
            return intent

    return _classify_intent_with_keywords(text)


def _classify_intent_with_keywords(text: str) -> Intent:
    normalized = text.lower()
    if any(term in normalized for term in ["encerrar", "sair", "tchau", "finalizar"]):
        return "end"
    if any(term in normalized for term in ["cotacao", "cotação", "dolar", "dólar", "euro", "cambio", "câmbio"]):
        return "exchange"
    if any(term in normalized for term in ["entrevista", "score", "recalcular"]):
        return "credit_interview"
    if any(term in normalized for term in ["limite", "credito", "crédito", "aumento"]):
        return "credit"
    return "unknown"


def _optional_runtime_llm():
    if not os.getenv("OPENROUTER_API_KEY"):
        return None
    try:
        return get_chat_model()
    except Exception:
        return None


def _classify_intent_with_llm(text: str, llm) -> Intent | None:
    messages = [
        ("system", INTENT_CLASSIFIER_PROMPT),
        ("human", text),
    ]

    try:
        response = llm.invoke(messages)
    except Exception:
        return None

    return _intent_from_model_content(str(getattr(response, "content", "")).strip())


def _intent_from_model_content(content: str) -> Intent | None:
    payload = _extract_json_object(content)
    if not payload:
        return _intent_from_plain_text(content)
    try:
        result = IntentResult.model_validate(payload)
    except Exception:
        return None
    return result.intent if result.confidence >= 0.5 else "unknown"


def _extract_json_object(content: str) -> dict | None:
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None


def _intent_from_plain_text(content: str) -> Intent | None:
    normalized = content.strip().lower()
    for intent in VALID_INTENTS:
        if normalized == intent:
            return intent
    return None


def route_after_triage(state: AgentState) -> str:
    if state.get("should_end") or not state.get("authenticated"):
        return "end"
    intent = state.get("intent", "unknown")
    if intent in {"credit", "credit_interview", "exchange"}:
        return intent
    return "end"


def triage_node(state: AgentState) -> AgentState:
    user_input = state.get("user_input", "")
    if _classify_intent_with_keywords(user_input) == "end":
        return {"should_end": True, "response": "Atendimento encerrado. Obrigado por falar com o Banco Agil."}

    if state.get("authenticated"):
        intent = classify_intent(user_input)
        return {
            "intent": intent,
            "response": "Como posso ajudar agora?" if intent == "unknown" else state.get("response", ""),
        }

    cpf = state.get("cpf") or _extract_cpf(user_input)
    birth_date = state.get("birth_date") or _extract_birth_date(user_input)
    if not cpf or not birth_date:
        return {
            "cpf": cpf or "",
            "birth_date": birth_date or "",
            "authenticated": False,
            "response": "Para comecar, informe seu CPF e data de nascimento.",
        }

    result = authenticate_client(cpf, birth_date, CLIENTS_PATH)
    if result.authenticated:
        return {
            "cpf": cpf,
            "birth_date": birth_date,
            "authenticated": True,
            "auth_attempts": 0,
            "client": result.client or {},
            "intent": "unknown",
            "response": "Autenticacao realizada. Como posso ajudar hoje?",
        }

    attempts = int(state.get("auth_attempts", 0)) + 1
    if attempts >= 3:
        return {
            "authenticated": False,
            "auth_attempts": attempts,
            "should_end": True,
            "response": "Nao foi possivel autenticar seus dados. Vou encerrar o atendimento por seguranca.",
        }
    return {
        "authenticated": False,
        "auth_attempts": attempts,
        "response": f"Dados nao conferem. Voce ainda tem {3 - attempts} tentativa(s).",
    }


def credit_node(state: AgentState) -> AgentState:
    cpf = state.get("cpf") or state.get("client", {}).get("cpf")
    if not cpf:
        return {"response": "Nao encontrei CPF autenticado para consultar credito."}

    requested_limit = state.get("requested_limit") or _extract_money(state.get("user_input", ""))
    if requested_limit:
        decision = request_credit_increase(
            cpf,
            requested_limit,
            CLIENTS_PATH,
            SCORE_LIMIT_PATH,
            REQUESTS_PATH,
        )
        if decision.status == "aprovado":
            response = (
                f"Seu pedido de aumento para R$ {decision.requested_limit:.2f} "
                "foi aprovado e registrado."
            )
        else:
            response = (
                f"Seu pedido de aumento para R$ {decision.requested_limit:.2f} foi rejeitado. "
                "Posso fazer uma entrevista de credito para tentar atualizar seu score."
            )
        return {"credit_status": decision.status, "response": response}

    current_limit = get_current_limit(cpf, CLIENTS_PATH)
    return {"response": f"Seu limite de credito atual e R$ {current_limit:.2f}."}


def credit_interview_node(state: AgentState) -> AgentState:
    answers = _extract_interview_answers(state.get("user_input", ""))
    if not answers:
        return {
            "response": (
                "Para recalcular seu score, informe renda, emprego, despesas, "
                "dependentes e se possui dividas."
            )
        }

    new_score = calculate_credit_score(**answers)
    cpf = state.get("cpf") or state.get("client", {}).get("cpf")
    if not cpf:
        return {"response": "Nao encontrei CPF autenticado para atualizar o score."}

    update_client_score(cpf, new_score, CLIENTS_PATH)
    return {
        "intent": "credit",
        "response": f"Seu score foi atualizado para {new_score}. Podemos tentar a analise de credito novamente.",
    }


def exchange_node(state: AgentState) -> AgentState:
    currency = _extract_currency(state.get("user_input", ""))
    try:
        quote = search_exchange_rate(currency)
    except (ExchangeConfigurationError, ExchangeLookupError) as exc:
        return {"response": f"Nao consegui consultar o cambio agora: {exc}"}
    return {"response": f"{quote.answer} Fonte: {quote.source_url or 'Tavily'}"}


def end_node(state: AgentState) -> AgentState:
    return {"response": state.get("response") or "Atendimento finalizado."}


def build_graph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(AgentState)
    graph.add_node("triage", triage_node)
    graph.add_node("credit", credit_node)
    graph.add_node("credit_interview", credit_interview_node)
    graph.add_node("exchange", exchange_node)
    graph.add_node("end", end_node)

    graph.add_edge(START, "triage")
    graph.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "credit": "credit",
            "credit_interview": "credit_interview",
            "exchange": "exchange",
            "end": "end",
        },
    )
    graph.add_edge("credit", END)
    graph.add_edge("credit_interview", END)
    graph.add_edge("exchange", END)
    graph.add_edge("end", END)
    return graph.compile()


def _extract_cpf(text: str) -> str | None:
    match = re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", text)
    return match.group(0) if match else None


def _extract_birth_date(text: str) -> str | None:
    match = re.search(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}", text)
    return match.group(0) if match else None


def _extract_money(text: str) -> float | None:
    match = re.search(r"(?:r\$\s*)?(\d+(?:[.,]\d{2})?)", text.lower())
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _extract_currency(text: str) -> str:
    normalized = text.lower()
    if "euro" in normalized or "eur" in normalized:
        return "EUR"
    if "libra" in normalized or "gbp" in normalized:
        return "GBP"
    match = re.search(r"\b[A-Z]{3}\b", text.upper())
    return match.group(0) if match else "USD"


def _extract_interview_answers(text: str) -> dict[str, float | int | str | bool] | None:
    renda = _find_number_after(text, "renda")
    despesas = _find_number_after(text, "despesas")
    dependentes = _find_number_after(text, "dependentes")
    emprego = _find_employment(text)
    has_debt = _find_debt_answer(text)
    if renda is None or despesas is None or dependentes is None or emprego is None or has_debt is None:
        return None
    return {
        "renda_mensal": renda,
        "tipo_emprego": emprego,
        "despesas": despesas,
        "dependentes": int(dependentes),
        "tem_dividas": has_debt,
    }


def _find_number_after(text: str, label: str) -> float | None:
    match = re.search(label + r"\D+(\d+(?:[.,]\d{1,2})?)", text.lower())
    return float(match.group(1).replace(",", ".")) if match else None


def _find_employment(text: str) -> str | None:
    normalized = text.lower()
    for employment in ["formal", "autonomo", "autônomo", "desempregado"]:
        if employment in normalized:
            return employment
    return None


def _find_debt_answer(text: str) -> bool | None:
    normalized = text.lower()
    if "dividas nao" in normalized or "dívidas não" in normalized or "sem dividas" in normalized:
        return False
    if "dividas sim" in normalized or "dívidas sim" in normalized or "com dividas" in normalized:
        return True
    return None
