from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


def has_hidden_path_segment(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


class DuplicateJsonKeyError(ValueError):
    def __init__(self, key: str) -> None:
        self.key = key


def json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(key)
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        return load_json_bytes(path.read_bytes(), path=path)
    except FileNotFoundError as exc:
        raise PackagerError(
            "missing_json_file",
            "required JSON input file does not exist",
            {"path": str(path.resolve())},
        ) from exc


def load_json_bytes(content: bytes, *, path: Path) -> dict[str, Any]:
    try:
        return json.loads(content.decode("utf-8"), object_pairs_hook=json_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackagerError(
            "invalid_json_file",
            "required JSON input file is not valid JSON",
            {"path": str(path.resolve()), "error": str(exc)},
        ) from exc
    except DuplicateJsonKeyError as exc:
        raise PackagerError(
            "invalid_json_duplicate_key",
            "required JSON input contains a duplicate object key",
            {"path": str(path.resolve()), "key": exc.key},
        ) from exc


def validate_relative_path(root: Path, candidate: Path, field: str) -> None:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise PackagerError(
            "path_outside_repo_root",
            "resolved path escapes repository root",
            {"field": field, "path": str(candidate), "repo_root": str(root.resolve())},
        ) from exc


def load_source_plugin_manifest(
    repository_root: Path, source_manifest: str | None = None
) -> dict[str, Any]:
    path = (
        repository_root / source_manifest
        if source_manifest is not None
        else repository_root / ".codex-plugin" / "plugin.json"
    )
    path = path.resolve()
    validate_relative_path(repository_root, path, "source_manifest")
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackagerError(
            "invalid_source_plugin_manifest",
            "source plugin manifest is not valid JSON",
            {"path": str(path)},
        ) from exc
    if not isinstance(payload, dict):
        raise PackagerError(
            "invalid_source_plugin_manifest",
            "source plugin manifest must contain an object",
            {"path": str(path)},
        )
    return payload


def load_yaml(path: Path) -> Any:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise PackagerError(
            "missing_yaml_dependency",
            "catalog mode requires the optional PyYAML dependency",
            {"path": str(path.resolve())},
        ) from exc
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PackagerError(
            "missing_yaml_file",
            "required YAML input file does not exist",
            {"path": str(path.resolve())},
        ) from exc
    except yaml.YAMLError as exc:
        raise PackagerError(
            "invalid_yaml_file",
            "required YAML input file is not valid YAML",
            {"path": str(path.resolve()), "error": str(exc)},
        ) from exc


def is_required_placeholder_string(value: Any, required_marker_prefix: str) -> bool:
    return isinstance(value, str) and value.startswith(required_marker_prefix)


def collect_required_placeholders(
    payload: Any, *, required_marker_prefix: str, field: str = ""
) -> list[dict[str, str]]:
    if is_required_placeholder_string(payload, required_marker_prefix):
        return [{"field": field or "$", "value": payload}]
    if isinstance(payload, dict):
        placeholders: list[dict[str, str]] = []
        for key, value in payload.items():
            next_field = f"{field}.{key}" if field else str(key)
            placeholders.extend(
                collect_required_placeholders(
                    value,
                    required_marker_prefix=required_marker_prefix,
                    field=next_field,
                )
            )
        return placeholders
    if isinstance(payload, list):
        placeholders = []
        for index, value in enumerate(payload):
            next_field = f"{field}[{index}]" if field else f"[{index}]"
            placeholders.extend(
                collect_required_placeholders(
                    value,
                    required_marker_prefix=required_marker_prefix,
                    field=next_field,
                )
            )
        return placeholders
    return []


def resolve_local_path(base: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (base / candidate).resolve()


def resolve_repository_root(raw_path: str, repo_root: Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def ensure_string(value: Any, *, field: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise PackagerError(
            "invalid_invocation_field",
            "field must be a string",
            {"field": field, "value": value},
        )
    normalized = value.strip()
    if not allow_empty and not normalized:
        raise PackagerError(
            "invalid_invocation_field",
            "field must be a non-empty string",
            {"field": field, "value": value},
        )
    return normalized


def parse_markdown_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return {}
    metadata: dict[str, str] = {}
    index = 1
    while index < len(lines):
        line = lines[index]
        if line == "---":
            return metadata
        if ":" not in line:
            index += 1
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value in {">", "|"}:
            index += 1
            block: list[str] = []
            while index < len(lines):
                next_line = lines[index]
                if next_line == "---":
                    metadata[key] = " ".join(part.strip() for part in block).strip()
                    return metadata
                if next_line and not next_line.startswith((" ", "\t")):
                    break
                block.append(next_line.strip())
                index += 1
            metadata[key] = " ".join(part.strip() for part in block).strip()
            continue
        metadata[key] = value.strip("\"'")
        index += 1
    return metadata
