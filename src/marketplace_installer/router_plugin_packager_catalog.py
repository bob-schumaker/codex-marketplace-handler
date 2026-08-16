from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


@dataclass(frozen=True)
class CatalogSelection:
    cohort_id: str
    role: str | None
    display_name: str | None
    skill_ids: list[str]
    skill_paths: list[str]
    routers: list[Any]


def resolve_catalog_paths(
    invocation: Any, *, resolve_local_path: Any, validate_relative_path: Any
) -> tuple[Path, Path]:
    cohort_catalog_path = resolve_local_path(
        invocation.repository_root, str(invocation.cohort_catalog_path)
    )
    router_catalog_path = resolve_local_path(
        invocation.repository_root, str(invocation.router_catalog_path)
    )
    validate_relative_path(
        invocation.repository_root, cohort_catalog_path, "cohort_catalog_path"
    )
    validate_relative_path(
        invocation.repository_root, router_catalog_path, "router_catalog_path"
    )
    return cohort_catalog_path, router_catalog_path


def load_catalog_lists(
    cohort_catalog_path: Path,
    router_catalog_path: Path,
    *,
    load_yaml: Any,
    collect_required_placeholders: Any,
    required_marker_prefix: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cohorts_payload = load_yaml(cohort_catalog_path)
    routers_payload = load_yaml(router_catalog_path)
    cohort_placeholders = collect_required_placeholders(
        cohorts_payload, required_marker_prefix=required_marker_prefix
    )
    router_placeholders = collect_required_placeholders(
        routers_payload, required_marker_prefix=required_marker_prefix
    )
    if cohort_placeholders or router_placeholders:
        raise PackagerError(
            "incomplete_scaffold",
            "catalog inputs still contain unresolved required markers",
            {
                "cohort_catalog_path": str(cohort_catalog_path.resolve()),
                "router_catalog_path": str(router_catalog_path.resolve()),
                "cohort_placeholders": cohort_placeholders,
                "router_placeholders": router_placeholders,
                "required_marker_prefix": required_marker_prefix,
            },
        )
    if not isinstance(cohorts_payload, dict) or not isinstance(routers_payload, dict):
        raise PackagerError(
            "invalid_catalog_shape",
            "catalog YAML must load to a mapping",
            {
                "cohort_catalog_path": str(cohort_catalog_path),
                "router_catalog_path": str(router_catalog_path),
            },
        )
    cohort_entries = cohorts_payload.get("cohorts")
    router_entries = routers_payload.get("routers")
    if not isinstance(cohort_entries, list) or not isinstance(router_entries, list):
        raise PackagerError(
            "invalid_catalog_shape",
            "catalog YAML must expose cohorts and routers lists",
            {
                "cohort_catalog_path": str(cohort_catalog_path),
                "router_catalog_path": str(router_catalog_path),
            },
        )
    return [entry for entry in cohort_entries if isinstance(entry, dict)], [
        entry for entry in router_entries if isinstance(entry, dict)
    ]


def select_catalog_cohort(
    invocation: Any,
    cohort_entries: list[dict[str, Any]],
    cohort_catalog_path: Path,
    *,
    normalize_slug: Any,
) -> tuple[str, dict[str, Any]]:
    cohort_id = normalize_slug(str(invocation.cohort_id))
    cohort_entry = next(
        (
            entry
            for entry in cohort_entries
            if normalize_slug(str(entry.get("id", ""))) == cohort_id
        ),
        None,
    )
    if cohort_entry is None:
        raise PackagerError(
            "missing_catalog_cohort",
            "catalog mode cohort_id does not exist in the cohort catalog",
            {
                "cohort_id": invocation.cohort_id,
                "cohort_catalog_path": str(cohort_catalog_path),
            },
        )
    return cohort_id, cohort_entry


def validate_catalog_skill_paths(
    invocation: Any,
    source_root: Path,
    skill_paths: list[str],
    *,
    normalize_skill_paths: Any,
) -> None:
    normalize_skill_paths(
        invocation.__class__(
            format_version=invocation.format_version,
            source_format_version=invocation.source_format_version,
            surface_mode=invocation.surface_mode,
            input_mode="skill_list",
            plugin_kind=invocation.plugin_kind,
            plugin_kind_source=invocation.plugin_kind_source,
            source_root=invocation.source_root,
            repository_root=invocation.repository_root,
            output_root=invocation.output_root,
            skill_paths=skill_paths,
            cohort_catalog_path=invocation.cohort_catalog_path,
            router_catalog_path=invocation.router_catalog_path,
            cohort_id=invocation.cohort_id,
            display_name_override=invocation.display_name_override,
            plugin_slug_override=invocation.plugin_slug_override,
            publisher_slug_override=invocation.publisher_slug_override,
            surface_id_override=invocation.surface_id_override,
            branding_asset_overrides=invocation.branding_asset_overrides,
            payload_assets=invocation.payload_assets,
            runtime_compatibility_version=invocation.runtime_compatibility_version,
            migration_contract_version=invocation.migration_contract_version,
            rollback_compatibility_hints=invocation.rollback_compatibility_hints,
            control_surface=invocation.control_surface,
            owned_integration_root=invocation.owned_integration_root,
            integration_points=invocation.integration_points,
            verification_targets=invocation.verification_targets,
            version_override=invocation.version_override,
            publication=invocation.publication,
            mcp_packaging=invocation.mcp_packaging,
            source_manifest=invocation.source_manifest,
            generated=invocation.generated,
            router_authority=invocation.router_authority,
            source_projection_receipt=invocation.source_projection_receipt,
        ),
        source_root,
    )


def routers_for_catalog_cohort(
    invocation: Any,
    cohort_id: str,
    skill_ids: list[str],
    router_entries: list[dict[str, Any]],
    router_catalog_path: Path,
    *,
    normalize_slug: Any,
    router_factory: Any,
) -> list[Any]:
    selected_router_entries = [
        entry
        for entry in router_entries
        if normalize_slug(str(entry.get("plugin", ""))) == cohort_id
    ]
    if not selected_router_entries:
        raise PackagerError(
            "missing_catalog_router",
            "catalog mode cohort has no routers in the router catalog",
            {
                "cohort_id": invocation.cohort_id,
                "router_catalog_path": str(router_catalog_path),
            },
        )
    routers: list[Any] = []
    owner_map: dict[str, str] = {}
    for entry in selected_router_entries:
        router_name = str(entry.get("name", "")).strip()
        router_description = str(entry.get("description", "")).strip()
        router_members = entry.get("members")
        if (
            not router_name
            or not router_description
            or not isinstance(router_members, list)
            or not router_members
        ):
            raise PackagerError(
                "invalid_catalog_shape",
                "router entries must declare name, description, and non-empty members",
                {"cohort_id": invocation.cohort_id, "router_entry": entry},
            )
        member_skill_ids = [str(member) for member in router_members]
        for member_skill_id in member_skill_ids:
            normalized = normalize_slug(member_skill_id)
            if normalized in owner_map:
                raise PackagerError(
                    "catalog_duplicate_member_ownership",
                    "catalog routers assign one member skill to multiple routers",
                    {
                        "skill_id": member_skill_id,
                        "first_router": owner_map[normalized],
                        "second_router": router_name,
                    },
                )
            owner_map[normalized] = router_name
        routers.append(
            router_factory(
                router_slug=normalize_slug(router_name),
                description=router_description,
                member_skill_ids=member_skill_ids,
            )
        )
    cohort_member_set = {normalize_slug(skill_id) for skill_id in skill_ids}
    extras = sorted(
        skill_id for skill_id in owner_map if skill_id not in cohort_member_set
    )
    if extras:
        raise PackagerError(
            "catalog_member_not_in_cohort",
            "catalog router references a member outside the selected cohort",
            {"cohort_id": invocation.cohort_id, "skill_ids": extras},
        )
    missing = sorted(
        skill_id for skill_id in skill_ids if normalize_slug(skill_id) not in owner_map
    )
    if missing:
        raise PackagerError(
            "catalog_missing_member_ownership",
            "catalog routers do not cover every cohort member",
            {"cohort_id": invocation.cohort_id, "skill_ids": missing},
        )
    return routers


def catalog_selection(
    invocation: Any,
    source_root: Path,
    *,
    resolve_catalog_paths_fn: Any,
    load_catalog_lists_fn: Any,
    select_catalog_cohort_fn: Any,
    validate_catalog_skill_paths_fn: Any,
    routers_for_catalog_cohort_fn: Any,
) -> tuple[CatalogSelection, dict[str, Any]]:
    cohort_catalog_path, router_catalog_path = resolve_catalog_paths_fn(invocation)
    cohort_entries, router_entries = load_catalog_lists_fn(
        cohort_catalog_path, router_catalog_path
    )
    cohort_id, cohort_entry = select_catalog_cohort_fn(
        invocation, cohort_entries, cohort_catalog_path
    )
    cohort_members = cohort_entry.get("members")
    if not isinstance(cohort_members, list) or not cohort_members:
        raise PackagerError(
            "invalid_catalog_shape",
            "selected cohort must declare a non-empty members list",
            {"cohort_id": invocation.cohort_id},
        )
    skill_ids = [str(member) for member in cohort_members]
    skill_paths = [
        str((source_root / skill_id).relative_to(invocation.repository_root))
        for skill_id in skill_ids
    ]
    validate_catalog_skill_paths_fn(invocation, source_root, skill_paths)
    routers = routers_for_catalog_cohort_fn(
        invocation,
        cohort_id,
        skill_ids,
        router_entries,
        router_catalog_path,
    )
    return (
        CatalogSelection(
            cohort_id=cohort_id,
            role=(
                str(cohort_entry.get("role")).strip()
                if cohort_entry.get("role") is not None
                else None
            ),
            display_name=(
                str(cohort_entry.get("display_name")).strip()
                if cohort_entry.get("display_name") is not None
                else None
            ),
            skill_ids=skill_ids,
            skill_paths=skill_paths,
            routers=routers,
        ),
        {
            "cohort_catalog_path": str(
                cohort_catalog_path.relative_to(invocation.repository_root)
            ),
            "router_catalog_path": str(
                router_catalog_path.relative_to(invocation.repository_root)
            ),
        },
    )
