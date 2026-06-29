from __future__ import annotations

from typing import Literal, TypedDict


Intent = Literal["credit", "credit_interview", "exchange", "end", "unknown"]
HistoryTurn = tuple[str, str]


class AgentState(TypedDict, total=False):
    user_input: str
    response: str
    cpf: str
    birth_date: str
    authenticated: bool
    auth_attempts: int
    client: dict[str, str]
    intent: Intent
    requested_limit: float
    credit_status: str
    active_flow: str
    interview_answers: dict
    interview_pending_field: str
    missing_credentials_count: int
    conversation_history: list[HistoryTurn]
    should_end: bool
