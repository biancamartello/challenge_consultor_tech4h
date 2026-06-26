from __future__ import annotations

import re
from typing import Any

from langsmith import traceable


CPF_PATTERN = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")


def mask_cpf(cpf: str | None) -> str | None:
    if not cpf:
        return None
    digits = re.sub(r"\D", "", cpf)
    if len(digits) < 4:
        return None
    return f"***{digits[-4:]}"


def sanitize_text(text: str) -> str:
    return CPF_PATTERN.sub(lambda match: mask_cpf(match.group(0)) or "***", text)


def build_turn_metadata(
    state: dict[str, Any],
    *,
    route: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "authenticated": bool(state.get("authenticated")),
        "auth_attempts": int(state.get("auth_attempts", 0)),
    }
    if state.get("intent"):
        metadata["intent"] = state["intent"]
    if route:
        metadata["route"] = route
    cpf_masked = mask_cpf(state.get("cpf") or state.get("client", {}).get("cpf"))
    if cpf_masked:
        metadata["cpf_masked"] = cpf_masked
    return metadata


@traceable(name="banking_assistant_turn", run_type="chain")
def record_turn_trace(
    *,
    user_input_masked: str,
    response_masked: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "user_input": user_input_masked,
        "response": response_masked,
        "metadata": metadata,
    }
