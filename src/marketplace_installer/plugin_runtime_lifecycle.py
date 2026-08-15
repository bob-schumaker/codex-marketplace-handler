# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_OPERATIONS = {"verify", "install", "update", "repair", "rollback"}
ALLOWED_CONTROL_OPERATIONS = ["verify", "install", "update", "repair", "rollback"]
ALLOWED_MIGRATION_STATES = {
    "none",
    "pending",
    "completed",
    "failed",
    "rollback_blocked",
}
ALLOWED_RECONCILIATION_MODES = {
    "install-if-missing",
    "replace-if-owned",
    "verify-only",
}
ALLOWED_VERIFICATION_TARGETS = {
    "active_file_exists",
    "active_file_contains",
    "user_state_exists",
    "integration_exists",
}
INSTALL_STATE_RELATIVE = Path(".runtime-lifecycle") / "install-state.json"
WORKSPACE_ROOT_RELATIVE = Path(".runtime-lifecycle") / "workspaces"
RELEASES_ROOT_RELATIVE = Path("releases")
USER_STATE_ROOT_RELATIVE = Path("user-state")
INTEGRATION_MARKER_SUFFIX = ".runtime-owner.json"
PAYLOAD_MANIFEST_RELATIVE = Path(".codex-plugin") / "payload-manifest.json"
RELEASE_METADATA_RELATIVE = Path(".codex-plugin") / "release-metadata.json"
PLUGIN_MANIFEST_RELATIVE = Path(".codex-plugin") / "plugin.json"
MAX_FILE_BYTES = 2 * 1024 * 1024


class LifecycleError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class ManifestEntry:
    relative_output_path: str
    content_hash: str
    acquisition_mode: str
    ownership_role: str
    ownership_class: str | None
    file_mode: str


@dataclass(frozen=True)
class ControlSurface:
    skill_id: str
    operations: tuple[str, ...]


@dataclass(frozen=True)
class IntegrationPoint:
    integration_id: str
    ownership_class: str
    target_relpath: str
    source_relpath: str
    reconciliation_mode: str
    restart_required: bool
    repair_policy: str
    rollback_policy: str


@dataclass(frozen=True)
class VerificationTarget:
    target_id: str
    kind: str
    relative_path: str | None
    integration_id: str | None
    expected_text: str | None


@dataclass(frozen=True)
class PluginContract:
    plugin_root: Path
    plugin_id: str
    plugin_version: str
    payload_fingerprint: str
    runtime_compatibility_version: str
    migration_contract_version: str | None
    rollback_compatibility_hints: dict[str, Any] | None
    control_surface: ControlSurface
    owned_integration_root: str | None
    payload_manifest: list[ManifestEntry]
    integration_points: tuple[IntegrationPoint, ...]
    verification_targets: tuple[VerificationTarget, ...]


@dataclass(frozen=True)
class InstallState:
    schema_version: str
    plugin_id: str
    plugin_version: str
    runtime_compatibility_version: str
    payload_fingerprint: str
    activation_timestamp: str
    install_root: Path
    active_release_path: Path
    rollback_candidate_path: Path | None
    rollback_candidate_fingerprint: str | None
    migration_state: str
    migration_version: str | None
    owned_integration_status: dict[str, dict[str, Any]]
    last_verify_code: str | None
    last_verify_timestamp: str | None


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LifecycleError(
            "missing_layer1_artifact",
            "required Layer 1 artifact is missing",
            {"path": str(path)},
        ) from exc
    except json.JSONDecodeError as exc:
        raise LifecycleError(
            "malformed_layer1_artifact",
            "required Layer 1 artifact is malformed JSON",
            {"path": str(path)},
        ) from exc


def _require_string(
    payload: dict[str, Any], field: str, *, allow_empty: bool = False
) -> str:
    value = payload.get(field)
    if not isinstance(value, str):
        raise LifecycleError(
            "invalid_contract",
            "field must be a string",
            {"field": field, "value": value},
        )
    if not allow_empty and not value.strip():
        raise LifecycleError(
            "invalid_contract",
            "field must not be empty",
            {"field": field, "value": value},
        )
    return value


def _looks_like_plugin_cache_path(path: Path) -> bool:
    parts = path.parts
    for index, part in enumerate(parts[:-2]):
        if part == ".codex" and parts[index + 1 : index + 3] == ("plugins", "cache"):
            return True
    return False


def _validate_install_root(install_root: Path, plugin_root: Path) -> Path:
    resolved = install_root.resolve()
    if not resolved.is_absolute():
        raise LifecycleError(
            "invalid_install_root",
            "install_root must resolve to an absolute path",
            {"install_root": str(install_root)},
        )
    if _looks_like_plugin_cache_path(resolved):
        raise LifecycleError(
            "invalid_install_root",
            "install_root must not resolve inside a Codex plugin cache path",
            {"install_root": str(resolved)},
        )
    try:
        resolved.relative_to(plugin_root.resolve())
    except ValueError:
        pass
    else:
        raise LifecycleError(
            "invalid_install_root",
            "install_root must not resolve inside the immutable plugin payload root",
            {"install_root": str(resolved), "plugin_root": str(plugin_root.resolve())},
        )
    existing_ancestor = resolved
    while not existing_ancestor.exists():
        existing_ancestor = existing_ancestor.parent
    if existing_ancestor.stat().st_uid != os.getuid():
        raise LifecycleError(
            "invalid_install_root",
            "install_root must be rooted beneath a user-owned directory",
            {
                "install_root": str(resolved),
                "existing_ancestor": str(existing_ancestor),
            },
        )
    return resolved


def _validate_relative_path(value: str, field: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise LifecycleError(
            "invalid_contract",
            "path must remain relative to the declared ownership boundary",
            {"field": field, "value": value},
        )
    return path.as_posix()


def _parse_control_surface(
    plugin_root: Path, payload: dict[str, Any]
) -> ControlSurface:
    raw = payload.get("control_surface")
    if not isinstance(raw, dict):
        raise LifecycleError(
            "missing_layer1_artifact",
            "release metadata must declare exactly one lifecycle control surface",
            {"field": "control_surface"},
        )
    skill_id = _require_string(raw, "skill_id")
    operations = raw.get("operations")
    if not isinstance(operations, list) or not operations:
        raise LifecycleError(
            "invalid_contract",
            "control_surface.operations must be a non-empty list",
            {"field": "control_surface.operations", "value": operations},
        )
    normalized_ops: list[str] = []
    for operation in operations:
        if operation not in ALLOWED_CONTROL_OPERATIONS:
            raise LifecycleError(
                "invalid_contract",
                "unsupported lifecycle operation",
                {"operation": operation},
            )
        normalized_ops.append(operation)
    skill_path = plugin_root / "skills" / skill_id / "SKILL.md"
    if not skill_path.is_file():
        raise LifecycleError(
            "missing_layer1_artifact",
            "declared lifecycle skill is missing from the plugin payload",
            {"skill_id": skill_id, "path": str(skill_path)},
        )
    return ControlSurface(skill_id=skill_id, operations=tuple(normalized_ops))


def _parse_manifest(payload: dict[str, Any]) -> tuple[str, list[ManifestEntry]]:
    fingerprint = _require_string(payload, "payload_fingerprint")
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise LifecycleError(
            "missing_layer1_artifact",
            "payload manifest must contain at least one entry",
            {"field": "entries"},
        )
    entries: list[ManifestEntry] = []
    for index, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            raise LifecycleError(
                "invalid_contract",
                "payload manifest entry must be a mapping",
                {"field": f"entries[{index}]"},
            )
        entries.append(
            ManifestEntry(
                relative_output_path=_validate_relative_path(
                    _require_string(entry, "relative_output_path"),
                    f"entries[{index}].relative_output_path",
                ),
                content_hash=_require_string(entry, "content_hash"),
                acquisition_mode=_require_string(entry, "acquisition_mode"),
                ownership_role=_require_string(entry, "ownership_role"),
                ownership_class=(
                    _require_string(entry, "ownership_class")
                    if entry.get("ownership_class") is not None
                    else None
                ),
                file_mode=_require_string(entry, "file_mode"),
            )
        )
    return fingerprint, entries


def _parse_integration_points(
    payload: dict[str, Any], manifest_by_path: dict[str, ManifestEntry]
) -> tuple[IntegrationPoint, ...]:
    raw_points = payload.get("integration_points", [])
    if not isinstance(raw_points, list):
        raise LifecycleError(
            "invalid_contract",
            "integration_points must be a list when present",
            {"field": "integration_points"},
        )
    owned_integration_root = _parse_owned_integration_root(payload, raw_points)
    points: list[IntegrationPoint] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_points):
        points.append(
            _parse_one_integration_point(
                raw,
                index,
                manifest_by_path,
                seen,
                owned_integration_root,
            )
        )
    return tuple(points)


def _parse_owned_integration_root(
    payload: dict[str, Any], raw_points: list[Any]
) -> str | None:
    raw_root = payload.get("owned_integration_root")
    if raw_root is None:
        if raw_points:
            raise LifecycleError(
                "missing_layer1_artifact",
                "release metadata must declare owned_integration_root when integration_points are present",
                {"field": "owned_integration_root"},
            )
        return None
    if not isinstance(raw_root, str):
        raise LifecycleError(
            "invalid_contract",
            "owned_integration_root must be a string when present",
            {"field": "owned_integration_root", "value": raw_root},
        )
    return _validate_relative_path(raw_root, "owned_integration_root")


def _parse_one_integration_point(
    raw: Any,
    index: int,
    manifest_by_path: dict[str, ManifestEntry],
    seen: set[str],
    owned_integration_root: str | None,
) -> IntegrationPoint:
    if not isinstance(raw, dict):
        raise LifecycleError(
            "invalid_contract",
            "integration point must be a mapping",
            {"field": f"integration_points[{index}]"},
        )
    integration_id = _require_string(raw, "id")
    _ensure_unique_integration_id(integration_id, seen)
    ownership_class = _parse_integration_ownership(integration_id, raw)
    target_relpath = _parse_integration_target(
        integration_id,
        raw,
        index,
        owned_integration_root,
    )
    source_relpath = _parse_integration_source(
        integration_id, raw, index, manifest_by_path
    )
    reconciliation_mode = _parse_reconciliation_mode(integration_id, raw)
    restart_required = _parse_restart_required(integration_id, raw)
    return IntegrationPoint(
        integration_id=integration_id,
        ownership_class=ownership_class,
        target_relpath=target_relpath,
        source_relpath=source_relpath,
        reconciliation_mode=reconciliation_mode,
        restart_required=restart_required,
        repair_policy=_require_string(raw, "repair_policy"),
        rollback_policy=_require_string(raw, "rollback_policy"),
    )


def _ensure_unique_integration_id(integration_id: str, seen: set[str]) -> None:
    normalized_id = integration_id.strip()
    if normalized_id in seen:
        raise LifecycleError(
            "invalid_contract",
            "integration point ids must be unique",
            {"integration_id": integration_id},
        )
    seen.add(normalized_id)


def _parse_integration_ownership(integration_id: str, raw: dict[str, Any]) -> str:
    ownership_class = _require_string(raw, "ownership_class")
    if ownership_class != "owned-integration-artifact":
        raise LifecycleError(
            "invalid_contract",
            "integration points must declare owned-integration-artifact ownership",
            {"integration_id": integration_id, "ownership_class": ownership_class},
        )
    return ownership_class


def _parse_integration_target(
    integration_id: str,
    raw: dict[str, Any],
    index: int,
    owned_integration_root: str | None,
) -> str:
    try:
        target_relpath = _validate_relative_path(
            _require_string(raw, "target_relpath"),
            f"integration_points[{index}].target_relpath",
        )
    except LifecycleError as exc:
        raise LifecycleError(
            "undeclared_integration_target",
            "integration target must remain within the declared owned boundary",
            {"integration_id": integration_id, "field": "target_relpath"},
        ) from exc
    if owned_integration_root is None:
        raise LifecycleError(
            "missing_layer1_artifact",
            "integration target requires a declared owned integration root",
            {"integration_id": integration_id},
        )
    owned_prefix = f"{owned_integration_root.rstrip('/')}/"
    if target_relpath != owned_integration_root and not target_relpath.startswith(
        owned_prefix
    ):
        raise LifecycleError(
            "undeclared_integration_target",
            "integration target must stay within the declared owned integration boundary",
            {
                "integration_id": integration_id,
                "target_relpath": target_relpath,
                "owned_integration_root": owned_integration_root,
            },
        )
    return target_relpath


def _parse_integration_source(
    integration_id: str,
    raw: dict[str, Any],
    index: int,
    manifest_by_path: dict[str, ManifestEntry],
) -> str:
    source_relpath = _validate_relative_path(
        _require_string(raw, "source_relpath"),
        f"integration_points[{index}].source_relpath",
    )
    source_entry = manifest_by_path.get(source_relpath)
    if source_entry is None:
        raise LifecycleError(
            "missing_layer1_artifact",
            "integration point source must exist in the payload manifest",
            {"integration_id": integration_id, "source_relpath": source_relpath},
        )
    if source_entry.ownership_class != "owned-integration-artifact":
        raise LifecycleError(
            "invalid_contract",
            "integration source manifest entry must be classified as owned integration",
            {
                "integration_id": integration_id,
                "source_relpath": source_relpath,
                "ownership_class": source_entry.ownership_class,
            },
        )
    return source_relpath


def _parse_reconciliation_mode(integration_id: str, raw: dict[str, Any]) -> str:
    reconciliation_mode = _require_string(raw, "reconciliation_mode")
    if reconciliation_mode not in ALLOWED_RECONCILIATION_MODES:
        raise LifecycleError(
            "invalid_contract",
            "unsupported integration reconciliation mode",
            {
                "integration_id": integration_id,
                "reconciliation_mode": reconciliation_mode,
            },
        )
    return reconciliation_mode


def _parse_restart_required(integration_id: str, raw: dict[str, Any]) -> bool:
    restart_required = raw.get("restart_required", False)
    if not isinstance(restart_required, bool):
        raise LifecycleError(
            "invalid_contract",
            "restart_required must be a boolean",
            {"integration_id": integration_id, "value": restart_required},
        )
    return restart_required


def _parse_verification_targets(
    payload: dict[str, Any], integration_ids: set[str]
) -> tuple[VerificationTarget, ...]:
    raw_targets = payload.get("verification_targets", [])
    if not isinstance(raw_targets, list):
        raise LifecycleError(
            "invalid_contract",
            "verification_targets must be a list when present",
            {"field": "verification_targets"},
        )
    targets: list[VerificationTarget] = []
    for index, raw in enumerate(raw_targets):
        if not isinstance(raw, dict):
            raise LifecycleError(
                "invalid_contract",
                "verification target must be a mapping",
                {"field": f"verification_targets[{index}]"},
            )
        target_id = _require_string(raw, "id")
        kind = _require_string(raw, "kind")
        if kind not in ALLOWED_VERIFICATION_TARGETS:
            raise LifecycleError(
                "invalid_contract",
                "unsupported verification target kind",
                {"target_id": target_id, "kind": kind},
            )
        relative_path = raw.get("relative_path")
        if relative_path is not None:
            relative_path = _validate_relative_path(
                _require_string(raw, "relative_path"),
                f"verification_targets[{index}].relative_path",
            )
        integration_id = raw.get("integration_id")
        if integration_id is not None:
            integration_id = _require_string(raw, "integration_id")
            if integration_id not in integration_ids:
                raise LifecycleError(
                    "invalid_contract",
                    "verification target references an unknown integration id",
                    {"target_id": target_id, "integration_id": integration_id},
                )
        expected_text = raw.get("expected_text")
        if expected_text is not None and not isinstance(expected_text, str):
            raise LifecycleError(
                "invalid_contract",
                "expected_text must be a string when present",
                {"target_id": target_id, "expected_text": expected_text},
            )
        targets.append(
            VerificationTarget(
                target_id=target_id,
                kind=kind,
                relative_path=relative_path,
                integration_id=integration_id,
                expected_text=expected_text,
            )
        )
    return tuple(targets)


def _load_plugin_contract(plugin_root: Path) -> PluginContract:
    root = plugin_root.resolve()
    manifest_payload = _load_json(root / PAYLOAD_MANIFEST_RELATIVE)
    release_payload = _load_json(root / RELEASE_METADATA_RELATIVE)
    plugin_manifest = _load_json(root / PLUGIN_MANIFEST_RELATIVE)
    payload_fingerprint, manifest_entries = _parse_manifest(manifest_payload)
    manifest_by_path = {entry.relative_output_path: entry for entry in manifest_entries}
    release_fingerprint = _require_string(release_payload, "payload_fingerprint")
    if release_fingerprint != payload_fingerprint:
        raise LifecycleError(
            "missing_layer1_artifact",
            "release metadata payload fingerprint does not match the payload manifest",
            {
                "payload_fingerprint": payload_fingerprint,
                "release_payload_fingerprint": release_fingerprint,
            },
        )
    control_surface = _parse_control_surface(root, release_payload)
    integration_points = _parse_integration_points(release_payload, manifest_by_path)
    verification_targets = _parse_verification_targets(
        release_payload, {point.integration_id for point in integration_points}
    )
    contract = PluginContract(
        plugin_root=root,
        plugin_id=_require_string(plugin_manifest, "id"),
        plugin_version=_require_string(plugin_manifest, "version"),
        payload_fingerprint=payload_fingerprint,
        runtime_compatibility_version=_require_string(
            release_payload, "runtime_compatibility_version"
        ),
        migration_contract_version=(
            _require_string(release_payload, "migration_contract_version")
            if release_payload.get("migration_contract_version") is not None
            else None
        ),
        rollback_compatibility_hints=(
            dict(release_payload["rollback_compatibility_hints"])
            if isinstance(release_payload.get("rollback_compatibility_hints"), dict)
            else None
        ),
        control_surface=control_surface,
        owned_integration_root=_parse_owned_integration_root(
            release_payload, release_payload.get("integration_points", [])
        ),
        payload_manifest=manifest_entries,
        integration_points=integration_points,
        verification_targets=verification_targets,
    )
    _validate_manifest_files(contract.plugin_root, contract.payload_manifest)
    return contract


def _validate_manifest_files(root: Path, entries: list[ManifestEntry]) -> None:
    for entry in entries:
        path = root / entry.relative_output_path
        if not path.is_file():
            raise LifecycleError(
                "missing_layer1_artifact",
                "payload manifest references a missing file",
                {"path": str(path), "relative_output_path": entry.relative_output_path},
            )
        if _hash_bytes(path.read_bytes()) != entry.content_hash:
            raise LifecycleError(
                "missing_layer1_artifact",
                "payload manifest hash does not match file content",
                {"path": str(path), "relative_output_path": entry.relative_output_path},
            )


def _state_path(install_root: Path) -> Path:
    return install_root / INSTALL_STATE_RELATIVE


def _load_install_state(install_root: Path) -> InstallState | None:
    path = _state_path(install_root)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        state = _parse_install_state_payload(payload)
        _validate_install_state_consistency(state, install_root.resolve())
        return state
    except json.JSONDecodeError as exc:
        raise LifecycleError(
            "state_invalid",
            "install-state is malformed JSON",
            {"path": str(path)},
        ) from exc
    except LifecycleError as exc:
        if exc.code == "invalid_contract":
            raise LifecycleError(
                "state_invalid",
                "install-state failed schema validation",
                {**exc.details, "path": str(path)},
            ) from exc
        raise


def _parse_install_state_payload(payload: dict[str, Any]) -> InstallState:
    schema_version = _require_string(payload, "schema_version")
    plugin_id = _require_string(payload, "plugin_id")
    plugin_version = _require_string(payload, "plugin_version")
    runtime_compatibility_version = _require_string(
        payload, "runtime_compatibility_version"
    )
    payload_fingerprint = _require_string(payload, "payload_fingerprint")
    activation_timestamp = _require_string(payload, "activation_timestamp")
    install_root_value = Path(_require_string(payload, "install_root")).resolve()
    active_release_path = Path(
        _require_string(payload, "active_release_path")
    ).resolve()
    rollback_candidate_path = _optional_path_field(payload, "rollback_candidate_path")
    rollback_candidate_fingerprint = _optional_string_field(
        payload, "rollback_candidate_fingerprint"
    )
    migration_state = _parse_migration_state(payload)
    migration_version = _optional_string_field(payload, "migration_version")
    owned_integration_status = _parse_owned_integration_status(payload)
    last_verify_code = _optional_string_field(payload, "last_verify_code")
    last_verify_timestamp = _optional_string_field(payload, "last_verify_timestamp")
    return InstallState(
        schema_version=schema_version,
        plugin_id=plugin_id,
        plugin_version=plugin_version,
        runtime_compatibility_version=runtime_compatibility_version,
        payload_fingerprint=payload_fingerprint,
        activation_timestamp=activation_timestamp,
        install_root=install_root_value,
        active_release_path=active_release_path,
        rollback_candidate_path=rollback_candidate_path,
        rollback_candidate_fingerprint=rollback_candidate_fingerprint,
        migration_state=migration_state,
        migration_version=migration_version,
        owned_integration_status=owned_integration_status,
        last_verify_code=last_verify_code,
        last_verify_timestamp=last_verify_timestamp,
    )


def _optional_path_field(payload: dict[str, Any], field: str) -> Path | None:
    value = payload.get(field)
    if value is None:
        return None
    return Path(_require_string(payload, field)).resolve()


def _optional_string_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    return _require_string(payload, field)


def _parse_migration_state(payload: dict[str, Any]) -> str:
    migration_state = _require_string(payload, "migration_state")
    if migration_state not in ALLOWED_MIGRATION_STATES:
        raise LifecycleError(
            "state_invalid",
            "install-state migration_state is invalid",
            {"migration_state": migration_state},
        )
    return migration_state


def _parse_owned_integration_status(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    owned_integration_status = payload.get("owned_integration_status")
    if not isinstance(owned_integration_status, dict):
        raise LifecycleError(
            "state_invalid",
            "owned_integration_status must be a mapping",
            {"field": "owned_integration_status"},
        )
    return owned_integration_status


def _validate_install_state_consistency(
    state: InstallState, expected_install_root: Path
) -> None:
    if state.install_root != expected_install_root:
        raise LifecycleError(
            "state_invalid",
            "install-state install_root does not match the selected install root",
            {
                "install_root": str(state.install_root),
                "expected_install_root": str(expected_install_root),
            },
        )
    if _looks_like_plugin_cache_path(state.install_root):
        raise LifecycleError(
            "state_invalid",
            "install-state install_root points into the plugin cache",
            {"install_root": str(state.install_root)},
        )
    if not state.active_release_path.is_dir():
        raise LifecycleError(
            "state_invalid",
            "install-state active_release_path is missing",
            {"active_release_path": str(state.active_release_path)},
        )
    if state.rollback_candidate_path is None and state.rollback_candidate_fingerprint:
        raise LifecycleError(
            "state_invalid",
            "rollback candidate fingerprint cannot exist without a rollback path",
            {},
        )
    if (
        state.rollback_candidate_path is not None
        and not state.rollback_candidate_path.is_dir()
    ):
        raise LifecycleError(
            "state_invalid",
            "rollback candidate path is missing",
            {"rollback_candidate_path": str(state.rollback_candidate_path)},
        )
    if state.migration_state != "none" and state.migration_version is None:
        raise LifecycleError(
            "state_invalid",
            "migration_version is required when migration_state is not none",
            {"migration_state": state.migration_state},
        )


def _entry_map(entries: list[ManifestEntry]) -> dict[str, ManifestEntry]:
    return {entry.relative_output_path: entry for entry in entries}


def _read_text_if_small(path: Path) -> str:
    content = path.read_bytes()
    if len(content) > MAX_FILE_BYTES:
        raise LifecycleError(
            "payload_mismatch",
            "verification target file is too large to read as text",
            {"path": str(path), "size": len(content)},
        )
    return content.decode("utf-8")


def _integration_target_path(install_root: Path, point: IntegrationPoint) -> Path:
    return install_root / point.target_relpath


def _integration_marker_path(target: Path) -> Path:
    return target.parent / f"{target.name}{INTEGRATION_MARKER_SUFFIX}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_marker(
    target: Path, plugin_id: str, integration_id: str, payload_fingerprint: str
) -> Path:
    marker_path = _integration_marker_path(target)
    _write_json(
        marker_path,
        {
            "format_version": 1,
            "plugin_id": plugin_id,
            "integration_id": integration_id,
            "payload_fingerprint": payload_fingerprint,
            "target_path": str(target),
        },
    )
    return marker_path


def _load_marker(target: Path) -> dict[str, Any] | None:
    marker_path = _integration_marker_path(target)
    if not marker_path.is_file():
        return None
    return _load_json(marker_path)


def _integration_owned(
    state: InstallState | None, point: IntegrationPoint, target: Path
) -> bool:
    marker = _load_marker(target)
    if marker is not None:
        return marker.get("integration_id") == point.integration_id and marker.get(
            "target_path"
        ) == str(target)
    if state is None:
        return False
    recorded = state.owned_integration_status.get(point.integration_id)
    if not isinstance(recorded, dict):
        return False
    return recorded.get("target_path") == str(target)


def _classify_recovery(result_code: str, has_rollback_candidate: bool = False) -> str:
    if result_code in {"success", "no_op"}:
        return "none"
    if result_code in {"payload_mismatch", "integration_missing", "integration_drift"}:
        return "repairable"
    if result_code == "compatibility_blocked" and has_rollback_candidate:
        return "rollbackable"
    return "unrecoverable"


def _build_diagnostic(
    *,
    operation: str,
    result_code: str,
    stage_id: str,
    plugin_id: str | None,
    plugin_version: str | None,
    install_root: Path,
    active_payload_fingerprint: str | None,
    active_release_path: Path | None,
    ownership_boundary_code: str | None = None,
    failures: list[dict[str, Any]] | None = None,
    integration_summary: list[dict[str, Any]] | None = None,
    verification_summary: dict[str, Any] | None = None,
    mutation_summary: dict[str, Any] | None = None,
    has_rollback_candidate: bool = False,
) -> dict[str, Any]:
    return {
        "diagnostic_schema_version": "1",
        "operation": operation,
        "result_code": result_code,
        "stage_id": stage_id,
        "recovery_class": _classify_recovery(result_code, has_rollback_candidate),
        "ownership_boundary_code": ownership_boundary_code,
        "plugin_id": plugin_id,
        "plugin_version": plugin_version,
        "install_root": str(install_root),
        "active_payload_fingerprint": active_payload_fingerprint,
        "active_release_path": str(active_release_path)
        if active_release_path
        else None,
        "verification_summary": verification_summary or {},
        "integration_summary": integration_summary or [],
        "failures": failures or [],
        "mutation_summary": mutation_summary or {},
    }


def _verify_active_release_files(
    state: InstallState,
) -> tuple[bool, list[dict[str, Any]]]:
    manifest_payload = _load_json(state.active_release_path / PAYLOAD_MANIFEST_RELATIVE)
    payload_fingerprint, entries = _parse_manifest(manifest_payload)
    failures: list[dict[str, Any]] = []
    if payload_fingerprint != state.payload_fingerprint:
        failures.append(
            {
                "result_code": "state_invalid",
                "stage_id": "verify/active-release-fingerprint",
                "details": {
                    "payload_fingerprint": payload_fingerprint,
                    "state_payload_fingerprint": state.payload_fingerprint,
                },
            }
        )
        return False, failures
    for entry in entries:
        path = state.active_release_path / entry.relative_output_path
        if not path.is_file():
            failures.append(
                {
                    "result_code": "payload_mismatch",
                    "stage_id": "verify/active-release-file-missing",
                    "details": {"relative_output_path": entry.relative_output_path},
                }
            )
            continue
        if _hash_bytes(path.read_bytes()) != entry.content_hash:
            failures.append(
                {
                    "result_code": "payload_mismatch",
                    "stage_id": "verify/active-release-hash-mismatch",
                    "details": {"relative_output_path": entry.relative_output_path},
                }
            )
    return not failures, failures


def _verification_target_results(
    contract: PluginContract, install_root: Path, active_release_path: Path
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for target in contract.verification_targets:
        if target.kind == "active_file_exists":
            assert target.relative_path is not None
            path = active_release_path / target.relative_path
            results.append(
                {
                    "id": target.target_id,
                    "kind": target.kind,
                    "ok": path.is_file(),
                    "path": str(path),
                }
            )
        elif target.kind == "active_file_contains":
            assert target.relative_path is not None
            path = active_release_path / target.relative_path
            ok = path.is_file() and target.expected_text in _read_text_if_small(path)
            results.append(
                {
                    "id": target.target_id,
                    "kind": target.kind,
                    "ok": ok,
                    "path": str(path),
                }
            )
        elif target.kind == "user_state_exists":
            assert target.relative_path is not None
            path = install_root / USER_STATE_ROOT_RELATIVE / target.relative_path
            results.append(
                {
                    "id": target.target_id,
                    "kind": target.kind,
                    "ok": path.is_file(),
                    "path": str(path),
                }
            )
        elif target.kind == "integration_exists":
            assert target.integration_id is not None
            point = next(
                point
                for point in contract.integration_points
                if point.integration_id == target.integration_id
            )
            path = _integration_target_path(install_root, point)
            results.append(
                {
                    "id": target.target_id,
                    "kind": target.kind,
                    "ok": path.is_file(),
                    "path": str(path),
                }
            )
    return results


def _integration_summary(
    contract: PluginContract,
    install_root: Path,
    source_root: Path,
    state: InstallState | None,
    *,
    enforce_verify_only: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summary: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for point in contract.integration_points:
        target = _integration_target_path(install_root, point)
        source = source_root / point.source_relpath
        target_exists = target.is_file()
        owned = _integration_owned(state, point, target) if target_exists else False
        status = "ok"
        if not target_exists:
            status = "missing"
            if point.reconciliation_mode != "verify-only" or enforce_verify_only:
                failures.append(
                    {
                        "result_code": "integration_missing",
                        "stage_id": "verify/integration-missing",
                        "details": {
                            "integration_id": point.integration_id,
                            "target_path": str(target),
                        },
                    }
                )
        elif not owned and point.reconciliation_mode != "verify-only":
            status = "ownership-ambiguous"
            failures.append(
                {
                    "result_code": "ownership_ambiguous",
                    "stage_id": "verify/integration-ownership",
                    "details": {
                        "integration_id": point.integration_id,
                        "target_path": str(target),
                    },
                }
            )
        elif _hash_bytes(target.read_bytes()) != _hash_bytes(source.read_bytes()):
            status = "drift"
            if point.reconciliation_mode != "verify-only" or enforce_verify_only:
                failures.append(
                    {
                        "result_code": "integration_drift",
                        "stage_id": "verify/integration-drift",
                        "details": {
                            "integration_id": point.integration_id,
                            "target_path": str(target),
                        },
                    }
                )
        summary.append(
            {
                "integration_id": point.integration_id,
                "target_path": str(target),
                "status": status,
                "owned": owned,
                "reconciliation_mode": point.reconciliation_mode,
                "restart_required": point.restart_required,
            }
        )
    return summary, failures


def _pick_failure_code(failures: list[dict[str, Any]]) -> str:
    priority = [
        "ownership_ambiguous",
        "state_invalid",
        "compatibility_blocked",
        "payload_mismatch",
        "integration_missing",
        "integration_drift",
    ]
    codes = {failure["result_code"] for failure in failures}
    for code in priority:
        if code in codes:
            return code
    return failures[0]["result_code"]


def _verify_operation(
    operation: str, contract: PluginContract, install_root: Path
) -> dict[str, Any]:
    try:
        state = _load_install_state(install_root)
    except LifecycleError as exc:
        return _build_diagnostic(
            operation=operation,
            result_code=exc.code,
            stage_id="verify/install-state",
            plugin_id=contract.plugin_id,
            plugin_version=contract.plugin_version,
            install_root=install_root,
            active_payload_fingerprint=None,
            active_release_path=None,
            ownership_boundary_code=(
                "install-root-invalid" if exc.code == "invalid_install_root" else None
            ),
            failures=[
                {
                    "result_code": exc.code,
                    "stage_id": "verify/install-state",
                    "details": exc.details,
                }
            ],
        )
    if state is None:
        return _build_diagnostic(
            operation=operation,
            result_code="missing_state",
            stage_id="verify/install-state-missing",
            plugin_id=contract.plugin_id,
            plugin_version=contract.plugin_version,
            install_root=install_root,
            active_payload_fingerprint=None,
            active_release_path=None,
            failures=[
                {
                    "result_code": "missing_state",
                    "stage_id": "verify/install-state-missing",
                    "details": {"install_state_path": str(_state_path(install_root))},
                }
            ],
        )
    failures: list[dict[str, Any]] = []
    if state.plugin_id != contract.plugin_id:
        failures.append(
            {
                "result_code": "compatibility_blocked",
                "stage_id": "verify/plugin-id",
                "details": {
                    "state_plugin_id": state.plugin_id,
                    "plugin_id": contract.plugin_id,
                },
            }
        )
    if state.runtime_compatibility_version != contract.runtime_compatibility_version:
        failures.append(
            {
                "result_code": "compatibility_blocked",
                "stage_id": "verify/runtime-compatibility",
                "details": {
                    "state_runtime_compatibility_version": state.runtime_compatibility_version,
                    "runtime_compatibility_version": contract.runtime_compatibility_version,
                },
            }
        )
    files_ok, file_failures = _verify_active_release_files(state)
    if not files_ok:
        failures.extend(file_failures)
    integration_summary, integration_failures = _integration_summary(
        contract, install_root, state.active_release_path, state
    )
    failures.extend(integration_failures)
    target_results = _verification_target_results(
        contract, install_root, state.active_release_path
    )
    for result in target_results:
        if not result["ok"]:
            failures.append(
                {
                    "result_code": (
                        "integration_missing"
                        if result["kind"] == "integration_exists"
                        else "payload_mismatch"
                    ),
                    "stage_id": "verify/verification-target",
                    "details": result,
                }
            )
    verification_summary = {
        "manifest_ok": files_ok,
        "target_results": target_results,
        "failure_count": len(failures),
    }
    if failures:
        result_code = _pick_failure_code(failures)
        return _build_diagnostic(
            operation=operation,
            result_code=result_code,
            stage_id=failures[0]["stage_id"],
            plugin_id=state.plugin_id,
            plugin_version=state.plugin_version,
            install_root=install_root,
            active_payload_fingerprint=state.payload_fingerprint,
            active_release_path=state.active_release_path,
            ownership_boundary_code=(
                "owned-integration-boundary"
                if result_code == "ownership_ambiguous"
                else None
            ),
            failures=failures,
            integration_summary=integration_summary,
            verification_summary=verification_summary,
            has_rollback_candidate=state.rollback_candidate_path is not None,
        )
    return _build_diagnostic(
        operation=operation,
        result_code="success",
        stage_id="verify/complete",
        plugin_id=state.plugin_id,
        plugin_version=state.plugin_version,
        install_root=install_root,
        active_payload_fingerprint=state.payload_fingerprint,
        active_release_path=state.active_release_path,
        integration_summary=integration_summary,
        verification_summary=verification_summary,
        has_rollback_candidate=state.rollback_candidate_path is not None,
    )


def _ensure_operation_allowed(contract: PluginContract, operation: str) -> None:
    if operation not in contract.control_surface.operations:
        raise LifecycleError(
            "invalid_contract",
            "requested operation is not declared by the control surface",
            {
                "operation": operation,
                "control_surface_operations": contract.control_surface.operations,
            },
        )


def _copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _create_workspace(install_root: Path) -> Path:
    workspace_root = install_root / WORKSPACE_ROOT_RELATIVE
    workspace_root.mkdir(parents=True, exist_ok=True)
    return Path(
        tempfile.mkdtemp(prefix="activation-", dir=str(workspace_root))
    ).resolve()


def _release_dir(install_root: Path, contract: PluginContract) -> Path:
    slug = contract.payload_fingerprint[:12]
    return install_root / RELEASES_ROOT_RELATIVE / f"{contract.plugin_version}__{slug}"


def _preserved_user_state_entries(contract: PluginContract) -> list[ManifestEntry]:
    return [
        entry
        for entry in contract.payload_manifest
        if entry.ownership_class == "preserved-user-state-artifact"
    ]


def _copy_preserved_user_state(
    contract: PluginContract, release_root: Path, install_root: Path
) -> list[str]:
    preserved: list[str] = []
    for entry in _preserved_user_state_entries(contract):
        source = release_root / entry.relative_output_path
        target = install_root / USER_STATE_ROOT_RELATIVE / entry.relative_output_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
        preserved.append(str(target))
    return preserved


def _write_install_state(state: InstallState, install_root: Path) -> None:
    _write_json(
        _state_path(install_root),
        {
            "schema_version": state.schema_version,
            "plugin_id": state.plugin_id,
            "plugin_version": state.plugin_version,
            "runtime_compatibility_version": state.runtime_compatibility_version,
            "payload_fingerprint": state.payload_fingerprint,
            "activation_timestamp": state.activation_timestamp,
            "install_root": str(state.install_root),
            "active_release_path": str(state.active_release_path),
            "rollback_candidate_path": (
                str(state.rollback_candidate_path)
                if state.rollback_candidate_path
                else None
            ),
            "rollback_candidate_fingerprint": state.rollback_candidate_fingerprint,
            "migration_state": state.migration_state,
            "migration_version": state.migration_version,
            "owned_integration_status": state.owned_integration_status,
            "last_verify_code": state.last_verify_code,
            "last_verify_timestamp": state.last_verify_timestamp,
        },
    )


def _validate_candidate_compatibility(
    operation: str, contract: PluginContract, state: InstallState | None
) -> None:
    if contract.migration_contract_version is not None:
        raise LifecycleError(
            "compatibility_blocked",
            "migration-required payloads are gated in the current Layer 2 slice",
            {
                "operation": operation,
                "migration_contract_version": contract.migration_contract_version,
            },
        )
    if state is None:
        return
    if state.migration_state in {"pending", "failed", "rollback_blocked"}:
        raise LifecycleError(
            "compatibility_blocked",
            "current migration state blocks lifecycle mutation",
            {"migration_state": state.migration_state},
        )
    if state.runtime_compatibility_version != contract.runtime_compatibility_version:
        raise LifecycleError(
            "compatibility_blocked",
            "runtime compatibility versions do not match",
            {
                "state_runtime_compatibility_version": state.runtime_compatibility_version,
                "runtime_compatibility_version": contract.runtime_compatibility_version,
            },
        )


def _reconcile_integration_points(
    *,
    contract: PluginContract,
    source_root: Path,
    install_root: Path,
    state: InstallState | None,
    allow_replace: bool,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    mutations: list[dict[str, Any]] = []
    status: dict[str, dict[str, Any]] = {}
    for point in contract.integration_points:
        target = _integration_target_path(install_root, point)
        source = source_root / point.source_relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        owned = _integration_owned(state, point, target) if target.exists() else False
        if point.reconciliation_mode == "verify-only":
            status[point.integration_id] = {
                "target_path": str(target),
                "status": "verify-only",
                "owned": owned,
                "marker_path": str(_integration_marker_path(target)),
            }
            continue
        if (
            target.exists()
            and not owned
            and point.reconciliation_mode == "replace-if-owned"
        ):
            raise LifecycleError(
                "ownership_ambiguous",
                "existing integration artifact is not proven owned",
                {
                    "integration_id": point.integration_id,
                    "target_path": str(target),
                    "integration_mutations": mutations,
                },
            )
        if (
            target.exists()
            and not owned
            and point.reconciliation_mode == "install-if-missing"
        ):
            raise LifecycleError(
                "ownership_ambiguous",
                "existing integration artifact is not proven owned",
                {
                    "integration_id": point.integration_id,
                    "target_path": str(target),
                    "integration_mutations": mutations,
                },
            )
        action = "noop"
        if not target.exists():
            shutil.copy2(source, target)
            action = "installed"
        elif allow_replace and point.reconciliation_mode == "replace-if-owned":
            shutil.copy2(source, target)
            action = "replaced"
        marker_path = _write_marker(
            target,
            contract.plugin_id,
            point.integration_id,
            contract.payload_fingerprint,
        )
        mutations.append(
            {
                "integration_id": point.integration_id,
                "action": action,
                "target_path": str(target),
                "marker_path": str(marker_path),
            }
        )
        status[point.integration_id] = {
            "target_path": str(target),
            "status": action,
            "owned": True,
            "marker_path": str(marker_path),
        }
    return mutations, status


def _post_activation_verify(
    contract: PluginContract,
    install_root: Path,
    active_release_path: Path,
    owned_integration_status: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    provisional_state = InstallState(
        schema_version="1",
        plugin_id=contract.plugin_id,
        plugin_version=contract.plugin_version,
        runtime_compatibility_version=contract.runtime_compatibility_version,
        payload_fingerprint=contract.payload_fingerprint,
        activation_timestamp=_now_timestamp(),
        install_root=install_root,
        active_release_path=active_release_path,
        rollback_candidate_path=None,
        rollback_candidate_fingerprint=None,
        migration_state="none",
        migration_version=None,
        owned_integration_status=owned_integration_status,
        last_verify_code=None,
        last_verify_timestamp=None,
    )
    files_ok, file_failures = _verify_active_release_files(provisional_state)
    integration_summary, integration_failures = _integration_summary(
        contract,
        install_root,
        active_release_path,
        provisional_state,
        enforce_verify_only=False,
    )
    target_results = _verification_target_results(
        contract, install_root, active_release_path
    )
    failures = list(file_failures) + list(integration_failures)
    for result in target_results:
        if not result["ok"]:
            failures.append(
                {
                    "result_code": (
                        "integration_missing"
                        if result["kind"] == "integration_exists"
                        else "payload_mismatch"
                    ),
                    "stage_id": "activate/verification-target",
                    "details": result,
                }
            )
    return {
        "ok": not failures,
        "manifest_ok": files_ok,
        "integration_summary": integration_summary,
        "target_results": target_results,
        "failures": failures,
    }


def _cleanup_paths(paths: list[Path]) -> None:
    for path in paths:
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)


def _activate(
    operation: str, contract: PluginContract, install_root: Path
) -> dict[str, Any]:
    state = _load_install_state(install_root)
    if operation == "install" and state is not None:
        raise LifecycleError(
            "compatibility_blocked",
            "install refuses when a durable install-state already exists",
            {"install_state_path": str(_state_path(install_root))},
        )
    if operation == "update" and state is None:
        raise LifecycleError(
            "missing_state",
            "update requires an existing durable install-state",
            {"install_state_path": str(_state_path(install_root))},
        )
    _validate_candidate_compatibility(operation, contract, state)
    if state is not None and state.payload_fingerprint == contract.payload_fingerprint:
        verify_result = _verify_operation("verify", contract, install_root)
        if verify_result["result_code"] == "success":
            return _build_diagnostic(
                operation=operation,
                result_code="no_op",
                stage_id=f"{operation}/no-op",
                plugin_id=state.plugin_id,
                plugin_version=state.plugin_version,
                install_root=install_root,
                active_payload_fingerprint=state.payload_fingerprint,
                active_release_path=state.active_release_path,
                verification_summary=verify_result["verification_summary"],
                integration_summary=verify_result["integration_summary"],
                has_rollback_candidate=state.rollback_candidate_path is not None,
            )
    workspace = _create_workspace(install_root)
    release_tmp = _release_dir(install_root, contract).with_suffix(".pending")
    release_final = _release_dir(install_root, contract)
    cleanup_targets = [workspace, release_tmp]
    mutation_summary: dict[str, Any] = {
        "workspace_path": str(workspace),
        "cleaned_workspace": False,
    }
    try:
        staged_root = workspace / "release"
        _copy_tree(contract.plugin_root, staged_root)
        _validate_manifest_files(staged_root, contract.payload_manifest)
        _cleanup_paths([release_tmp])
        _copy_tree(staged_root, release_tmp)
        if release_final.exists():
            _cleanup_paths([release_final])
        release_tmp.parent.mkdir(parents=True, exist_ok=True)
        release_tmp.rename(release_final)
        preserved_paths = _copy_preserved_user_state(
            contract, release_final, install_root
        )
        integration_mutations, owned_status = _reconcile_integration_points(
            contract=contract,
            source_root=release_final,
            install_root=install_root,
            state=state,
            allow_replace=operation == "update",
        )
        post_verify = _post_activation_verify(
            contract, install_root, release_final, owned_status
        )
        if not post_verify["ok"]:
            raise LifecycleError(
                _pick_failure_code(post_verify["failures"]),
                "post-activation verification failed",
                {
                    "failures": post_verify["failures"],
                    "release_path": str(release_final),
                },
            )
        new_state = InstallState(
            schema_version="1",
            plugin_id=contract.plugin_id,
            plugin_version=contract.plugin_version,
            runtime_compatibility_version=contract.runtime_compatibility_version,
            payload_fingerprint=contract.payload_fingerprint,
            activation_timestamp=_now_timestamp(),
            install_root=install_root,
            active_release_path=release_final,
            rollback_candidate_path=(state.active_release_path if state else None),
            rollback_candidate_fingerprint=(
                state.payload_fingerprint if state else None
            ),
            migration_state="none",
            migration_version=None,
            owned_integration_status=owned_status,
            last_verify_code="success",
            last_verify_timestamp=_now_timestamp(),
        )
        _write_install_state(new_state, install_root)
        _cleanup_paths([workspace])
        mutation_summary.update(
            {
                "cleaned_workspace": True,
                "active_release_path": str(release_final),
                "preserved_user_state_paths": preserved_paths,
                "integration_mutations": integration_mutations,
                "rollback_candidate_path": (
                    str(new_state.rollback_candidate_path)
                    if new_state.rollback_candidate_path
                    else None
                ),
            }
        )
        return _build_diagnostic(
            operation=operation,
            result_code="success",
            stage_id=f"{operation}/complete",
            plugin_id=contract.plugin_id,
            plugin_version=contract.plugin_version,
            install_root=install_root,
            active_payload_fingerprint=contract.payload_fingerprint,
            active_release_path=release_final,
            verification_summary={
                "manifest_ok": post_verify["manifest_ok"],
                "target_results": post_verify["target_results"],
                "failure_count": 0,
            },
            integration_summary=post_verify["integration_summary"],
            mutation_summary=mutation_summary,
            has_rollback_candidate=new_state.rollback_candidate_path is not None,
        )
    except LifecycleError as exc:
        _cleanup_paths(cleanup_targets)
        mutation_summary["cleaned_workspace"] = not workspace.exists()
        mutation_summary["cleaned_release_tmp"] = not release_tmp.exists()
        raise LifecycleError(
            exc.code,
            exc.message,
            {**exc.details, "mutation_summary": mutation_summary},
        ) from exc


def _repair(contract: PluginContract, install_root: Path) -> dict[str, Any]:
    state = _load_install_state(install_root)
    if state is None:
        raise LifecycleError(
            "missing_state",
            "repair requires an existing durable install-state",
            {"install_state_path": str(_state_path(install_root))},
        )
    if state.payload_fingerprint != contract.payload_fingerprint:
        raise LifecycleError(
            "compatibility_blocked",
            "repair requires the selected payload to match the active install-state fingerprint",
            {
                "state_payload_fingerprint": state.payload_fingerprint,
                "payload_fingerprint": contract.payload_fingerprint,
            },
        )
    verify_before = _verify_operation("verify", contract, install_root)
    if verify_before["result_code"] == "success":
        return _build_diagnostic(
            operation="repair",
            result_code="no_op",
            stage_id="repair/no-op",
            plugin_id=state.plugin_id,
            plugin_version=state.plugin_version,
            install_root=install_root,
            active_payload_fingerprint=state.payload_fingerprint,
            active_release_path=state.active_release_path,
            verification_summary=verify_before["verification_summary"],
            integration_summary=verify_before["integration_summary"],
            has_rollback_candidate=state.rollback_candidate_path is not None,
        )
    if verify_before["recovery_class"] != "repairable":
        return _build_diagnostic(
            operation="repair",
            result_code=verify_before["result_code"],
            stage_id="repair/refused",
            plugin_id=state.plugin_id,
            plugin_version=state.plugin_version,
            install_root=install_root,
            active_payload_fingerprint=state.payload_fingerprint,
            active_release_path=state.active_release_path,
            ownership_boundary_code=verify_before["ownership_boundary_code"],
            failures=verify_before["failures"],
            verification_summary=verify_before["verification_summary"],
            integration_summary=verify_before["integration_summary"],
            has_rollback_candidate=state.rollback_candidate_path is not None,
        )
    manifest_entries = _entry_map(contract.payload_manifest)
    restored_paths: list[str] = []
    for failure in verify_before["failures"]:
        if failure["result_code"] != "payload_mismatch":
            continue
        relative_output_path = failure["details"].get("relative_output_path")
        if not relative_output_path:
            continue
        entry = manifest_entries.get(relative_output_path)
        if entry is None or entry.ownership_class == "preserved-user-state-artifact":
            continue
        source = contract.plugin_root / relative_output_path
        target = state.active_release_path / relative_output_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        restored_paths.append(str(target))
    integration_mutations, owned_status = _reconcile_integration_points(
        contract=contract,
        source_root=state.active_release_path,
        install_root=install_root,
        state=state,
        allow_replace=True,
    )
    updated_state = InstallState(
        **{**state.__dict__, "owned_integration_status": owned_status}
    )
    _write_install_state(updated_state, install_root)
    verify_after = _verify_operation("verify", contract, install_root)
    if verify_after["result_code"] != "success":
        return _build_diagnostic(
            operation="repair",
            result_code=verify_after["result_code"],
            stage_id="repair/post-verify",
            plugin_id=state.plugin_id,
            plugin_version=state.plugin_version,
            install_root=install_root,
            active_payload_fingerprint=state.payload_fingerprint,
            active_release_path=state.active_release_path,
            ownership_boundary_code=verify_after["ownership_boundary_code"],
            failures=verify_after["failures"],
            verification_summary=verify_after["verification_summary"],
            integration_summary=verify_after["integration_summary"],
            mutation_summary={
                "restored_paths": restored_paths,
                "integration_mutations": integration_mutations,
            },
            has_rollback_candidate=state.rollback_candidate_path is not None,
        )
    return _build_diagnostic(
        operation="repair",
        result_code="success",
        stage_id="repair/complete",
        plugin_id=state.plugin_id,
        plugin_version=state.plugin_version,
        install_root=install_root,
        active_payload_fingerprint=state.payload_fingerprint,
        active_release_path=state.active_release_path,
        verification_summary=verify_after["verification_summary"],
        integration_summary=verify_after["integration_summary"],
        mutation_summary={
            "restored_paths": restored_paths,
            "integration_mutations": integration_mutations,
        },
        has_rollback_candidate=state.rollback_candidate_path is not None,
    )


def _rollback(contract: PluginContract, install_root: Path) -> dict[str, Any]:
    state = _load_install_state(install_root)
    if state is None:
        raise LifecycleError(
            "missing_state",
            "rollback requires an existing durable install-state",
            {"install_state_path": str(_state_path(install_root))},
        )
    if (
        state.rollback_candidate_path is None
        or state.rollback_candidate_fingerprint is None
    ):
        return _build_diagnostic(
            operation="rollback",
            result_code="compatibility_blocked",
            stage_id="rollback/missing-candidate",
            plugin_id=state.plugin_id,
            plugin_version=state.plugin_version,
            install_root=install_root,
            active_payload_fingerprint=state.payload_fingerprint,
            active_release_path=state.active_release_path,
            failures=[
                {
                    "result_code": "compatibility_blocked",
                    "stage_id": "rollback/missing-candidate",
                    "details": {"rollback_candidate_path": None},
                }
            ],
            has_rollback_candidate=False,
        )
    if state.migration_state in {"pending", "failed", "rollback_blocked"}:
        return _build_diagnostic(
            operation="rollback",
            result_code="compatibility_blocked",
            stage_id="rollback/migration-state",
            plugin_id=state.plugin_id,
            plugin_version=state.plugin_version,
            install_root=install_root,
            active_payload_fingerprint=state.payload_fingerprint,
            active_release_path=state.active_release_path,
            failures=[
                {
                    "result_code": "compatibility_blocked",
                    "stage_id": "rollback/migration-state",
                    "details": {"migration_state": state.migration_state},
                }
            ],
            has_rollback_candidate=True,
        )
    candidate_manifest = _load_json(
        state.rollback_candidate_path / PAYLOAD_MANIFEST_RELATIVE
    )
    candidate_fingerprint, _candidate_entries = _parse_manifest(candidate_manifest)
    if candidate_fingerprint != state.rollback_candidate_fingerprint:
        return _build_diagnostic(
            operation="rollback",
            result_code="compatibility_blocked",
            stage_id="rollback/candidate-fingerprint",
            plugin_id=state.plugin_id,
            plugin_version=state.plugin_version,
            install_root=install_root,
            active_payload_fingerprint=state.payload_fingerprint,
            active_release_path=state.active_release_path,
            failures=[
                {
                    "result_code": "compatibility_blocked",
                    "stage_id": "rollback/candidate-fingerprint",
                    "details": {
                        "rollback_candidate_fingerprint": state.rollback_candidate_fingerprint,
                        "candidate_payload_fingerprint": candidate_fingerprint,
                    },
                }
            ],
            has_rollback_candidate=True,
        )
    candidate_contract = _load_plugin_contract(state.rollback_candidate_path)
    mutations: list[dict[str, Any]] = []
    owned_status = state.owned_integration_status
    try:
        integration_mutations, owned_status = _reconcile_integration_points(
            contract=candidate_contract,
            source_root=state.rollback_candidate_path,
            install_root=install_root,
            state=state,
            allow_replace=True,
        )
        mutations.extend(integration_mutations)
    except LifecycleError as exc:
        partial_mutations = exc.details.get("integration_mutations", [])
        return _build_diagnostic(
            operation="rollback",
            result_code="partial_rollback_failure",
            stage_id="rollback/integration-reconcile",
            plugin_id=state.plugin_id,
            plugin_version=state.plugin_version,
            install_root=install_root,
            active_payload_fingerprint=state.payload_fingerprint,
            active_release_path=state.active_release_path,
            ownership_boundary_code=(
                "owned-integration-boundary"
                if exc.code == "ownership_ambiguous"
                else None
            ),
            failures=[
                {
                    "result_code": exc.code,
                    "stage_id": "rollback/integration-reconcile",
                    "details": exc.details,
                }
            ],
            mutation_summary={"integration_mutations": partial_mutations},
            has_rollback_candidate=True,
        )
    previous_active_path = state.active_release_path
    previous_active_fingerprint = state.payload_fingerprint
    new_state = InstallState(
        schema_version="1",
        plugin_id=state.plugin_id,
        plugin_version=candidate_contract.plugin_version,
        runtime_compatibility_version=candidate_contract.runtime_compatibility_version,
        payload_fingerprint=state.rollback_candidate_fingerprint,
        activation_timestamp=_now_timestamp(),
        install_root=install_root,
        active_release_path=state.rollback_candidate_path,
        rollback_candidate_path=previous_active_path,
        rollback_candidate_fingerprint=previous_active_fingerprint,
        migration_state="none",
        migration_version=None,
        owned_integration_status=owned_status,
        last_verify_code="success",
        last_verify_timestamp=_now_timestamp(),
    )
    _write_install_state(new_state, install_root)
    verify_after = _verify_operation("verify", candidate_contract, install_root)
    if verify_after["result_code"] != "success":
        return _build_diagnostic(
            operation="rollback",
            result_code="partial_rollback_failure",
            stage_id="rollback/post-verify",
            plugin_id=new_state.plugin_id,
            plugin_version=new_state.plugin_version,
            install_root=install_root,
            active_payload_fingerprint=new_state.payload_fingerprint,
            active_release_path=new_state.active_release_path,
            failures=verify_after["failures"],
            integration_summary=verify_after["integration_summary"],
            verification_summary=verify_after["verification_summary"],
            mutation_summary={"integration_mutations": mutations},
            has_rollback_candidate=True,
        )
    return _build_diagnostic(
        operation="rollback",
        result_code="success",
        stage_id="rollback/complete",
        plugin_id=new_state.plugin_id,
        plugin_version=new_state.plugin_version,
        install_root=install_root,
        active_payload_fingerprint=new_state.payload_fingerprint,
        active_release_path=new_state.active_release_path,
        verification_summary=verify_after["verification_summary"],
        integration_summary=verify_after["integration_summary"],
        mutation_summary={"integration_mutations": mutations},
        has_rollback_candidate=True,
    )


def run(
    operation: str, plugin_root: Path | str, install_root: Path | str
) -> dict[str, Any]:
    if operation not in ALLOWED_OPERATIONS:
        raise LifecycleError(
            "invalid_operation",
            "operation must be verify, install, update, repair, or rollback",
            {"operation": operation},
        )
    try:
        plugin_root_path = Path(plugin_root).resolve()
        contract = _load_plugin_contract(plugin_root_path)
        _ensure_operation_allowed(contract, operation)
        resolved_install_root = _validate_install_root(
            Path(install_root), plugin_root_path
        )
        if operation == "verify":
            result = _verify_operation(operation, contract, resolved_install_root)
        elif operation in {"install", "update"}:
            result = _activate(operation, contract, resolved_install_root)
        elif operation == "repair":
            result = _repair(contract, resolved_install_root)
        else:
            result = _rollback(contract, resolved_install_root)
    except LifecycleError as exc:
        plugin_root_path = Path(plugin_root).resolve()
        resolved_install_root = Path(install_root).resolve()
        contract = None
        try:
            contract = _load_plugin_contract(plugin_root_path)
        except LifecycleError:
            contract = None
        active_state = None
        try:
            active_state = _load_install_state(resolved_install_root)
        except LifecycleError:
            active_state = None
        result = _build_diagnostic(
            operation=operation,
            result_code=exc.code,
            stage_id=f"{operation}/failed",
            plugin_id=(
                active_state.plugin_id
                if active_state
                else contract.plugin_id
                if contract
                else None
            ),
            plugin_version=(
                active_state.plugin_version
                if active_state
                else contract.plugin_version
                if contract
                else None
            ),
            install_root=resolved_install_root,
            active_payload_fingerprint=(
                active_state.payload_fingerprint if active_state else None
            ),
            active_release_path=(
                active_state.active_release_path if active_state else None
            ),
            ownership_boundary_code=(
                "owned-integration-boundary"
                if exc.code in {"ownership_ambiguous", "undeclared_integration_target"}
                else "install-root-invalid"
                if exc.code == "invalid_install_root"
                else None
            ),
            failures=[
                {
                    "result_code": exc.code,
                    "stage_id": f"{operation}/failed",
                    "details": exc.details,
                }
            ],
            mutation_summary=exc.details.get("mutation_summary", {})
            if isinstance(exc.details, dict)
            else {},
            has_rollback_candidate=(
                active_state.rollback_candidate_path is not None
                if active_state is not None
                else False
            ),
        )
    try:
        state = _load_install_state(resolved_install_root)
    except LifecycleError:
        state = None
    if state is not None and result["result_code"] in {
        "success",
        "no_op",
        "payload_mismatch",
        "integration_missing",
        "integration_drift",
        "compatibility_blocked",
        "state_invalid",
        "ownership_ambiguous",
    }:
        state = InstallState(
            **{
                **state.__dict__,
                "last_verify_code": result["result_code"]
                if operation == "verify"
                else state.last_verify_code,
                "last_verify_timestamp": _now_timestamp()
                if operation == "verify"
                else state.last_verify_timestamp,
            }
        )
        _write_install_state(state, resolved_install_root)
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plugin runtime lifecycle framework")
    parser.add_argument("operation", choices=sorted(ALLOWED_OPERATIONS))
    parser.add_argument("--plugin-root", required=True)
    parser.add_argument("--install-root", required=True)
    parser.add_argument("--format", choices=("json",), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = run(args.operation, Path(args.plugin_root), Path(args.install_root))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["result_code"] in {"success", "no_op"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
