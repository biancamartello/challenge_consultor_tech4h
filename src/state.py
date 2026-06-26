from __future__ import annotations

from typing import Literal, TypedDict


Intent = Literal["credit", "credit_interview", "exchange", "end", "unknown"]


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
    should_end: bool
