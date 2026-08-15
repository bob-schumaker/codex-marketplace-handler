from __future__ import annotations

from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


def normalize_request_for_packager(
    invocation: Any,
    repo_root: Any,
    *,
    normalize_native_request_fn: Any,
    discover_source_root_fn: Any,
    derive_source_root_from_skill_paths_fn: Any,
    validate_relative_path_fn: Any,
    load_bootstrap_state_fn: Any,
    catalog_selection_fn: Any,
    normalize_skill_paths_fn: Any,
    router_factory: Any,
    normalize_plugin_metadata_fn: Any,
    normalize_slug_fn: Any,
    normalize_payload_assets_fn: Any,
    normalize_mcp_packaging_fn: Any,
    resolve_publication_contract_fn: Any,
    replace_fn: Any,
    normalize_control_surface_fn: Any,
    validate_control_surface_visibility_fn: Any,
    normalize_owned_integration_root_fn: Any,
    normalize_metadata_records_fn: Any,
    validate_integration_points_fn: Any,
    bootstrap_state_path_fn: Any,
    normalized_request_factory: Any,
) -> Any:
    if invocation.input_mode == "native_routed":
        return normalize_native_request_fn(invocation, repo_root)
    if invocation.source_root:
        source_root = (invocation.repository_root / invocation.source_root).resolve()
        source_root_text = invocation.source_root
        source_root_source = "explicit"
    elif invocation.input_mode == "repo_bootstrap":
        source_root, source_root_text = discover_source_root_fn(
            invocation.repository_root
        )
        source_root_source = "discovered"
    else:
        source_root, source_root_text = derive_source_root_from_skill_paths_fn(
            invocation.repository_root, invocation.skill_paths
        )
        source_root_source = "derived"
    validate_relative_path_fn(repo_root, source_root, "source_root")
    bootstrap_state = load_bootstrap_state_fn(invocation.repository_root)
    if bootstrap_state and bootstrap_state.get("source_root") != source_root_text:
        bootstrap_state = None
    catalog_selection = None
    catalog_info: dict[str, Any] = {}
    if invocation.input_mode == "catalog":
        catalog_selection, catalog_info = catalog_selection_fn(invocation, source_root)
        skill_ids = catalog_selection.skill_ids
        skill_paths = catalog_selection.skill_paths
        routers = catalog_selection.routers
    else:
        skill_ids, skill_paths = normalize_skill_paths_fn(invocation, source_root)
        routers = [
            router_factory(
                router_slug=skill_id,
                description=f"Route {skill_id} workflows.",
                member_skill_ids=[skill_id],
            )
            for skill_id in skill_ids
        ]
    metadata, metadata_info = normalize_plugin_metadata_fn(
        invocation,
        invocation.repository_root,
        bootstrap_state,
        plugin_slug_default=(
            catalog_selection.cohort_id if catalog_selection else None
        ),
        display_name_default=(
            catalog_selection.display_name if catalog_selection else None
        ),
        role_default=(catalog_selection.role if catalog_selection else None),
    )
    surface_seed = invocation.surface_id_override or metadata.plugin_slug
    surface_id = normalize_slug_fn(surface_seed)
    if not surface_id:
        raise PackagerError(
            "invalid_surface_id",
            "surface_id must normalize to a non-empty slug",
            {"surface_seed": surface_seed},
        )
    payload_assets = normalize_payload_assets_fn(invocation, source_root)
    mcp_packaging = normalize_mcp_packaging_fn(invocation, skill_ids, payload_assets)
    publication_contract = resolve_publication_contract_fn(invocation, mcp_packaging)
    if mcp_packaging is not None:
        metadata = replace_fn(metadata, packaging_mode="mcp-direct-surface")
    control_surface = normalize_control_surface_fn(invocation.control_surface)
    validate_control_surface_visibility_fn(
        control_surface,
        set(skill_ids)
        if mcp_packaging is not None
        else {router.router_slug for router in routers},
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
            "input_mode": invocation.input_mode,
            "plugin_kind": invocation.plugin_kind,
            "plugin_kind_source": invocation.plugin_kind_source,
            "surface_id_source": (
                "override" if invocation.surface_id_override else "derived"
            ),
            "skill_ids_source": (
                "explicit"
                if invocation.input_mode == "skill_list"
                else ("catalog" if invocation.input_mode == "catalog" else "discovered")
            ),
            "source_root_source": source_root_source,
            "plugin_metadata_sources": metadata_info["plugin_metadata_sources"],
            "rejected_candidates": metadata_info["rejected_candidates"],
            "bootstrap_state_reused": bool(bootstrap_state),
            "publication_source": (
                "top_level"
                if invocation.publication is not None
                else ("mcp_packaging" if mcp_packaging is not None else None)
            ),
            **catalog_info,
        },
        input_mode=invocation.input_mode,
        bootstrap_state_path=bootstrap_state_path_fn(invocation.repository_root),
        payload_assets=payload_assets,
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
        version_override=(
            str(invocation.version_override).strip()
            if invocation.version_override is not None
            else None
        ),
        publication_contract=publication_contract,
        mcp_packaging=mcp_packaging,
    )


def normalize_request_with_packager_deps(
    invocation: Any,
    repo_root: Any,
    *,
    normalize_request_for_packager_fn: Any,
    normalize_native_request_fn: Any,
    discover_source_root_fn: Any,
    derive_source_root_from_skill_paths_fn: Any,
    validate_relative_path_fn: Any,
    load_bootstrap_state_fn: Any,
    catalog_selection_fn: Any,
    normalize_skill_paths_fn: Any,
    router_factory: Any,
    normalize_plugin_metadata_fn: Any,
    normalize_slug_fn: Any,
    normalize_payload_assets_fn: Any,
    normalize_mcp_packaging_fn: Any,
    resolve_publication_contract_fn: Any,
    replace_fn: Any,
    normalize_control_surface_fn: Any,
    validate_control_surface_visibility_fn: Any,
    normalize_owned_integration_root_fn: Any,
    normalize_metadata_records_fn: Any,
    validate_integration_points_fn: Any,
    bootstrap_state_path_fn: Any,
    normalized_request_factory: Any,
) -> Any:
    return normalize_request_for_packager_fn(
        invocation,
        repo_root,
        normalize_native_request_fn=normalize_native_request_fn,
        discover_source_root_fn=discover_source_root_fn,
        derive_source_root_from_skill_paths_fn=derive_source_root_from_skill_paths_fn,
        validate_relative_path_fn=validate_relative_path_fn,
        load_bootstrap_state_fn=load_bootstrap_state_fn,
        catalog_selection_fn=catalog_selection_fn,
        normalize_skill_paths_fn=normalize_skill_paths_fn,
        router_factory=router_factory,
        normalize_plugin_metadata_fn=normalize_plugin_metadata_fn,
        normalize_slug_fn=normalize_slug_fn,
        normalize_payload_assets_fn=normalize_payload_assets_fn,
        normalize_mcp_packaging_fn=normalize_mcp_packaging_fn,
        resolve_publication_contract_fn=resolve_publication_contract_fn,
        replace_fn=replace_fn,
        normalize_control_surface_fn=normalize_control_surface_fn,
        validate_control_surface_visibility_fn=validate_control_surface_visibility_fn,
        normalize_owned_integration_root_fn=normalize_owned_integration_root_fn,
        normalize_metadata_records_fn=normalize_metadata_records_fn,
        validate_integration_points_fn=validate_integration_points_fn,
        bootstrap_state_path_fn=bootstrap_state_path_fn,
        normalized_request_factory=normalized_request_factory,
    )
