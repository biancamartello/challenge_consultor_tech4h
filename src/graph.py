from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from src.conversation import (
    auth_success_response,
    credit_decision_response,
    credit_increase_guidance_response,
    credit_increase_not_possible_response,
    credit_interview_declined_response,
    credit_interview_offer_response,
    current_limit_response,
    interview_question_response,
    interview_reask_response,
    interview_result_response,
    missing_credentials_response,
)
from src.exchange_subgraph import exchange_app
from src.llm import optional_chat_model
from src.schemas import CreditInterviewAnswers, IntentResult, LimitIncreaseRequest
from src.state import AgentState, HistoryTurn, Intent
from src.tools.auth import authenticate_client
from src.tools.credit import get_client_by_cpf, get_current_limit, max_limit_for_score, request_credit_increase
from src.tools.scoring import calculate_credit_score, update_client_score


logger = logging.getLogger("banco_agil")

CLIENTS_PATH = Path("data/clientes.csv")
SCORE_LIMIT_PATH = Path("data/score_limite.csv")
REQUESTS_PATH = Path("data/solicitacoes_aumento_limite.csv")

INTERVIEW_FIELDS: tuple[str, ...] = (
    "renda_mensal",
    "tipo_emprego",
    "despesas",
    "dependentes",
    "tem_dividas",
)

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

AMOUNT_PROMPT = """Voce extrai o valor de limite de credito desejado pelo cliente do Banco Agil.
Entenda numeros por extenso, abreviacoes e formatos informais (ex: "cinco mil" = 5000, "5k" = 5000, "uns 8 mil reais" = 8000).
Responda somente com um JSON valido neste formato:
{"requested_limit": number_ou_null}
Use null se o cliente nao informou um valor."""


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
    return optional_chat_model()


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


# --- LLM-driven structured extraction (NLU) ------------------------------------


def extract_requested_limit(text: str, llm=None) -> float | None:
    model = llm if llm is not None else _optional_runtime_llm()
    if model is not None:
        value = _extract_amount_with_llm(text, model)
        if value is not None:
            return value
    return _extract_money(text)


def _extract_amount_with_llm(text: str, llm) -> float | None:
    try:
        response = llm.invoke([("system", AMOUNT_PROMPT), ("human", text)])
    except Exception:
        return None
    payload = _extract_json_object(str(getattr(response, "content", "")).strip())
    if not payload:
        return None
    raw = payload.get("requested_limit")
    if raw in (None, "", 0, 0.0):
        return None
    try:
        return LimitIncreaseRequest(requested_limit=float(raw)).requested_limit
    except Exception:
        return None


def extract_interview_field(field: str, text: str, llm=None):
    model = llm if llm is not None else _optional_runtime_llm()
    if model is not None:
        value = _extract_field_with_llm(field, text, model)
        if value is not None:
            return value
    return _extract_field_fallback(field, text)


def _field_prompt(field: str) -> str:
    descriptions = {
        "renda_mensal": "a renda mensal do cliente em reais (numero).",
        "tipo_emprego": "o tipo de emprego, normalizado para um destes: formal, autonomo, desempregado.",
        "despesas": "as despesas fixas mensais do cliente em reais (numero).",
        "dependentes": "o numero de dependentes (inteiro).",
        "tem_dividas": "se o cliente possui dividas ativas (true ou false).",
    }
    desc = descriptions.get(field, "o dado solicitado.")
    return (
        "Voce extrai dados de uma entrevista de credito do Banco Agil. "
        f"Extraia {desc} "
        'Responda somente com um JSON valido no formato {"value": valor_ou_null}. '
        "Use null se nao for possivel extrair."
    )


def _extract_field_with_llm(field: str, text: str, llm):
    try:
        response = llm.invoke([("system", _field_prompt(field)), ("human", text)])
    except Exception:
        return None
    payload = _extract_json_object(str(getattr(response, "content", "")).strip())
    if not payload or "value" not in payload:
        return None
    return _coerce_field(field, payload["value"])


def _coerce_field(field: str, raw):
    if raw is None:
        return None
    try:
        if field in {"renda_mensal", "despesas"}:
            return float(raw)
        if field == "dependentes":
            return int(raw)
        if field == "tipo_emprego":
            value = str(raw).strip().lower()
            return value if value in {"formal", "autonomo", "autônomo", "desempregado"} else None
        if field == "tem_dividas":
            if isinstance(raw, bool):
                return raw
            value = str(raw).strip().lower()
            if value in {"true", "sim", "1"}:
                return True
            if value in {"false", "nao", "não", "0"}:
                return False
            return None
    except (TypeError, ValueError):
        return None
    return None


def _extract_field_fallback(field: str, text: str):
    if field in {"renda_mensal", "despesas"}:
        return _extract_money(text)
    if field == "dependentes":
        return _first_int(text)
    if field == "tipo_emprego":
        return _find_employment(text)
    if field == "tem_dividas":
        return _find_debt_answer(text)
    return None


def interpret_affirmative(text: str, llm=None) -> bool | None:
    model = llm if llm is not None else _optional_runtime_llm()
    if model is not None:
        result = _affirmative_with_llm(text, model)
        if result is not None:
            return result
    return _affirmative_fallback(text)


def _affirmative_with_llm(text: str, llm) -> bool | None:
    prompt = (
        "O cliente respondeu a uma oferta (sim ou nao). "
        'Responda somente com JSON {"answer": "yes|no|unknown"}.'
    )
    try:
        response = llm.invoke([("system", prompt), ("human", text)])
    except Exception:
        return None
    payload = _extract_json_object(str(getattr(response, "content", "")).strip())
    if not payload:
        return None
    answer = str(payload.get("answer", "")).strip().lower()
    if answer == "yes":
        return True
    if answer == "no":
        return False
    return None


def _affirmative_fallback(text: str) -> bool | None:
    normalized = text.lower()
    if any(term in normalized for term in ["nao", "não", "depois", "agora nao", "agora não", "deixa", "negativo"]):
        return False
    if any(term in normalized for term in ["sim", "quero", "pode", "claro", "vamos", "bora", "aceito", "positivo", "isso"]):
        return True
    return None


# --- Routing -------------------------------------------------------------------


def route_after_triage(state: AgentState) -> str:
    if state.get("should_end") or not state.get("authenticated"):
        return "end"
    flow = state.get("active_flow") or ""
    if flow == "credit_interview":
        return "credit_interview"
    if flow == "credit_interview_offer":
        return "credit"
    if flow == "credit_increase":
        return "credit"
    intent = state.get("intent", "unknown")
    if intent in {"credit", "credit_interview", "exchange"}:
        return intent
    return "end"


def route_after_credit(state: AgentState) -> str:
    if state.get("active_flow") == "credit_interview":
        return "credit_interview"
    return "end"


# --- Nodes ---------------------------------------------------------------------


def _conversation_history(state: AgentState) -> list[HistoryTurn] | None:
    raw = state.get("conversation_history")
    if not raw:
        return None
    return list(raw)


def _client_name(state: AgentState) -> str | None:
    name = (state.get("client") or {}).get("nome", "").strip()
    return name or None


def triage_node(state: AgentState) -> AgentState:
    user_input = state.get("user_input", "")
    if _classify_intent_with_keywords(user_input) == "end":
        return {"should_end": True, "response": "Atendimento encerrado. Obrigado por falar com o Banco Agil."}

    if state.get("authenticated"):
        flow = state.get("active_flow") or ""
        if flow in {"credit_interview", "credit_interview_offer"}:
            return {}

        intent = classify_intent(user_input)
        if flow == "credit_increase" and intent not in {"exchange", "credit_interview", "end"}:
            return {"intent": intent}

        update: AgentState = {"intent": intent, "active_flow": ""}
        if intent == "unknown":
            update["response"] = (
                "Como posso ajudar agora? Posso ver seu limite, solicitar um aumento, "
                "fazer a entrevista de credito ou consultar a cotacao de uma moeda."
            )
        return update

    cpf = state.get("cpf") or _extract_cpf(user_input)
    birth_date = state.get("birth_date") or _extract_birth_date(user_input)
    if not cpf or not birth_date:
        missing_credentials_count = int(state.get("missing_credentials_count", 0)) + 1
        return {
            "cpf": cpf or "",
            "birth_date": birth_date or "",
            "authenticated": False,
            "missing_credentials_count": missing_credentials_count,
            "response": missing_credentials_response(
                has_cpf=bool(cpf),
                has_birth_date=bool(birth_date),
                greeting_detected=_looks_like_greeting(user_input),
                turn_count=missing_credentials_count,
                history=_conversation_history(state),
            ),
        }

    try:
        result = authenticate_client(cpf, birth_date, CLIENTS_PATH)
    except Exception:
        logger.exception("authentication failure")
        return {"response": "Tive um problema ao validar seus dados agora. Pode tentar novamente em instantes?"}

    if result.authenticated:
        return {
            "cpf": cpf,
            "birth_date": birth_date,
            "authenticated": True,
            "auth_attempts": 0,
            "client": result.client or {},
            "intent": "unknown",
            "response": auth_success_response(
                (result.client or {}).get("nome"),
                history=_conversation_history(state),
            ),
        }

    attempts = int(state.get("auth_attempts", 0)) + 1
    if attempts >= 3:
        return {
            "authenticated": False,
            "auth_attempts": attempts,
            "should_end": True,
            "response": "Os dados informados nao conferem com o nosso cadastro. Por seguranca, vou encerrar o atendimento por aqui.",
        }
    return {
        "authenticated": False,
        "auth_attempts": attempts,
        "response": f"Os dados informados nao conferem com o nosso cadastro. Voce ainda tem {3 - attempts} tentativa(s). Pode revisar CPF e data de nascimento e me enviar novamente?",
    }


def credit_node(state: AgentState) -> AgentState:
    cpf = state.get("cpf") or state.get("client", {}).get("cpf")
    if not cpf:
        return {"response": "Nao encontrei um cadastro autenticado para consultar credito."}

    user_input = state.get("user_input", "")
    flow = state.get("active_flow") or ""

    if flow == "credit_interview_offer":
        wants = interpret_affirmative(user_input)
        if wants is True:
            return {"active_flow": "credit_interview", "interview_answers": {}, "interview_pending_field": ""}
        if wants is False:
            return {"active_flow": "", "credit_status": "", "response": credit_interview_declined_response(history=_conversation_history(state), client_name=_client_name(state))}
        return {"response": credit_interview_offer_response(history=_conversation_history(state), client_name=_client_name(state))}

    try:
        requested_limit = extract_requested_limit(user_input)
        credit_action = _classify_credit_action(user_input, requested_limit=requested_limit, active_flow=flow)

        if credit_action == "increase_limit":
            if not requested_limit:
                current_limit = get_current_limit(cpf, CLIENTS_PATH)
                max_allowed = _max_allowed_limit_for_client(cpf)
                if max_allowed is not None and max_allowed <= current_limit:
                    return {
                        "active_flow": "credit_interview_offer",
                        "credit_status": "rejeitado",
                        "response": credit_increase_not_possible_response(
                            current_limit=current_limit,
                            history=_conversation_history(state),
                            client_name=_client_name(state),
                        ),
                    }
                return {
                    "active_flow": "credit_increase",
                    "response": credit_increase_guidance_response(
                        current_limit=current_limit,
                        max_allowed_limit=max_allowed,
                        history=_conversation_history(state),
                        client_name=_client_name(state),
                    ),
                }

            decision = request_credit_increase(
                cpf,
                requested_limit,
                CLIENTS_PATH,
                SCORE_LIMIT_PATH,
                REQUESTS_PATH,
            )
            if decision.status == "aprovado":
                return {
                    "credit_status": "aprovado",
                    "requested_limit": decision.requested_limit,
                    "active_flow": "",
                    "response": credit_decision_response(
                        requested_limit=decision.requested_limit,
                        status="aprovado",
                        history=_conversation_history(state),
                        client_name=_client_name(state),
                    ),
                }
            return {
                "credit_status": "rejeitado",
                "requested_limit": decision.requested_limit,
                "active_flow": "credit_interview_offer",
                "response": credit_decision_response(
                    requested_limit=decision.requested_limit,
                    status="rejeitado",
                    history=_conversation_history(state),
                    client_name=_client_name(state),
                ),
            }

        current_limit = get_current_limit(cpf, CLIENTS_PATH)
        return {
            "active_flow": "credit_increase",
            "response": current_limit_response(
                current_limit=current_limit,
                history=_conversation_history(state),
                client_name=_client_name(state),
            ),
        }
    except Exception:
        logger.exception("credit_node failure")
        return {"response": "Tive um problema ao acessar seus dados de credito agora. Pode tentar novamente em instantes?"}


def credit_interview_node(state: AgentState) -> AgentState:
    cpf = state.get("cpf") or state.get("client", {}).get("cpf")
    if not cpf:
        return {"response": "Nao encontrei um cadastro autenticado para a entrevista."}

    answers = dict(state.get("interview_answers") or {})
    pending = state.get("interview_pending_field") or ""
    user_input = state.get("user_input", "")

    try:
        if pending:
            value = extract_interview_field(pending, user_input)
            if value is None:
                return {"response": interview_reask_response(pending, history=_conversation_history(state), client_name=_client_name(state))}
            answers[pending] = value

        next_field = next((field for field in INTERVIEW_FIELDS if field not in answers), None)
        if next_field is not None:
            return {
                "active_flow": "credit_interview",
                "interview_answers": answers,
                "interview_pending_field": next_field,
                "response": interview_question_response(next_field, history=_conversation_history(state), client_name=_client_name(state)),
            }

        validated = CreditInterviewAnswers(
            renda_mensal=answers["renda_mensal"],
            tipo_emprego=answers["tipo_emprego"],
            despesas=answers["despesas"],
            dependentes=answers["dependentes"],
            tem_dividas=answers["tem_dividas"],
        )
        new_score = calculate_credit_score(
            renda_mensal=validated.renda_mensal,
            tipo_emprego=validated.tipo_emprego,
            despesas=validated.despesas,
            dependentes=validated.dependentes,
            tem_dividas=validated.tem_dividas,
        )
        update_client_score(cpf, new_score, CLIENTS_PATH)
        return {
            "active_flow": "",
            "interview_answers": {},
            "interview_pending_field": "",
            "credit_status": "",
            "requested_limit": 0,
            "intent": "credit",
            "response": interview_result_response(
                new_score=new_score,
                history=_conversation_history(state),
                client_name=_client_name(state),
            ),
        }
    except Exception:
        logger.exception("credit_interview_node failure")
        return {"response": "Tive um problema ao processar a entrevista agora. Podemos tentar de novo?"}


def exchange_node(state: AgentState) -> AgentState:
    out = exchange_app.invoke({"user_input": state.get("user_input", "")})
    return {"response": out["response"]}


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
    graph.add_conditional_edges(
        "credit",
        route_after_credit,
        {
            "credit_interview": "credit_interview",
            "end": END,
        },
    )
    graph.add_edge("credit_interview", END)
    graph.add_edge("exchange", END)
    graph.add_edge("end", END)
    return graph.compile()


def _classify_credit_action(
    text: str,
    *,
    requested_limit: float | None,
    active_flow: str | None,
) -> str:
    if active_flow == "credit_increase":
        return "increase_limit"
    if _has_increase_terms(text.lower()):
        return "increase_limit"
    return "consult_limit"


def _has_increase_terms(normalized_text: str) -> bool:
    return any(
        term in normalized_text
        for term in [
            "aument",
            "maior",
            "elevar",
            "subir meu limite",
            "subir o limite",
            "poder de compra",
            "como faco pra aumentar",
            "como faço pra aumentar",
            "solicitar aumento",
        ]
    )


def _max_allowed_limit_for_client(cpf: str) -> float | None:
    try:
        client = get_client_by_cpf(cpf, CLIENTS_PATH)
        return max_limit_for_score(int(float(client["score"])), SCORE_LIMIT_PATH)
    except Exception:
        return None


def _extract_cpf(text: str) -> str | None:
    match = re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", text)
    return match.group(0) if match else None


def _extract_birth_date(text: str) -> str | None:
    match = re.search(r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4}", text)
    return match.group(0) if match else None


def _extract_money(text: str) -> float | None:
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


def _first_int(text: str) -> int | None:
    normalized = text.lower()
    words = {
        "nenhum": 0,
        "nenhuma": 0,
        "zero": 0,
        "um": 1,
        "uma": 1,
        "dois": 2,
        "duas": 2,
        "tres": 3,
        "três": 3,
        "quatro": 4,
        "cinco": 5,
    }
    for word, value in words.items():
        if re.search(r"\b" + word + r"\b", normalized):
            return value
    match = re.search(r"\b(\d+)\b", normalized)
    return int(match.group(1)) if match else None


def _find_employment(text: str) -> str | None:
    normalized = text.lower()
    for employment in ["formal", "autonomo", "autônomo", "desempregado"]:
        if employment in normalized:
            return employment
    return None


def _find_debt_answer(text: str) -> bool | None:
    normalized = text.lower()
    if any(term in normalized for term in ["nao", "não", "sem divida", "sem dívida", "nenhuma divida", "nenhuma dívida"]):
        return False
    if any(term in normalized for term in ["sim", "tenho", "possuo", "com divida", "com dívida"]):
        return True
    return None


def _looks_like_greeting(text: str) -> bool:
    normalized = text.lower()
    return any(
        term in normalized
        for term in ["oi", "ola", "olá", "eai", "e aí", "tudo bem", "bom dia", "boa tarde", "boa noite"]
    )
