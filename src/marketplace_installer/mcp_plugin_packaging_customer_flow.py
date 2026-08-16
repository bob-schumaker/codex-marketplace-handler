#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["packaging==26.3", "PyYAML==6.0.3"]
# ///
"""Customer-facing MCP plugin packaging wrapper for first-slice Layer 3 flows."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_mcp import (
    mcp_launch_contract_invocation_payload,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    McpLaunchContract,
    normalize_mcp_environment,
    normalize_mcp_launch_contract,
)
from marketplace_installer.router_plugin_packager_hashing import hash_tree
from marketplace_installer.router_plugin_packager_parsing import (
    collect_required_placeholders,
)
from marketplace_installer.router_plugin_packager_constants import (
    RECEIPT_NAME,
    REQUIRED_MARKER_PREFIX,
)
from marketplace_installer.router_plugin_packager_text import (
    display_name_from_slug,
    normalize_slug,
    normalize_whitespace,
)

try:
    from marketplace_installer.router_plugin_packager_script_loading import (
        load_sibling_module,
    )
except ModuleNotFoundError:
    from router_plugin_packager_script_loading import load_sibling_module


router_packager = load_sibling_module("router_plugin_packager.py")

PackagerError = router_packager.PackagerError

DERIVED_INVOCATIONS_DIR = (
    Path(".codex-plugin") / "router-plugin-packager" / "derived-invocations"
)
DERIVATION_REPORTS_DIR = (
    Path(".codex-plugin") / "router-plugin-packager" / "derivation-reports"
)
REGISTRY_ASSET_IDS = {
    "manifest.json": "registry-manifest",
    "release-manifest.json": "release-manifest",
    "operation-registry.json": "operation-registry",
    "schemas": "schema-bundle",
}
REQUIRED_RELEASE_FILES = (
    "manifest.json",
    "release-manifest.json",
    "operation-registry.json",
)
ALLOWED_OVERRIDE_PATTERNS = (
    "plugin_slug_override",
    "display_name_override",
    "surface_id_override",
    "skill_paths",
    "source_root",
    "output_root",
    "registry_root",
    "mcp_packaging.launch_contract.*",
    "mcp_packaging.plugin_artifact_contract.*",
    "mcp_packaging.skill_release_contract.*",
    "mcp_packaging.publication.*",
    "mcp_packaging.staging_contract.*",
)
REQUIRED_PHRASE_OPTIONS = (
    (
        "Treat the active release manifest and matching capability/schema snapshot as the authority. Only invoke a mutation when it is released and discoverable; never infer a generic CRUD operation from a related read or write tool.",
        "Treat the active release manifest and matching capability/schema snapshot as the authority.",
    ),
    (
        "Never invoke SharePoint write behavior; no SharePoint write tool is registered in this release.",
    ),
    (
        "Do not claim that a disabled capability can be activated by changing credentials, tenants, endpoints, profiles, or approval settings.",
    ),
)
FORBIDDEN_PHRASE = "you can activate a disabled capability by changing credentials"
WRAPPER_OWNED_ROOT = Path(".codex-plugin") / "router-plugin-packager"
DERIVED_GENERATED_DIR = WRAPPER_OWNED_ROOT / "generated"
GENERATED_REGISTRY_DIR = WRAPPER_OWNED_ROOT / "generated-registry"
MCP_CONFIG_PATH = Path("router-plugin-config.json")
MCP_REGISTRY_ROOT = Path("router-plugin-registry")
MCP_SCAFFOLD_REPORT_NAME = "scaffold-report.json"
MCP_SETUP_INPUT_MANIFEST_NAME = "setup-input-manifest.json"
PACKAGE_REPORT_FORMAT_VERSION = 1


class CustomerFlowError(Exception):
    """Raised when customer-flow derivation fails."""

    def __init__(self, error_code: str, message: str, details: dict[str, Any]) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details

    def payload(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


@dataclass(frozen=True)
class CandidatePlugin:
    plugin_root: Path
    plugin_json: dict[str, Any] | None
    mcp_json: dict[str, Any] | None
    skill_id: str
    skill_path: Path
    skill_text: str
    evidence_source: str


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_json_object
        )
    except FileNotFoundError as exc:
        raise CustomerFlowError(
            "insufficient_evidence",
            "required JSON file does not exist",
            {"path": str(path)},
        ) from exc
    except json.JSONDecodeError as exc:
        raise CustomerFlowError(
            "insufficient_evidence",
            "required JSON file is not valid JSON",
            {"path": str(path), "error": str(exc)},
        ) from exc
    except _DuplicateJsonKeyError as exc:
        raise CustomerFlowError(
            "invalid_json_duplicate_key",
            "required JSON file contains a duplicate object key",
            {"path": str(path), "key": exc.key},
        ) from exc


class _DuplicateJsonKeyError(ValueError):
    def __init__(self, key: str) -> None:
        self.key = key


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _resolve_repo_relative_path(repo_root: Path, value: str, field: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        raise CustomerFlowError(
            "mcp_setup_invalid",
            "MCP setup path must be repository-relative",
            {"field": field, "value": value},
        )
    resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise CustomerFlowError(
            "mcp_setup_invalid",
            "MCP setup path escapes the repository root",
            {"field": field, "value": value},
        ) from exc
    return resolved


def _mcp_setup_error(
    error_code: str, message: str, details: dict[str, Any]
) -> CustomerFlowError:
    return CustomerFlowError(error_code, message, details)


def _load_mcp_setup_json(path: Path, artifact_id: str) -> dict[str, Any]:
    try:
        return _load_json(path)
    except CustomerFlowError as exc:
        raise _mcp_setup_error(
            "mcp_setup_invalid",
            "required MCP setup input is missing or invalid",
            {"artifact_id": artifact_id, "path": str(path), "cause": exc.error_code},
        ) from exc


def _ensure_marker_free(payload: dict[str, Any], artifact_id: str, path: Path) -> None:
    placeholders = [
        placeholder
        for placeholder in collect_required_placeholders(
            payload, required_marker_prefix=REQUIRED_MARKER_PREFIX
        )
        if placeholder["field"] != "required_marker_prefix"
    ]
    if placeholders:
        raise _mcp_setup_error(
            "mcp_setup_incomplete",
            "MCP setup inputs still contain required markers",
            {
                "artifact_id": artifact_id,
                "path": str(path),
                "unresolved_placeholders": placeholders,
            },
        )


def _validate_authoritative_mcp_inputs(repo_root: Path) -> Path:  # noqa: C901
    """Accept only a completed durable registry before derivation can write."""

    config_path = repo_root / MCP_CONFIG_PATH
    if not config_path.is_file():
        legacy_root = repo_root / GENERATED_REGISTRY_DIR
        if legacy_root.exists() or any(repo_root.rglob("generated_registry")):
            raise _mcp_setup_error(
                "mcp_setup_migration_required",
                "legacy MCP registry state requires an explicit migration",
                {"config_path": MCP_CONFIG_PATH.as_posix()},
            )
        if (repo_root / MCP_REGISTRY_ROOT).exists() or (
            repo_root / WRAPPER_OWNED_ROOT
        ).exists():
            raise _mcp_setup_error(
                "mcp_setup_invalid_state",
                "MCP state exists without its durable config authority",
                {"config_path": MCP_CONFIG_PATH.as_posix()},
            )
        raise _mcp_setup_error(
            "mcp_setup_required",
            "run mcp-setup before deriving MCP packaging inputs",
            {"config_path": MCP_CONFIG_PATH.as_posix()},
        )
    config = _load_mcp_setup_json(config_path, "mcp_config")
    _ensure_marker_free(config, "mcp_config", config_path)
    if config.get("plugin_kind") != "mcp_based":
        raise _mcp_setup_error(
            "mcp_setup_invalid",
            "MCP setup config must declare plugin_kind mcp_based",
            {"path": MCP_CONFIG_PATH.as_posix()},
        )
    registry_root_value = config.get("registry_root")
    input_manifest_value = config.get("input_manifest_path")
    if not isinstance(registry_root_value, str) or not isinstance(
        input_manifest_value, str
    ):
        raise _mcp_setup_error(
            "mcp_setup_invalid",
            "MCP setup config is missing durable registry authority paths",
            {"path": MCP_CONFIG_PATH.as_posix()},
        )
    registry_root = _resolve_repo_relative_path(
        repo_root, registry_root_value, "registry_root"
    )
    input_manifest_path = _resolve_repo_relative_path(
        repo_root, input_manifest_value, "input_manifest_path"
    )
    input_manifest = _load_mcp_setup_json(input_manifest_path, "setup_input_manifest")
    _ensure_marker_free(input_manifest, "setup_input_manifest", input_manifest_path)
    if (
        input_manifest.get("config_path") != MCP_CONFIG_PATH.as_posix()
        or input_manifest.get("registry_root") != registry_root_value
    ):
        raise _mcp_setup_error(
            "mcp_setup_invalid",
            "MCP setup control-plane records disagree",
            {
                "config_path": MCP_CONFIG_PATH.as_posix(),
                "input_manifest_path": input_manifest_value,
            },
        )
    scaffold_report_path = registry_root / MCP_SCAFFOLD_REPORT_NAME
    scaffold_report = _load_mcp_setup_json(scaffold_report_path, "scaffold_report")
    state = scaffold_report.get("state")
    if state == "scaffolded":
        raise _mcp_setup_error(
            "mcp_setup_incomplete",
            "MCP setup scaffold must be completed before packaging",
            {"path": str(scaffold_report_path), "state": state},
        )
    if state in {"stale", "invalid"}:
        raise _mcp_setup_error(
            "mcp_setup_invalid_state",
            "MCP setup registry state is not packageable",
            {"path": str(scaffold_report_path), "state": state},
        )
    if state != "complete":
        raise _mcp_setup_error(
            "mcp_setup_invalid",
            "MCP setup scaffold report has an unsupported state",
            {"path": str(scaffold_report_path), "state": state},
        )
    _ensure_marker_free(scaffold_report, "scaffold_report", scaffold_report_path)
    registry_manifest = _load_mcp_setup_json(
        registry_root / "manifest.json", "registry_manifest"
    )
    release_manifest = _load_mcp_setup_json(
        registry_root / "release-manifest.json", "release_manifest"
    )
    operation_registry = _load_mcp_setup_json(
        registry_root / "operation-registry.json", "operation_registry"
    )
    for artifact_id, payload, path in (
        ("registry_manifest", registry_manifest, registry_root / "manifest.json"),
        ("release_manifest", release_manifest, registry_root / "release-manifest.json"),
        (
            "operation_registry",
            operation_registry,
            registry_root / "operation-registry.json",
        ),
    ):
        _ensure_marker_free(payload, artifact_id, path)
    inventory = registry_manifest.get("release_asset_inventory")
    if not isinstance(inventory, list) or set(inventory) != set(REGISTRY_ASSET_IDS):
        raise _mcp_setup_error(
            "mcp_setup_invalid",
            "registry manifest does not declare the required release inventory",
            {"path": str(registry_root / "manifest.json"), "inventory": inventory},
        )
    return registry_root


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    """Persist a client-owned config without exposing a partial rewrite."""

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError as exc:
        raise CustomerFlowError(
            "insufficient_evidence",
            "required TOML file does not exist",
            {"path": str(path)},
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise CustomerFlowError(
            "insufficient_evidence",
            "required TOML file is not valid",
            {"path": str(path), "error": str(exc)},
        ) from exc


def _normalize_slug(value: str) -> str:
    return normalize_slug(value)


def _display_name_from_slug(value: str) -> str:
    return display_name_from_slug(value)


def _hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _hash_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _hash_path(path: Path) -> str:
    if path.is_dir():
        return hash_tree(path)
    return _hash_file(path)


def _package_report(
    *,
    outcome: str,
    diagnostic_code: str,
    owned_paths: list[Path],
    unresolved_markers: list[dict[str, Any]] | None = None,
    packager: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the stable result contract for the resumable user-facing command."""

    payload: dict[str, Any] = {
        "format_version": PACKAGE_REPORT_FORMAT_VERSION,
        "outcome": outcome,
        "diagnostic_code": diagnostic_code,
        "state_subcode": diagnostic_code,
        "owned_paths": [str(path) for path in owned_paths],
        "unresolved_markers": unresolved_markers or [],
        "plugin_generated": outcome == "packaged",
        "published": False,
        "installed": False,
    }
    if packager is not None:
        payload["packager"] = packager
    return payload


def _load_setup_helper() -> Any:
    """Load setup lazily so the two helpers can remain independently runnable."""

    setup_script = Path(__file__).resolve().parent / "router_plugin_packager_setup.py"
    spec = importlib.util.spec_from_file_location(
        "router_plugin_packager_setup", setup_script
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _package(
    repo_root: Path, *, mode: str, surface_id: str | None, overrides_path: Path | None
) -> dict[str, Any]:
    """Resume packaging from durable MCP inputs without selecting internal phases."""

    repo_root = repo_root.resolve()
    try:
        _validate_authoritative_mcp_inputs(repo_root)
    except CustomerFlowError as exc:
        if exc.error_code == "mcp_setup_required":
            setup = _load_setup_helper()
            setup_result = setup.execute(
                "scaffold", repo_root, plugin_kind="mcp_based", mcp_mode=mode
            )
            report = setup_result["completeness_report"]
            return _package_report(
                outcome="scaffold_created",
                diagnostic_code=exc.error_code,
                owned_paths=[
                    repo_root / MCP_CONFIG_PATH,
                    repo_root / MCP_REGISTRY_ROOT,
                    repo_root / ".codex-plugin" / "router-plugin-packager" / "drafts",
                ],
                unresolved_markers=report.get("unresolved_placeholders", []),
            )
        if exc.error_code == "mcp_setup_incomplete":
            return _package_report(
                outcome="awaiting_completion",
                diagnostic_code=exc.error_code,
                owned_paths=[
                    repo_root / MCP_CONFIG_PATH,
                    repo_root / MCP_REGISTRY_ROOT,
                ],
                unresolved_markers=exc.details.get("unresolved_placeholders", []),
            )
        return _package_report(
            outcome="invalid",
            diagnostic_code=exc.error_code,
            owned_paths=[repo_root / MCP_CONFIG_PATH, repo_root / MCP_REGISTRY_ROOT],
        )

    # A complete registry is derived, planned, and applied in one command. Each
    # phase retains its existing strict validation and receipt behavior.
    execute(
        "preview",
        repo_root,
        mode=mode,
        surface_id=surface_id,
        overrides_path=overrides_path,
    )
    execute(
        "plan",
        repo_root,
        mode=mode,
        surface_id=surface_id,
        overrides_path=overrides_path,
    )
    applied = execute(
        "apply",
        repo_root,
        mode=mode,
        surface_id=surface_id,
        overrides_path=overrides_path,
    )
    return _package_report(
        outcome="packaged",
        diagnostic_code="packaged",
        owned_paths=[repo_root / WRAPPER_OWNED_ROOT],
        packager=applied["packager"],
    )


def _flatten_override_keys(payload: Any, prefix: str = "") -> list[str]:
    if isinstance(payload, dict):
        keys: list[str] = []
        for key, value in payload.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            keys.extend(_flatten_override_keys(value, next_prefix))
        return keys
    return [prefix]


def _matches_allowed_pattern(key: str) -> bool:
    for pattern in ALLOWED_OVERRIDE_PATTERNS:
        if pattern.endswith(".*"):
            base = pattern[:-2]
            if key == base or key.startswith(f"{base}."):
                return True
            continue
        if key == pattern:
            return True
    return False


def _validate_overrides(overrides: dict[str, Any]) -> None:
    unknown = sorted(
        key
        for key in _flatten_override_keys(overrides)
        if not _matches_allowed_pattern(key)
    )
    if unknown:
        raise CustomerFlowError(
            "unknown_override_key",
            "override file contains unsupported keys",
            {"unknown_keys": unknown},
        )


def _is_wrapper_owned_path(repo_root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(repo_root)
    except ValueError:
        return False
    return relative == WRAPPER_OWNED_ROOT or WRAPPER_OWNED_ROOT in relative.parents


def _find_candidate_plugins(repo_root: Path) -> list[CandidatePlugin]:
    candidates: list[CandidatePlugin] = []
    for plugin_json_path in sorted(repo_root.rglob(".codex-plugin/plugin.json")):
        plugin_root = plugin_json_path.parent.parent
        if _is_wrapper_owned_path(repo_root, plugin_root):
            continue
        if (plugin_root / RECEIPT_NAME).is_file():
            continue
        mcp_path = plugin_root / ".mcp.json"
        skills_root = plugin_root / "skills"
        if not mcp_path.is_file() or not skills_root.is_dir():
            continue
        skill_dirs = [
            path
            for path in sorted(skills_root.iterdir())
            if (path / "SKILL.md").is_file()
        ]
        if len(skill_dirs) != 1:
            continue
        skill_path = skill_dirs[0]
        candidates.append(
            CandidatePlugin(
                plugin_root=plugin_root,
                plugin_json=_load_json(plugin_json_path),
                mcp_json=_load_json(mcp_path),
                skill_id=skill_path.name,
                skill_path=skill_path,
                skill_text=(skill_path / "SKILL.md").read_text(encoding="utf-8"),
                evidence_source="checked_in_plugin",
            )
        )
    return candidates


def _release_manifest(registry_root: Path) -> dict[str, Any]:
    return _load_json(registry_root / "release-manifest.json")


def _source_plugin_id(registry_root: Path) -> str:
    release_manifest = _release_manifest(registry_root)
    artifact_policy = release_manifest.get("artifact_policy")
    if not isinstance(artifact_policy, dict):
        raise CustomerFlowError(
            "insufficient_evidence",
            "release manifest is missing artifact_policy",
            {"path": str(registry_root / "release-manifest.json")},
        )
    plugin_id = artifact_policy.get("plugin_id")
    if not isinstance(plugin_id, str) or not plugin_id.strip():
        raise CustomerFlowError(
            "insufficient_evidence",
            "release manifest is missing artifact_policy.plugin_id",
            {"path": str(registry_root / "release-manifest.json")},
        )
    return plugin_id.strip()


def _extract_json_code_block(
    markdown_path: Path, *, required_keys: set[str], expected_name: str
) -> dict[str, Any] | None:
    text = markdown_path.read_text(encoding="utf-8")
    fence = "```json"
    cursor = 0
    while True:
        start = text.find(fence, cursor)
        if start == -1:
            return None
        block_start = text.find("\n", start)
        if block_start == -1:
            return None
        end = text.find("```", block_start + 1)
        if end == -1:
            return None
        cursor = end + 3
        candidate_text = text[block_start + 1 : end].strip()
        try:
            payload = json.loads(candidate_text)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if not required_keys.issubset(payload):
            continue
        if payload.get("name") != expected_name:
            continue
        return payload


def _derive_plugin_manifest_from_repo_evidence(
    repo_root: Path, plugin_name: str
) -> dict[str, Any]:
    spec_path = repo_root / "specs" / "03-oci-codex-plugin.md"
    if not spec_path.is_file():
        raise CustomerFlowError(
            "insufficient_evidence",
            "repo-native plugin metadata spec is missing",
            {"path": str(spec_path)},
        )
    payload = _extract_json_code_block(
        spec_path,
        required_keys={
            "name",
            "description",
            "skills",
            "mcpServers",
            "author",
            "interface",
        },
        expected_name=plugin_name,
    )
    if payload is None:
        raise CustomerFlowError(
            "insufficient_evidence",
            "repo-native plugin metadata spec does not contain a matching plugin manifest example",
            {"path": str(spec_path), "plugin_name": plugin_name},
        )
    return payload


def _derive_launch_contract_from_repo_evidence(
    repo_root: Path, registry_root: Path, plugin_name: str
) -> dict[str, Any]:
    release_manifest = _release_manifest(registry_root)
    package = release_manifest.get("package")
    if not isinstance(package, dict):
        raise CustomerFlowError(
            "insufficient_evidence",
            "release manifest is missing package metadata",
            {"path": str(registry_root / "release-manifest.json")},
        )
    package_name = package.get("name")
    entrypoint = package.get("entry_point")
    if not isinstance(package_name, str) or not isinstance(entrypoint, str):
        raise CustomerFlowError(
            "insufficient_evidence",
            "release manifest is missing package.name or package.entry_point",
            {"path": str(registry_root / "release-manifest.json")},
        )
    mise = _load_toml(repo_root / ".mise.toml")
    tools = mise.get("tools")
    if not isinstance(tools, dict):
        raise CustomerFlowError(
            "insufficient_evidence",
            "repo-native .mise.toml is missing tools.python",
            {"path": str(repo_root / ".mise.toml")},
        )
    python_version = tools.get("python")
    if not isinstance(python_version, str) or not python_version.strip():
        raise CustomerFlowError(
            "insufficient_evidence",
            "repo-native .mise.toml is missing tools.python",
            {"path": str(repo_root / ".mise.toml")},
        )
    pyproject = _load_toml(repo_root / "pyproject.toml")
    poetry = pyproject.get("tool", {}).get("poetry", {})
    sources = poetry.get("source")
    if not isinstance(sources, list):
        raise CustomerFlowError(
            "insufficient_evidence",
            "pyproject.toml is missing tool.poetry.source entries",
            {"path": str(repo_root / "pyproject.toml")},
        )
    primary_source = next(
        (
            source
            for source in sources
            if isinstance(source, dict) and source.get("priority") == "primary"
        ),
        None,
    )
    if not isinstance(primary_source, dict) or not isinstance(
        primary_source.get("url"), str
    ):
        raise CustomerFlowError(
            "insufficient_evidence",
            "pyproject.toml is missing a primary Poetry source URL",
            {"path": str(repo_root / "pyproject.toml")},
        )
    return {
        "schema_version": 1,
        "server_id": plugin_name,
        "transport": "stdio",
        "command": "uvx",
        "python_version": python_version.strip(),
        "package_index": str(primary_source["url"]),
        "package_name": package_name,
        "entrypoint": entrypoint,
        "extra_args": [],
        "forbidden_arg_fragments": [
            "auth",
            "credential",
            "endpoint",
            "profile",
            "tenant",
        ],
    }


def _derive_runtime_version_from_repo_evidence(
    repo_root: Path, registry_root: Path
) -> str:
    release_manifest = _release_manifest(registry_root)
    package = release_manifest.get("package")
    if isinstance(package, dict) and isinstance(package.get("version"), str):
        return str(package["version"])
    pyproject = _load_toml(repo_root / "pyproject.toml")
    project = pyproject.get("project")
    if isinstance(project, dict) and isinstance(project.get("version"), str):
        return str(project["version"])
    raise CustomerFlowError(
        "insufficient_evidence",
        "repo-native package version could not be derived",
        {
            "release_manifest": str(registry_root / "release-manifest.json"),
            "pyproject": str(repo_root / "pyproject.toml"),
        },
    )


def _first_named_party(entries: Any) -> str | None:
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def _derive_project_author_name(
    repo_root: Path, fallback_author: dict[str, Any] | None = None
) -> str:
    pyproject = _load_toml(repo_root / "pyproject.toml")
    project = pyproject.get("project")
    if isinstance(project, dict):
        author_name = _first_named_party(project.get("authors"))
        if author_name is not None:
            return author_name
        maintainer_name = _first_named_party(project.get("maintainers"))
        if maintainer_name is not None:
            return maintainer_name
    if isinstance(fallback_author, dict):
        fallback_name = fallback_author.get("name")
        if isinstance(fallback_name, str) and fallback_name.strip():
            return fallback_name.strip()
    raise CustomerFlowError(
        "insufficient_evidence",
        "project author name could not be derived from repo metadata",
        {"pyproject": str(repo_root / "pyproject.toml")},
    )


def _extract_skill_heading_display_name(skill_text: str) -> str | None:
    lines = skill_text.splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            heading = stripped[2:].strip()
            if heading:
                return heading
    return None


def _derive_canonical_plugin_display_name(
    candidate: CandidatePlugin, overrides: dict[str, Any]
) -> str:
    override = overrides.get("display_name_override")
    if isinstance(override, str) and override.strip():
        return override.strip()
    skill_heading = _extract_skill_heading_display_name(candidate.skill_text)
    if skill_heading is not None:
        return skill_heading
    plugin_name = str(candidate.plugin_json.get("name", "")).strip()  # type: ignore[union-attr]
    if plugin_name:
        return _display_name_from_slug(plugin_name)
    raise CustomerFlowError(
        "insufficient_evidence",
        "canonical plugin display name could not be derived",
        {"skill_path": str(candidate.skill_path)},
    )


def _is_usable_registry_root(path: Path, *, mode: str) -> bool:
    del mode
    if not path.is_dir():
        return False
    return all((path / name).exists() for name in REQUIRED_RELEASE_FILES)


def _fallback_registry_roots(
    repo_root: Path, *, mode: str, expected_root: Path
) -> list[Path]:
    roots: list[Path] = []
    for path in sorted(repo_root.rglob("generated_registry")):
        resolved = path.resolve()
        if resolved == expected_root:
            continue
        if _is_usable_registry_root(resolved, mode=mode):
            roots.append(resolved)
    return roots


def _find_source_candidates(
    repo_root: Path, registry_root: Path
) -> list[CandidatePlugin]:
    plugin_id = _source_plugin_id(registry_root)
    skill_paths = []
    for skill_path in sorted(repo_root.rglob("SKILL.md")):
        if _is_wrapper_owned_path(repo_root, skill_path):
            continue
        if skill_path.parent.name != plugin_id:
            continue
        if skill_path.parent.parent.name != "skills":
            continue
        skill_paths.append(skill_path)
    candidates: list[CandidatePlugin] = []
    for skill_file in skill_paths:
        plugin_root = skill_file.parents[2]
        candidates.append(
            CandidatePlugin(
                plugin_root=plugin_root,
                plugin_json=_derive_plugin_manifest_from_repo_evidence(
                    repo_root, plugin_id
                ),
                mcp_json=None,
                skill_id=skill_file.parent.name,
                skill_path=skill_file.parent,
                skill_text=skill_file.read_text(encoding="utf-8"),
                evidence_source="repo_native_source",
            )
        )
    return candidates


def _select_candidate(
    repo_root: Path,
    registry_root: Path,
    surface_id_override: str | None,
    mode: str,
) -> CandidatePlugin:
    candidates = _find_candidate_plugins(repo_root)
    if not candidates and mode == "bootstrap":
        candidates = _find_source_candidates(repo_root, registry_root)
    if not candidates:
        raise CustomerFlowError(
            "insufficient_evidence",
            "no MCP plugin candidate could be derived from checked-in or repo-native evidence",
            {"repo_root": str(repo_root)},
        )
    if surface_id_override is not None:
        normalized = _normalize_slug(surface_id_override)
        candidates = [
            candidate
            for candidate in candidates
            if _normalize_slug(str(candidate.plugin_json.get("name", ""))) == normalized
            or _normalize_slug(candidate.skill_id) == normalized
        ]
    if len(candidates) != 1:
        raise CustomerFlowError(
            "ambiguous_candidates",
            "customer-flow could not select exactly one MCP plugin candidate",
            {
                "candidate_roots": [
                    str(candidate.plugin_root.relative_to(repo_root))
                    for candidate in candidates
                ]
            },
        )
    return candidates[0]


def _find_registry_root(repo_root: Path, overrides: dict[str, Any], mode: str) -> Path:
    del mode
    registry_root = _validate_authoritative_mcp_inputs(repo_root)
    override_root = overrides.get("registry_root")
    if override_root is not None:
        configured_root = registry_root.relative_to(repo_root).as_posix()
        if override_root != configured_root:
            raise CustomerFlowError(
                "conflicting_evidence",
                "registry_root override conflicts with the durable MCP setup config",
                {
                    "registry_root_override": override_root,
                    "configured_registry_root": configured_root,
                },
            )
    return registry_root


def _parse_launch_contract(mcp_json: dict[str, Any]) -> dict[str, Any]:  # noqa: C901
    if set(mcp_json) != {"mcpServers"}:
        raise CustomerFlowError(
            "insufficient_evidence",
            "checked-in .mcp.json may contain only mcpServers",
            {"keys": sorted(mcp_json)},
        )
    servers = mcp_json.get("mcpServers")
    if not isinstance(servers, dict) or len(servers) != 1:
        raise CustomerFlowError(
            "insufficient_evidence",
            "checked-in .mcp.json must define exactly one MCP server",
            {"mcpServers": servers},
        )
    server_id, descriptor = next(iter(servers.items()))
    if (
        not isinstance(server_id, str)
        or not server_id
        or not isinstance(descriptor, dict)
    ):
        raise CustomerFlowError(
            "insufficient_evidence",
            "MCP server descriptor must be an object",
            {"server_id": server_id},
        )
    unknown_descriptor_properties = sorted(set(descriptor) - {"command", "args", "env"})
    if unknown_descriptor_properties:
        raise CustomerFlowError(
            "insufficient_evidence",
            "MCP server descriptor contains unsupported properties",
            {
                "server_id": server_id,
                "unknown_properties": unknown_descriptor_properties,
            },
        )
    args = descriptor.get("args")
    if descriptor.get("command") != "uvx" or not isinstance(args, list):
        raise CustomerFlowError(
            "insufficient_evidence",
            "only uvx-backed stdio descriptors are supported in the first slice",
            {"server_id": server_id},
        )
    try:
        python_index = args.index("--python")
        default_index = args.index("--default-index")
        from_index = args.index("--from")
        stdio_index = args.index("--stdio")
    except ValueError as exc:
        raise CustomerFlowError(
            "insufficient_evidence",
            "checked-in .mcp.json is missing required uvx launch arguments",
            {"server_id": server_id, "args": args},
        ) from exc
    if not (
        python_index + 1 < len(args)
        and default_index + 1 < len(args)
        and from_index + 2 < len(args)
    ):
        raise CustomerFlowError(
            "insufficient_evidence",
            "checked-in .mcp.json has incomplete required launch arguments",
            {"server_id": server_id, "args": args},
        )
    if (
        python_index != 0
        or default_index != 2
        or from_index != 4
        or stdio_index != len(args) - 1
    ):
        raise CustomerFlowError(
            "insufficient_evidence",
            "checked-in .mcp.json does not use the canonical uvx launch ordering",
            {"server_id": server_id, "args": args},
        )
    extra_args = args[from_index + 3 : stdio_index]
    environment_present = "env" in descriptor
    try:
        environment = normalize_mcp_environment(
            descriptor.get("env", {}), field="mcpServers.env"
        )
    except router_packager.PackagerError as exc:
        raise CustomerFlowError(
            exc.error_code,
            "checked-in .mcp.json has an invalid environment map",
            {"server_id": server_id, "cause": exc.error_code},
        ) from exc
    launch_contract = {
        "schema_version": 2 if environment_present else 1,
        "server_id": server_id,
        "transport": "stdio",
        "command": "uvx",
        "python_version": args[python_index + 1],
        "package_index": args[default_index + 1],
        "package_name": args[from_index + 1],
        "entrypoint": args[from_index + 2],
        "extra_args": extra_args,
        "forbidden_arg_fragments": [
            "auth",
            "credential",
            "endpoint",
            "profile",
            "tenant",
        ],
    }
    if environment_present:
        launch_contract["environment"] = dict(environment)
        launch_contract["environment_authority"] = "native_descriptor"
    return launch_contract


def _config_launch_contract(
    config: dict[str, Any],
) -> tuple[dict[str, Any] | None, bool]:
    """Return the client-owned launch overlay and whether its shape is legacy."""

    mcp_packaging = config.get("mcp_packaging")
    if mcp_packaging is None:
        return None, False
    if not isinstance(mcp_packaging, dict):
        raise CustomerFlowError(
            "mcp_setup_invalid", "mcp_packaging must be an object", {}
        )
    launch_contract = mcp_packaging.get("launch_contract")
    if launch_contract is None:
        return None, False
    if not isinstance(launch_contract, dict):
        raise CustomerFlowError(
            "mcp_setup_invalid",
            "router-plugin-config.json launch_contract must be an object",
            {},
        )
    legacy_shape = set(launch_contract) == {"environment"}
    v2_shape = set(launch_contract) == {
        "schema_version",
        "environment",
        "environment_authority",
    }
    v3_shape = set(launch_contract) == {
        "schema_version",
        "environment",
        "environment_authority",
        "package_version",
    }
    if not legacy_shape and not v2_shape and not v3_shape:
        raise CustomerFlowError(
            "mcp_setup_invalid",
            "router-plugin-config.json launch_contract must be the legacy environment override, v2 environment contract, or v3 package-version contract",
            {},
        )
    if v2_shape and (
        launch_contract["schema_version"] != 2
        or launch_contract["environment_authority"] != "config"
    ):
        raise CustomerFlowError(
            "mcp_setup_invalid",
            "router-plugin-config.json v2 launch_contract requires schema_version=2 and environment_authority=config",
            {},
        )
    if v3_shape and (
        launch_contract["schema_version"] != 3
        or launch_contract["environment_authority"] != "config"
    ):
        raise CustomerFlowError(
            "mcp_setup_invalid",
            "router-plugin-config.json v3 launch_contract requires schema_version=3 and environment_authority=config",
            {},
        )
    try:
        environment = normalize_mcp_environment(
            launch_contract["environment"],
            field="mcp_packaging.launch_contract.environment",
        )
    except router_packager.PackagerError as exc:
        raise CustomerFlowError(exc.error_code, exc.message, exc.details) from exc
    if legacy_shape:
        return {"environment": dict(environment)}, True
    overlay = dict(launch_contract)
    overlay["environment"] = dict(environment)
    return overlay, False


def _config_launch_environment(config: dict[str, Any]) -> dict[str, str] | None:
    overlay, _ = _config_launch_contract(config)
    return None if overlay is None else dict(overlay["environment"])


def _pending_config_launch_contract_migration(
    config: dict[str, Any],
    contract: McpLaunchContract,
) -> dict[str, Any] | None:
    """Describe the one-time client-config upgrade without mutating it."""

    overlay, legacy_shape = _config_launch_contract(config)
    environment = None if overlay is None else overlay["environment"]
    if legacy_shape:
        assert environment is not None
        resolved_environment = environment
    elif environment is None and contract.input_schema_version == 1:
        resolved_environment = {}
    else:
        return None
    migrated = dict(config)
    mcp_packaging = dict(config.get("mcp_packaging", {}))
    mcp_packaging["launch_contract"] = {
        "schema_version": 2,
        "environment": resolved_environment,
        "environment_authority": "config",
    }
    migrated["mcp_packaging"] = mcp_packaging
    return {
        "format": "mcp-launch-contract-config-migration-v1",
        "config_path": MCP_CONFIG_PATH.as_posix(),
        "from": "legacy_environment_override" if legacy_shape else "v1_launch_contract",
        "to": {
            "schema_version": 2,
            "environment": resolved_environment,
            "environment_authority": "config",
        },
        "updated_config": migrated,
    }


def _derive_skill_release_contract(skill_id: str, skill_text: str) -> dict[str, Any]:
    normalized_skill_text = normalize_whitespace(skill_text).casefold()
    required_phrases: list[str] = []
    missing_options: list[tuple[str, ...]] = []
    for options in REQUIRED_PHRASE_OPTIONS:
        matched = next(
            (
                phrase
                for phrase in options
                if normalize_whitespace(phrase).casefold() in normalized_skill_text
            ),
            None,
        )
        if matched is None:
            missing_options.append(options)
            continue
        required_phrases.append(matched)
    if missing_options:
        raise CustomerFlowError(
            "insufficient_evidence",
            "skill text is missing required release-control phrases",
            {"skill_id": skill_id, "missing_required_phrase_options": missing_options},
        )
    return {
        "skill_id": skill_id,
        "advertised_operation_ids": [
            "jira.issue.update",
            "sharepoint.site.read",
        ],
        "required_phrases": required_phrases,
        "forbidden_phrases": [FORBIDDEN_PHRASE],
    }


def _derive_source_root_text(
    repo_root: Path, candidate: CandidatePlugin, overrides: dict[str, Any]
) -> str:
    override = overrides.get("source_root")
    if override:
        return str(override)
    return (candidate.plugin_root / "skills").relative_to(repo_root).as_posix()


def _derive_payload_assets(
    repo_root: Path, registry_root: Path, *, mode: str, source_root_text: str
) -> list[dict[str, Any]]:
    del mode, source_root_text
    relative_registry = registry_root.relative_to(repo_root).as_posix()
    assets: list[dict[str, Any]] = []
    for source_name, asset_id in REGISTRY_ASSET_IDS.items():
        source = f"{relative_registry}/{source_name}"
        destination = (
            f"release-surface/{source_name}"
            if source_name != "schemas"
            else "release-surface/schemas"
        )
        if not (repo_root / source).exists():
            raise CustomerFlowError(
                "missing_release_surface_asset",
                "release-surface asset is missing",
                {
                    "source": source,
                },
            )
        assets.append(
            {
                "id": asset_id,
                "acquisition_mode": "copied",
                "source": source,
                "destination": destination,
                "ownership_role": asset_id,
                "ownership_class": "immutable-runtime-artifact",
            }
        )
    return assets


def _merge_nested(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_nested(merged[key], value)
            continue
        merged[key] = value
    return merged


def _resolve_mcp_identity_defaults(
    candidate: CandidatePlugin, overrides: dict[str, Any]
) -> tuple[str, str, str]:
    canonical_display_name = _derive_canonical_plugin_display_name(candidate, overrides)
    contract_name = _normalize_slug(canonical_display_name)
    if not contract_name:
        raise CustomerFlowError(
            "insufficient_evidence",
            "canonical plugin display name does not normalize to a non-empty slug",
            {"display_name": canonical_display_name},
        )
    resolved_plugin_slug = str(
        overrides.get("plugin_slug_override") or contract_name
    ).strip()
    if not resolved_plugin_slug:
        resolved_plugin_slug = contract_name
    resolved_surface_id = str(
        overrides.get("surface_id_override") or resolved_plugin_slug
    ).strip()
    if not resolved_surface_id:
        resolved_surface_id = resolved_plugin_slug
    return canonical_display_name, resolved_plugin_slug, resolved_surface_id


def _build_mcp_packaging_payload(
    *,
    repo_root: Path,
    candidate: CandidatePlugin,
    contract_name: str,
    resolved_plugin_slug: str,
    launch_contract: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    assert candidate.plugin_json is not None
    plugin_artifact_contract = {
        "name": contract_name,
        "description": candidate.plugin_json.get("description", ""),
        "author": {
            "name": _derive_project_author_name(
                repo_root, candidate.plugin_json.get("author")
            )
        },
        "interface": candidate.plugin_json.get("interface", {}),
        "skills_path": candidate.plugin_json.get("skills", "./skills/"),
        "mcp_servers_path": candidate.plugin_json.get("mcpServers", "./.mcp.json"),
    }
    interface = plugin_artifact_contract["interface"]
    category = interface.get("category") if isinstance(interface, dict) else None
    if category != "Productivity":
        raise CustomerFlowError(
            "insufficient_evidence",
            "MCP publication requires interface.category=Productivity",
            {"category": category},
        )
    required_preserved = [
        ".mcp.json",
        f"skills/{candidate.skill_id}/SKILL.md",
        "release-surface/manifest.json",
        "release-surface/release-manifest.json",
        "release-surface/operation-registry.json",
    ]
    mcp_packaging = {
        "plugin_artifact_contract": plugin_artifact_contract,
        "launch_contract": launch_contract,
        "release_surface": {
            "registry_manifest_asset_id": "registry-manifest",
            "release_manifest_asset_id": "release-manifest",
            "operation_registry_asset_id": "operation-registry",
            "schema_bundle_asset_id": "schema-bundle",
        },
        "skill_release_contract": _derive_skill_release_contract(
            candidate.skill_id, candidate.skill_text
        ),
        "publication": {"category": category},
        "staging_contract": {
            "format_version": 1,
            "marketplace_name": "local",
            "plugin_relpath": f"plugins/{resolved_plugin_slug}",
            "version_suffix_source": "cachebuster",
            "allowed_mutations": [
                {
                    "path": ".codex-plugin/plugin.json",
                    "field_path": "version",
                    "transform": "append-version-suffix",
                }
            ],
            "required_byte_preserved_paths": required_preserved,
        },
    }
    return mcp_packaging, required_preserved


def _derive_invocation(  # noqa: C901
    repo_root: Path,
    mode: str,
    surface_id_override: str | None,
    overrides: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    registry_root = _find_registry_root(repo_root, overrides, mode)
    candidate = _select_candidate(
        repo_root,
        registry_root,
        surface_id_override or overrides.get("surface_id_override"),
        mode,
    )
    assert candidate.plugin_json is not None
    plugin_name = str(candidate.plugin_json.get("name", "")).strip()
    if not plugin_name:
        raise CustomerFlowError(
            "insufficient_evidence",
            "checked-in plugin manifest is missing a plugin name",
            {"plugin_root": str(candidate.plugin_root.relative_to(repo_root))},
        )
    canonical_display_name, resolved_plugin_slug, resolved_surface_id = (
        _resolve_mcp_identity_defaults(candidate, overrides)
    )
    contract_name = _normalize_slug(canonical_display_name)
    assert contract_name
    if candidate.mcp_json is not None:
        launch_contract = _parse_launch_contract(candidate.mcp_json)
    else:
        launch_contract = _derive_launch_contract_from_repo_evidence(
            repo_root, registry_root, plugin_name
        )
    config = _load_json(repo_root / MCP_CONFIG_PATH)
    config_overlay, config_legacy_shape = _config_launch_contract(config)
    if config_overlay is not None:
        if config_legacy_shape:
            launch_contract.update(
                {
                    "schema_version": 2,
                    "environment": config_overlay["environment"],
                    "environment_authority": "config",
                }
            )
        else:
            launch_contract.update(config_overlay)
    source_root_text = _derive_source_root_text(repo_root, candidate, overrides)
    payload_assets = _derive_payload_assets(
        repo_root,
        registry_root,
        mode=mode,
        source_root_text=source_root_text,
    )
    mcp_packaging, required_preserved = _build_mcp_packaging_payload(
        repo_root=repo_root,
        candidate=candidate,
        contract_name=contract_name,
        resolved_plugin_slug=resolved_plugin_slug,
        launch_contract=launch_contract,
    )
    payload: dict[str, Any] = {
        "format_version": 1,
        "input_mode": "skill_list",
        "plugin_kind": "mcp_based",
        "repository_root": ".",
        "output_root": f"./{(DERIVED_GENERATED_DIR / resolved_plugin_slug).as_posix()}",
        "source_root": source_root_text,
        "skill_paths": [str(candidate.skill_path.relative_to(repo_root).as_posix())],
        "plugin_slug_override": resolved_plugin_slug,
        "display_name_override": canonical_display_name,
        "surface_id_override": resolved_surface_id,
        "publisher_slug_override": "local",
        "version_override": (
            candidate.plugin_json.get("version")
            if candidate.mcp_json is not None
            else _derive_runtime_version_from_repo_evidence(repo_root, registry_root)
        ),
        "payload_assets": payload_assets,
        "publication": mcp_packaging["publication"],
        "mcp_packaging": mcp_packaging,
    }
    payload = _merge_nested(payload, overrides)
    override_launch_contract = (
        overrides.get("mcp_packaging", {}).get("launch_contract", {})
        if isinstance(overrides.get("mcp_packaging"), dict)
        else {}
    )
    if (
        isinstance(override_launch_contract, dict)
        and "environment" in override_launch_contract
        and payload["mcp_packaging"]["launch_contract"].get("schema_version") != 3
    ):
        resolved_launch_contract = payload["mcp_packaging"]["launch_contract"]
        resolved_launch_contract["schema_version"] = 2
        resolved_launch_contract["environment_authority"] = "config"
    try:
        normalized_launch_contract = normalize_mcp_launch_contract(
            payload["mcp_packaging"]["launch_contract"]
        )
    except router_packager.PackagerError as exc:
        raise CustomerFlowError(exc.error_code, exc.message, exc.details) from exc
    payload["mcp_packaging"]["launch_contract"] = (
        mcp_launch_contract_invocation_payload(normalized_launch_contract)
    )
    pending_config_migration = _pending_config_launch_contract_migration(
        config, normalized_launch_contract
    )
    reported_config_migration = (
        {
            key: value
            for key, value in pending_config_migration.items()
            if key != "updated_config"
        }
        if pending_config_migration is not None
        else None
    )
    surface_id = str(payload.get("surface_id_override") or resolved_surface_id)
    invocation_path = (
        repo_root / DERIVED_INVOCATIONS_DIR / f"{_normalize_slug(surface_id)}.json"
    )
    report_path = (
        repo_root / DERIVATION_REPORTS_DIR / f"{_normalize_slug(surface_id)}.json"
    )
    evidence_files = [candidate.skill_path / "SKILL.md"]
    plugin_manifest_path = candidate.plugin_root / ".codex-plugin" / "plugin.json"
    if plugin_manifest_path.is_file():
        evidence_files.append(plugin_manifest_path)
    mcp_descriptor_path = candidate.plugin_root / ".mcp.json"
    if mcp_descriptor_path.is_file():
        evidence_files.append(mcp_descriptor_path)
    else:
        for path in [
            repo_root / ".mise.toml",
            repo_root / "pyproject.toml",
            repo_root / "specs" / "03-oci-codex-plugin.md",
            registry_root / "release-manifest.json",
        ]:
            if path.is_file():
                evidence_files.append(path)
    evidence_files.extend(
        [
            registry_root / "manifest.json",
            registry_root / "release-manifest.json",
            registry_root / "operation-registry.json",
        ]
    )
    fingerprint_payload = {
        "mode": mode,
        "skill_paths": payload["skill_paths"],
        "release_surface_sources": [
            asset["source"] for asset in payload["payload_assets"]
        ],
        "override_values": overrides,
        "file_hashes": {
            str(path.relative_to(repo_root)): _hash_file(path)
            for path in evidence_files
        },
        "wrapper_contract_version": 1,
    }
    report = {
        "surface_id": _normalize_slug(surface_id),
        "mode": mode,
        "selected_values": {
            "plugin_root": str(candidate.plugin_root.relative_to(repo_root)),
            "skill_id": candidate.skill_id,
            "registry_root": str(registry_root.relative_to(repo_root)),
            "source_root": source_root_text,
            "output_root": payload["output_root"],
        },
        "selected_value_precedence": {
            "surface_id_override": "explicit_user_override"
            if "surface_id_override" in overrides
            else candidate.evidence_source,
            "registry_root": "explicit_user_override"
            if "registry_root" in overrides
            else "repo_native_evidence",
            "plugin_candidate": candidate.evidence_source,
        },
        "source_evidence": {
            "skill_markdown": str(
                (candidate.skill_path / "SKILL.md").relative_to(repo_root)
            ),
            "candidate_source": candidate.evidence_source,
        },
        "rejected_candidates": [],
        "unresolved_required_fields": [],
        "evidence_fingerprint": _hash_bytes(
            json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")
        ),
        "written_artifact_paths": {
            "invocation_path": str(invocation_path.relative_to(repo_root)),
            "derivation_report_path": str(report_path.relative_to(repo_root)),
        },
        "packager_handoff_attempted": False,
        "pending_config_migration": reported_config_migration,
        "_pending_config_migration_write": pending_config_migration,
    }
    if plugin_manifest_path.is_file():
        report["source_evidence"]["plugin_manifest"] = str(
            plugin_manifest_path.relative_to(repo_root)
        )
    else:
        report["source_evidence"]["plugin_manifest_spec"] = str(
            (repo_root / "specs" / "03-oci-codex-plugin.md").relative_to(repo_root)
        )
    if mcp_descriptor_path.is_file():
        report["source_evidence"]["mcp_descriptor"] = str(
            mcp_descriptor_path.relative_to(repo_root)
        )
    else:
        report["source_evidence"]["mcp_descriptor_inputs"] = [
            str((repo_root / ".mise.toml").relative_to(repo_root)),
            str((repo_root / "pyproject.toml").relative_to(repo_root)),
            str((registry_root / "release-manifest.json").relative_to(repo_root)),
        ]
    return payload, report


def _run_packager_handoff(
    command: str, payload: dict[str, Any], repo_root: Path
) -> dict[str, Any]:
    handoff_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".router-packager-handoff-",
            suffix=".json",
            dir=repo_root,
            delete=False,
        ) as handle:
            handoff_path = Path(handle.name)
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return router_packager.run(command, handoff_path, repo_root)
    finally:
        if handoff_path is not None and handoff_path.exists():
            handoff_path.unlink()


def execute(
    command: str,
    repo_root: Path,
    *,
    mode: str = "reconciliation",
    surface_id: str | None = None,
    overrides_path: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    if command == "package":
        return _package(
            repo_root,
            mode=mode,
            surface_id=surface_id,
            overrides_path=overrides_path,
        )
    overrides: dict[str, Any] = {}
    if overrides_path is not None:
        overrides = _load_json(overrides_path.resolve())
        _validate_overrides(overrides)
    payload, report = _derive_invocation(repo_root, mode, surface_id, overrides)
    pending_config_migration = report.pop("_pending_config_migration_write")
    if command == "apply" and pending_config_migration is not None:
        # Validate the complete pre-migration package before changing the
        # client-owned authority. `plan` does not create the generated payload.
        _run_packager_handoff("plan", payload, repo_root)
        _write_json_atomically(
            repo_root / MCP_CONFIG_PATH,
            pending_config_migration["updated_config"],
        )
        payload, report = _derive_invocation(repo_root, mode, surface_id, overrides)
        report.pop("_pending_config_migration_write")
        assert report["pending_config_migration"] is None
    invocation_path = repo_root / report["written_artifact_paths"]["invocation_path"]
    report_path = repo_root / report["written_artifact_paths"]["derivation_report_path"]
    _write_json(invocation_path, payload)
    _write_json(report_path, report)
    result = {
        "command": command,
        "repo_root": str(repo_root),
        "invocation_path": str(invocation_path),
        "derivation_report_path": str(report_path),
        "invocation": payload,
        "derivation_report": report,
    }
    if command == "preview":
        return result
    report["packager_handoff_attempted"] = True
    _write_json(report_path, report)
    result["packager"] = _run_packager_handoff(command, payload, repo_root)
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Customer-facing MCP plugin packaging wrapper."
    )
    parser.add_argument("command", choices=("package", "preview", "plan", "apply"))
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument(
        "--mode", choices=("bootstrap", "reconciliation"), default="reconciliation"
    )
    parser.add_argument("--surface-id")
    parser.add_argument("--overrides", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        payload = execute(
            args.command,
            args.repo_root,
            mode=args.mode,
            surface_id=args.surface_id,
            overrides_path=args.overrides,
        )
    except CustomerFlowError as exc:
        print(json.dumps(exc.payload(), indent=2, sort_keys=True))
        return 1
    except PackagerError as exc:
        print(json.dumps(exc.payload(), indent=2, sort_keys=True))
        return 1
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if payload.get("outcome") == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
