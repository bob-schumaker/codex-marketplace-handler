from __future__ import annotations

from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


def require_invocation_fields(payload: dict[str, Any], surface_mode: str) -> None:
    required_fields = ("repository_root", "output_root")
    if surface_mode == "legacy":
        required_fields = ("input_mode", *required_fields)
    for field in required_fields:
        if field not in payload:
            raise PackagerError(
                "missing_invocation_field",
                "invocation is missing a required field",
                {"field": field},
            )


def parse_legacy_input_mode(payload: dict[str, Any]) -> str:
    input_mode = payload["input_mode"]
    if input_mode not in {"repo_bootstrap", "skill_list", "catalog"}:
        raise PackagerError(
            "invalid_input_mode",
            "input_mode must be repo_bootstrap, skill_list, or catalog",
            {"input_mode": input_mode},
        )
    return input_mode


def validate_legacy_mode_inputs(
    payload: dict[str, Any], input_mode: str, invocation_path: Path
) -> list[str]:
    skill_paths = list(payload.get("skill_paths", []))
    if input_mode == "skill_list" and not skill_paths:
        raise PackagerError(
            "missing_skill_paths",
            "skill_list mode requires ordered skill_paths",
            {"invocation_path": str(invocation_path.resolve())},
        )
    if input_mode == "catalog":
        for field in ("cohort_catalog_path", "router_catalog_path", "cohort_id"):
            if not payload.get(field):
                raise PackagerError(
                    "missing_invocation_field",
                    "catalog mode is missing a required field",
                    {
                        "invocation_path": str(invocation_path.resolve()),
                        "field": field,
                    },
                )
    return skill_paths


def parse_plugin_kind(payload: dict[str, Any]) -> tuple[str, str]:
    plugin_kind = str(payload.get("plugin_kind", "skills_only")).strip()
    if plugin_kind not in {"skills_only", "mcp_based"}:
        raise PackagerError(
            "invalid_plugin_kind",
            "plugin_kind must be skills_only or mcp_based",
            {"plugin_kind": payload.get("plugin_kind")},
        )
    if payload.get("mcp_packaging") is not None and plugin_kind != "mcp_based":
        raise PackagerError(
            "mcp_packaging_requires_explicit_plugin_kind",
            "mcp_packaging requires plugin_kind to be mcp_based",
            {"plugin_kind": plugin_kind},
        )
    if plugin_kind == "mcp_based" and payload.get("mcp_packaging") is None:
        raise PackagerError(
            "missing_invocation_field",
            "mcp_based plugin_kind requires mcp_packaging",
            {"field": "mcp_packaging"},
        )
    return plugin_kind, ("explicit" if "plugin_kind" in payload else "default")


def parse_native_router_authority(
    payload: dict[str, Any],
    repository_root: Path,
    *,
    ensure_string: Any,
    resolve_repository_root: Any,
    validate_relative_path: Any,
) -> dict[str, Any]:
    authority = payload.get("router_authority")
    if not isinstance(authority, dict):
        raise PackagerError(
            "missing_router_authority",
            "native_routed mode requires one router_authority declaration",
            {"field": "router_authority"},
        )
    has_catalog = "catalog" in authority
    has_routers = "routers" in authority
    if has_catalog == has_routers:
        raise PackagerError(
            "ambiguous_router_authority",
            "router_authority must declare exactly one of catalog or routers",
            {"router_authority": authority},
        )
    if has_catalog:
        ensure_string(authority["catalog"], field="router_authority.catalog")
        catalog_path = ensure_string(
            authority.get("catalog_path"), field="router_authority.catalog_path"
        )
        validate_relative_path(
            repository_root,
            resolve_repository_root(catalog_path, repository_root),
            "router_authority.catalog_path",
        )
        return authority
    routers = authority["routers"]
    if not isinstance(routers, list) or not routers:
        raise PackagerError(
            "invalid_router_authority",
            "router_authority.routers must be a non-empty list",
            {"router_authority": authority},
        )
    for index, router in enumerate(routers):
        if not isinstance(router, dict):
            raise PackagerError(
                "invalid_router_authority",
                "router_authority routers must be objects",
                {"index": index},
            )
        ensure_string(
            router.get("name"), field=f"router_authority.routers[{index}].name"
        )
        ensure_string(
            router.get("description"),
            field=f"router_authority.routers[{index}].description",
        )
        members = router.get("members")
        if not isinstance(members, list) or not members:
            raise PackagerError(
                "invalid_router_authority",
                "each explicit router requires ordered member paths",
                {"index": index, "field": "members"},
            )
        for member_index, member in enumerate(members):
            ensure_string(
                member,
                field=f"router_authority.routers[{index}].members[{member_index}]",
            )
    return authority


def validate_native_invocation(
    payload: dict[str, Any],
    repository_root: Path,
    *,
    ensure_string: Any,
    resolve_repository_root: Any,
    validate_relative_path: Any,
    parse_native_router_authority_fn: Any,
) -> None:
    if "input_mode" in payload:
        raise PackagerError(
            "native_routed_rejects_legacy_input_mode",
            (
                "native_routed mode must use source_manifest and router_authority, "
                "not input_mode"
            ),
            {"input_mode": payload["input_mode"]},
        )
    source_manifest = ensure_string(
        payload.get("source_manifest"), field="source_manifest"
    )
    source_manifest_path = resolve_repository_root(source_manifest, repository_root)
    validate_relative_path(repository_root, source_manifest_path, "source_manifest")
    if (
        source_manifest_path.name != "plugin.json"
        or source_manifest_path.parent.name != ".codex-plugin"
    ):
        raise PackagerError(
            "invalid_source_manifest",
            "source_manifest must name .codex-plugin/plugin.json",
            {"source_manifest": source_manifest},
        )
    generated = payload.get("generated")
    if not isinstance(generated, dict):
        raise PackagerError(
            "missing_invocation_field",
            "native_routed mode requires generated identity",
            {"field": "generated"},
        )
    ensure_string(generated.get("name"), field="generated.name")
    ensure_string(generated.get("surface_id"), field="generated.surface_id")
    parse_native_router_authority_fn(
        payload,
        repository_root,
        ensure_string=ensure_string,
        resolve_repository_root=resolve_repository_root,
        validate_relative_path=validate_relative_path,
    )


def parse_invocation(
    invocation_path: Path,
    repo_root: Path,
    *,
    load_json: Any,
    upgrade_v1_invocation_fn: Any,
    collect_required_placeholders: Any,
    required_marker_prefix: str,
    parse_surface_mode_fn: Any,
    require_invocation_fields_fn: Any,
    parse_legacy_input_mode_fn: Any,
    resolve_repository_root: Any,
    resolve_local_path: Any,
    validate_native_invocation_fn: Any,
    validate_legacy_mode_inputs_fn: Any,
    parse_plugin_kind_fn: Any,
    invocation_factory: Any,
    validate_relative_path: Any,
) -> Any:
    payload = load_json(invocation_path)
    if not isinstance(payload, dict):
        raise PackagerError(
            "invalid_invocation_format",
            "invocation must be a JSON object",
            {"invocation_path": str(invocation_path.resolve())},
        )
    source_format_version = payload.get("format_version")
    if source_format_version == 1:
        payload = upgrade_v1_invocation_fn(payload)
    elif source_format_version != 2:
        raise PackagerError(
            "invalid_invocation_format",
            "invocation format_version must be 1 or 2",
            {
                "invocation_path": str(invocation_path.resolve()),
                "format_version": source_format_version,
            },
        )
    elif "surface_mode" not in payload:
        raise PackagerError(
            "missing_invocation_field",
            "version 2 invocations must select a surface_mode",
            {"field": "surface_mode"},
        )
    placeholders = collect_required_placeholders(
        payload, required_marker_prefix=required_marker_prefix
    )
    if placeholders:
        raise PackagerError(
            "incomplete_scaffold",
            "invocation still contains unresolved required markers",
            {
                "invocation_path": str(invocation_path.resolve()),
                "placeholders": placeholders,
                "required_marker_prefix": required_marker_prefix,
            },
        )
    surface_mode = parse_surface_mode_fn(payload)
    require_invocation_fields_fn(payload, surface_mode)
    input_mode = (
        parse_legacy_input_mode_fn(payload)
        if surface_mode == "legacy"
        else "native_routed"
    )
    repository_root = resolve_repository_root(payload["repository_root"], repo_root)
    output_root = resolve_local_path(invocation_path.parent, payload["output_root"])
    if surface_mode == "native_routed":
        validate_native_invocation_fn(payload, repository_root)
    skill_paths = (
        validate_legacy_mode_inputs_fn(payload, input_mode, invocation_path)
        if surface_mode == "legacy"
        else []
    )
    plugin_kind, plugin_kind_source = parse_plugin_kind_fn(payload)
    invocation = invocation_factory(
        format_version=2,
        source_format_version=source_format_version,
        surface_mode=surface_mode,
        input_mode=input_mode,
        plugin_kind=plugin_kind,
        plugin_kind_source=plugin_kind_source,
        source_root=payload.get("source_root"),
        repository_root=repository_root,
        output_root=output_root,
        skill_paths=skill_paths,
        cohort_catalog_path=payload.get("cohort_catalog_path"),
        router_catalog_path=payload.get("router_catalog_path"),
        cohort_id=payload.get("cohort_id"),
        display_name_override=payload.get("display_name_override"),
        plugin_slug_override=payload.get("plugin_slug_override"),
        publisher_slug_override=payload.get("publisher_slug_override"),
        surface_id_override=payload.get("surface_id_override"),
        branding_asset_overrides=dict(payload.get("branding_asset_overrides", {})),
        payload_assets=list(payload.get("payload_assets", [])),
        runtime_compatibility_version=payload.get("runtime_compatibility_version"),
        migration_contract_version=payload.get("migration_contract_version"),
        rollback_compatibility_hints=payload.get("rollback_compatibility_hints"),
        control_surface=payload.get("control_surface"),
        owned_integration_root=payload.get("owned_integration_root"),
        integration_points=list(payload.get("integration_points", [])),
        verification_targets=list(payload.get("verification_targets", [])),
        version_override=payload.get("version_override"),
        publication=payload.get("publication"),
        mcp_packaging=payload.get("mcp_packaging"),
        source_manifest=payload.get("source_manifest"),
        generated=payload.get("generated"),
        router_authority=payload.get("router_authority"),
    )
    validate_relative_path(repo_root, invocation.repository_root, "repository_root")
    validate_relative_path(repo_root, invocation.output_root, "output_root")
    return invocation
