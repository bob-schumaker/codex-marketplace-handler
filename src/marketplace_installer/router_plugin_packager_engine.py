#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["packaging==26.3", "PyYAML==6.0.3"]
# ///
"""Portable first-slice router plugin packager."""

from __future__ import annotations

import argparse
import os
import shutil
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError
from marketplace_installer.router_plugin_packager_constants import (
    DECISION_STATE_DIR as _DECISION_STATE_DIR,
)
from marketplace_installer.router_plugin_packager_constants import (
    PUBLICATION_METADATA_NAME as _PUBLICATION_METADATA_NAME,
)
from marketplace_installer.router_plugin_packager_constants import (
    RECEIPT_NAME as _RECEIPT_NAME,
)
from marketplace_installer.router_plugin_packager_constants import (
    REQUIRED_MARKER_PREFIX as _REQUIRED_MARKER_PREFIX,
)
from marketplace_installer.router_plugin_packager_hashing import (
    canonical_json_bytes as _canonical_json_bytes,
)
from marketplace_installer.router_plugin_packager_hashing import (
    hash_bytes as _hash_bytes,
)
from marketplace_installer.router_plugin_packager_hashing import hash_text as _hash_text
from marketplace_installer.router_plugin_packager_hashing import hash_tree as _hash_tree
from marketplace_installer.router_plugin_packager_branding import (
    discover_branding_assets as _discover_branding_assets_impl,
)
from marketplace_installer.router_plugin_packager_branding import (
    resolve_branding_assets as _resolve_branding_assets_impl,
)
from marketplace_installer.router_plugin_packager_catalog import CatalogSelection
from marketplace_installer.router_plugin_packager_authority import (
    mcp_authority_identity as _mcp_authority_identity_impl,
)
from marketplace_installer.router_plugin_packager_catalog import (
    catalog_selection as _catalog_selection_impl,
)
from marketplace_installer.router_plugin_packager_catalog import (
    load_catalog_lists as _load_catalog_lists_impl,
)
from marketplace_installer.router_plugin_packager_catalog import (
    resolve_catalog_paths as _resolve_catalog_paths_impl,
)
from marketplace_installer.router_plugin_packager_catalog import (
    routers_for_catalog_cohort as _routers_for_catalog_cohort_impl,
)
from marketplace_installer.router_plugin_packager_catalog import (
    select_catalog_cohort as _select_catalog_cohort_impl,
)
from marketplace_installer.router_plugin_packager_catalog import (
    validate_catalog_skill_paths as _validate_catalog_skill_paths_impl,
)
from marketplace_installer.router_plugin_packager_control import (
    normalize_control_surface as _normalize_control_surface_impl,
)
from marketplace_installer.router_plugin_packager_control import (
    normalize_metadata_records as _normalize_metadata_records_impl,
)
from marketplace_installer.router_plugin_packager_control import (
    normalize_owned_integration_root as _normalize_owned_integration_root_impl,
)
from marketplace_installer.router_plugin_packager_control import (
    validate_control_surface_visibility as _validate_control_surface_visibility_impl,
)
from marketplace_installer.router_plugin_packager_control import (
    validate_integration_points as _validate_integration_points_impl,
)
from marketplace_installer.router_plugin_packager_io import (
    print_error as _print_error_payload,
)
from marketplace_installer.router_plugin_packager_io import (
    print_payload as _print_payload,
)
from marketplace_installer.router_plugin_packager_io import write_json as _write_json
from marketplace_installer.router_plugin_packager_invocation import (
    parse_invocation as _parse_invocation_impl,
)
from marketplace_installer.router_plugin_packager_invocation import (
    parse_native_router_authority as _parse_native_router_authority_impl,
)
from marketplace_installer.router_plugin_packager_invocation import (
    parse_legacy_input_mode as _parse_legacy_input_mode_impl,
)
from marketplace_installer.router_plugin_packager_invocation import (
    parse_plugin_kind as _parse_plugin_kind_impl,
)
from marketplace_installer.router_plugin_packager_invocation import (
    require_invocation_fields as _require_invocation_fields_impl,
)
from marketplace_installer.router_plugin_packager_invocation import (
    validate_native_invocation as _validate_native_invocation_impl,
)
from marketplace_installer.router_plugin_packager_invocation import (
    validate_legacy_mode_inputs as _validate_legacy_mode_inputs_impl,
)
from marketplace_installer.router_plugin_packager_mcp import (
    mcp_descriptor_payload as _mcp_descriptor_payload,
)
from marketplace_installer.router_plugin_packager_mcp import (
    mcp_launch_contract_provenance as _mcp_launch_contract_provenance,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    McpLaunchContract as _McpLaunchContract,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    normalize_mcp_environment as _normalize_mcp_environment_impl,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    normalize_mcp_launch_contract as _normalize_mcp_launch_contract_impl,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    normalize_mcp_packaging as _normalize_mcp_packaging_impl,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    normalize_mcp_release_surface as _normalize_mcp_release_surface_impl,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    normalize_mcp_skill_release_contract as _normalize_mcp_skill_release_contract_impl,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    normalize_mcp_staging_contract as _normalize_mcp_staging_contract_impl,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    normalize_publication_contract as _normalize_publication_contract_impl,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    require_mapping as _require_mapping_impl,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    require_string_list as _require_string_list_impl,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    resolve_publication_contract as _resolve_publication_contract_impl,
)
from marketplace_installer.router_plugin_packager_mcp import (
    validate_mcp_descriptor_round_trip as _validate_mcp_descriptor_round_trip_impl,
)
from marketplace_installer.router_plugin_packager_manifest import (
    compute_version as _compute_version_impl,
)
from marketplace_installer.router_plugin_packager_manifest import (
    plugin_id as _plugin_id,
)
from marketplace_installer.router_plugin_packager_manifest import (
    plugin_manifest as _plugin_manifest,
)
from marketplace_installer.router_plugin_packager_metadata import (
    normalize_plugin_metadata as _normalize_plugin_metadata_impl,
)
from marketplace_installer.router_plugin_packager_native import (
    NATIVE_ROUTED_BOOTSTRAP_STATE_NAME,
)
from marketplace_installer.router_plugin_packager_native import (
    NATIVE_ROUTED_RECEIPT_FORMAT,
)
from marketplace_installer.router_plugin_packager_native import (
    load_native_router_catalog as _load_native_router_catalog_impl,
)
from marketplace_installer.router_plugin_packager_native import (
    normalize_native_request as _normalize_native_request_impl,
)
from marketplace_installer.router_plugin_packager_native import (
    normalize_native_request_with_packager_deps as _normalize_native_request_with_packager_deps,
)
from marketplace_installer.router_plugin_packager_native import (
    native_generated_tree_digest_from_disk as _native_generated_tree_digest_from_disk_impl,
)
from marketplace_installer.router_plugin_packager_native import (
    native_generated_tree_digest_from_outputs as _native_generated_tree_digest_from_outputs_impl,
)
from marketplace_installer.router_plugin_packager_native import (
    native_receipt_contract as _native_receipt_contract_impl,
)
from marketplace_installer.router_plugin_packager_native import (
    normalize_native_plugin_metadata as _normalize_native_plugin_metadata_impl,
)
from marketplace_installer.router_plugin_packager_native import (
    normalize_native_router_catalog_authority as _normalize_native_router_catalog_authority_impl,
)
from marketplace_installer.router_plugin_packager_native import (
    validate_native_output_isolation as _validate_native_output_isolation_impl,
)
from marketplace_installer.router_plugin_packager_normalization import (
    normalize_request_for_packager as _normalize_request_for_packager,
)
from marketplace_installer.router_plugin_packager_normalization import (
    normalize_request_with_packager_deps as _normalize_request_with_packager_deps,
)
from marketplace_installer.router_plugin_packager_parsing import (
    collect_required_placeholders as _collect_required_placeholders,
)
from marketplace_installer.router_plugin_packager_parsing import (
    ensure_string as _ensure_string,
)
from marketplace_installer.router_plugin_packager_parsing import (
    has_hidden_path_segment as _has_hidden_path_segment,
)
from marketplace_installer.router_plugin_packager_parsing import load_json as _load_json
from marketplace_installer.router_plugin_packager_parsing import (
    load_json_bytes as _load_json_bytes,
)
from marketplace_installer.router_plugin_packager_parsing import (
    load_source_plugin_manifest as _load_source_plugin_manifest,
)
from marketplace_installer.router_plugin_packager_parsing import load_yaml as _load_yaml
from marketplace_installer.router_plugin_packager_parsing import (
    parse_markdown_frontmatter as _parse_markdown_frontmatter,
)
from marketplace_installer.router_plugin_packager_parsing import (
    resolve_local_path as _resolve_local_path,
)
from marketplace_installer.router_plugin_packager_parsing import (
    resolve_repository_root as _resolve_repository_root,
)
from marketplace_installer.router_plugin_packager_parsing import (
    validate_relative_path as _validate_relative_path,
)
from marketplace_installer.router_plugin_packager_outputs import (
    BuildOutputsPackagerDeps,
)
from marketplace_installer.router_plugin_packager_outputs import (
    build_outputs_for_packager as _build_outputs_for_packager,
)
from marketplace_installer.router_plugin_packager_outputs import (
    build_outputs_with_packager_deps as _build_outputs_with_packager_deps,
)
from marketplace_installer.router_plugin_packager_outputs import (
    build_record_payload_entry_for_packager as _build_record_payload_entry_for_packager,
)
from marketplace_installer.router_plugin_packager_outputs import (
    add_branding_outputs as _add_branding_outputs_impl,
)
from marketplace_installer.router_plugin_packager_outputs import (
    add_direct_skill_outputs as _add_direct_skill_outputs_impl,
)
from marketplace_installer.router_plugin_packager_outputs import (
    add_native_interface_asset_outputs as _add_native_interface_asset_outputs_impl,
)
from marketplace_installer.router_plugin_packager_outputs import (
    add_payload_asset_outputs as _add_payload_asset_outputs_impl,
)
from marketplace_installer.router_plugin_packager_outputs import (
    add_module_outputs as _add_module_outputs_impl,
)
from marketplace_installer.router_plugin_packager_outputs import (
    populate_primary_outputs_for_packager as _populate_primary_outputs_for_packager,
)
from marketplace_installer.router_plugin_packager_outputs import (
    add_router_outputs as _add_router_outputs_impl,
)
from marketplace_installer.router_plugin_packager_payloads import (
    normalize_one_payload_asset as _normalize_one_payload_asset_impl,
)
from marketplace_installer.router_plugin_packager_payloads import (
    normalize_payload_acquisition_mode as _normalize_payload_acquisition_mode_impl,
)
from marketplace_installer.router_plugin_packager_payloads import (
    normalize_payload_assets as _normalize_payload_assets_impl,
)
from marketplace_installer.router_plugin_packager_payloads import (
    normalize_payload_exclude as _normalize_payload_exclude_impl,
)
from marketplace_installer.router_plugin_packager_payloads import (
    normalize_payload_normalization as _normalize_payload_normalization_impl,
)
from marketplace_installer.router_plugin_packager_payloads import (
    normalize_payload_overwrite_policy as _normalize_payload_overwrite_policy_impl,
)
from marketplace_installer.router_plugin_packager_payloads import (
    normalize_payload_paths as _normalize_payload_paths_impl,
)
from marketplace_installer.router_plugin_packager_payloads import (
    normalize_template_parameters as _normalize_template_parameters_impl,
)
from marketplace_installer.router_plugin_packager_payloads import (
    validate_payload_mode_specific_fields as _validate_payload_mode_specific_fields_impl,
)
from marketplace_installer.router_plugin_packager_payloads import (
    validate_payload_source_path as _validate_payload_source_path_impl,
)
from marketplace_installer.router_plugin_packager_outputs import (
    iter_glob_payload_files as _iter_glob_payload_files_impl,
)
from marketplace_installer.router_plugin_packager_outputs import (
    iter_native_interface_asset_paths as _iter_native_interface_asset_paths_impl,
)
from marketplace_installer.router_plugin_packager_outputs import (
    iter_payload_files as _iter_payload_files_impl,
)
from marketplace_installer.router_plugin_packager_outputs import (
    router_skill_content as _router_skill_content_impl,
)
from marketplace_installer.router_plugin_packager_outputs import (
    semantic_router_frontmatter_description as _semantic_router_frontmatter_description_impl,
)
from marketplace_installer.router_plugin_packager_outputs import (
    validate_pregenerated_provenance as _validate_pregenerated_provenance_impl,
)
from marketplace_installer.router_plugin_packager_receipts import (
    promotion_receipt_path as _promotion_receipt_path_impl,
)
from marketplace_installer.router_plugin_packager_receipts import (
    recover_interrupted_promotion_for_packager as _recover_interrupted_promotion_for_packager,
)
from marketplace_installer.router_plugin_packager_receipts import (
    remove_stale_paths_for_packager as _remove_stale_paths_for_packager,
)
from marketplace_installer.router_plugin_packager_receipts import (
    summarize_outputs_for_packager as _summarize_outputs_for_packager,
)
from marketplace_installer.router_plugin_packager_receipts import (
    validate_output_ownership_for_packager as _validate_output_ownership_for_packager,
)
from marketplace_installer.router_plugin_packager_receipts import (
    validate_existing_destination as _validate_existing_destination,
)
from marketplace_installer.router_plugin_packager_runtime import (
    build_parser_for_packager as _build_parser_for_packager,
)
from marketplace_installer.router_plugin_packager_runtime import (
    execute_packager_command_for_packager as _execute_packager_command_for_packager,
)
from marketplace_installer.router_plugin_packager_runtime import (
    run_packager_with_deps as _run_packager_with_deps,
)
from marketplace_installer.router_plugin_packager_runtime import (
    run_main_for_packager as _run_main_for_packager,
)
from marketplace_installer.router_plugin_packager_release import (
    add_proof_artifacts as _add_proof_artifacts_impl,
)
from marketplace_installer.router_plugin_packager_release import (
    build_output_state as _build_output_state_impl,
)
from marketplace_installer.router_plugin_packager_release import (
    build_receipt_payload as _build_receipt_payload_impl,
)
from marketplace_installer.router_plugin_packager_release import (
    build_normalized_request_summary as _build_normalized_request_summary_impl,
)
from marketplace_installer.router_plugin_packager_release import (
    build_state_payloads as _build_state_payloads_impl,
)
from marketplace_installer.router_plugin_packager_release import (
    emit_native_state_outputs as _emit_native_state_outputs_impl,
)
from marketplace_installer.router_plugin_packager_release import (
    emit_packaging_artifacts as _emit_packaging_artifacts_impl,
)
from marketplace_installer.router_plugin_packager_release import (
    finalize_release_state_for_packager as _finalize_release_state_for_packager,
)
from marketplace_installer.router_plugin_packager_release import (
    prepare_packaging_artifacts_for_packager as _prepare_packaging_artifacts_for_packager,
)
from marketplace_installer.router_plugin_packager_release import (
    find_payload_asset as _find_payload_asset,
)
from marketplace_installer.router_plugin_packager_release import (
    load_release_surface_payloads as _load_release_surface_payloads_impl,
)
from marketplace_installer.router_plugin_packager_release import (
    payload_asset_records as _payload_asset_records,
)
from marketplace_installer.router_plugin_packager_release import (
    validate_skill_release_consistency as _validate_skill_release_consistency_impl,
)
from marketplace_installer.router_plugin_packager_staging import (
    apply_generated_output_for_packager as _apply_generated_output_for_packager,
)
from marketplace_installer.router_plugin_packager_staging import (
    apply_staging_plan_for_validation as _apply_staging_plan_for_validation_impl,
)
from marketplace_installer.router_plugin_packager_staging import (
    promote_staged_output_for_packager as _promote_staged_output_for_packager,
)
from marketplace_installer.router_plugin_packager_staging import (
    set_nested_field as _set_nested_field,
)
from marketplace_installer.router_plugin_packager_staging import (
    staging_plan_payload as _staging_plan_payload,
)
from marketplace_installer.router_plugin_packager_staging import (
    validate_staged_marketplace_install as _validate_staged_marketplace_install_impl,
)
from marketplace_installer.router_plugin_packager_staging import (
    validate_staged_plugin_artifact as _validate_staged_plugin_artifact_impl,
)
from marketplace_installer.router_plugin_packager_staging import (
    write_output_tree_for_packager as _write_output_tree_for_packager,
)
from marketplace_installer.router_plugin_packager_source import (
    bootstrap_state_path as _bootstrap_state_path_impl,
)
from marketplace_installer.router_plugin_packager_source_projection import (
    verify_source_projection as _verify_source_projection,
)
from marketplace_installer.router_plugin_packager_source import (
    collect_skill_sources as _collect_skill_sources_impl,
)
from marketplace_installer.router_plugin_packager_source import (
    derive_source_root_from_skill_paths as _derive_source_root_from_skill_paths_impl,
)
from marketplace_installer.router_plugin_packager_source import (
    discover_source_root as _discover_source_root_impl,
)
from marketplace_installer.router_plugin_packager_source import (
    discover_visible_skill_paths as _discover_visible_skill_paths_impl,
)
from marketplace_installer.router_plugin_packager_source import (
    load_bootstrap_state as _load_bootstrap_state_impl,
)
from marketplace_installer.router_plugin_packager_source import (
    normalize_skill_paths as _normalize_skill_paths_impl,
)
from marketplace_installer.router_plugin_packager_text import (
    collect_semantic_summaries as _collect_semantic_summaries,
)
from marketplace_installer.router_plugin_packager_text import (
    collect_trigger_phrases as _collect_trigger_phrases,
)
from marketplace_installer.router_plugin_packager_text import (
    display_name_from_slug as _display_name_from_slug,
)
from marketplace_installer.router_plugin_packager_text import (
    join_human_list as _join_human_list,
)
from marketplace_installer.router_plugin_packager_text import (
    normalize_slug as _normalize_slug,
)
from marketplace_installer.router_plugin_packager_text import (
    normalize_whitespace as _normalize_whitespace,
)
from marketplace_installer.router_plugin_packager_text import (
    render_template_text as _render_template_text,
)
from marketplace_installer.router_plugin_packager_text import (
    strip_terminal_punctuation as _strip_terminal_punctuation,
)
from marketplace_installer.router_plugin_packager_text import (
    truncate_sentence as _truncate_sentence,
)


OWNERSHIP_CLASSES = frozenset(
    {
        "immutable-runtime-artifact",
        "replaceable-upgrade-artifact",
        "preserved-user-state-artifact",
        "owned-integration-artifact",
    }
)


@dataclass(frozen=True)
class Invocation:
    format_version: int
    source_format_version: int
    surface_mode: str
    input_mode: str
    plugin_kind: str
    plugin_kind_source: str
    source_root: str | None
    repository_root: Path
    output_root: Path
    skill_paths: list[str]
    cohort_catalog_path: str | None
    router_catalog_path: str | None
    cohort_id: str | None
    display_name_override: str | None
    plugin_slug_override: str | None
    publisher_slug_override: str | None
    surface_id_override: str | None
    branding_asset_overrides: dict[str, str]
    payload_assets: list[dict[str, Any]]
    runtime_compatibility_version: str | None
    migration_contract_version: str | None
    rollback_compatibility_hints: dict[str, Any] | None
    control_surface: dict[str, Any] | None
    owned_integration_root: str | None
    integration_points: list[dict[str, Any]]
    verification_targets: list[dict[str, Any]]
    version_override: str | None
    publication: dict[str, Any] | None
    mcp_packaging: dict[str, Any] | None
    source_manifest: str | None
    generated: dict[str, str] | None
    router_authority: dict[str, Any] | None
    source_projection_receipt: str | None


@dataclass(frozen=True)
class Router:
    router_slug: str
    description: str
    member_skill_ids: list[str]


@dataclass(frozen=True)
class PluginMetadata:
    publisher_slug: str
    plugin_slug: str
    display_name: str
    description: str
    author: dict[str, str]
    host_metadata: dict[str, Any]
    packaging_mode: str
    role: str | None
    branding_assets: dict[str, str]
    interface: dict[str, Any]


@dataclass(frozen=True)
class PayloadAsset:
    asset_id: str
    acquisition_mode: str
    source: str
    source_glob: str | None
    destination: str
    ownership_role: str
    ownership_class: str | None
    exclude: tuple[str, ...]
    normalization: str
    overwrite_policy: str
    provenance_path: str | None
    template_parameters: dict[str, Any]


@dataclass(frozen=True)
class NormalizedRequest:
    source_root: Path
    source_root_text: str
    repository_root: Path
    output_root: Path
    plugin_kind: str
    surface_id: str
    skill_ids: list[str]
    skill_paths: list[str]
    routers: list[Router]
    plugin_metadata: PluginMetadata
    decision_record: dict[str, Any]
    input_mode: str
    bootstrap_state_path: Path
    payload_assets: list[PayloadAsset]
    runtime_compatibility_version: str
    migration_contract_version: str | None
    rollback_compatibility_hints: dict[str, Any] | None
    control_surface: dict[str, Any] | None
    owned_integration_root: str | None
    integration_points: list[dict[str, Any]]
    verification_targets: list[dict[str, Any]]
    version_override: str | None
    publication_contract: "PublicationContract" | None
    mcp_packaging: "McpPackaging" | None


NATIVE_ROUTED_DECISION_STATE_NAME = "native-routed-decision-record.json"


@dataclass(frozen=True)
class McpReleaseSurface:
    registry_manifest_asset_id: str
    release_manifest_asset_id: str
    operation_registry_asset_id: str
    schema_bundle_asset_id: str


@dataclass(frozen=True)
class McpSkillReleaseContract:
    skill_id: str
    advertised_operation_ids: tuple[str, ...]
    required_phrases: tuple[str, ...]
    forbidden_phrases: tuple[str, ...]


@dataclass(frozen=True)
class McpStagingMutationRule:
    path: str
    field_path: str
    transform: str


@dataclass(frozen=True)
class McpStagingContract:
    format_version: int
    marketplace_name: str
    plugin_relpath: str
    version_suffix_source: str
    allowed_mutations: tuple[McpStagingMutationRule, ...]
    required_byte_preserved_paths: tuple[str, ...]


@dataclass(frozen=True)
class PublicationContract:
    category: str


@dataclass(frozen=True)
class McpPackaging:
    artifact_name: str
    description: str
    author_name: str
    interface: dict[str, Any]
    skills_path: str
    mcp_servers_path: str
    launch_contract: _McpLaunchContract
    release_surface: McpReleaseSurface
    skill_release_contract: McpSkillReleaseContract
    publication_contract: PublicationContract
    staging_contract: McpStagingContract


ALLOWED_SUPPORT_SUBTREES = ("references", "scripts", "templates", "assets")
EXCLUDED_SUPPORT_SEGMENTS = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".rumdl_cache",
    "graphify-out",
}
MCP_AUTHORITY_CONFIG_NAME = "router-plugin-config.json"
PROMOTION_RECEIPT_SUFFIX = ".router-plugin-packager-promotion.json"
PAYLOAD_MANIFEST_NAME = ".codex-plugin/payload-manifest.json"
RELEASE_METADATA_NAME = ".codex-plugin/release-metadata.json"
MCP_DESCRIPTOR_NAME = ".mcp.json"
STAGING_PLAN_NAME = ".codex-plugin/staging-plan.json"
BOOTSTRAP_STATE_NAME = "bootstrap-state.json"
BRANDING_SLOT_CANDIDATES = {
    "logo": ("logo", "icon"),
    "dark_logo": ("dark-logo", "dark_logo", "logo-dark", "darklogo"),
    "composer_icon": ("composer-icon", "composer_icon", "composericon", "icon"),
}


def _mcp_authority_identity(request: NormalizedRequest) -> dict[str, str] | None:
    return _mcp_authority_identity_impl(
        request,
        config_name=MCP_AUTHORITY_CONFIG_NAME,
        load_json=_load_json,
        resolve_local_path=_resolve_local_path,
        validate_relative_path=_validate_relative_path,
        hash_bytes=_hash_bytes,
        hash_tree=_hash_tree,
        toolchain_manifest_candidates=(
            Path(__file__).parent / "toolchain-manifest.json",
            Path(__file__).parent / "codex-packaging-toolchain-manifest.json",
        ),
    )


def _semantic_router_frontmatter_description(
    router: Router, modules: list[dict[str, str]]
) -> str:
    return _semantic_router_frontmatter_description_impl(
        router,
        modules,
        normalize_whitespace=_normalize_whitespace,
        collect_semantic_summaries=_collect_semantic_summaries,
        collect_trigger_phrases=_collect_trigger_phrases,
        join_human_list=_join_human_list,
        strip_terminal_punctuation=_strip_terminal_punctuation,
        truncate_sentence=_truncate_sentence,
    )


def _upgrade_v1_invocation(payload: dict[str, Any]) -> dict[str, Any]:
    """Translate the original direct-plugin invocation shape into v2 in memory."""
    upgraded = dict(payload)
    upgraded["format_version"] = 2
    upgraded["surface_mode"] = "legacy"
    return upgraded


def _parse_native_router_authority(
    payload: dict[str, Any], repository_root: Path
) -> dict[str, Any]:
    return _parse_native_router_authority_impl(
        payload,
        repository_root,
        ensure_string=_ensure_string,
        resolve_repository_root=_resolve_repository_root,
        validate_relative_path=_validate_relative_path,
    )


def _validate_native_invocation(payload: dict[str, Any], repository_root: Path) -> None:
    _validate_native_invocation_impl(
        payload,
        repository_root,
        ensure_string=_ensure_string,
        resolve_repository_root=_resolve_repository_root,
        validate_relative_path=_validate_relative_path,
        parse_native_router_authority_fn=_parse_native_router_authority_impl,
    )


def _parse_surface_mode(payload: dict[str, Any]) -> str:
    surface_mode = payload.get("surface_mode", "legacy")
    if surface_mode not in {"legacy", "native_routed"}:
        raise PackagerError(
            "invalid_surface_mode",
            "surface_mode must be legacy or native_routed",
            {"surface_mode": surface_mode},
        )
    return surface_mode


def _require_invocation_fields(payload: dict[str, Any], surface_mode: str) -> None:
    _require_invocation_fields_impl(payload, surface_mode)


def _parse_legacy_input_mode(payload: dict[str, Any]) -> str:
    return _parse_legacy_input_mode_impl(payload)


def _validate_legacy_mode_inputs(
    payload: dict[str, Any], input_mode: str, invocation_path: Path
) -> list[str]:
    return _validate_legacy_mode_inputs_impl(payload, input_mode, invocation_path)


def parse_invocation(invocation_path: Path, repo_root: Path) -> Invocation:
    return _parse_invocation_impl(
        invocation_path,
        repo_root,
        load_json=_load_json,
        upgrade_v1_invocation_fn=_upgrade_v1_invocation,
        collect_required_placeholders=_collect_required_placeholders,
        required_marker_prefix=_REQUIRED_MARKER_PREFIX,
        parse_surface_mode_fn=_parse_surface_mode,
        require_invocation_fields_fn=_require_invocation_fields,
        parse_legacy_input_mode_fn=_parse_legacy_input_mode,
        resolve_repository_root=_resolve_repository_root,
        resolve_local_path=_resolve_local_path,
        validate_native_invocation_fn=_validate_native_invocation,
        validate_legacy_mode_inputs_fn=_validate_legacy_mode_inputs,
        parse_plugin_kind_fn=_parse_plugin_kind,
        invocation_factory=Invocation,
        validate_relative_path=_validate_relative_path,
    )


def _parse_plugin_kind(payload: dict[str, Any]) -> tuple[str, str]:
    return _parse_plugin_kind_impl(payload)


def _normalize_payload_assets(
    invocation: Invocation, source_root: Path
) -> list[PayloadAsset]:
    del source_root
    return _normalize_payload_assets_impl(
        invocation,
        normalize_one_payload_asset_fn=_normalize_one_payload_asset,
        normalize_slug=_normalize_slug,
    )


def _normalize_one_payload_asset(
    invocation: Invocation, index: int, raw_asset: Any
) -> PayloadAsset:
    return _normalize_one_payload_asset_impl(
        invocation,
        index,
        raw_asset,
        payload_asset_factory=PayloadAsset,
        ensure_string=_ensure_string,
        normalize_slug=_normalize_slug,
        ownership_classes=OWNERSHIP_CLASSES,
        normalize_payload_acquisition_mode_fn=_normalize_payload_acquisition_mode,
        normalize_payload_paths_fn=_normalize_payload_paths,
        normalize_payload_exclude_fn=_normalize_payload_exclude,
        normalize_payload_normalization_fn=_normalize_payload_normalization,
        normalize_payload_overwrite_policy_fn=_normalize_payload_overwrite_policy,
        normalize_template_parameters_fn=_normalize_template_parameters,
        validate_payload_mode_specific_fields_fn=_validate_payload_mode_specific_fields,
        resolve_local_path=_resolve_local_path,
        validate_payload_source_path_fn=_validate_payload_source_path,
    )


def _normalize_payload_acquisition_mode(
    raw_asset: dict[str, Any], field_prefix: str
) -> str:
    return _normalize_payload_acquisition_mode_impl(
        raw_asset, field_prefix, ensure_string=_ensure_string
    )


def _normalize_payload_paths(
    raw_asset: dict[str, Any], field_prefix: str
) -> tuple[str, str | None, Path]:
    return _normalize_payload_paths_impl(
        raw_asset, field_prefix, ensure_string=_ensure_string
    )


def _normalize_payload_exclude(
    raw_asset: dict[str, Any], field_prefix: str
) -> list[str]:
    return _normalize_payload_exclude_impl(raw_asset, field_prefix)


def _normalize_payload_normalization(
    asset_id: str, raw_asset: dict[str, Any], field_prefix: str
) -> str:
    return _normalize_payload_normalization_impl(
        asset_id, raw_asset, field_prefix, ensure_string=_ensure_string
    )


def _normalize_payload_overwrite_policy(
    asset_id: str, raw_asset: dict[str, Any], field_prefix: str
) -> str:
    return _normalize_payload_overwrite_policy_impl(
        asset_id, raw_asset, field_prefix, ensure_string=_ensure_string
    )


def _normalize_template_parameters(
    raw_asset: dict[str, Any], field_prefix: str
) -> dict[str, Any]:
    return _normalize_template_parameters_impl(raw_asset, field_prefix)


def _validate_payload_mode_specific_fields(
    asset_id: str,
    acquisition_mode: str,
    provenance_path: str | None,
    template_parameters: dict[str, Any],
    source_glob: str | None,
) -> None:
    _validate_payload_mode_specific_fields_impl(
        asset_id,
        acquisition_mode,
        provenance_path,
        template_parameters,
        source_glob,
    )


def _validate_payload_source_path(
    invocation: Invocation,
    source_path: Path,
    source: str,
    source_glob: str | None,
    field_prefix: str,
    asset_id: str,
) -> None:
    _validate_payload_source_path_impl(
        invocation,
        source_path,
        source,
        source_glob,
        field_prefix,
        asset_id,
        validate_relative_path=_validate_relative_path,
    )


def _normalize_control_surface(
    raw_control_surface: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return _normalize_control_surface_impl(
        raw_control_surface, ensure_string=_ensure_string
    )


def _validate_control_surface_visibility(
    control_surface: dict[str, Any] | None, visible_skill_ids: set[str]
) -> None:
    _validate_control_surface_visibility_impl(control_surface, visible_skill_ids)


def _normalize_owned_integration_root(raw_root: str | None) -> str | None:
    return _normalize_owned_integration_root_impl(
        raw_root, ensure_string=_ensure_string
    )


def _normalize_metadata_records(
    raw_records: list[dict[str, Any]], field: str
) -> list[dict[str, Any]]:
    return _normalize_metadata_records_impl(raw_records, field)


def _validate_integration_points(
    integration_points: list[dict[str, Any]], owned_integration_root: str | None
) -> None:
    _validate_integration_points_impl(
        integration_points,
        owned_integration_root,
        ensure_string=_ensure_string,
    )


def _require_mapping(value: Any, *, field: str) -> dict[str, Any]:
    return _require_mapping_impl(value, field=field)


def _require_string_list(value: Any, *, field: str) -> list[str]:
    return _require_string_list_impl(value, field=field)


def _normalize_mcp_packaging(
    invocation: Invocation, skill_ids: list[str], payload_assets: list[PayloadAsset]
) -> McpPackaging | None:
    return _normalize_mcp_packaging_impl(
        invocation,
        skill_ids,
        payload_assets,
        require_mapping_fn=_require_mapping,
        ensure_string=_ensure_string,
        normalize_mcp_launch_contract_fn=_normalize_mcp_launch_contract_impl,
        normalize_mcp_release_surface_fn=_normalize_mcp_release_surface,
        normalize_mcp_skill_release_contract_fn=_normalize_mcp_skill_release_contract,
        normalize_publication_contract_fn=_normalize_publication_contract,
        normalize_mcp_staging_contract_fn=_normalize_mcp_staging_contract,
        mcp_packaging_factory=McpPackaging,
    )


def _normalize_publication_contract(
    payload: dict[str, Any], *, field: str
) -> PublicationContract:
    return _normalize_publication_contract_impl(
        payload,
        field=field,
        publication_contract_factory=PublicationContract,
        ensure_string=_ensure_string,
    )


def _resolve_publication_contract(
    invocation: Invocation, mcp_packaging: McpPackaging | None
) -> PublicationContract | None:
    return _resolve_publication_contract_impl(
        invocation,
        mcp_packaging,
        require_mapping_fn=_require_mapping,
        normalize_publication_contract_fn=_normalize_publication_contract,
    )


def _normalize_mcp_release_surface(
    payload: dict[str, Any], payload_assets: list[PayloadAsset]
) -> McpReleaseSurface:
    return _normalize_mcp_release_surface_impl(
        payload,
        payload_assets,
        ensure_string=_ensure_string,
        mcp_release_surface_factory=McpReleaseSurface,
    )


def _normalize_mcp_skill_release_contract(
    payload: dict[str, Any], skill_ids: list[str]
) -> McpSkillReleaseContract:
    return _normalize_mcp_skill_release_contract_impl(
        payload,
        skill_ids,
        ensure_string=_ensure_string,
        require_string_list_fn=_require_string_list,
        mcp_skill_release_contract_factory=McpSkillReleaseContract,
    )


def _normalize_mcp_staging_contract(payload: dict[str, Any]) -> McpStagingContract:
    return _normalize_mcp_staging_contract_impl(
        payload,
        ensure_string=_ensure_string,
        require_mapping_fn=_require_mapping,
        require_string_list_fn=_require_string_list,
        mcp_staging_mutation_rule_factory=McpStagingMutationRule,
        mcp_staging_contract_factory=McpStagingContract,
    )


def _discover_visible_skill_paths(source_root: Path) -> list[Path]:
    return _discover_visible_skill_paths_impl(source_root)


def _discover_source_root(repository_root: Path) -> tuple[Path, str]:
    return _discover_source_root_impl(repository_root)


def _derive_source_root_from_skill_paths(
    repository_root: Path, skill_paths: list[str]
) -> tuple[Path, str]:
    return _derive_source_root_from_skill_paths_impl(repository_root, skill_paths)


def _normalize_skill_paths(
    invocation: Invocation, source_root: Path
) -> tuple[list[str], list[str]]:
    return _normalize_skill_paths_impl(
        invocation,
        source_root,
        discover_visible_skill_paths_fn=_discover_visible_skill_paths,
        resolve_local_path=_resolve_local_path,
        validate_relative_path=_validate_relative_path,
        normalize_slug=_normalize_slug,
    )


def _resolve_catalog_paths(invocation: Invocation) -> tuple[Path, Path]:
    return _resolve_catalog_paths_impl(
        invocation,
        resolve_local_path=_resolve_local_path,
        validate_relative_path=_validate_relative_path,
    )


def _load_catalog_lists(
    cohort_catalog_path: Path, router_catalog_path: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _load_catalog_lists_impl(
        cohort_catalog_path,
        router_catalog_path,
        load_yaml=_load_yaml,
        collect_required_placeholders=_collect_required_placeholders,
        required_marker_prefix=_REQUIRED_MARKER_PREFIX,
    )


def _select_catalog_cohort(
    invocation: Invocation,
    cohort_entries: list[dict[str, Any]],
    cohort_catalog_path: Path,
) -> tuple[str, dict[str, Any]]:
    return _select_catalog_cohort_impl(
        invocation,
        cohort_entries,
        cohort_catalog_path,
        normalize_slug=_normalize_slug,
    )


def _validate_catalog_skill_paths(
    invocation: Invocation, source_root: Path, skill_paths: list[str]
) -> None:
    _validate_catalog_skill_paths_impl(
        invocation,
        source_root,
        skill_paths,
        normalize_skill_paths=_normalize_skill_paths,
    )


def _routers_for_catalog_cohort(
    invocation: Invocation,
    cohort_id: str,
    skill_ids: list[str],
    router_entries: list[dict[str, Any]],
    router_catalog_path: Path,
) -> list[Router]:
    return _routers_for_catalog_cohort_impl(
        invocation,
        cohort_id,
        skill_ids,
        router_entries,
        router_catalog_path,
        normalize_slug=_normalize_slug,
        router_factory=Router,
    )


def _catalog_selection(
    invocation: Invocation, source_root: Path
) -> tuple[CatalogSelection, dict[str, Any]]:
    return _catalog_selection_impl(
        invocation,
        source_root,
        resolve_catalog_paths_fn=_resolve_catalog_paths,
        load_catalog_lists_fn=_load_catalog_lists,
        select_catalog_cohort_fn=_select_catalog_cohort,
        validate_catalog_skill_paths_fn=_validate_catalog_skill_paths,
        routers_for_catalog_cohort_fn=_routers_for_catalog_cohort,
    )


def _discover_branding_assets(
    repository_root: Path,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    return _discover_branding_assets_impl(
        repository_root,
        branding_slot_candidates=BRANDING_SLOT_CANDIDATES,
        has_hidden_path_segment=_has_hidden_path_segment,
        normalize_slug=_normalize_slug,
    )


def _bootstrap_state_path(repository_root: Path) -> Path:
    return _bootstrap_state_path_impl(
        repository_root,
        decision_state_dir=_DECISION_STATE_DIR,
        bootstrap_state_name=BOOTSTRAP_STATE_NAME,
    )


def _load_bootstrap_state(repository_root: Path) -> dict[str, Any] | None:
    return _load_bootstrap_state_impl(
        repository_root,
        bootstrap_state_path_fn=_bootstrap_state_path,
        validate_existing_destination=_validate_existing_destination,
        load_json=_load_json,
    )


def _resolve_branding_assets(
    invocation: Invocation,
    repository_root: Path,
    bootstrap_state: dict[str, Any] | None,
) -> tuple[dict[str, str], dict[str, Any]]:
    return _resolve_branding_assets_impl(
        invocation,
        repository_root,
        bootstrap_state,
        discover_branding_assets_fn=_discover_branding_assets,
        validate_relative_path=_validate_relative_path,
    )


def _normalize_plugin_metadata(
    invocation: Invocation,
    repository_root: Path,
    bootstrap_state: dict[str, Any] | None,
    *,
    plugin_slug_default: str | None = None,
    display_name_default: str | None = None,
    role_default: str | None = None,
) -> tuple[PluginMetadata, dict[str, Any]]:
    return _normalize_plugin_metadata_impl(
        invocation,
        repository_root,
        bootstrap_state,
        resolve_branding_assets_fn=_resolve_branding_assets,
        normalize_slug=_normalize_slug,
        display_name_from_slug=_display_name_from_slug,
        load_source_plugin_manifest=_load_source_plugin_manifest,
        plugin_metadata_factory=PluginMetadata,
        plugin_slug_default=plugin_slug_default,
        display_name_default=display_name_default,
        role_default=role_default,
    )


def _validate_native_output_isolation(
    output_root: Path, source_plugin_root: Path, member_roots: list[Path]
) -> None:
    _validate_native_output_isolation_impl(
        output_root, source_plugin_root, member_roots
    )


def _native_generated_tree_digest_from_outputs(outputs: dict[str, bytes]) -> str:
    return _native_generated_tree_digest_from_outputs_impl(
        outputs,
        receipt_name=_RECEIPT_NAME,
        hash_bytes=_hash_bytes,
        hash_text=_hash_text,
    )


def _native_generated_tree_digest_from_disk(output_root: Path) -> str:
    return _native_generated_tree_digest_from_disk_impl(
        output_root,
        receipt_name=_RECEIPT_NAME,
        hash_bytes=_hash_bytes,
        hash_text=_hash_text,
    )


def _normalize_native_plugin_metadata(  # noqa: C901
    invocation: Invocation,
    source_manifest: dict[str, Any],
) -> tuple[PluginMetadata, dict[str, Any]]:
    return _normalize_native_plugin_metadata_impl(
        invocation,
        source_manifest,
        plugin_metadata_factory=PluginMetadata,
        ensure_string=_ensure_string,
        normalize_slug=_normalize_slug,
        display_name_from_slug=_display_name_from_slug,
    )


def _native_receipt_contract(request: NormalizedRequest) -> dict[str, Any]:
    return _native_receipt_contract_impl(request)


def _load_native_router_catalog(catalog_path: Path) -> list[dict[str, Any]]:
    return _load_native_router_catalog_impl(
        catalog_path,
        load_yaml=_load_yaml,
        collect_required_placeholders=_collect_required_placeholders,
        required_marker_prefix=_REQUIRED_MARKER_PREFIX,
    )


def _normalize_native_router_catalog_authority(  # noqa: C901
    invocation: Invocation,
    source_plugin_root: Path,
    source_skills_root: Path,
    authority: dict[str, Any],
) -> tuple[list[str], list[str], list[Router], list[Path]]:
    return _normalize_native_router_catalog_authority_impl(
        invocation,
        source_plugin_root,
        source_skills_root,
        authority,
        ensure_string=_ensure_string,
        normalize_slug=_normalize_slug,
        resolve_repository_root=_resolve_repository_root,
        validate_relative_path=_validate_relative_path,
        load_native_router_catalog_fn=_load_native_router_catalog,
        router_factory=Router,
        discover_visible_skill_paths_fn=_discover_visible_skill_paths,
    )


def _normalize_native_request(  # noqa: C901
    invocation: Invocation, repo_root: Path
) -> NormalizedRequest:
    return _normalize_native_request_with_packager_deps(
        invocation,
        repo_root,
        normalize_native_request_fn=_normalize_native_request_impl,
        ensure_string=_ensure_string,
        normalize_slug=_normalize_slug,
        resolve_repository_root=_resolve_repository_root,
        validate_relative_path=_validate_relative_path,
        load_source_plugin_manifest=_load_source_plugin_manifest,
        normalize_native_router_catalog_authority_fn=_normalize_native_router_catalog_authority,
        discover_visible_skill_paths_fn=_discover_visible_skill_paths,
        validate_native_output_isolation_fn=_validate_native_output_isolation,
        normalize_native_plugin_metadata_fn=_normalize_native_plugin_metadata,
        resolve_publication_contract_fn=_resolve_publication_contract,
        normalize_control_surface_fn=_normalize_control_surface,
        validate_control_surface_visibility_fn=_validate_control_surface_visibility,
        normalize_owned_integration_root_fn=_normalize_owned_integration_root,
        normalize_metadata_records_fn=_normalize_metadata_records,
        validate_integration_points_fn=_validate_integration_points,
        normalize_payload_assets_fn=_normalize_payload_assets,
        normalized_request_factory=NormalizedRequest,
        router_factory=Router,
    )


def _normalize_request(invocation: Invocation, repo_root: Path) -> NormalizedRequest:
    return _normalize_request_with_packager_deps(
        invocation,
        repo_root,
        normalize_request_for_packager_fn=_normalize_request_for_packager,
        normalize_native_request_fn=_normalize_native_request,
        discover_source_root_fn=_discover_source_root,
        derive_source_root_from_skill_paths_fn=_derive_source_root_from_skill_paths,
        validate_relative_path_fn=_validate_relative_path,
        load_bootstrap_state_fn=_load_bootstrap_state,
        catalog_selection_fn=_catalog_selection,
        normalize_skill_paths_fn=_normalize_skill_paths,
        router_factory=Router,
        normalize_plugin_metadata_fn=_normalize_plugin_metadata,
        normalize_slug_fn=_normalize_slug,
        normalize_payload_assets_fn=_normalize_payload_assets,
        normalize_mcp_packaging_fn=_normalize_mcp_packaging,
        resolve_publication_contract_fn=_resolve_publication_contract,
        replace_fn=replace,
        normalize_control_surface_fn=_normalize_control_surface,
        validate_control_surface_visibility_fn=_validate_control_surface_visibility,
        normalize_owned_integration_root_fn=_normalize_owned_integration_root,
        normalize_metadata_records_fn=_normalize_metadata_records,
        validate_integration_points_fn=_validate_integration_points,
        bootstrap_state_path_fn=_bootstrap_state_path,
        normalized_request_factory=NormalizedRequest,
    )


def _collect_skill_sources(  # noqa: C901
    request: NormalizedRequest,
) -> dict[str, dict[str, Any]]:
    return _collect_skill_sources_impl(
        request,
        resolve_local_path=_resolve_local_path,
        normalize_slug=_normalize_slug,
        parse_markdown_frontmatter=_parse_markdown_frontmatter,
        allowed_support_subtrees=ALLOWED_SUPPORT_SUBTREES,
        excluded_support_segments=EXCLUDED_SUPPORT_SEGMENTS,
    )


def _iter_native_interface_asset_paths(request: NormalizedRequest) -> list[str]:
    return _iter_native_interface_asset_paths_impl(request)


def _router_skill_content(
    router: Router,
    modules: list[dict[str, str]],
    frontmatter_description: str,
) -> str:
    return _router_skill_content_impl(router, modules, frontmatter_description)


def _validate_pregenerated_provenance(
    request: NormalizedRequest, asset: PayloadAsset, source_path: Path
) -> dict[str, Any]:
    return _validate_pregenerated_provenance_impl(
        request,
        asset,
        source_path,
        resolve_local_path=_resolve_local_path,
        validate_relative_path=_validate_relative_path,
        load_json=_load_json,
        hash_tree=_hash_tree,
        hash_bytes=_hash_bytes,
    )


def _iter_glob_payload_files(
    source_path: Path, asset: PayloadAsset
) -> list[tuple[Path, Path]]:
    return _iter_glob_payload_files_impl(source_path, asset)


def _iter_payload_files(
    request: NormalizedRequest, asset: PayloadAsset
) -> list[tuple[Path, Path]]:
    return _iter_payload_files_impl(
        request,
        asset,
        resolve_local_path=_resolve_local_path,
        iter_glob_payload_files_fn=_iter_glob_payload_files,
    )


def _add_router_outputs(
    request: NormalizedRequest,
    skills: dict[str, dict[str, Any]],
    add_output: Any,
    record_payload_entry: Any,
) -> None:
    _add_router_outputs_impl(
        request,
        skills,
        add_output,
        record_payload_entry,
        semantic_router_frontmatter_description_fn=_semantic_router_frontmatter_description,
        router_skill_content_fn=_router_skill_content,
    )


def _add_direct_skill_outputs(
    request: NormalizedRequest,
    skills: dict[str, dict[str, Any]],
    add_output: Any,
    record_payload_entry: Any,
) -> None:
    _add_direct_skill_outputs_impl(
        request,
        skills,
        add_output,
        record_payload_entry,
        hash_bytes=_hash_bytes,
    )


def _add_module_outputs(
    request: NormalizedRequest,
    skills: dict[str, dict[str, Any]],
    add_output: Any,
    record_payload_entry: Any,
) -> None:
    _add_module_outputs_impl(
        request,
        skills,
        add_output,
        record_payload_entry,
        hash_bytes=_hash_bytes,
    )


def _add_branding_outputs(
    request: NormalizedRequest,
    add_output: Any,
    record_payload_entry: Any,
) -> dict[str, str]:
    return _add_branding_outputs_impl(request, add_output, record_payload_entry)


def _add_native_interface_asset_outputs(
    request: NormalizedRequest,
    add_output: Any,
    record_payload_entry: Any,
) -> None:
    _add_native_interface_asset_outputs_impl(
        request,
        add_output,
        record_payload_entry,
        iter_native_interface_asset_paths_fn=_iter_native_interface_asset_paths,
        validate_relative_path=_validate_relative_path,
        hash_bytes=_hash_bytes,
    )


def _add_payload_asset_outputs(
    request: NormalizedRequest,
    add_output: Any,
    record_payload_entry: Any,
) -> None:
    _add_payload_asset_outputs_impl(
        request,
        add_output,
        record_payload_entry,
        resolve_local_path=_resolve_local_path,
        validate_pregenerated_provenance_fn=_validate_pregenerated_provenance,
        render_template_text=_render_template_text,
        hash_bytes=_hash_bytes,
        iter_payload_files_fn=_iter_payload_files,
    )


def _validate_mcp_descriptor_round_trip(contract: _McpLaunchContract) -> None:
    _validate_mcp_descriptor_round_trip_impl(
        contract, mcp_descriptor_payload_fn=_mcp_descriptor_payload
    )


def _load_release_surface_payloads(
    request: NormalizedRequest,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _load_release_surface_payloads_impl(
        request,
        load_json=_load_json,
        resolve_local_path=_resolve_local_path,
        find_payload_asset_fn=_find_payload_asset,
    )


def _validate_skill_release_consistency(
    request: NormalizedRequest, skills: dict[str, dict[str, Any]]
) -> None:
    _validate_skill_release_consistency_impl(
        request,
        skills,
        load_release_surface_payloads_fn=_load_release_surface_payloads,
        normalize_whitespace=_normalize_whitespace,
    )


def apply_staging_plan_for_validation(
    source_root: Path, staging_plan: dict[str, Any], staged_root: Path, cachebuster: str
) -> dict[str, Any]:
    return _apply_staging_plan_for_validation_impl(
        source_root,
        staging_plan,
        staged_root,
        cachebuster,
        validate_staged_plugin_artifact_fn=_validate_staged_plugin_artifact,
        load_json_fn=_load_json,
        set_nested_field_fn=_set_nested_field,
        write_json_fn=_write_json,
    )


def _validate_staged_plugin_artifact(plugin_root: Path) -> tuple[str, str]:
    return _validate_staged_plugin_artifact_impl(
        plugin_root,
        load_json_fn=_load_json,
        ensure_string_fn=_ensure_string,
        normalize_mcp_environment_fn=_normalize_mcp_environment_impl,
        mcp_descriptor_name=MCP_DESCRIPTOR_NAME,
    )


def validate_staged_marketplace_install(
    source_root: Path,
    staging_plan: dict[str, Any],
    sandbox_root: Path,
    cachebuster: str,
) -> dict[str, Any]:
    return _validate_staged_marketplace_install_impl(
        source_root,
        staging_plan,
        sandbox_root,
        cachebuster,
        validate_staged_plugin_artifact_fn=_validate_staged_plugin_artifact,
        apply_staging_plan_for_validation_fn=apply_staging_plan_for_validation,
        ensure_string_fn=_ensure_string,
        write_json_fn=_write_json,
        hash_tree_fn=_hash_tree,
    )


def _add_proof_artifacts(
    request: NormalizedRequest,
    payload_manifest_entries: list[dict[str, Any]],
    add_output: Any,
    record_payload_entry: Any,
) -> tuple[str, dict[str, Any]]:
    return _add_proof_artifacts_impl(
        request,
        payload_manifest_entries,
        add_output,
        record_payload_entry,
        payload_manifest_name=PAYLOAD_MANIFEST_NAME,
        release_metadata_name=RELEASE_METADATA_NAME,
        hash_text=_hash_text,
    )


_BUILD_OUTPUTS_PACKAGER_DEPS = BuildOutputsPackagerDeps(
    build_outputs_for_packager_fn=_build_outputs_for_packager,
    collect_skill_sources_fn=_collect_skill_sources,
    validate_skill_release_consistency_fn=_validate_skill_release_consistency,
    build_record_payload_entry_for_packager_fn=_build_record_payload_entry_for_packager,
    populate_primary_outputs_for_packager_fn=_populate_primary_outputs_for_packager,
    prepare_packaging_artifacts_for_packager_fn=_prepare_packaging_artifacts_for_packager,
    finalize_release_state_for_packager_fn=_finalize_release_state_for_packager,
    add_direct_skill_outputs_fn=_add_direct_skill_outputs,
    add_router_outputs_fn=_add_router_outputs,
    add_module_outputs_fn=_add_module_outputs,
    add_native_interface_asset_outputs_fn=_add_native_interface_asset_outputs,
    add_branding_outputs_fn=_add_branding_outputs,
    add_payload_asset_outputs_fn=_add_payload_asset_outputs,
    compute_version_fn=_compute_version_impl,
    plugin_id_fn=_plugin_id,
    emit_packaging_artifacts_fn=_emit_packaging_artifacts_impl,
    plugin_manifest_fn=_plugin_manifest,
    validate_mcp_descriptor_round_trip_fn=_validate_mcp_descriptor_round_trip,
    mcp_descriptor_payload_fn=_mcp_descriptor_payload,
    staging_plan_payload_fn=_staging_plan_payload,
    add_proof_artifacts_fn=_add_proof_artifacts,
    native_generated_tree_digest_from_outputs_fn=_native_generated_tree_digest_from_outputs,
    build_receipt_payload_fn=_build_receipt_payload_impl,
    build_state_payloads_fn=_build_state_payloads_impl,
    emit_native_state_outputs_fn=_emit_native_state_outputs_impl,
    build_normalized_request_summary_fn=_build_normalized_request_summary_impl,
    build_output_state_fn=_build_output_state_impl,
    payload_asset_records_fn=_payload_asset_records,
    mcp_launch_contract_provenance_fn=_mcp_launch_contract_provenance,
    mcp_authority_identity_fn=_mcp_authority_identity,
    native_receipt_contract_fn=_native_receipt_contract,
    publication_metadata_name=_PUBLICATION_METADATA_NAME,
    mcp_descriptor_name=MCP_DESCRIPTOR_NAME,
    staging_plan_name=STAGING_PLAN_NAME,
    receipt_name=_RECEIPT_NAME,
    decision_state_dir=_DECISION_STATE_DIR,
    native_routed_decision_state_name=NATIVE_ROUTED_DECISION_STATE_NAME,
    native_routed_bootstrap_state_name=NATIVE_ROUTED_BOOTSTRAP_STATE_NAME,
    normalize_slug=_normalize_slug,
    hash_bytes=_hash_bytes,
    hash_text=_hash_text,
    canonical_json_bytes=_canonical_json_bytes,
)


def _build_outputs(  # noqa: C901
    request: NormalizedRequest,
) -> tuple[dict[str, bytes], dict[str, int], dict[str, Any], str]:
    return _build_outputs_with_packager_deps(
        request,
        deps=_BUILD_OUTPUTS_PACKAGER_DEPS,
    )


def run(command: str, invocation_path: Path, repo_root: Path) -> dict[str, Any]:
    return _run_packager_with_deps(
        command,
        invocation_path,
        repo_root,
        parse_invocation_fn=parse_invocation,
        normalize_request_fn=_normalize_request,
        execute_packager_command_for_packager_fn=_execute_packager_command_for_packager,
        receipt_name=_RECEIPT_NAME,
        suffix=PROMOTION_RECEIPT_SUFFIX,
        native_receipt_format=NATIVE_ROUTED_RECEIPT_FORMAT,
        load_json_fn=_load_json,
        write_json_fn=_write_json,
        validate_existing_destination_fn=_validate_existing_destination,
        build_outputs_fn=_build_outputs,
        summarize_outputs_for_packager_fn=_summarize_outputs_for_packager,
        recover_interrupted_promotion_for_packager_fn=_recover_interrupted_promotion_for_packager,
        apply_generated_output_for_packager_fn=_apply_generated_output_for_packager,
        native_receipt_contract_fn=_native_receipt_contract,
        native_generated_tree_digest_from_disk_fn=_native_generated_tree_digest_from_disk,
        os_module=os,
        shutil_module=shutil,
        uuid_module=uuid,
        validate_output_ownership_for_packager_fn=_validate_output_ownership_for_packager,
        write_output_tree_for_packager_fn=_write_output_tree_for_packager,
        remove_stale_paths_for_packager_fn=_remove_stale_paths_for_packager,
        promote_staged_output_for_packager_fn=_promote_staged_output_for_packager,
        promotion_receipt_path_fn=_promotion_receipt_path_impl,
        verify_source_projection_fn=_verify_source_projection,
        load_json_bytes_fn=_load_json_bytes,
        hash_bytes_fn=_hash_bytes,
    )


def build_parser() -> argparse.ArgumentParser:
    return _build_parser_for_packager(description=__doc__, default_repo_root=Path.cwd())


def _print_error(error: PackagerError, output_format: str) -> None:
    _print_error_payload(error.payload(), output_format)


def main(argv: list[str] | None = None) -> int:
    return _run_main_for_packager(
        argv,
        build_parser_fn=_build_parser_for_packager,
        run_fn=run,
        print_payload_fn=_print_payload,
        print_error_payload_fn=_print_error_payload,
        packager_error_type=PackagerError,
        description=__doc__,
        default_repo_root=Path.cwd(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
