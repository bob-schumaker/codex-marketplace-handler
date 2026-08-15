#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["packaging==26.3", "PyYAML==6.0.3"]
# ///
"""Repo-local setup scaffolding bootstrap for router plugin packaging."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


PACKAGER_SCRIPT = Path(__file__).resolve().parent / "router_plugin_packager.py"
PACKAGER_SPEC = importlib.util.spec_from_file_location(
    "router_plugin_packager", PACKAGER_SCRIPT
)
assert PACKAGER_SPEC is not None
assert PACKAGER_SPEC.loader is not None
router_packager = importlib.util.module_from_spec(PACKAGER_SPEC)
sys.modules[PACKAGER_SPEC.name] = router_packager
PACKAGER_SPEC.loader.exec_module(router_packager)

CUSTOMER_FLOW_SCRIPT = (
    Path(__file__).resolve().parent / "mcp_plugin_packaging_customer_flow.py"
)
CUSTOMER_FLOW_SPEC = importlib.util.spec_from_file_location(
    "mcp_plugin_packaging_customer_flow", CUSTOMER_FLOW_SCRIPT
)
assert CUSTOMER_FLOW_SPEC is not None
assert CUSTOMER_FLOW_SPEC.loader is not None
customer_flow = importlib.util.module_from_spec(CUSTOMER_FLOW_SPEC)
sys.modules[CUSTOMER_FLOW_SPEC.name] = customer_flow
CUSTOMER_FLOW_SPEC.loader.exec_module(customer_flow)

PackagerError = router_packager.PackagerError

DRAFTS_ROOT = Path(".codex-plugin") / "router-plugin-packager" / "drafts"
INVOCATION_PATH = DRAFTS_ROOT / "invocation.json"
REVIEW_NOTES_PATH = DRAFTS_ROOT / "review-notes.md"
COMPLETENESS_REPORT_PATH = DRAFTS_ROOT / "completeness-report.json"
HELPER_ARTIFACTS_PATH = DRAFTS_ROOT / "helper-artifacts.json"
MCP_DERIVATION_REPORT_PATH = DRAFTS_ROOT / "mcp-derivation-report.json"
ANALYSIS_REQUEST_PATH = DRAFTS_ROOT / "analysis-request.json"
GENERATED_SOURCE_ROOT = DRAFTS_ROOT / "generated-source" / "skills"
MCP_CONFIG_PATH = Path("router-plugin-config.json")
MCP_REGISTRY_ROOT = Path("router-plugin-registry")
MCP_REGISTRY_MANIFEST_PATH = MCP_REGISTRY_ROOT / "manifest.json"
MCP_RELEASE_MANIFEST_PATH = MCP_REGISTRY_ROOT / "release-manifest.json"
MCP_OPERATION_REGISTRY_PATH = MCP_REGISTRY_ROOT / "operation-registry.json"
MCP_SCAFFOLD_REPORT_PATH = MCP_REGISTRY_ROOT / "scaffold-report.json"
MCP_SETUP_INPUT_MANIFEST_PATH = MCP_REGISTRY_ROOT / "setup-input-manifest.json"
MCP_SCHEMAS_ROOT = MCP_REGISTRY_ROOT / "schemas"


class SetupError(Exception):
    """Raised when setup scaffolding cannot be generated or validated."""

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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_json_if_missing(path: Path, payload: dict[str, Any]) -> bool:
    """Create a scaffold record once without replacing client-owned inputs."""

    if path.exists():
        return False
    _write_json(path, payload)
    return True


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SetupError(
            "missing_required_artifact",
            "required setup artifact does not exist",
            {"path": str(path)},
        ) from exc
    except json.JSONDecodeError as exc:
        raise SetupError(
            "invalid_setup_artifact",
            "required setup artifact is not valid JSON",
            {"path": str(path), "error": str(exc)},
        ) from exc


def _relative_text(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _default_output_root(plugin_slug: str) -> str:
    return f"./.codex-plugin/router-plugin-packager/generated/{plugin_slug}"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_helper_artifacts(
    repo_root: Path, *, include_analysis_request: bool = False
) -> dict[str, Any]:
    manifest = {
        "format_version": 1,
        "repository_root": ".",
        "artifacts": [
            {
                "artifact_id": "invocation",
                "path": _relative_text(repo_root, repo_root / INVOCATION_PATH),
                "format": "json",
                "required": True,
                "consumed_by_packaging": True,
            },
            {
                "artifact_id": "review_notes",
                "path": _relative_text(repo_root, repo_root / REVIEW_NOTES_PATH),
                "format": "markdown",
                "required": False,
                "consumed_by_packaging": False,
            },
            {
                "artifact_id": "completeness_report",
                "path": _relative_text(repo_root, repo_root / COMPLETENESS_REPORT_PATH),
                "format": "json",
                "required": False,
                "consumed_by_packaging": False,
            },
            {
                "artifact_id": "helper_artifacts",
                "path": _relative_text(repo_root, repo_root / HELPER_ARTIFACTS_PATH),
                "format": "json",
                "required": False,
                "consumed_by_packaging": False,
            },
        ],
    }
    if include_analysis_request:
        manifest["artifacts"].append(
            {
                "artifact_id": "analysis_request",
                "path": _relative_text(repo_root, repo_root / ANALYSIS_REQUEST_PATH),
                "format": "json",
                "required": False,
                "consumed_by_packaging": False,
            }
        )
    return manifest


def _build_mcp_helper_artifacts(
    repo_root: Path, *, include_analysis_request: bool = False
) -> dict[str, Any]:
    manifest = _build_helper_artifacts(
        repo_root, include_analysis_request=include_analysis_request
    )
    manifest["artifacts"].append(
        {
            "artifact_id": "mcp_derivation_report",
            "path": _relative_text(repo_root, repo_root / MCP_DERIVATION_REPORT_PATH),
            "format": "json",
            "required": False,
            "consumed_by_packaging": False,
        }
    )
    manifest["artifacts"].extend(
        [
            {
                "artifact_id": "mcp_config",
                "path": MCP_CONFIG_PATH.as_posix(),
                "format": "json",
                "required": True,
                "consumed_by_packaging": True,
            },
            {
                "artifact_id": "mcp_scaffold_report",
                "path": MCP_SCAFFOLD_REPORT_PATH.as_posix(),
                "format": "json",
                "required": True,
                "consumed_by_packaging": True,
            },
        ]
    )
    return manifest


def _scaffold_mcp_registry_root(repo_root: Path) -> None:
    """Create durable, explicitly incomplete MCP inputs for a clean repository."""

    marker = router_packager.REQUIRED_MARKER_PREFIX
    _write_json_if_missing(
        repo_root / MCP_CONFIG_PATH,
        {
            "format_version": 1,
            "plugin_kind": "mcp_based",
            "protocol_version": "1.0",
            "registry_root": MCP_REGISTRY_ROOT.as_posix(),
            "surface_mode": f"{marker} choose preserve_mcp_first or generate_routed",
            "input_manifest_path": MCP_SETUP_INPUT_MANIFEST_PATH.as_posix(),
            "mcp_packaging": {
                "launch_contract": {
                    "schema_version": 2,
                    "environment": {},
                    "environment_authority": "config",
                }
            },
        },
    )
    (repo_root / MCP_SCHEMAS_ROOT).mkdir(parents=True, exist_ok=True)
    inventory = [
        MCP_REGISTRY_MANIFEST_PATH.name,
        MCP_RELEASE_MANIFEST_PATH.name,
        MCP_OPERATION_REGISTRY_PATH.name,
        MCP_SCHEMAS_ROOT.name,
    ]
    _write_json_if_missing(
        repo_root / MCP_REGISTRY_MANIFEST_PATH,
        {
            "format_version": 1,
            "release_asset_inventory": inventory,
            "release_manifest_path": MCP_RELEASE_MANIFEST_PATH.name,
            "operation_registry_path": MCP_OPERATION_REGISTRY_PATH.name,
            "schemas_root": MCP_SCHEMAS_ROOT.name,
        },
    )
    _write_json_if_missing(
        repo_root / MCP_RELEASE_MANIFEST_PATH,
        {
            "format_version": 1,
            "artifact_policy": f"{marker} supply release artifact policy",
            "package": f"{marker} supply package and entrypoint contract",
            "selected_operation_ids": f"{marker} select released operation ids",
        },
    )
    _write_json_if_missing(
        repo_root / MCP_OPERATION_REGISTRY_PATH,
        {"format_version": 1, "operations": f"{marker} supply released operations"},
    )
    _write_json_if_missing(
        repo_root / MCP_SETUP_INPUT_MANIFEST_PATH,
        {
            "format_version": 1,
            "config_path": MCP_CONFIG_PATH.as_posix(),
            "registry_root": MCP_REGISTRY_ROOT.as_posix(),
            "required_inputs": [
                MCP_REGISTRY_MANIFEST_PATH.as_posix(),
                MCP_RELEASE_MANIFEST_PATH.as_posix(),
                MCP_OPERATION_REGISTRY_PATH.as_posix(),
                MCP_SCHEMAS_ROOT.as_posix(),
            ],
        },
    )
    _write_json_if_missing(
        repo_root / MCP_SCAFFOLD_REPORT_PATH,
        {
            "format_version": 1,
            "state": "scaffolded",
            "required_marker_prefix": marker,
            "registry_root": MCP_REGISTRY_ROOT.as_posix(),
            "release_asset_inventory": inventory,
        },
    )


def _build_analysis_request(
    repo_root: Path,
    *,
    plugin_kind: str,
    mcp_mode: str,
    invocation: dict[str, Any],
) -> dict[str, Any]:
    unresolved_fields = [
        item["field"]
        for item in router_packager._collect_required_placeholders(
            invocation, required_marker_prefix=router_packager.REQUIRED_MARKER_PREFIX
        )
    ]
    return {
        "format_version": 1,
        "analysis_kind": "model_review_request",
        "repository_root": ".",
        "plugin_kind": plugin_kind,
        "mcp_mode": mcp_mode,
        "objective": (
            "Review the scaffolded plugin packaging inputs using only repository-local"
            " evidence and identify any values that can be filled or must remain"
            " unresolved."
        ),
        "inputs": {
            "invocation_path": _relative_text(repo_root, repo_root / INVOCATION_PATH),
            "review_notes_path": _relative_text(
                repo_root, repo_root / REVIEW_NOTES_PATH
            ),
            "completeness_report_path": _relative_text(
                repo_root, repo_root / COMPLETENESS_REPORT_PATH
            ),
        },
        "constraints": [
            "Use only files that exist in the repository.",
            "Do not use network access or information from other repositories.",
            "Do not invent missing values; leave unresolved fields explicit.",
        ],
        "expected_output": {
            "status_values": ["complete", "partial", "cannot_derive"],
            "required_keys": [
                "status",
                "filled_fields",
                "unresolved_fields",
                "supporting_files",
            ],
        },
        "current_unresolved_fields": unresolved_fields,
    }


def _review_notes(
    *,
    source_root_text: str,
    skill_paths: list[str],
    plugin_slug: str,
    display_name: str,
    output_root: str,
    publisher_slug: str | None,
    resolved_branding: dict[str, str],
    ambiguous_branding: dict[str, list[str]],
) -> str:
    inferred_lines = [
        f"- `source_root`: `{source_root_text}`",
        f"- `skill_paths`: {', '.join(f'`{path}`' for path in skill_paths)}",
        f"- `plugin_slug_override`: `{plugin_slug}`",
        f"- `display_name_override`: `{display_name}`",
        f"- `output_root`: `{output_root}`",
    ]
    copied_lines: list[str] = []
    if publisher_slug is not None:
        copied_lines.append(f"- `publisher_slug_override`: `{publisher_slug}`")
    if resolved_branding:
        copied_lines.extend(
            f"- `branding_asset_overrides.{slot}`: `{path}`"
            for slot, path in sorted(resolved_branding.items())
        )
    unresolved_lines = [
        f"- `branding_asset_overrides.{slot}`: choose one of "
        f"{', '.join(f'`{candidate}`' for candidate in candidates)}"
        for slot, candidates in sorted(ambiguous_branding.items())
    ]
    optional_lines = []
    if publisher_slug is None:
        optional_lines.append(
            "- `publisher_slug_override`: unset; strict packaging will default to `local`"
        )
    return "\n".join(
        [
            "# Router plugin packager setup review",
            "",
            "This draft was generated from one repo inspection pass. Review the"
            " explicit skill list and any unresolved markers before running the"
            " strict packager.",
            "",
            "## Inferred values",
            "",
            *inferred_lines,
            "",
            "## Copied-through reviewed values",
            "",
            *(copied_lines or ["- none"]),
            "",
            "## Unresolved required values",
            "",
            *(unresolved_lines or ["- none"]),
            "",
            "## Optional unset values",
            "",
            *(optional_lines or ["- none"]),
            "",
            "## Why unresolved values remain",
            "",
            *(
                [
                    f"- `{slot}` has multiple equally strong branding candidates; the helper will not guess."
                    for slot in sorted(ambiguous_branding)
                ]
                or ["- none"]
            ),
            "",
        ]
    )


def _mcp_review_notes(
    *, payload: dict[str, Any], report: dict[str, Any], fallback_reason: str | None
) -> str:
    selected = dict(report.get("selected_values", {}))
    inferred_lines = [
        f"- `plugin_kind`: `{payload.get('plugin_kind')}`",
        f"- `skill_paths`: {', '.join(f'`{path}`' for path in payload.get('skill_paths', [])) or 'none'}",
        f"- `source_root`: `{payload.get('source_root', '')}`",
        f"- `output_root`: `{payload.get('output_root', '')}`",
        f"- `surface_id_override`: `{payload.get('surface_id_override', '')}`",
        f"- `version_override`: `{payload.get('version_override', '')}`",
    ]
    if selected.get("registry_root"):
        inferred_lines.append(f"- `registry_root`: `{selected['registry_root']}`")
    unresolved_placeholders = router_packager._collect_required_placeholders(
        payload, required_marker_prefix=router_packager.REQUIRED_MARKER_PREFIX
    )
    unresolved_lines = [
        f"- `{entry['field']}`: `{entry['value']}`" for entry in unresolved_placeholders
    ]
    why_lines = []
    if fallback_reason is not None:
        why_lines.append(
            f"- helper could not derive a complete MCP invocation: {fallback_reason}"
        )
    return "\n".join(
        [
            "# Router plugin packager setup review",
            "",
            "This draft was generated for MCP-first packaging. Review the inferred"
            " release-surface inputs and replace any required markers before"
            " running the strict packager.",
            "",
            "## Inferred values",
            "",
            *inferred_lines,
            "",
            "## Copied-through reviewed values",
            "",
            "- none",
            "",
            "## Unresolved required values",
            "",
            *(unresolved_lines or ["- none"]),
            "",
            "## Optional unset values",
            "",
            "- `publisher_slug_override`: unset; strict packaging will default to `local` unless explicitly supplied",
            "",
            "## Why unresolved values remain",
            "",
            *(why_lines or ["- none"]),
            "",
        ]
    )


def _generated_mcp_skill_display_name(
    display_name: str | None, plugin_slug: str
) -> str:
    if (
        isinstance(display_name, str)
        and display_name
        and not display_name.startswith(router_packager.REQUIRED_MARKER_PREFIX)
    ):
        return display_name
    return router_packager._display_name_from_slug(plugin_slug)


def _ensure_generated_mcp_guidance_skill(
    repo_root: Path, *, plugin_slug: str, display_name: str | None
) -> tuple[str, list[str]]:
    source_root = repo_root / GENERATED_SOURCE_ROOT
    skill_root = source_root / plugin_slug
    skill_display_name = _generated_mcp_skill_display_name(display_name, plugin_slug)
    skill_text = "\n".join(
        [
            "---",
            f"name: {plugin_slug}",
            f"description: Use {skill_display_name} MCP workflows through the packaged release surface.",
            "---",
            "",
            f"# {skill_display_name}",
            "",
            "Use the packaged MCP release surface for approved workflows.",
            "Treat the release manifest and schema bundle as the authority for",
            "available operations and input shapes.",
            "",
        ]
    )
    _write_text(skill_root / "SKILL.md", skill_text)
    return (
        _relative_text(repo_root, source_root),
        [_relative_text(repo_root, skill_root)],
    )


def _build_scaffold_payloads(
    repo_root: Path,
    *,
    display_name: str | None = None,
    version: str | None = None,
    analyze: bool = False,
) -> tuple[dict[str, Any], str]:
    source_root, source_root_text = router_packager._discover_source_root(repo_root)
    skill_roots = router_packager._discover_visible_skill_paths(source_root)
    skill_paths = [_relative_text(repo_root, path) for path in skill_roots]
    bootstrap_state = router_packager._load_bootstrap_state(repo_root)
    repo_slug = router_packager._normalize_slug(repo_root.name)
    if not repo_slug:
        raise SetupError(
            "invalid_repo_name",
            "repository name does not normalize to a non-empty plugin slug",
            {"repository_root": str(repo_root)},
        )
    resolved_display_name = display_name or router_packager._display_name_from_slug(
        repo_slug
    )
    publisher_slug = None
    if bootstrap_state:
        raw = bootstrap_state.get("publisher_slug")
        if isinstance(raw, str) and raw.strip():
            publisher_slug = router_packager._normalize_slug(raw)
    discovered_branding, ambiguous_branding = router_packager._discover_branding_assets(
        repo_root
    )
    invocation: dict[str, Any] = {
        "format_version": 1,
        "input_mode": "skill_list",
        "plugin_kind": "skills_only",
        "source_root": source_root_text,
        "repository_root": ".",
        "output_root": _default_output_root(repo_slug),
        "skill_paths": skill_paths,
        "plugin_slug_override": repo_slug,
        "display_name_override": resolved_display_name,
    }
    if version is not None:
        invocation["version_override"] = version
    if publisher_slug is not None:
        invocation["publisher_slug_override"] = publisher_slug
    branding_overrides = dict(discovered_branding)
    for slot, candidates in sorted(ambiguous_branding.items()):
        branding_overrides[slot] = (
            f"{router_packager.REQUIRED_MARKER_PREFIX} choose branding winner for"
            f" {slot} from {', '.join(candidates)}"
        )
    if branding_overrides:
        invocation["branding_asset_overrides"] = branding_overrides
    helper_artifacts = _build_helper_artifacts(
        repo_root, include_analysis_request=analyze
    )
    review_notes = _review_notes(
        source_root_text=source_root_text,
        skill_paths=skill_paths,
        plugin_slug=repo_slug,
        display_name=resolved_display_name,
        output_root=invocation["output_root"],
        publisher_slug=publisher_slug,
        resolved_branding=discovered_branding,
        ambiguous_branding=ambiguous_branding,
    )
    payloads: dict[str, Any] = {
        "invocation": invocation,
        "helper_artifacts": helper_artifacts,
    }
    if analyze:
        payloads["analysis_request"] = _build_analysis_request(
            repo_root,
            plugin_kind="skills_only",
            mcp_mode="reconciliation",
            invocation=invocation,
        )
    return (payloads, review_notes)


def _fallback_mcp_invocation(
    repo_root: Path,
    reason: str,
    *,
    display_name: str | None = None,
    version: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    repo_slug = router_packager._normalize_slug(repo_root.name) or "plugin"
    source_root_text: str | None = None
    skill_paths: list[str] = []
    derived_display_name: str | None = None
    try:
        source_root, discovered_source_root_text = (
            router_packager._discover_source_root(repo_root)
        )
        source_root_text = discovered_source_root_text
        skill_roots = router_packager._discover_visible_skill_paths(source_root)
        if skill_roots:
            skill_paths = [_relative_text(repo_root, path) for path in skill_roots]
        if len(skill_roots) == 1:
            skill_text = (skill_roots[0] / "SKILL.md").read_text(encoding="utf-8")
            derived_display_name = customer_flow._extract_skill_heading_display_name(
                skill_text
            )
    except PackagerError:
        pass
    resolved_display_name = (
        display_name
        or derived_display_name
        or f"__REQUIRED__: choose plugin display name for {repo_slug}"
    )
    resolved_slug = (
        router_packager._normalize_slug(resolved_display_name)
        if not resolved_display_name.startswith(router_packager.REQUIRED_MARKER_PREFIX)
        else repo_slug
    ) or repo_slug
    if source_root_text is None or not skill_paths:
        source_root_text, skill_paths = _ensure_generated_mcp_guidance_skill(
            repo_root,
            plugin_slug=resolved_slug,
            display_name=resolved_display_name,
        )
    payload = {
        "format_version": 1,
        "input_mode": "skill_list",
        "plugin_kind": "mcp_based",
        "repository_root": ".",
        "output_root": _default_output_root(resolved_slug),
        "source_root": source_root_text,
        "skill_paths": skill_paths,
        "plugin_slug_override": resolved_slug,
        "display_name_override": resolved_display_name,
        "surface_id_override": resolved_slug,
        "version_override": version or "__REQUIRED__: choose runtime version",
        "mcp_packaging": "__REQUIRED__: supply mcp_packaging contract after registry_root and guidance skill are confirmed",
    }
    report = {
        "mode": "bootstrap",
        "selected_values": {
            "source_root": source_root_text,
            "output_root": payload["output_root"],
        },
        "unresolved_required_fields": [
            {"field": "mcp_packaging", "reason": reason},
        ],
    }
    return payload, report


def _build_mcp_scaffold_payloads(
    repo_root: Path,
    *,
    mcp_mode: str,
    display_name: str | None = None,
    version: str | None = None,
    analyze: bool = False,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    try:
        derive_overrides = (
            {"display_name_override": display_name} if display_name is not None else {}
        )
        payload, report = customer_flow._derive_invocation(
            repo_root, mcp_mode, None, derive_overrides
        )
        if version is not None:
            payload["version_override"] = version
        fallback_reason = None
    except customer_flow.CustomerFlowError as exc:
        payload, report = _fallback_mcp_invocation(
            repo_root,
            exc.message,
            display_name=display_name,
            version=version,
        )
        fallback_reason = exc.message
    helper_artifacts = _build_mcp_helper_artifacts(
        repo_root, include_analysis_request=analyze
    )
    review_notes = _mcp_review_notes(
        payload=payload, report=report, fallback_reason=fallback_reason
    )
    payloads: dict[str, Any] = {
        "invocation": payload,
        "helper_artifacts": helper_artifacts,
        "mcp_derivation_report": report,
    }
    if analyze:
        payloads["analysis_request"] = _build_analysis_request(
            repo_root,
            plugin_kind="mcp_based",
            mcp_mode=mcp_mode,
            invocation=payload,
        )
    return (payloads, review_notes, report)


def _collect_report_from_manifest(repo_root: Path) -> dict[str, Any]:
    manifest_path = repo_root / HELPER_ARTIFACTS_PATH
    manifest = _load_json(manifest_path)
    if manifest.get("format_version") != 1 or not isinstance(
        manifest.get("artifacts"), list
    ):
        raise SetupError(
            "invalid_setup_manifest",
            "helper-artifacts.json must expose format_version=1 and an artifacts list",
            {"path": str(manifest_path)},
        )
    missing_required_files: list[dict[str, str]] = []
    unresolved_placeholders: list[dict[str, str]] = []
    checked_artifacts: list[dict[str, Any]] = []
    for artifact in manifest["artifacts"]:
        if not isinstance(artifact, dict):
            raise SetupError(
                "invalid_setup_manifest",
                "each setup artifact entry must be a mapping",
                {"path": str(manifest_path)},
            )
        artifact_id = str(artifact.get("artifact_id", "")).strip()
        relative_path = str(artifact.get("path", "")).strip()
        format_name = str(artifact.get("format", "")).strip()
        required = bool(artifact.get("required"))
        consumed_by_packaging = bool(artifact.get("consumed_by_packaging"))
        artifact_path = (repo_root / relative_path).resolve()
        router_packager._validate_relative_path(repo_root, artifact_path, artifact_id)
        exists = artifact_path.exists()
        checked_artifacts.append(
            {
                "artifact_id": artifact_id,
                "path": relative_path,
                "required": required,
                "consumed_by_packaging": consumed_by_packaging,
                "exists": exists,
            }
        )
        if required and not exists:
            missing_required_files.append(
                {"artifact_id": artifact_id, "path": relative_path}
            )
            continue
        if not consumed_by_packaging or not exists:
            continue
        parsed_payload: Any
        if format_name == "json":
            parsed_payload = _load_json(artifact_path)
        elif format_name == "yaml":
            parsed_payload = router_packager._load_yaml(artifact_path)
        else:
            raise SetupError(
                "unsupported_setup_artifact_format",
                "consumed setup artifacts must be json or yaml",
                {"artifact_id": artifact_id, "format": format_name},
            )
        for placeholder in router_packager._collect_required_placeholders(
            parsed_payload,
            required_marker_prefix=router_packager.REQUIRED_MARKER_PREFIX,
        ):
            if placeholder["field"] == "required_marker_prefix":
                continue
            unresolved_placeholders.append(
                {
                    "artifact_id": artifact_id,
                    "path": relative_path,
                    "field": placeholder["field"],
                    "value": placeholder["value"],
                }
            )
    status = (
        "incomplete"
        if missing_required_files or unresolved_placeholders
        else "complete"
    )
    return {
        "format_version": 1,
        "repository_root": ".",
        "required_marker_prefix": router_packager.REQUIRED_MARKER_PREFIX,
        "status": status,
        "helper_artifacts_path": _relative_text(repo_root, manifest_path),
        "checked_artifacts": checked_artifacts,
        "missing_required_files": missing_required_files,
        "unresolved_placeholders": unresolved_placeholders,
    }


def execute(
    command: str,
    repo_root: Path,
    *,
    plugin_kind: str = "skills_only",
    mcp_mode: str = "reconciliation",
    display_name: str | None = None,
    version: str | None = None,
    analyze: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    if command == "scaffold":
        if plugin_kind == "skills_only":
            payloads, review_notes = _build_scaffold_payloads(
                repo_root,
                display_name=display_name,
                version=version,
                analyze=analyze,
            )
        elif plugin_kind == "mcp_based":
            _scaffold_mcp_registry_root(repo_root)
            payloads, review_notes, _report = _build_mcp_scaffold_payloads(
                repo_root,
                mcp_mode=mcp_mode,
                display_name=display_name,
                version=version,
                analyze=analyze,
            )
            _write_json(
                repo_root / MCP_DERIVATION_REPORT_PATH,
                payloads["mcp_derivation_report"],
            )
        else:
            raise SetupError(
                "invalid_plugin_kind",
                "plugin_kind must be skills_only or mcp_based",
                {"plugin_kind": plugin_kind},
            )
        _write_json(repo_root / INVOCATION_PATH, payloads["invocation"])
        _write_json(repo_root / HELPER_ARTIFACTS_PATH, payloads["helper_artifacts"])
        (repo_root / REVIEW_NOTES_PATH).parent.mkdir(parents=True, exist_ok=True)
        (repo_root / REVIEW_NOTES_PATH).write_text(review_notes, encoding="utf-8")
        if analyze:
            _write_json(repo_root / ANALYSIS_REQUEST_PATH, payloads["analysis_request"])
    elif command != "validate":
        raise SetupError(
            "invalid_setup_command",
            "setup command must be scaffold or validate",
            {"command": command},
        )
    report = _collect_report_from_manifest(repo_root)
    _write_json(repo_root / COMPLETENESS_REPORT_PATH, report)
    return {
        "command": command,
        "invocation_path": _relative_text(repo_root, repo_root / INVOCATION_PATH),
        "review_notes_path": _relative_text(repo_root, repo_root / REVIEW_NOTES_PATH),
        "completeness_report_path": _relative_text(
            repo_root, repo_root / COMPLETENESS_REPORT_PATH
        ),
        "helper_artifacts_path": _relative_text(
            repo_root, repo_root / HELPER_ARTIFACTS_PATH
        ),
        "analysis_requested": analyze,
        "plugin_kind": plugin_kind,
        "completeness_report": report,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("scaffold", "validate"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--plugin-kind", choices=("skills_only", "mcp_based"), default="skills_only"
    )
    parser.add_argument(
        "--mcp-mode", choices=("bootstrap", "reconciliation"), default="reconciliation"
    )
    parser.add_argument("--display-name")
    parser.add_argument("--version")
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Write a model-review request artifact next to the scaffolded drafts.",
    )
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser


def _print_text(payload: dict[str, Any]) -> None:
    report = payload["completeness_report"]
    print(payload["command"])
    print(payload["invocation_path"])
    print(report["status"])


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        payload = execute(
            args.command,
            args.repo_root,
            plugin_kind=args.plugin_kind,
            mcp_mode=args.mcp_mode,
            display_name=args.display_name,
            version=args.version,
            analyze=args.analyze,
        )
    except SetupError as exc:
        print(json.dumps(exc.payload(), indent=2, sort_keys=True))
        return 1
    except PackagerError as exc:
        print(json.dumps(exc.payload(), indent=2, sort_keys=True))
        return 1
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
