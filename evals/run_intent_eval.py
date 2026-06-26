from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langsmith import Client

from src.graph import classify_intent


DATASET_NAME = "banco-agil-intent-classification"
DATASET_PATH = Path(__file__).parent / "datasets" / "intent_cases.jsonl"


def load_examples(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    with path.open() as file:
        return [json.loads(line) for line in file if line.strip()]


def ensure_dataset(client: Client, dataset_name: str = DATASET_NAME) -> str:
    if client.has_dataset(dataset_name=dataset_name):
        return dataset_name

    dataset = client.create_dataset(dataset_name=dataset_name)
    client.create_examples(
        dataset_id=dataset.id,
        examples=load_examples(),
    )
    return dataset_name


def target(inputs: dict[str, Any]) -> dict[str, str]:
    return {"intent": classify_intent(inputs["text"])}


def intent_accuracy(outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> bool:
    return outputs.get("intent") == reference_outputs.get("intent")


def main() -> None:
    load_dotenv()
    client = Client()
    dataset_name = ensure_dataset(client)
    results = client.evaluate(
        target,
        data=dataset_name,
        evaluators=[intent_accuracy],
        experiment_prefix="intent-classifier",
    )
    print(f"LangSmith experiment: {results.experiment_name}")


if __name__ == "__main__":
    main()
