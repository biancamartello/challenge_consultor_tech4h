from __future__ import annotations

import re

from src.llm import get_chat_model
from src.observability import sanitize_text
from src.state import HistoryTurn


DEFAULT_MAX_HISTORY_MESSAGES = 10

HUMANIZED_SYSTEM_PROMPT = """Voce e uma atendente digital do Banco Agil.
Fale em portugues do Brasil, com energia, acolhimento e naturalidade.
Nao seja robotico. Responda como uma pessoa de atendimento bancaria cordial.
Seja breve, mas calorosa. Nao invente dados. Nao peca informacoes alem das necessarias.
Nunca invente nomes de clientes. Se um nome oficial for informado na instrucao, use somente esse.
Use o historico recente da conversa, quando fornecido, para manter continuidade natural.
Nao repita saudacoes se o atendimento ja comecou. Nao reinicie do zero."""


def build_short_history(
    messages: list[dict[str, str]],
    *,
    max_messages: int = DEFAULT_MAX_HISTORY_MESSAGES,
) -> list[HistoryTurn]:
    selected = messages[-max_messages:] if len(messages) > max_messages else messages
    history: list[HistoryTurn] = []
    for message in selected:
        role = message.get("role", "")
        content = message.get("content", "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        content = content.replace("\\$", "$")
        history.append((role, sanitize_text(content)))
    return history


def welcome_response(*, history: list[HistoryTurn] | None = None) -> str:
    return _humanize(
        template_id="initial_greeting",
        instruction=(
            "Crie uma saudacao inicial calorosa para o Banco Agil. "
            "Diga que esta animada para ajudar e peca CPF e data de nascimento para comecar com seguranca."
        ),
        fallback=(
            "Oie! Que bom ter voce por aqui. Estou animada para te ajudar no Banco Agil. "
            "Para comecarmos com seguranca, me envie seu CPF e sua data de nascimento, por favor."
        ),
        history=history,
    )


def missing_credentials_response(
    *,
    has_cpf: bool,
    has_birth_date: bool,
    greeting_detected: bool,
    turn_count: int,
    history: list[HistoryTurn] | None = None,
) -> str:
    missing = []
    if not has_cpf:
        missing.append("CPF")
    if not has_birth_date:
        missing.append("data de nascimento")
    missing_text = " e ".join(missing)
    greeting_context = "A pessoa cumprimentou antes de informar os dados." if greeting_detected else ""
    return _humanize(
        template_id="missing_credentials",
        instruction=(
            f"{greeting_context} Responda ao cumprimento com simpatia e explique que, "
            f"para proteger a conta, voce precisa de: {missing_text}. "
            "Convide a pessoa a enviar esses dados de um jeito leve."
        ),
        fallback=_missing_credentials_fallback(missing_text, greeting_detected, turn_count),
        history=history,
    )


def auth_success_response(
    client_name: str | None = None,
    *,
    history: list[HistoryTurn] | None = None,
) -> str:
    fallback_name = f", {client_name}" if client_name else ""
    return _humanize(
        template_id="auth_success",
        instruction=(
            "A autenticacao foi bem-sucedida. Agradeca pelos dados, "
            "transmita seguranca e pergunte como pode ajudar hoje no Banco Agil."
        ),
        fallback=(
            f"Perfeito{fallback_name}, obrigada por confirmar seus dados. "
            "Ja esta tudo certo por aqui. Como posso te ajudar hoje no Banco Agil?"
        ),
        history=history,
        client_name=client_name,
    )


def current_limit_response(
    *,
    current_limit: float,
    history: list[HistoryTurn] | None = None,
    client_name: str | None = None,
) -> str:
    return _humanize(
        template_id="current_limit",
        instruction=(
            f"Informe de forma acolhedora que o limite de credito atual e R$ {current_limit:.2f}. "
            "Depois pergunte se a pessoa quer simular ou solicitar um aumento."
        ),
        fallback=(
            f"Seu limite de credito atual e R$ {current_limit:.2f}. "
            "Se quiser, tambem posso te ajudar a solicitar um aumento agora."
        ),
        history=history,
        client_name=client_name,
    )


def credit_increase_guidance_response(
    *,
    current_limit: float,
    max_allowed_limit: float | None,
    history: list[HistoryTurn] | None = None,
    client_name: str | None = None,
) -> str:
    max_part = (
        f"Pelos dados atuais da sua conta, consigo analisar pedidos de ate R$ {max_allowed_limit:.2f}. "
        if max_allowed_limit is not None
        else ""
    )
    return _humanize(
        template_id="credit_increase_guidance",
        instruction=(
            f"A pessoa quer aumentar o limite. O limite atual e R$ {current_limit:.2f}. "
            f"{max_part}"
            "Explique brevemente que voce pode abrir a solicitacao e precisa que ela informe o novo limite desejado."
        ),
        fallback=(
            f"Claro, eu te ajudo com isso. Hoje seu limite esta em R$ {current_limit:.2f}. "
            f"{max_part}"
            "Me diga qual novo limite voce gostaria de solicitar que eu faco a analise por aqui."
        ),
        history=history,
        client_name=client_name,
    )


def credit_decision_response(
    *,
    requested_limit: float,
    status: str,
    history: list[HistoryTurn] | None = None,
    client_name: str | None = None,
) -> str:
    if status == "aprovado":
        fallback = (
            f"Boa noticia: seu pedido de aumento para R$ {requested_limit:.2f} foi aprovado e registrado."
        )
        instruction = (
            f"O pedido de aumento para R$ {requested_limit:.2f} foi aprovado. "
            "Comunique de forma calorosa e objetiva."
        )
    else:
        fallback = (
            f"Analisei seu pedido de aumento para R$ {requested_limit:.2f}, mas ele foi rejeitado neste momento. "
            "Se quiser, posso fazer uma entrevista de credito para tentar atualizar seu score."
        )
        instruction = (
            f"O pedido de aumento para R$ {requested_limit:.2f} foi rejeitado. "
            "Explique com empatia e ofereca entrevista de credito para atualizar o score."
        )
    return _humanize(
        template_id=f"credit_decision_{status}",
        instruction=instruction,
        fallback=fallback,
        history=history,
        client_name=client_name,
    )


def credit_interview_start_response(
    *,
    history: list[HistoryTurn] | None = None,
    client_name: str | None = None,
) -> str:
    return _humanize(
        template_id="credit_interview_start",
        instruction=(
            "A solicitacao de aumento foi rejeitada pelo score atual. "
            "Comece a entrevista de credito com empatia e peca, em uma unica mensagem, "
            "renda mensal, tipo de emprego, despesas fixas mensais, numero de dependentes e se existem dividas ativas."
        ),
        fallback=(
            "Para tentar melhorar essa analise, posso atualizar seu score com uma entrevista rapida. "
            "Me envie sua renda mensal, tipo de emprego, despesas fixas mensais, numero de dependentes e se possui dividas ativas."
        ),
        history=history,
        client_name=client_name,
    )


def credit_increase_not_possible_response(
    *,
    current_limit: float,
    history: list[HistoryTurn] | None = None,
    client_name: str | None = None,
) -> str:
    return _humanize(
        template_id="credit_increase_not_possible",
        instruction=(
            f"O limite atual e R$ {current_limit:.2f} e o score atual nao permite aumento agora. "
            "Explique isso com empatia e ofereca uma entrevista de credito rapida para tentar melhorar o score, "
            "perguntando se a pessoa quer fazer."
        ),
        fallback=(
            f"Seu limite atual ja e R$ {current_limit:.2f} e, pelo seu score atual, nao consigo aprovar um aumento agora. "
            "Posso fazer uma entrevista de credito rapida para tentar melhorar seu score. Voce gostaria de fazer?"
        ),
        history=history,
        client_name=client_name,
    )


def credit_interview_offer_response(
    *,
    history: list[HistoryTurn] | None = None,
    client_name: str | None = None,
) -> str:
    return _humanize(
        template_id="credit_interview_offer",
        instruction=(
            "Pergunte de forma gentil e clara se a pessoa deseja fazer a entrevista de credito agora "
            "para tentar atualizar o score."
        ),
        fallback=(
            "So para confirmar: voce gostaria de fazer a entrevista de credito agora para tentarmos atualizar seu score?"
        ),
        history=history,
        client_name=client_name,
    )


def credit_interview_declined_response(
    *,
    history: list[HistoryTurn] | None = None,
    client_name: str | None = None,
) -> str:
    return _humanize(
        template_id="credit_interview_declined",
        instruction=(
            "A pessoa nao quer fazer a entrevista agora. Responda com gentileza, sem insistir, "
            "e ofereca ajuda com outros assuntos como consultar limite ou cotacao de moedas."
        ),
        fallback=(
            "Sem problemas! Se mudar de ideia, e so me chamar. "
            "Posso te ajudar com mais alguma coisa, como consultar seu limite ou a cotacao de uma moeda?"
        ),
        history=history,
        client_name=client_name,
    )


INTERVIEW_QUESTIONS = {
    "renda_mensal": "Qual e a sua renda mensal aproximada?",
    "tipo_emprego": "Qual e o seu tipo de emprego: formal, autonomo ou desempregado?",
    "despesas": "Quanto voce gasta por mes, em media, com despesas fixas?",
    "dependentes": "Quantos dependentes voce tem?",
    "tem_dividas": "Voce possui dividas ativas no momento?",
}


def interview_question_response(
    field: str,
    *,
    history: list[HistoryTurn] | None = None,
    client_name: str | None = None,
) -> str:
    question = INTERVIEW_QUESTIONS.get(field, "Pode me contar um pouco mais?")
    return _humanize(
        template_id=f"interview_{field}",
        instruction=(
            "Voce esta conduzindo uma entrevista de credito, uma pergunta por vez. "
            f"Faca esta pergunta de forma breve e calorosa: {question}"
        ),
        fallback=question,
        history=history,
        client_name=client_name,
    )


def interview_reask_response(
    field: str,
    *,
    history: list[HistoryTurn] | None = None,
    client_name: str | None = None,
) -> str:
    question = INTERVIEW_QUESTIONS.get(field, "Pode me dar mais detalhes?")
    return _humanize(
        template_id=f"interview_reask_{field}",
        instruction=(
            "Voce nao conseguiu entender a resposta anterior nesta entrevista de credito. "
            f"Peca a informacao de novo, com gentileza: {question}"
        ),
        fallback=f"Desculpe, nao consegui entender. {question}",
        history=history,
        client_name=client_name,
    )


def interview_result_response(
    *,
    new_score: int,
    history: list[HistoryTurn] | None = None,
    client_name: str | None = None,
) -> str:
    return _humanize(
        template_id="interview_result",
        instruction=(
            f"A entrevista terminou e o novo score do cliente e {new_score} (de 0 a 1000). "
            "Comunique com simpatia e convide a pessoa a tentar a solicitacao de aumento novamente."
        ),
        fallback=(
            f"Prontinho! Seu score foi atualizado para {new_score}. "
            "Se quiser, podemos tentar a solicitacao de aumento de limite novamente."
        ),
        history=history,
        client_name=client_name,
    )


def exchange_response(*, answer: str, source: str | None) -> str:
    source_text = f" Fonte: {source}." if source else ""
    return f"{answer}{source_text} Posso te ajudar em mais alguma coisa?"


def normalize_response_text(text: str) -> str:
    cleaned = re.sub(r"[*_`>#]", "", text)
    cleaned = re.sub(r"^\s*[-•]\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def to_streamlit_safe(text: str) -> str:
    return text.replace("$", "\\$")


def _client_name_instruction(client_name: str | None) -> str:
    if not client_name:
        return ""
    return (
        f"Dados oficiais do cliente autenticado: nome = {client_name}. "
        f"Se usar o nome na resposta, use EXCLUSIVAMENTE '{client_name}'. "
        "Ignore nomes diferentes que possam aparecer no historico. Nunca invente nomes.\n\n"
    )


def _humanize(
    *,
    template_id: str,
    instruction: str,
    fallback: str,
    history: list[HistoryTurn] | None = None,
    client_name: str | None = None,
) -> str:
    del template_id  # reserved for tracing/evals
    instruction = f"{_client_name_instruction(client_name)}{instruction}"
    try:
        model = get_chat_model(temperature=0.7)
        messages: list[tuple[str, str]] = [("system", HUMANIZED_SYSTEM_PROMPT)]
        if history:
            for role, content in history:
                langchain_role = "human" if role == "user" else "ai"
                messages.append((langchain_role, content))
        messages.append(("human", instruction))
        response = model.invoke(messages)
        text = str(getattr(response, "content", "")).strip()
        if text:
            return normalize_response_text(text)
    except Exception:
        pass
    return fallback


def _missing_credentials_fallback(missing_text: str, greeting_detected: bool, turn_count: int) -> str:
    greetings = [
        "Oie, tudo bem por aqui e espero que por ai tambem!",
        "Eii, tudo bem? Que bom falar com voce.",
        "Oi! Tudo certo por aqui, obrigada por perguntar.",
    ]
    prefix = greetings[turn_count % len(greetings)] if greeting_detected else "Claro, vamos comecar."
    return (
        f"{prefix} Para eu te ajudar com seguranca no Banco Agil, preciso que voce me envie "
        f"{missing_text}. Assim que eu validar seus dados, seguimos com o que voce precisar."
    )
