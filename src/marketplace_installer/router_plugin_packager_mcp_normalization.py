from __future__ import annotations

import re
from typing import Any

from packaging.version import InvalidVersion, Version

from marketplace_installer.router_plugin_packager_errors import PackagerError


_DISTRIBUTION_NAME_RE = re.compile(r"[A-Za-z0-9]+(?:[-_.]+[A-Za-z0-9]+)*")


def validate_distribution_name(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _DISTRIBUTION_NAME_RE.fullmatch(value):
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "package name must be a Python distribution name",
            {"field": field},
        )
    return value


def normalize_package_version(value: Any, *, field: str) -> str:
    if value == "":
        return ""
    if not isinstance(value, str) or value != value.strip():
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "package_version must be a canonical public PEP 440 version",
            {"field": field},
        )
    try:
        version = Version(value)
    except InvalidVersion as exc:
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "package_version must be a canonical public PEP 440 version",
            {"field": field},
        ) from exc
    if version.local is not None or str(version) != value:
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "package_version must be a canonical public PEP 440 version",
            {"field": field},
        )
    return value


def require_mapping(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PackagerError(
            "invalid_invocation_field",
            "field must be a mapping",
            {"field": field, "value": value},
        )
    return dict(value)


def require_string_list(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise PackagerError(
            "invalid_invocation_field",
            "field must be a non-empty string list",
            {"field": field, "value": value},
        )
    return [str(item).strip() for item in value]


def normalize_publication_contract(
    payload: dict[str, Any],
    *,
    field: str,
    publication_contract_factory: Any,
    ensure_string: Any,
) -> Any:
    category = ensure_string(payload.get("category"), field=f"{field}.category")
    if category != "Productivity":
        raise PackagerError(
            "invalid_publication_contract",
            "publication category must be Productivity",
            {"category": category},
        )
    return publication_contract_factory(category=category)


def resolve_publication_contract(
    invocation: Any,
    mcp_packaging: Any | None,
    *,
    require_mapping_fn: Any,
    normalize_publication_contract_fn: Any,
) -> Any | None:
    if invocation.publication is None:
        return mcp_packaging.publication_contract if mcp_packaging is not None else None
    publication = require_mapping_fn(invocation.publication, field="publication")
    normalized = normalize_publication_contract_fn(publication, field="publication")
    if mcp_packaging is not None and normalized != mcp_packaging.publication_contract:
        raise PackagerError(
            "conflicting_publication_contract",
            "publication conflicts with mcp_packaging.publication",
            {},
        )
    return normalized


def normalize_mcp_packaging(
    invocation: Any,
    skill_ids: list[str],
    payload_assets: list[Any],
    *,
    require_mapping_fn: Any,
    ensure_string: Any,
    normalize_mcp_launch_contract_fn: Any,
    normalize_mcp_release_surface_fn: Any,
    normalize_mcp_skill_release_contract_fn: Any,
    normalize_publication_contract_fn: Any,
    normalize_mcp_staging_contract_fn: Any,
    mcp_packaging_factory: Any,
) -> Any | None:
    if invocation.mcp_packaging is None:
        return None
    payload = require_mapping_fn(invocation.mcp_packaging, field="mcp_packaging")
    artifact = require_mapping_fn(
        payload.get("plugin_artifact_contract"),
        field="mcp_packaging.plugin_artifact_contract",
    )
    launch = require_mapping_fn(
        payload.get("launch_contract"), field="mcp_packaging.launch_contract"
    )
    release_surface = require_mapping_fn(
        payload.get("release_surface"), field="mcp_packaging.release_surface"
    )
    skill_release = require_mapping_fn(
        payload.get("skill_release_contract"),
        field="mcp_packaging.skill_release_contract",
    )
    staging = require_mapping_fn(
        payload.get("staging_contract"), field="mcp_packaging.staging_contract"
    )
    publication = require_mapping_fn(
        payload.get("publication"), field="mcp_packaging.publication"
    )
    return mcp_packaging_factory(
        artifact_name=ensure_string(
            artifact.get("name"), field="mcp_packaging.plugin_artifact_contract.name"
        ),
        description=ensure_string(
            artifact.get("description"),
            field="mcp_packaging.plugin_artifact_contract.description",
        ),
        author_name=ensure_string(
            require_mapping_fn(
                artifact.get("author"),
                field="mcp_packaging.plugin_artifact_contract.author",
            ).get("name"),
            field="mcp_packaging.plugin_artifact_contract.author.name",
        ),
        interface=require_mapping_fn(
            artifact.get("interface"),
            field="mcp_packaging.plugin_artifact_contract.interface",
        ),
        skills_path=ensure_string(
            artifact.get("skills_path", "./skills/"),
            field="mcp_packaging.plugin_artifact_contract.skills_path",
        ),
        mcp_servers_path=ensure_string(
            artifact.get("mcp_servers_path", "./.mcp.json"),
            field="mcp_packaging.plugin_artifact_contract.mcp_servers_path",
        ),
        launch_contract=normalize_mcp_launch_contract_fn(launch),
        release_surface=normalize_mcp_release_surface_fn(
            release_surface, payload_assets
        ),
        skill_release_contract=normalize_mcp_skill_release_contract_fn(
            skill_release, skill_ids
        ),
        publication_contract=normalize_publication_contract_fn(
            publication, field="mcp_packaging.publication"
        ),
        staging_contract=normalize_mcp_staging_contract_fn(staging),
    )


def normalize_mcp_launch_contract(  # noqa: C901
    payload: dict[str, Any],
    *,
    ensure_string: Any,
    require_string_list_fn: Any,
    normalize_mcp_environment_fn: Any,
    validate_mcp_launch_policy_fn: Any,
    mcp_launch_contract_factory: Any,
) -> Any:
    schema_version = payload.get("schema_version")
    allowed_v1 = {
        "schema_version",
        "server_id",
        "transport",
        "command",
        "python_version",
        "package_index",
        "package_name",
        "entrypoint",
        "extra_args",
        "forbidden_arg_fragments",
    }
    allowed_v2 = {*allowed_v1, "environment", "environment_authority"}
    allowed_v3 = {*allowed_v2, "package_version"}
    if type(schema_version) is not int or schema_version not in {1, 2, 3}:
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "mcp launch contract schema_version must be 1, 2, or 3",
            {"schema_version": schema_version},
        )
    allowed = {1: allowed_v1, 2: allowed_v2, 3: allowed_v3}[schema_version]
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "mcp launch contract contains unsupported properties",
            {"unknown_properties": unknown},
        )
    if schema_version == 1 and "environment" in payload:
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "schema version 1 must not declare environment",
            {},
        )
    if schema_version in {2, 3} and "environment" not in payload:
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "schema version 2 or 3 requires environment",
            {},
        )
    if schema_version == 3 and "package_version" not in payload:
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "schema version 3 requires package_version",
            {},
        )
    transport = ensure_string(
        payload.get("transport"), field="mcp_packaging.launch_contract.transport"
    )
    if transport != "stdio":
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "the current supported MCP launch profile requires transport=stdio",
            {"transport": transport},
        )
    command = ensure_string(
        payload.get("command"), field="mcp_packaging.launch_contract.command"
    )
    if command != "uvx":
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "the current supported MCP launch profile requires command=uvx",
            {"command": command},
        )
    extra_args = payload.get("extra_args", [])
    if extra_args is None:
        extra_args = []
    if not isinstance(extra_args, list) or not all(
        isinstance(item, str) for item in extra_args
    ):
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "launch_contract.extra_args must be a string list when present",
            {"extra_args": extra_args},
        )
    forbidden_arg_fragments = payload.get(
        "forbidden_arg_fragments",
        ["auth", "credential", "endpoint", "profile", "tenant"],
    )
    fragments = require_string_list_fn(
        forbidden_arg_fragments,
        field="mcp_packaging.launch_contract.forbidden_arg_fragments",
    )
    environment = normalize_mcp_environment_fn(
        payload.get("environment", {}),
        field="mcp_packaging.launch_contract.environment",
    )
    authority = payload.get("environment_authority")
    if authority is None:
        authority = "legacy_empty" if schema_version == 1 else "config"
    if authority not in {"config", "native_descriptor", "legacy_empty"}:
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "environment_authority must be config, native_descriptor, or legacy_empty",
            {"environment_authority": authority},
        )
    if environment and authority == "legacy_empty":
        raise PackagerError(
            "invalid_mcp_launch_contract",
            "legacy_empty authority requires an empty environment",
            {},
        )
    package_name = ensure_string(
        payload.get("package_name"), field="mcp_packaging.launch_contract.package_name"
    )
    package_version = ""
    if schema_version == 3:
        package_name = validate_distribution_name(
            payload.get("package_name"),
            field="mcp_packaging.launch_contract.package_name",
        )
        if authority != "config":
            raise PackagerError(
                "invalid_mcp_launch_contract",
                "schema version 3 requires environment_authority=config",
                {},
            )
        package_version = normalize_package_version(
            payload.get("package_version"),
            field="mcp_packaging.launch_contract.package_version",
        )
    normalized = mcp_launch_contract_factory(
        schema_version=3 if schema_version == 3 else 2,
        input_schema_version=schema_version,
        server_id=ensure_string(
            payload.get("server_id"), field="mcp_packaging.launch_contract.server_id"
        ),
        transport=transport,
        command=command,
        python_version=ensure_string(
            payload.get("python_version"),
            field="mcp_packaging.launch_contract.python_version",
        ),
        package_index=ensure_string(
            payload.get("package_index"),
            field="mcp_packaging.launch_contract.package_index",
        ),
        package_name=package_name,
        package_version=package_version,
        entrypoint=ensure_string(
            payload.get("entrypoint"),
            field="mcp_packaging.launch_contract.entrypoint",
        ),
        extra_args=tuple(str(item) for item in extra_args),
        forbidden_arg_fragments=tuple(fragments),
        environment=environment,
        environment_authority=authority,
    )
    validate_mcp_launch_policy_fn(normalized)
    return normalized


def normalize_mcp_environment(
    value: Any, *, field: str, canonical_json_bytes: Any
) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, dict):
        raise PackagerError(
            "env_invalid_type", "environment must be an object", {"field": field}
        )
    if len(value) > 8:
        raise PackagerError(
            "env_invalid_value",
            "environment may contain at most 8 entries",
            {"field": field},
        )
    environment: list[tuple[str, str]] = []
    for name, raw_value in value.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", name):
            raise PackagerError(
                "env_invalid_name",
                "environment variable name is invalid",
                {"field": field},
            )
        if not isinstance(raw_value, str):
            raise PackagerError(
                "env_invalid_type",
                "environment value must be a string",
                {"field": field, "name": name},
            )
        encoded = raw_value.encode("utf-8")
        if not 1 <= len(encoded) <= 512 or any(
            ord(char) < 32 or ord(char) == 127 for char in raw_value
        ):
            raise PackagerError(
                "env_invalid_value",
                "environment value is invalid",
                {"field": field, "name": name},
            )
        environment.append((name, raw_value))
    environment.sort()
    canonical = canonical_json_bytes(dict(environment))
    if len(canonical) > 2048:
        raise PackagerError(
            "env_invalid_value", "environment map exceeds 2 KiB", {"field": field}
        )
    return tuple(environment)


def normalize_mcp_release_surface(
    payload: dict[str, Any],
    payload_assets: list[Any],
    *,
    ensure_string: Any,
    mcp_release_surface_factory: Any,
) -> Any:
    asset_ids = {asset.asset_id: asset for asset in payload_assets}
    normalized = mcp_release_surface_factory(
        registry_manifest_asset_id=ensure_string(
            payload.get("registry_manifest_asset_id"),
            field="mcp_packaging.release_surface.registry_manifest_asset_id",
        ),
        release_manifest_asset_id=ensure_string(
            payload.get("release_manifest_asset_id"),
            field="mcp_packaging.release_surface.release_manifest_asset_id",
        ),
        operation_registry_asset_id=ensure_string(
            payload.get("operation_registry_asset_id"),
            field="mcp_packaging.release_surface.operation_registry_asset_id",
        ),
        schema_bundle_asset_id=ensure_string(
            payload.get("schema_bundle_asset_id"),
            field="mcp_packaging.release_surface.schema_bundle_asset_id",
        ),
    )
    for field_name, asset_id in (
        ("registry_manifest_asset_id", normalized.registry_manifest_asset_id),
        ("release_manifest_asset_id", normalized.release_manifest_asset_id),
        ("operation_registry_asset_id", normalized.operation_registry_asset_id),
        ("schema_bundle_asset_id", normalized.schema_bundle_asset_id),
    ):
        asset = asset_ids.get(asset_id)
        if asset is None:
            raise PackagerError(
                "missing_mcp_release_asset",
                "mcp release-surface asset id does not exist in payload_assets",
                {"field": field_name, "asset_id": asset_id},
            )
        if asset.acquisition_mode not in {"copied", "pre_generated"}:
            raise PackagerError(
                "invalid_mcp_release_asset",
                "mcp release-surface assets must be copied or pre_generated",
                {"field": field_name, "asset_id": asset_id},
            )
    return normalized


def normalize_mcp_skill_release_contract(
    payload: dict[str, Any],
    skill_ids: list[str],
    *,
    ensure_string: Any,
    require_string_list_fn: Any,
    mcp_skill_release_contract_factory: Any,
) -> Any:
    skill_id = ensure_string(
        payload.get("skill_id"),
        field="mcp_packaging.skill_release_contract.skill_id",
    )
    if skill_id not in skill_ids:
        raise PackagerError(
            "invalid_mcp_skill_release_contract",
            "skill_release_contract.skill_id must be one of the packaged skills",
            {"skill_id": skill_id, "skill_ids": skill_ids},
        )
    return mcp_skill_release_contract_factory(
        skill_id=skill_id,
        advertised_operation_ids=tuple(
            require_string_list_fn(
                payload.get("advertised_operation_ids", []),
                field="mcp_packaging.skill_release_contract.advertised_operation_ids",
            )
        ),
        required_phrases=tuple(
            require_string_list_fn(
                payload.get("required_phrases", []),
                field="mcp_packaging.skill_release_contract.required_phrases",
            )
        ),
        forbidden_phrases=tuple(
            require_string_list_fn(
                payload.get("forbidden_phrases", []),
                field="mcp_packaging.skill_release_contract.forbidden_phrases",
            )
        ),
    )


def normalize_mcp_staging_contract(
    payload: dict[str, Any],
    *,
    ensure_string: Any,
    require_mapping_fn: Any,
    require_string_list_fn: Any,
    mcp_staging_mutation_rule_factory: Any,
    mcp_staging_contract_factory: Any,
) -> Any:
    format_version = payload.get("format_version")
    if format_version != 1:
        raise PackagerError(
            "invalid_mcp_staging_contract",
            "staging_contract.format_version must be 1",
            {"format_version": format_version},
        )
    raw_mutations = payload.get("allowed_mutations", [])
    if not isinstance(raw_mutations, list) or not raw_mutations:
        raise PackagerError(
            "invalid_mcp_staging_contract",
            "staging_contract.allowed_mutations must be a non-empty list",
            {"allowed_mutations": raw_mutations},
        )
    mutations: list[Any] = []
    for index, raw_rule in enumerate(raw_mutations):
        rule = require_mapping_fn(
            raw_rule,
            field=f"mcp_packaging.staging_contract.allowed_mutations[{index}]",
        )
        transform = ensure_string(
            rule.get("transform"),
            field=f"mcp_packaging.staging_contract.allowed_mutations[{index}].transform",
        )
        if transform != "append-version-suffix":
            raise PackagerError(
                "invalid_mcp_staging_contract",
                "only append-version-suffix staging mutations are supported",
                {"transform": transform},
            )
        mutations.append(
            mcp_staging_mutation_rule_factory(
                path=ensure_string(
                    rule.get("path"),
                    field=f"mcp_packaging.staging_contract.allowed_mutations[{index}].path",
                ),
                field_path=ensure_string(
                    rule.get("field_path"),
                    field=f"mcp_packaging.staging_contract.allowed_mutations[{index}].field_path",
                ),
                transform=transform,
            )
        )
    return mcp_staging_contract_factory(
        format_version=1,
        marketplace_name=ensure_string(
            payload.get("marketplace_name"),
            field="mcp_packaging.staging_contract.marketplace_name",
        ),
        plugin_relpath=ensure_string(
            payload.get("plugin_relpath"),
            field="mcp_packaging.staging_contract.plugin_relpath",
        ),
        version_suffix_source=ensure_string(
            payload.get("version_suffix_source", "cachebuster"),
            field="mcp_packaging.staging_contract.version_suffix_source",
        ),
        allowed_mutations=tuple(mutations),
        required_byte_preserved_paths=tuple(
            require_string_list_fn(
                payload.get("required_byte_preserved_paths", []),
                field="mcp_packaging.staging_contract.required_byte_preserved_paths",
            )
        ),
    )


def validate_mcp_launch_policy(contract: Any) -> None:
    forbidden = tuple(fragment.lower() for fragment in contract.forbidden_arg_fragments)
    dangerous_values = [
        *contract.extra_args,
        contract.entrypoint,
        contract.package_name,
    ]
    for value in dangerous_values:
        lower = value.lower()
        if any(fragment in lower for fragment in forbidden):
            raise PackagerError(
                "forbidden_mcp_launch_argument",
                "mcp launch contract contains a forbidden runtime argument fragment",
                {
                    "value": value,
                    "forbidden_arg_fragments": list(contract.forbidden_arg_fragments),
                },
            )
