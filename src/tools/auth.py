from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CLIENTS_PATH = Path("data/clientes.csv")


@dataclass(frozen=True)
class AuthResult:
    authenticated: bool
    client: dict[str, str] | None = None
    message: str = ""


class AuthenticationDataError(RuntimeError):
    """Raised when the client CSV cannot be read safely."""


def normalize_cpf(cpf: str) -> str:
    return re.sub(r"\D", "", cpf)


def normalize_birth_date(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
        day, month, year = value.split("/")
        return f"{year}-{month}-{day}"
    return value


def authenticate_client(
    cpf: str,
    birth_date: str,
    clients_path: str | Path = DEFAULT_CLIENTS_PATH,
) -> AuthResult:
    path = Path(clients_path)
    if not path.exists():
        raise AuthenticationDataError(f"Base de clientes nao encontrada: {path}")

    target_cpf = normalize_cpf(cpf)
    target_birth_date = normalize_birth_date(birth_date)

    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            if (
                normalize_cpf(row.get("cpf", "")) == target_cpf
                and normalize_birth_date(row.get("data_nascimento", "")) == target_birth_date
            ):
                return AuthResult(
                    authenticated=True,
                    client=row,
                    message=f"Cliente {row.get('nome', '')} autenticado com sucesso.",
                )

    return AuthResult(
        authenticated=False,
        client=None,
        message="Nao foi possivel autenticar com os dados informados.",
    )
