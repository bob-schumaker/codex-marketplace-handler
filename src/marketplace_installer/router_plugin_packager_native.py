from __future__ import annotations

from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


NATIVE_TOP_LEVEL_METADATA_FIELDS = frozenset(
    {"description", "author", "homepage", "repository", "license", "keywords"}
)
NATIVE_INTERFACE_SCALAR_FIELDS = frozenset(
    {
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "websiteURL",
        "privacyPolicyURL",
        "termsOfServiceURL",
        "defaultPrompt",
        "brandColor",
    }
)
NATIVE_INTERFACE_PATH_FIELDS = frozenset(
    {"composerIcon", "logo", "logoDark", "screenshots"}
)
UNSUPPORTED_NATIVE_PLUGIN_FIELDS = frozenset({"hooks", "apps", "mcpServers", "agents"})
NATIVE_ROUTED_BOOTSTRAP_STATE_NAME = "native-routed-bootstrap-state.json"
NATIVE_ROUTED_RECEIPT_FORMAT = "router-plugin-packager-native-routed-receipt-v1"


def validate_native_output_isolation(
    output_root: Path, source_plugin_root: Path, member_roots: list[Path]
) -> None:
    boundaries = [source_plugin_root, *member_roots]
    for boundary in boundaries:
        try:
            output_root.relative_to(boundary)
        except ValueError:
            pass
        else:
            raise PackagerError(
                "invalid_output_root",
                "output_root may not be inside the native plugin source tree",
                {
                    "output_root": str(output_root),
                    "source_boundary": str(boundary),
                },
            )
        try:
            boundary.relative_to(output_root)
        except ValueError:
            pass
        else:
            raise PackagerError(
                "invalid_output_root",
                "output_root may not contain the native plugin source tree",
                {
                    "output_root": str(output_root),
                    "source_boundary": str(boundary),
                },
            )


def native_generated_tree_digest_from_outputs(
    outputs: dict[str, bytes], *, receipt_name: str, hash_bytes: Any, hash_text: Any
) -> str:
    lines = []
    for relative_path in sorted(path for path in outputs if path != receipt_name):
        lines.append(f"{relative_path}\t{hash_bytes(outputs[relative_path])}")
    return hash_text("\n".join(lines))


def native_generated_tree_digest_from_disk(
    output_root: Path, *, receipt_name: str, hash_bytes: Any, hash_text: Any
) -> str:
    lines = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(output_root).as_posix()
        if (
            relative == receipt_name
            or relative.endswith(".router-plugin-packager-promotion.json")
            or ".stage-" in relative
            or ".backup-" in relative
        ):
            continue
        lines.append(f"{relative}\t{hash_bytes(path.read_bytes())}")
    return hash_text("\n".join(lines))


def normalize_native_plugin_metadata(  # noqa: C901
    invocation: Any,
    source_manifest: dict[str, Any],
    *,
    plugin_metadata_factory: Any,
    ensure_string: Any,
    normalize_slug: Any,
    display_name_from_slug: Any,
) -> tuple[Any, dict[str, Any]]:
    unsupported = sorted(
        field for field in UNSUPPORTED_NATIVE_PLUGIN_FIELDS if field in source_manifest
    )
    if unsupported:
        raise PackagerError(
            "unsupported_native_plugin_component",
            "native_routed mode does not support copying source runtime components",
            {"unsupported_fields": unsupported},
        )
    plugin_slug = normalize_slug(
        ensure_string(invocation.generated.get("name"), field="generated.name")
    )
    if not plugin_slug:
        raise PackagerError(
            "invalid_native_generated_name",
            "generated.name must normalize to a non-empty plugin slug",
            {"generated": invocation.generated},
        )
    source_name = normalize_slug(
        ensure_string(source_manifest.get("name"), field="source_manifest.name")
    )
    if plugin_slug == source_name:
        raise PackagerError(
            "native_generated_name_collision",
            "generated.name must differ from the source plugin manifest name",
            {"generated_name": plugin_slug, "source_name": source_name},
        )
    source_description = source_manifest.get("description")
    description = (
        source_description.strip()
        if isinstance(source_description, str) and source_description.strip()
        else f"{display_name_from_slug(plugin_slug)} skills."
    )
    source_author = source_manifest.get("author")
    if source_author is not None and (
        not isinstance(source_author, dict)
        or not isinstance(source_author.get("name"), str)
        or not source_author["name"].strip()
    ):
        raise PackagerError(
            "invalid_source_plugin_manifest",
            "source manifest author must be an object with a non-empty name",
            {"field": "author"},
        )
    author = (
        dict(source_author)
        if isinstance(source_author, dict)
        else {"name": display_name_from_slug(plugin_slug)}
    )
    host_metadata: dict[str, Any] = {}
    for key in NATIVE_TOP_LEVEL_METADATA_FIELDS:
        if key not in source_manifest or key in {"description", "author"}:
            continue
        value = source_manifest[key]
        if key == "keywords":
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                raise PackagerError(
                    "invalid_source_plugin_manifest",
                    "source manifest keywords must be a non-empty string list",
                    {"field": key, "value": value},
                )
            host_metadata[key] = value
            continue
        if not isinstance(value, str) or not value.strip():
            raise PackagerError(
                "invalid_source_plugin_manifest",
                "allowlisted source manifest metadata must use the expected scalar type",
                {"field": key, "value": value},
            )
        host_metadata[key] = value.strip()
    source_interface = source_manifest.get("interface")
    if source_interface is not None and not isinstance(source_interface, dict):
        raise PackagerError(
            "invalid_source_plugin_manifest",
            "source manifest interface must be an object when present",
            {"field": "interface"},
        )
    interface: dict[str, Any] = {}
    if isinstance(source_interface, dict):
        for key, value in source_interface.items():
            if key in NATIVE_INTERFACE_SCALAR_FIELDS:
                if key == "capabilities":
                    if not isinstance(value, list) or not all(
                        isinstance(item, str) and item.strip() for item in value
                    ):
                        raise PackagerError(
                            "invalid_source_plugin_manifest",
                            "source interface capabilities must be a non-empty string list",
                            {"field": f"interface.{key}", "value": value},
                        )
                    interface[key] = value
                    continue
                if not isinstance(value, str) or not value.strip():
                    raise PackagerError(
                        "invalid_source_plugin_manifest",
                        "allowlisted source interface metadata must use the expected scalar type",
                        {"field": f"interface.{key}", "value": value},
                    )
                interface[key] = value.strip()
                continue
            if key in NATIVE_INTERFACE_PATH_FIELDS:
                if key == "screenshots":
                    if not isinstance(value, list) or not all(
                        isinstance(item, str) and item.strip().startswith("./")
                        for item in value
                    ):
                        raise PackagerError(
                            "invalid_source_plugin_manifest",
                            "source interface screenshots must be a list of ./ relative paths",
                            {"field": f"interface.{key}", "value": value},
                        )
                    interface[key] = [item.strip() for item in value]
                    continue
                if not isinstance(value, str) or not value.strip().startswith("./"):
                    raise PackagerError(
                        "invalid_source_plugin_manifest",
                        "source interface asset paths must be ./ relative paths",
                        {"field": f"interface.{key}", "value": value},
                    )
                interface[key] = value.strip()
    display_name = str(
        interface.get("displayName") or display_name_from_slug(plugin_slug)
    )
    return (
        plugin_metadata_factory(
            publisher_slug=normalize_slug(
                invocation.publisher_slug_override or author["name"] or "local"
            ),
            plugin_slug=plugin_slug,
            display_name=display_name,
            description=description,
            author=author,
            host_metadata=host_metadata,
            packaging_mode="router-surface",
            role=None,
            branding_assets={},
            interface=interface,
        ),
        {
            "plugin_metadata_sources": {
                "publisher_slug": "override"
                if invocation.publisher_slug_override
                else "source_plugin_manifest",
                "plugin_slug": "generated.name",
                "display_name": "source_plugin_manifest"
                if "displayName" in interface
                else "derived",
                "host_metadata": "source_plugin_manifest",
                "branding_assets": "source_plugin_manifest",
            },
            "rejected_candidates": [],
        },
    )


def native_receipt_contract(request: Any) -> dict[str, Any]:
    return {
        "format": NATIVE_ROUTED_RECEIPT_FORMAT,
        "source_manifest": request.decision_record["source_manifest"],
        "source_plugin_version": request.decision_record["source_plugin_version"],
        "router_authority": request.decision_record["router_authority"],
        "skill_paths": request.skill_paths,
        "state_scope": request.decision_record["state_scope"],
    }


def load_native_router_catalog(
    catalog_path: Path,
    *,
    load_yaml: Any,
    collect_required_placeholders: Any,
    required_marker_prefix: str,
) -> list[dict[str, Any]]:
    payload = load_yaml(catalog_path)
    placeholders = collect_required_placeholders(
        payload, required_marker_prefix=required_marker_prefix
    )
    if placeholders:
        raise PackagerError(
            "incomplete_scaffold",
            "native router catalog still contains unresolved required markers",
            {
                "catalog_path": str(catalog_path.resolve()),
                "placeholders": placeholders,
                "required_marker_prefix": required_marker_prefix,
            },
        )
    if not isinstance(payload, dict):
        raise PackagerError(
            "invalid_catalog_shape",
            "native router catalog YAML must load to a mapping",
            {"catalog_path": str(catalog_path)},
        )
    router_entries = payload.get("routers")
    if not isinstance(router_entries, list):
        raise PackagerError(
            "invalid_catalog_shape",
            "native router catalog YAML must expose a routers list",
            {"catalog_path": str(catalog_path)},
        )
    return [entry for entry in router_entries if isinstance(entry, dict)]


def normalize_native_router_catalog_authority(  # noqa: C901
    invocation: Any,
    source_plugin_root: Path,
    source_skills_root: Path,
    authority: dict[str, Any],
    *,
    ensure_string: Any,
    normalize_slug: Any,
    resolve_repository_root: Any,
    validate_relative_path: Any,
    load_native_router_catalog_fn: Any,
    router_factory: Any,
    discover_visible_skill_paths_fn: Any,
) -> tuple[list[str], list[str], list[Any], list[Path]]:
    catalog_id = normalize_slug(
        ensure_string(authority.get("catalog"), field="router_authority.catalog")
    )
    if not catalog_id:
        raise PackagerError(
            "missing_catalog_router",
            "router_authority.catalog must normalize to a non-empty slug",
            {"router_authority": authority},
        )
    catalog_path = resolve_repository_root(
        ensure_string(
            authority.get("catalog_path"), field="router_authority.catalog_path"
        ),
        invocation.repository_root,
    )
    validate_relative_path(
        invocation.repository_root, catalog_path, "router_authority.catalog_path"
    )
    router_entries = load_native_router_catalog_fn(catalog_path)
    selected = [
        entry
        for entry in router_entries
        if normalize_slug(str(entry.get("plugin", ""))) == catalog_id
    ]
    if not selected:
        raise PackagerError(
            "missing_catalog_router",
            "native_routed catalog authority has no routers for the selected catalog id",
            {
                "catalog": authority.get("catalog"),
                "catalog_path": str(
                    catalog_path.relative_to(invocation.repository_root)
                ),
            },
        )
    skill_ids: list[str] = []
    skill_paths: list[str] = []
    member_roots: list[Path] = []
    owner_map: dict[str, str] = {}
    routers: list[Any] = []
    for entry in selected:
        router_name = ensure_string(entry.get("name"), field="catalog router.name")
        router_description = ensure_string(
            entry.get("description"), field="catalog router.description"
        )
        raw_members = entry.get("members")
        if not isinstance(raw_members, list) or not raw_members:
            raise PackagerError(
                "invalid_catalog_shape",
                "native catalog router entries must declare a non-empty members list",
                {"router_entry": entry},
            )
        member_skill_ids: list[str] = []
        for raw_member in raw_members:
            member_skill_id = normalize_slug(str(raw_member))
            if not member_skill_id:
                raise PackagerError(
                    "invalid_catalog_shape",
                    "native catalog router members must normalize to non-empty skill IDs",
                    {"member": raw_member, "router_entry": entry},
                )
            if member_skill_id in owner_map:
                raise PackagerError(
                    "catalog_duplicate_member_ownership",
                    "native catalog routers assign one member skill to multiple routers",
                    {
                        "skill_id": member_skill_id,
                        "first_router": owner_map[member_skill_id],
                        "second_router": router_name,
                    },
                )
            member_root = (source_skills_root / member_skill_id).resolve()
            validate_relative_path(
                source_plugin_root, member_root, "router_authority.catalog member"
            )
            if member_root.is_symlink() or not member_root.is_dir():
                raise PackagerError(
                    "catalog_member_not_in_cohort",
                    "native catalog router references a member outside the source plugin skills tree",
                    {
                        "skill_id": member_skill_id,
                        "catalog_path": str(
                            catalog_path.relative_to(invocation.repository_root)
                        ),
                    },
                )
            if not (member_root / "SKILL.md").is_file():
                raise PackagerError(
                    "catalog_member_not_in_cohort",
                    "native catalog router member must resolve to a source skill directory with SKILL.md",
                    {
                        "skill_id": member_skill_id,
                        "catalog_path": str(
                            catalog_path.relative_to(invocation.repository_root)
                        ),
                    },
                )
            owner_map[member_skill_id] = router_name
            if member_skill_id not in skill_ids:
                skill_ids.append(member_skill_id)
                skill_paths.append(
                    member_root.relative_to(invocation.repository_root).as_posix()
                )
                member_roots.append(member_root)
            member_skill_ids.append(member_skill_id)
        routers.append(
            router_factory(
                router_slug=normalize_slug(router_name),
                description=router_description,
                member_skill_ids=member_skill_ids,
            )
        )
    discovered_skill_ids = {
        normalize_slug(path.name)
        for path in discover_visible_skill_paths_fn(source_skills_root)
    }
    extras = sorted(
        skill_id for skill_id in owner_map if skill_id not in discovered_skill_ids
    )
    if extras:
        raise PackagerError(
            "catalog_member_not_in_cohort",
            "native catalog router references a member outside the source plugin skills tree",
            {"skill_ids": extras, "catalog": authority.get("catalog")},
        )
    missing = sorted(
        skill_id for skill_id in discovered_skill_ids if skill_id not in owner_map
    )
    if missing:
        raise PackagerError(
            "catalog_missing_member_ownership",
            "native catalog routers do not cover every visible source skill",
            {"skill_ids": missing, "catalog": authority.get("catalog")},
        )
    return skill_ids, skill_paths, routers, member_roots


def normalize_native_request(  # noqa: C901
    invocation: Any,
    repo_root: Path,
    *,
    ensure_string: Any,
    normalize_slug: Any,
    resolve_repository_root: Any,
    validate_relative_path: Any,
    load_source_plugin_manifest: Any,
    normalize_native_router_catalog_authority_fn: Any,
    discover_visible_skill_paths_fn: Any,
    validate_native_output_isolation_fn: Any,
    normalize_native_plugin_metadata_fn: Any,
    resolve_publication_contract_fn: Any,
    normalize_control_surface_fn: Any,
    validate_control_surface_visibility_fn: Any,
    normalize_owned_integration_root_fn: Any,
    normalize_metadata_records_fn: Any,
    validate_integration_points_fn: Any,
    normalize_payload_assets_fn: Any,
    normalized_request_factory: Any,
    router_factory: Any,
) -> Any:
    assert invocation.source_manifest is not None
    assert invocation.generated is not None
    source_manifest_path = resolve_repository_root(
        invocation.source_manifest, invocation.repository_root
    )
    source_manifest = load_source_plugin_manifest(
        invocation.repository_root, invocation.source_manifest
    )
    if not source_manifest:
        raise PackagerError(
            "missing_source_plugin_manifest",
            "native_routed mode requires an existing source plugin manifest",
            {"source_manifest": invocation.source_manifest},
        )
    source_version = ensure_string(
        source_manifest.get("version"), field="source_manifest.version"
    )
    source_plugin_root = source_manifest_path.parent.parent.resolve()
    validate_relative_path(repo_root, source_plugin_root, "source_plugin_root")
    source_root = source_plugin_root
    source_root_text = source_plugin_root.relative_to(
        invocation.repository_root
    ).as_posix()
    source_skills_root = source_plugin_root / "skills"
    if not source_skills_root.is_dir() or source_skills_root.is_symlink():
        raise PackagerError(
            "invalid_source_root",
            "native_routed mode requires a regular source skills directory at <plugin>/skills",
            {"source_root": str(source_skills_root)},
        )
    authority = invocation.router_authority or {}
    if "catalog" in authority:
        skill_ids, skill_paths, routers, member_roots = (
            normalize_native_router_catalog_authority_fn(
                invocation, source_plugin_root, source_skills_root, authority
            )
        )
    else:
        raw_routers = authority.get("routers", [])
        skill_ids = []
        skill_paths = []
        routers = []
        member_roots = []
        member_path_by_id: dict[str, str] = {}
        for router in raw_routers:
            router_slug = normalize_slug(str(router["name"]))
            if not router_slug:
                raise PackagerError(
                    "invalid_router_authority",
                    "native_routed router names must normalize to non-empty slugs",
                    {"router": router},
                )
            member_skill_ids: list[str] = []
            for member in router["members"]:
                member_path = resolve_repository_root(
                    member, invocation.repository_root
                )
                validate_relative_path(
                    source_plugin_root, member_path, "router_authority.routers.members"
                )
                try:
                    member_path.relative_to(source_skills_root)
                except ValueError as exc:
                    raise PackagerError(
                        "invalid_router_authority",
                        "native_routed router members must resolve under <plugin>/skills",
                        {"member": member},
                    ) from exc
                if member_path.is_symlink() or not member_path.is_dir():
                    raise PackagerError(
                        "invalid_router_authority",
                        "native_routed router members must be regular skill directories",
                        {"member": member},
                    )
                if not (member_path / "SKILL.md").is_file():
                    raise PackagerError(
                        "invalid_router_authority",
                        "native_routed router members must contain SKILL.md",
                        {"member": member},
                    )
                skill_id = normalize_slug(member_path.name)
                if not skill_id:
                    raise PackagerError(
                        "invalid_router_authority",
                        "native_routed router member names must normalize to non-empty slugs",
                        {"member": member},
                    )
                repo_relative_member = member_path.relative_to(
                    invocation.repository_root
                ).as_posix()
                existing = member_path_by_id.get(skill_id)
                if existing is not None and existing != repo_relative_member:
                    raise PackagerError(
                        "duplicate_skill_id",
                        "native_routed router members normalize to duplicate skill IDs",
                        {
                            "skill_id": skill_id,
                            "first_path": existing,
                            "second_path": repo_relative_member,
                        },
                    )
                member_path_by_id[skill_id] = repo_relative_member
                if skill_id not in skill_ids:
                    skill_ids.append(skill_id)
                    skill_paths.append(repo_relative_member)
                    member_roots.append(member_path)
                member_skill_ids.append(skill_id)
            routers.append(
                router_factory(
                    router_slug=router_slug,
                    description=str(router["description"]).strip(),
                    member_skill_ids=member_skill_ids,
                )
            )
        discovered_members = {
            path.relative_to(invocation.repository_root).as_posix()
            for path in discover_visible_skill_paths_fn(source_skills_root)
        }
        assigned_members = set(skill_paths)
        if discovered_members != assigned_members:
            raise PackagerError(
                "incomplete_router_authority",
                "native_routed router authority must cover every visible source skill exactly once",
                {
                    "unassigned_members": sorted(discovered_members - assigned_members),
                    "unknown_members": sorted(assigned_members - discovered_members),
                },
            )
    validate_native_output_isolation_fn(
        invocation.output_root.resolve(), source_plugin_root, member_roots
    )
    metadata, metadata_info = normalize_native_plugin_metadata_fn(
        invocation, source_manifest
    )
    surface_id = normalize_slug(
        ensure_string(
            invocation.generated.get("surface_id"), field="generated.surface_id"
        )
    )
    if not surface_id:
        raise PackagerError(
            "invalid_surface_id",
            "generated.surface_id must normalize to a non-empty slug",
            {"generated": invocation.generated},
        )
    if surface_id == normalize_slug(
        ensure_string(source_manifest.get("name"), field="source_manifest.name")
    ):
        raise PackagerError(
            "native_surface_id_collision",
            "generated.surface_id must differ from the source plugin identity",
            {"surface_id": surface_id, "source_manifest": invocation.source_manifest},
        )
    publication_contract = resolve_publication_contract_fn(invocation, None)
    control_surface = normalize_control_surface_fn(invocation.control_surface)
    validate_control_surface_visibility_fn(
        control_surface, {router.router_slug for router in routers}
    )
    owned_integration_root = normalize_owned_integration_root_fn(
        invocation.owned_integration_root
    )
    integration_points = normalize_metadata_records_fn(
        invocation.integration_points, "integration_points"
    )
    validate_integration_points_fn(integration_points, owned_integration_root)
    verification_targets = normalize_metadata_records_fn(
        invocation.verification_targets, "verification_targets"
    )
    return normalized_request_factory(
        source_root=source_root,
        source_root_text=source_root_text,
        repository_root=invocation.repository_root,
        output_root=invocation.output_root,
        plugin_kind=invocation.plugin_kind,
        surface_id=surface_id,
        skill_ids=skill_ids,
        skill_paths=skill_paths,
        routers=routers,
        plugin_metadata=metadata,
        decision_record={
            "surface_mode": invocation.surface_mode,
            "input_mode": invocation.input_mode,
            "plugin_kind": invocation.plugin_kind,
            "plugin_kind_source": invocation.plugin_kind_source,
            "surface_id_source": "generated.surface_id",
            "skill_ids_source": "router_authority",
            "source_root_source": "source_manifest",
            "plugin_metadata_sources": metadata_info["plugin_metadata_sources"],
            "rejected_candidates": metadata_info["rejected_candidates"],
            "bootstrap_state_reused": False,
            "publication_source": "top_level"
            if invocation.publication is not None
            else None,
            "source_manifest": invocation.source_manifest,
            "source_plugin_version": source_version,
            "router_authority": invocation.router_authority,
            "state_scope": "output_root_local",
        },
        input_mode=invocation.input_mode,
        bootstrap_state_path=invocation.output_root
        / ".codex-plugin"
        / NATIVE_ROUTED_BOOTSTRAP_STATE_NAME,
        payload_assets=normalize_payload_assets_fn(invocation, source_root),
        runtime_compatibility_version=str(
            invocation.runtime_compatibility_version or "1"
        ),
        migration_contract_version=(
            str(invocation.migration_contract_version).strip()
            if invocation.migration_contract_version is not None
            else None
        ),
        rollback_compatibility_hints=invocation.rollback_compatibility_hints,
        control_surface=control_surface,
        owned_integration_root=owned_integration_root,
        integration_points=integration_points,
        verification_targets=verification_targets,
        version_override=source_version,
        publication_contract=publication_contract,
        mcp_packaging=None,
    )


def normalize_native_request_with_packager_deps(
    invocation: Any,
    repo_root: Path,
    *,
    normalize_native_request_fn: Any,
    ensure_string: Any,
    normalize_slug: Any,
    resolve_repository_root: Any,
    validate_relative_path: Any,
    load_source_plugin_manifest: Any,
    normalize_native_router_catalog_authority_fn: Any,
    discover_visible_skill_paths_fn: Any,
    validate_native_output_isolation_fn: Any,
    normalize_native_plugin_metadata_fn: Any,
    resolve_publication_contract_fn: Any,
    normalize_control_surface_fn: Any,
    validate_control_surface_visibility_fn: Any,
    normalize_owned_integration_root_fn: Any,
    normalize_metadata_records_fn: Any,
    validate_integration_points_fn: Any,
    normalize_payload_assets_fn: Any,
    normalized_request_factory: Any,
    router_factory: Any,
) -> Any:
    return normalize_native_request_fn(
        invocation,
        repo_root,
        ensure_string=ensure_string,
        normalize_slug=normalize_slug,
        resolve_repository_root=resolve_repository_root,
        validate_relative_path=validate_relative_path,
        load_source_plugin_manifest=load_source_plugin_manifest,
        normalize_native_router_catalog_authority_fn=normalize_native_router_catalog_authority_fn,
        discover_visible_skill_paths_fn=discover_visible_skill_paths_fn,
        validate_native_output_isolation_fn=validate_native_output_isolation_fn,
        normalize_native_plugin_metadata_fn=normalize_native_plugin_metadata_fn,
        resolve_publication_contract_fn=resolve_publication_contract_fn,
        normalize_control_surface_fn=normalize_control_surface_fn,
        validate_control_surface_visibility_fn=validate_control_surface_visibility_fn,
        normalize_owned_integration_root_fn=normalize_owned_integration_root_fn,
        normalize_metadata_records_fn=normalize_metadata_records_fn,
        validate_integration_points_fn=validate_integration_points_fn,
        normalize_payload_assets_fn=normalize_payload_assets_fn,
        normalized_request_factory=normalized_request_factory,
        router_factory=router_factory,
    )
