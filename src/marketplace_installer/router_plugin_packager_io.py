from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def print_payload(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(payload["surface_id"])
    print(payload["decision_state_path"])
    for path in payload["generated_output_paths"]:
        print(path)


def print_error(error_payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(error_payload, indent=2, sort_keys=True))
        return
    print(error_payload["message"])
