from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.tools.auth import normalize_cpf


DEFAULT_CLIENTS_PATH = Path("data/clientes.csv")
DEFAULT_SCORE_LIMIT_PATH = Path("data/score_limite.csv")
DEFAULT_REQUESTS_PATH = Path("data/solicitacoes_aumento_limite.csv")


@dataclass(frozen=True)
class CreditDecision:
    cpf: str
    current_limit: float
    requested_limit: float
    max_allowed_limit: float
    status: str


class CreditDataError(RuntimeError):
    """Raised when credit data cannot be found or interpreted."""


REQUEST_FIELDS = [
    "cpf_cliente",
    "data_hora_solicitacao",
    "limite_atual",
    "novo_limite_solicitado",
    "status_pedido",
]


def get_client_by_cpf(cpf: str, clients_path: str | Path = DEFAULT_CLIENTS_PATH) -> dict[str, str]:
    path = Path(clients_path)
    target_cpf = normalize_cpf(cpf)
    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            if normalize_cpf(row.get("cpf", "")) == target_cpf:
                return row
    raise CreditDataError("Cliente nao encontrado para analise de credito.")


def get_current_limit(cpf: str, clients_path: str | Path = DEFAULT_CLIENTS_PATH) -> float:
    client = get_client_by_cpf(cpf, clients_path)
    return float(client["limite_credito"])


def max_limit_for_score(
    score: int,
    score_limit_path: str | Path = DEFAULT_SCORE_LIMIT_PATH,
) -> float:
    path = Path(score_limit_path)
    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            score_min = int(row["score_min"])
            score_max = int(row["score_max"])
            if score_min <= score <= score_max:
                return float(row["limite_maximo"])
    raise CreditDataError("Score fora das faixas configuradas.")


def request_credit_increase(
    cpf: str,
    requested_limit: float,
    clients_path: str | Path = DEFAULT_CLIENTS_PATH,
    score_limit_path: str | Path = DEFAULT_SCORE_LIMIT_PATH,
    requests_path: str | Path = DEFAULT_REQUESTS_PATH,
) -> CreditDecision:
    client = get_client_by_cpf(cpf, clients_path)
    current_limit = float(client["limite_credito"])
    score = int(float(client["score"]))
    max_allowed = max_limit_for_score(score, score_limit_path)
    status = "aprovado" if requested_limit <= max_allowed else "rejeitado"

    decision = CreditDecision(
        cpf=normalize_cpf(cpf),
        current_limit=current_limit,
        requested_limit=float(requested_limit),
        max_allowed_limit=max_allowed,
        status=status,
    )
    append_limit_request(decision, requests_path)
    return decision


def append_limit_request(
    decision: CreditDecision,
    requests_path: str | Path = DEFAULT_REQUESTS_PATH,
) -> None:
    path = Path(requests_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not path.exists() or path.stat().st_size == 0

    with path.open("a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REQUEST_FIELDS)
        if should_write_header:
            writer.writeheader()
        writer.writerow(
            {
                "cpf_cliente": decision.cpf,
                "data_hora_solicitacao": datetime.now(timezone.utc).isoformat(),
                "limite_atual": f"{decision.current_limit:.2f}",
                "novo_limite_solicitado": f"{decision.requested_limit:.2f}",
                "status_pedido": decision.status,
            }
        )
