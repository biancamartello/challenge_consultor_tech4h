from __future__ import annotations

import csv
from pathlib import Path

from src.tools.auth import normalize_cpf


DEFAULT_CLIENTS_PATH = Path("data/clientes.csv")

EMPLOYMENT_WEIGHTS = {
    "formal": 300,
    "autonomo": 200,
    "autônomo": 200,
    "desempregado": 0,
}

DEPENDENT_WEIGHTS = {
    0: 100,
    1: 80,
    2: 60,
}


class ScoringDataError(RuntimeError):
    """Raised when score data cannot be updated safely."""


def calculate_credit_score(
    renda_mensal: float,
    tipo_emprego: str,
    despesas: float,
    dependentes: int,
    tem_dividas: bool,
) -> int:
    employment_key = tipo_emprego.strip().lower()
    employment_weight = EMPLOYMENT_WEIGHTS.get(employment_key, 0)
    dependent_weight = DEPENDENT_WEIGHTS.get(dependentes, 30)
    debt_weight = -100 if tem_dividas else 100

    raw_score = (
        (float(renda_mensal) / (float(despesas) + 1)) * 30
        + employment_weight
        + dependent_weight
        + debt_weight
    )
    return max(0, min(1000, round(raw_score)))


def update_client_score(
    cpf: str,
    new_score: int,
    clients_path: str | Path = DEFAULT_CLIENTS_PATH,
) -> None:
    path = Path(clients_path)
    target_cpf = normalize_cpf(cpf)

    with path.open(newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise ScoringDataError("Base de clientes sem cabecalho.")
        rows = list(reader)

    updated = False
    for row in rows:
        if normalize_cpf(row.get("cpf", "")) == target_cpf:
            row["score"] = str(int(new_score))
            updated = True
            break

    if not updated:
        raise ScoringDataError("Cliente nao encontrado para atualizacao de score.")

    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
