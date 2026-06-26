from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    intent: Literal["credit", "credit_interview", "exchange", "end", "unknown"]
    confidence: float = Field(ge=0, le=1)


class LimitIncreaseRequest(BaseModel):
    requested_limit: float = Field(gt=0)


class CreditInterviewAnswers(BaseModel):
    renda_mensal: float = Field(ge=0)
    tipo_emprego: Literal["formal", "autonomo", "autônomo", "desempregado"]
    despesas: float = Field(ge=0)
    dependentes: int = Field(ge=0)
    tem_dividas: bool
