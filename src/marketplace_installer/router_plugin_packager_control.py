from __future__ import annotations

from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


def normalize_control_surface(
    raw_control_surface: dict[str, Any] | None, *, ensure_string: Any
) -> dict[str, Any] | None:
    if raw_control_surface is None:
        return None
    if not isinstance(raw_control_surface, dict):
        raise PackagerError(
            "invalid_invocation_field",
            "control_surface must be a mapping when present",
            {"field": "control_surface", "value": raw_control_surface},
        )
    normalized = dict(raw_control_surface)
    normalized["skill_id"] = ensure_string(
        normalized.get("skill_id"), field="control_surface.skill_id"
    )
    operations = normalized.get("operations")
    if (
        not isinstance(operations, list)
        or not operations
        or not all(isinstance(item, str) and item.strip() for item in operations)
    ):
        raise PackagerError(
            "invalid_invocation_field",
            "control_surface.operations must be a non-empty string list",
            {"field": "control_surface.operations", "value": operations},
        )
    normalized["operations"] = [str(item).strip() for item in operations]
    return normalized


def validate_control_surface_visibility(
    control_surface: dict[str, Any] | None, visible_skill_ids: set[str]
) -> None:
    if control_surface is None:
        return
    skill_id = str(control_surface["skill_id"])
    if skill_id not in visible_skill_ids:
        raise PackagerError(
            "invalid_control_surface",
            "control_surface.skill_id must name a visible packaged skill",
            {
                "skill_id": skill_id,
                "visible_skill_ids": sorted(visible_skill_ids),
            },
        )


def normalize_owned_integration_root(
    raw_root: str | None, *, ensure_string: Any
) -> str | None:
    if raw_root is None:
        return None
    normalized = ensure_string(raw_root, field="owned_integration_root")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise PackagerError(
            "invalid_invocation_field",
            "owned_integration_root must remain relative to the install root boundary",
            {"field": "owned_integration_root", "value": raw_root},
        )
    return path.as_posix()


def normalize_metadata_records(
    raw_records: list[dict[str, Any]], field: str
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(raw_records):
        if not isinstance(record, dict):
            raise PackagerError(
                "invalid_invocation_field",
                "metadata record must be a mapping",
                {"field": f"{field}[{index}]", "value": record},
            )
        normalized.append(dict(record))
    return normalized


def validate_integration_points(
    integration_points: list[dict[str, Any]],
    owned_integration_root: str | None,
    *,
    ensure_string: Any,
) -> None:
    if not integration_points:
        return
    if owned_integration_root is None:
        raise PackagerError(
            "missing_invocation_field",
            "owned_integration_root is required when integration_points are present",
            {"field": "owned_integration_root"},
        )
    root = Path(owned_integration_root)
    for index, point in enumerate(integration_points):
        ensure_string(point.get("id"), field=f"integration_points[{index}].id")
        target_relpath = ensure_string(
            point.get("target_relpath"),
            field=f"integration_points[{index}].target_relpath",
        )
        target = Path(target_relpath)
        if target.is_absolute() or ".." in target.parts or root not in target.parents:
            raise PackagerError(
                "invalid_invocation_field",
                "integration point target_relpath must remain under owned_integration_root",
                {
                    "field": f"integration_points[{index}].target_relpath",
                    "target_relpath": target_relpath,
                    "owned_integration_root": owned_integration_root,
                },
            )
