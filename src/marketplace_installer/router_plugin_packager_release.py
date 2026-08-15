from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


def find_payload_asset(request: Any, asset_id: str) -> Any:
    for asset in request.payload_assets:
        if asset.asset_id == asset_id:
            return asset
    raise PackagerError(
        "missing_payload_asset",
        "payload asset id does not exist",
        {"asset_id": asset_id},
    )


def load_release_surface_payloads(
    request: Any, *, load_json: Any, resolve_local_path: Any, find_payload_asset_fn: Any
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    assert request.mcp_packaging is not None
    release_surface = request.mcp_packaging.release_surface
    registry_manifest = load_json(
        resolve_local_path(
            request.repository_root,
            find_payload_asset_fn(
                request, release_surface.registry_manifest_asset_id
            ).source,
        )
    )
    release_manifest = load_json(
        resolve_local_path(
            request.repository_root,
            find_payload_asset_fn(
                request, release_surface.release_manifest_asset_id
            ).source,
        )
    )
    operation_registry = load_json(
        resolve_local_path(
            request.repository_root,
            find_payload_asset_fn(
                request, release_surface.operation_registry_asset_id
            ).source,
        )
    )
    return registry_manifest, release_manifest, operation_registry


def validate_v3_release_package(
    release_package: dict[str, Any], launch_contract: Any
) -> None:
    from marketplace_installer.router_plugin_packager_mcp_normalization import (
        normalize_package_version,
        validate_distribution_name,
    )

    try:
        release_name = validate_distribution_name(
            release_package.get("name"), field="release_manifest.package.name"
        )
        release_version = (
            normalize_package_version(
                release_package.get("version"),
                field="release_manifest.package.version",
            )
            if launch_contract.package_version
            else None
        )
    except PackagerError as exc:
        raise PackagerError(
            "mcp_launch_release_mismatch",
            "release manifest has an invalid package identity for schema version 3",
            exc.details,
        ) from exc
    if release_name != launch_contract.package_name or (
        launch_contract.package_version
        and release_version != launch_contract.package_version
    ):
        raise PackagerError(
            "mcp_launch_release_mismatch",
            "launch contract does not match the governed release package version",
            {
                "launch_package_name": launch_contract.package_name,
                "launch_package_version": launch_contract.package_version,
                "release_package": release_package,
            },
        )


def validate_release_package_identity(
    release_package: dict[str, Any], launch_contract: Any
) -> None:
    if (
        release_package.get("name") != launch_contract.package_name
        or release_package.get("entry_point") != launch_contract.entrypoint
    ):
        raise PackagerError(
            "mcp_launch_release_mismatch",
            "launch contract does not match the governed release package identity",
            {
                "launch_package_name": launch_contract.package_name,
                "launch_entrypoint": launch_contract.entrypoint,
                "release_package": release_package,
            },
        )
    if launch_contract.schema_version == 3:
        validate_v3_release_package(release_package, launch_contract)


def validate_skill_release_consistency(
    request: Any,
    skills: dict[str, dict[str, Any]],
    *,
    load_release_surface_payloads_fn: Any,
    normalize_whitespace: Any,
) -> None:
    if request.mcp_packaging is None:
        return
    contract = request.mcp_packaging.skill_release_contract
    _, release_manifest, operation_registry = load_release_surface_payloads_fn(request)
    release_package = release_manifest.get("package")
    if not isinstance(release_package, dict):
        raise PackagerError(
            "mcp_launch_release_mismatch",
            "release manifest must declare the package-backed launch identity",
            {"field": "package"},
        )
    launch_contract = request.mcp_packaging.launch_contract
    validate_release_package_identity(release_package, launch_contract)
    selected_operation_ids = set(release_manifest.get("selected_operation_ids", []))
    operations = operation_registry.get("operations", [])
    operation_ids = {
        operation.get("operation_id")
        for operation in operations
        if isinstance(operation, dict)
        and isinstance(operation.get("operation_id"), str)
    }
    skill_file = Path(skills[contract.skill_id]["skill_file"])
    skill_text = skill_file.read_text(encoding="utf-8")
    normalized_skill_text = normalize_whitespace(skill_text).casefold()
    for operation_id in contract.advertised_operation_ids:
        if (
            operation_id not in operation_ids
            or operation_id not in selected_operation_ids
        ):
            raise PackagerError(
                "mcp_skill_release_mismatch",
                "skill contract advertises an operation absent from the selected release surface",
                {"skill_id": contract.skill_id, "operation_id": operation_id},
            )
    for phrase in contract.required_phrases:
        if normalize_whitespace(phrase).casefold() not in normalized_skill_text:
            raise PackagerError(
                "mcp_skill_release_mismatch",
                "skill contract is missing a required release-surface phrase",
                {"skill_id": contract.skill_id, "phrase": phrase},
            )
    for phrase in contract.forbidden_phrases:
        if normalize_whitespace(phrase).casefold() in normalized_skill_text:
            raise PackagerError(
                "mcp_skill_release_mismatch",
                "skill contract contains a forbidden release-surface phrase",
                {"skill_id": contract.skill_id, "phrase": phrase},
            )


def add_proof_artifacts(
    request: Any,
    payload_manifest_entries: list[dict[str, Any]],
    add_output: Any,
    record_payload_entry: Any,
    *,
    payload_manifest_name: str,
    release_metadata_name: str,
    hash_text: Any,
) -> tuple[str, dict[str, Any]]:
    sorted_entries = sorted(
        payload_manifest_entries,
        key=lambda item: item["relative_output_path"],
    )
    payload_fingerprint_seed = json.dumps(
        [
            {
                "path": entry["relative_output_path"],
                "hash": entry["content_hash"],
                "mode": entry["acquisition_mode"],
            }
            for entry in sorted_entries
        ],
        sort_keys=True,
    )
    payload_fingerprint = hash_text(payload_fingerprint_seed)
    payload_manifest_rel = Path(payload_manifest_name)
    payload_manifest_payload = {
        "format_version": 1,
        "payload_fingerprint": payload_fingerprint,
        "packager_format_version": 1,
        "entries": sorted_entries,
    }
    payload_manifest_bytes = (
        json.dumps(payload_manifest_payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    add_output(
        payload_manifest_rel,
        payload_manifest_bytes,
        {
            **record_payload_entry(
                relative_path=payload_manifest_rel,
                content=payload_manifest_bytes,
                source_reference="generated:payload-manifest",
                acquisition_mode="generated",
                ownership_role="payload-manifest",
                ownership_class=None,
                transform_kind="payload-manifest",
            ),
            "payload_fingerprint": payload_fingerprint,
        },
    )
    release_metadata_rel = Path(release_metadata_name)
    release_metadata_payload = {
        "format_version": 1,
        "packager_format_version": 1,
        "payload_fingerprint": payload_fingerprint,
        "runtime_compatibility_version": request.runtime_compatibility_version,
        "migration_contract_version": request.migration_contract_version,
        "rollback_compatibility_hints": request.rollback_compatibility_hints,
        "control_surface": request.control_surface,
        "owned_integration_root": request.owned_integration_root,
        "integration_points": request.integration_points,
        "verification_targets": request.verification_targets,
    }
    release_metadata_bytes = (
        json.dumps(release_metadata_payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    add_output(
        release_metadata_rel,
        release_metadata_bytes,
        {
            **record_payload_entry(
                relative_path=release_metadata_rel,
                content=release_metadata_bytes,
                source_reference="generated:release-metadata",
                acquisition_mode="generated",
                ownership_role="release-metadata",
                ownership_class=None,
                transform_kind="release-metadata",
            ),
            "payload_fingerprint": payload_fingerprint,
        },
    )
    return payload_fingerprint, payload_manifest_payload


def payload_asset_records(
    request: Any, *, include_extended_fields: bool
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for asset in request.payload_assets:
        record = {
            "id": asset.asset_id,
            "acquisition_mode": asset.acquisition_mode,
            "source": asset.source,
            "source_glob": asset.source_glob,
            "destination": asset.destination,
            "ownership_role": asset.ownership_role,
            "ownership_class": asset.ownership_class,
            "provenance_path": asset.provenance_path,
            "template_parameters": asset.template_parameters,
        }
        if include_extended_fields:
            record["exclude"] = list(asset.exclude)
            record["normalization"] = asset.normalization
            record["overwrite_policy"] = asset.overwrite_policy
        records.append(record)
    return records


def build_receipt_payload(
    request: Any,
    *,
    plugin_id: str,
    version: str,
    payload_fingerprint: str,
    generated_paths: list[str],
    entries: list[dict[str, Any]],
    receipt_name: str,
    mcp_descriptor_bytes_sha256: str | None,
    mcp_descriptor_canonical_sha256: str | None,
    native_generated_tree_digest: str | None,
    mcp_launch_contract_provenance_fn: Any,
    mcp_authority_identity_fn: Any,
    native_receipt_contract_fn: Any,
) -> dict[str, Any]:
    payload = {
        "format_version": 1,
        "surface_id": request.surface_id,
        "plugin_id": plugin_id,
        "version": version,
        "packaging_mode": request.plugin_metadata.packaging_mode,
        "payload_fingerprint": payload_fingerprint,
        "generated_paths": generated_paths + [receipt_name],
        "entries": entries,
        "normalized_request": {
            "input_mode": request.input_mode,
            "plugin_kind": request.plugin_kind,
            "surface_id": request.surface_id,
            "skill_ids": request.skill_ids,
            "decision_record": request.decision_record,
            "version_override": request.version_override,
            "publication": (
                {"category": request.publication_contract.category}
                if request.publication_contract is not None
                else None
            ),
            "payload_assets": payload_asset_records(
                request, include_extended_fields=False
            ),
        },
    }
    if request.mcp_packaging is not None:
        payload["normalized_request"]["mcp_packaging"] = {
            "launch_contract": mcp_launch_contract_provenance_fn(
                request.mcp_packaging.launch_contract
            ),
            "mcp_descriptor_bytes_sha256": mcp_descriptor_bytes_sha256,
            "mcp_descriptor_canonical_sha256": mcp_descriptor_canonical_sha256,
        }
        authority_identity = mcp_authority_identity_fn(request)
        if authority_identity is not None:
            payload["mcp_authority"] = authority_identity
    if request.input_mode == "native_routed":
        payload["native_routed"] = {
            **native_receipt_contract_fn(request),
            "generated_tree_digest": native_generated_tree_digest,
        }
    return payload


def build_state_payloads(
    request: Any,
    *,
    plugin_id: str,
    version: str,
    decision_state_dir: str,
    native_routed_decision_state_name: str,
    native_routed_bootstrap_state_name: str,
    normalize_slug: Any,
) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    if request.input_mode == "native_routed":
        decision_state_path = (
            request.output_root / ".codex-plugin" / native_routed_decision_state_name
        )
        bootstrap_state_path = (
            request.output_root / ".codex-plugin" / native_routed_bootstrap_state_name
        )
    else:
        decision_state_path = (
            request.repository_root
            / decision_state_dir
            / f"{normalize_slug(request.surface_id)}.json"
        )
        bootstrap_state_path = request.bootstrap_state_path
    decision_state_payload = {
        "format_version": 1,
        "input_mode": request.input_mode,
        "plugin_kind": request.plugin_kind,
        "surface_id": request.surface_id,
        "plugin_id": plugin_id,
        "display_name": request.plugin_metadata.display_name,
        "source_root": request.source_root_text,
        "repository_root": str(request.repository_root),
        "output_root": str(request.output_root),
        "version": version,
        "packaging_mode": request.plugin_metadata.packaging_mode,
        "skill_ids": request.skill_ids,
        "payload_assets": payload_asset_records(request, include_extended_fields=False),
        "version_override": request.version_override,
        "decision_record": request.decision_record,
    }
    bootstrap_state_payload = {
        "format_version": 1,
        "repository_root": str(request.repository_root),
        "source_root": request.source_root_text,
        "publisher_slug": request.plugin_metadata.publisher_slug,
        "branding_assets": request.plugin_metadata.branding_assets,
    }
    return (
        decision_state_path,
        decision_state_payload,
        bootstrap_state_path,
        bootstrap_state_payload,
    )


def emit_packaging_artifacts(
    request: Any,
    *,
    version: str,
    branding_output_paths: dict[str, str],
    publication_metadata_name: str,
    mcp_descriptor_name: str,
    staging_plan_name: str,
    add_output: Any,
    record_payload_entry: Any,
    plugin_manifest_fn: Any,
    normalize_slug: Any,
    validate_mcp_descriptor_round_trip_fn: Any,
    mcp_descriptor_payload_fn: Any,
    staging_plan_payload_fn: Any,
    hash_bytes: Any,
    canonical_json_bytes: Any,
) -> tuple[dict[str, Any], str | None, str | None]:
    plugin_manifest_rel = Path(".codex-plugin") / "plugin.json"
    manifest_payload = plugin_manifest_fn(
        request.plugin_metadata,
        request.surface_id,
        version,
        branding_output_paths,
        mcp_packaging=request.mcp_packaging,
        normalize_slug=normalize_slug,
    )
    manifest_bytes = (
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    add_output(
        plugin_manifest_rel,
        manifest_bytes,
        {
            **record_payload_entry(
                relative_path=plugin_manifest_rel,
                content=manifest_bytes,
                source_reference="generated:plugin-manifest",
                acquisition_mode="generated",
                ownership_role="plugin-manifest",
                ownership_class=None,
                transform_kind="plugin-manifest",
            ),
            "version": version,
        },
    )
    if request.publication_contract is not None:
        publication_metadata_rel = Path(publication_metadata_name)
        publication_metadata_payload = {
            "format": "router-plugin-publication-metadata-v1",
            "plugin_slug": manifest_payload["name"],
            "category": request.publication_contract.category,
        }
        publication_metadata_bytes = (
            json.dumps(publication_metadata_payload, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        add_output(
            publication_metadata_rel,
            publication_metadata_bytes,
            record_payload_entry(
                relative_path=publication_metadata_rel,
                content=publication_metadata_bytes,
                source_reference="generated:publication-metadata",
                acquisition_mode="generated",
                ownership_role="publication-metadata",
                ownership_class=None,
                transform_kind="publication-metadata",
            ),
        )
    mcp_descriptor_bytes_sha256: str | None = None
    mcp_descriptor_canonical_sha256: str | None = None
    if request.mcp_packaging is not None:
        validate_mcp_descriptor_round_trip_fn(request.mcp_packaging.launch_contract)
        mcp_descriptor_rel = Path(mcp_descriptor_name)
        mcp_descriptor_payload = mcp_descriptor_payload_fn(
            request.mcp_packaging.launch_contract
        )
        mcp_descriptor_bytes = (
            json.dumps(mcp_descriptor_payload, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        mcp_descriptor_bytes_sha256 = hash_bytes(mcp_descriptor_bytes)
        mcp_descriptor_canonical_sha256 = hash_bytes(
            canonical_json_bytes(mcp_descriptor_payload)
        )
        add_output(
            mcp_descriptor_rel,
            mcp_descriptor_bytes,
            {
                **record_payload_entry(
                    relative_path=mcp_descriptor_rel,
                    content=mcp_descriptor_bytes,
                    source_reference="generated:mcp-descriptor",
                    acquisition_mode="generated",
                    ownership_role="mcp-launch-descriptor",
                    ownership_class=None,
                    transform_kind="mcp-launch-descriptor",
                ),
                "server_id": request.mcp_packaging.launch_contract.server_id,
            },
        )
        staging_plan_payload = staging_plan_payload_fn(request, version)
        assert staging_plan_payload is not None
        staging_plan_rel = Path(staging_plan_name)
        staging_plan_bytes = (
            json.dumps(staging_plan_payload, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        add_output(
            staging_plan_rel,
            staging_plan_bytes,
            {
                **record_payload_entry(
                    relative_path=staging_plan_rel,
                    content=staging_plan_bytes,
                    source_reference="generated:staging-plan",
                    acquisition_mode="generated",
                    ownership_role="staging-plan",
                    ownership_class=None,
                    transform_kind="staging-plan",
                ),
            },
        )
    return (
        manifest_payload,
        mcp_descriptor_bytes_sha256,
        mcp_descriptor_canonical_sha256,
    )


def prepare_packaging_artifacts_for_packager(
    request: Any,
    *,
    outputs: dict[str, bytes],
    add_output: Any,
    record_payload_entry: Any,
    branding_output_paths: dict[str, str],
    publication_metadata_name: str,
    mcp_descriptor_name: str,
    staging_plan_name: str,
    compute_version_fn: Any,
    plugin_id_fn: Any,
    normalize_slug: Any,
    hash_bytes: Any,
    hash_text: Any,
    emit_packaging_artifacts_fn: Any,
    plugin_manifest_fn: Any,
    validate_mcp_descriptor_round_trip_fn: Any,
    mcp_descriptor_payload_fn: Any,
    staging_plan_payload_fn: Any,
    canonical_json_bytes: Any,
) -> tuple[str, str, str | None, str | None]:
    plugin_id, version = compute_version_fn(
        request,
        outputs,
        plugin_id_fn=plugin_id_fn,
        normalize_slug=normalize_slug,
        hash_bytes=hash_bytes,
        hash_text=hash_text,
    )
    (
        _manifest_payload,
        mcp_descriptor_bytes_sha256,
        mcp_descriptor_canonical_sha256,
    ) = emit_packaging_artifacts_fn(
        request,
        version=version,
        branding_output_paths=branding_output_paths,
        publication_metadata_name=publication_metadata_name,
        mcp_descriptor_name=mcp_descriptor_name,
        staging_plan_name=staging_plan_name,
        add_output=add_output,
        record_payload_entry=record_payload_entry,
        plugin_manifest_fn=plugin_manifest_fn,
        normalize_slug=normalize_slug,
        validate_mcp_descriptor_round_trip_fn=validate_mcp_descriptor_round_trip_fn,
        mcp_descriptor_payload_fn=mcp_descriptor_payload_fn,
        staging_plan_payload_fn=staging_plan_payload_fn,
        hash_bytes=hash_bytes,
        canonical_json_bytes=canonical_json_bytes,
    )
    return (
        plugin_id,
        version,
        mcp_descriptor_bytes_sha256,
        mcp_descriptor_canonical_sha256,
    )


def build_normalized_request_summary(
    request: Any,
    *,
    payload_asset_records_fn: Any,
) -> dict[str, Any]:
    return {
        "format_version": 1,
        "plugin_kind": request.plugin_kind,
        "source_root": request.source_root_text,
        "repository_root": ".",
        "output_root": str(request.output_root.relative_to(request.repository_root)),
        "surface_id": request.surface_id,
        "skill_ids": request.skill_ids,
        "routers": [
            {
                "router_slug": router.router_slug,
                "description": router.description,
                "member_skill_ids": router.member_skill_ids,
            }
            for router in request.routers
        ],
        "plugin_metadata": {
            "publisher_slug": request.plugin_metadata.publisher_slug,
            "plugin_slug": request.plugin_metadata.plugin_slug,
            "display_name": request.plugin_metadata.display_name,
            "packaging_mode": request.plugin_metadata.packaging_mode,
            "branding_assets": request.plugin_metadata.branding_assets,
        },
        "version_override": request.version_override,
        "payload_assets": payload_asset_records_fn(
            request, include_extended_fields=True
        ),
        "runtime_compatibility_version": request.runtime_compatibility_version,
        "migration_contract_version": request.migration_contract_version,
        "rollback_compatibility_hints": request.rollback_compatibility_hints,
        "control_surface": request.control_surface,
        "owned_integration_root": request.owned_integration_root,
        "integration_points": request.integration_points,
        "verification_targets": request.verification_targets,
        "publication": (
            {"category": request.publication_contract.category}
            if request.publication_contract is not None
            else None
        ),
        "mcp_packaging": (
            {
                "plugin_artifact_contract": {
                    "name": request.mcp_packaging.artifact_name,
                    "description": request.mcp_packaging.description,
                    "author": {"name": request.mcp_packaging.author_name},
                    "interface": request.mcp_packaging.interface,
                    "skills_path": request.mcp_packaging.skills_path,
                    "mcp_servers_path": request.mcp_packaging.mcp_servers_path,
                },
                "launch_contract": {
                    "schema_version": request.mcp_packaging.launch_contract.schema_version,
                    "server_id": request.mcp_packaging.launch_contract.server_id,
                    "transport": request.mcp_packaging.launch_contract.transport,
                    "command": request.mcp_packaging.launch_contract.command,
                    "python_version": request.mcp_packaging.launch_contract.python_version,
                    "package_index": request.mcp_packaging.launch_contract.package_index,
                    "package_name": request.mcp_packaging.launch_contract.package_name,
                    "entrypoint": request.mcp_packaging.launch_contract.entrypoint,
                    "extra_args": list(
                        request.mcp_packaging.launch_contract.extra_args
                    ),
                    "forbidden_arg_fragments": list(
                        request.mcp_packaging.launch_contract.forbidden_arg_fragments
                    ),
                },
                "release_surface": {
                    "registry_manifest_asset_id": request.mcp_packaging.release_surface.registry_manifest_asset_id,
                    "release_manifest_asset_id": request.mcp_packaging.release_surface.release_manifest_asset_id,
                    "operation_registry_asset_id": request.mcp_packaging.release_surface.operation_registry_asset_id,
                    "schema_bundle_asset_id": request.mcp_packaging.release_surface.schema_bundle_asset_id,
                },
                "skill_release_contract": {
                    "skill_id": request.mcp_packaging.skill_release_contract.skill_id,
                    "advertised_operation_ids": list(
                        request.mcp_packaging.skill_release_contract.advertised_operation_ids
                    ),
                    "required_phrases": list(
                        request.mcp_packaging.skill_release_contract.required_phrases
                    ),
                    "forbidden_phrases": list(
                        request.mcp_packaging.skill_release_contract.forbidden_phrases
                    ),
                },
                "publication": {
                    "category": request.mcp_packaging.publication_contract.category,
                },
                "staging_contract": {
                    "format_version": request.mcp_packaging.staging_contract.format_version,
                    "marketplace_name": request.mcp_packaging.staging_contract.marketplace_name,
                    "plugin_relpath": request.mcp_packaging.staging_contract.plugin_relpath,
                    "version_suffix_source": request.mcp_packaging.staging_contract.version_suffix_source,
                    "allowed_mutations": [
                        {
                            "path": rule.path,
                            "field_path": rule.field_path,
                            "transform": rule.transform,
                        }
                        for rule in request.mcp_packaging.staging_contract.allowed_mutations
                    ],
                    "required_byte_preserved_paths": list(
                        request.mcp_packaging.staging_contract.required_byte_preserved_paths
                    ),
                },
            }
            if request.mcp_packaging is not None
            else None
        ),
        "decision_record": request.decision_record,
    }


def emit_native_state_outputs(
    request: Any,
    *,
    decision_state_path: Path,
    decision_state_payload: dict[str, Any],
    bootstrap_state_path: Path,
    bootstrap_state_payload: dict[str, Any],
    add_output: Any,
    record_payload_entry: Any,
) -> None:
    if request.input_mode != "native_routed":
        return
    decision_state_rel = decision_state_path.relative_to(request.output_root)
    decision_state_bytes = (
        json.dumps(decision_state_payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    add_output(
        decision_state_rel,
        decision_state_bytes,
        record_payload_entry(
            relative_path=decision_state_rel,
            content=decision_state_bytes,
            source_reference="generated:native-routed-decision-record",
            acquisition_mode="generated",
            ownership_role="decision-record",
            ownership_class=None,
            transform_kind="decision-record",
        ),
    )
    bootstrap_state_rel = bootstrap_state_path.relative_to(request.output_root)
    bootstrap_state_bytes = (
        json.dumps(bootstrap_state_payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    add_output(
        bootstrap_state_rel,
        bootstrap_state_bytes,
        record_payload_entry(
            relative_path=bootstrap_state_rel,
            content=bootstrap_state_bytes,
            source_reference="generated:native-routed-bootstrap-state",
            acquisition_mode="generated",
            ownership_role="bootstrap-state",
            ownership_class=None,
            transform_kind="bootstrap-state",
        ),
    )


def build_output_state(
    *,
    bootstrap_state_path: Path,
    bootstrap_state_payload: dict[str, Any],
    decision_state_path: Path,
    decision_state_payload: dict[str, Any],
    plugin_id: str,
    normalized_request: dict[str, Any],
) -> dict[str, Any]:
    return {
        "bootstrap_state_path": bootstrap_state_path,
        "bootstrap_state_payload": bootstrap_state_payload,
        "decision_state_path": decision_state_path,
        "decision_state_payload": decision_state_payload,
        "plugin_id": plugin_id,
        "normalized_request": normalized_request,
    }


def finalize_release_state_for_packager(
    request: Any,
    *,
    accumulator: Any,
    record_payload_entry_fn: Any,
    plugin_id: str,
    version: str,
    receipt_name: str,
    mcp_descriptor_bytes_sha256: str | None,
    mcp_descriptor_canonical_sha256: str | None,
    decision_state_dir: str,
    native_routed_decision_state_name: str,
    native_routed_bootstrap_state_name: str,
    add_proof_artifacts_fn: Any,
    native_generated_tree_digest_from_outputs_fn: Any,
    build_receipt_payload_fn: Any,
    build_state_payloads_fn: Any,
    emit_native_state_outputs_fn: Any,
    build_normalized_request_summary_fn: Any,
    build_output_state_fn: Any,
    payload_asset_records_fn: Any,
    mcp_launch_contract_provenance_fn: Any,
    mcp_authority_identity_fn: Any,
    native_receipt_contract_fn: Any,
    normalize_slug: Any,
) -> dict[str, Any]:
    payload_fingerprint, _payload_manifest_payload = add_proof_artifacts_fn(
        request,
        accumulator.payload_manifest_entries,
        accumulator.add_output,
        record_payload_entry_fn,
    )
    native_generated_tree_digest = (
        native_generated_tree_digest_from_outputs_fn(accumulator.outputs)
        if request.input_mode == "native_routed"
        else None
    )
    generated_paths = sorted(accumulator.outputs)
    receipt_payload = build_receipt_payload_fn(
        request,
        plugin_id=plugin_id,
        version=version,
        payload_fingerprint=payload_fingerprint,
        generated_paths=generated_paths,
        entries=accumulator.entries,
        receipt_name=receipt_name,
        mcp_descriptor_bytes_sha256=mcp_descriptor_bytes_sha256,
        mcp_descriptor_canonical_sha256=mcp_descriptor_canonical_sha256,
        native_generated_tree_digest=native_generated_tree_digest,
        mcp_launch_contract_provenance_fn=mcp_launch_contract_provenance_fn,
        mcp_authority_identity_fn=mcp_authority_identity_fn,
        native_receipt_contract_fn=native_receipt_contract_fn,
    )
    receipt_rel = Path(receipt_name)
    accumulator.outputs[receipt_rel.as_posix()] = (
        json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    accumulator.output_modes[receipt_rel.as_posix()] = 0o644
    (
        decision_state_path,
        decision_state_payload,
        bootstrap_state_path,
        bootstrap_state_payload,
    ) = build_state_payloads_fn(
        request,
        plugin_id=plugin_id,
        version=version,
        decision_state_dir=decision_state_dir,
        native_routed_decision_state_name=native_routed_decision_state_name,
        native_routed_bootstrap_state_name=native_routed_bootstrap_state_name,
        normalize_slug=normalize_slug,
    )
    emit_native_state_outputs_fn(
        request,
        decision_state_path=decision_state_path,
        decision_state_payload=decision_state_payload,
        bootstrap_state_path=bootstrap_state_path,
        bootstrap_state_payload=bootstrap_state_payload,
        add_output=accumulator.add_output,
        record_payload_entry=record_payload_entry_fn,
    )
    normalized_request = build_normalized_request_summary_fn(
        request,
        payload_asset_records_fn=payload_asset_records_fn,
    )
    state = build_output_state_fn(
        bootstrap_state_path=bootstrap_state_path,
        bootstrap_state_payload=bootstrap_state_payload,
        decision_state_path=decision_state_path,
        decision_state_payload=decision_state_payload,
        plugin_id=plugin_id,
        normalized_request=normalized_request,
    )
    return state
