from __future__ import annotations

from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


def normalize_payload_assets(
    invocation: Any,
    *,
    normalize_one_payload_asset_fn: Any,
    normalize_slug: Any,
) -> list[Any]:
    assets: list[Any] = []
    seen_ids: set[str] = set()
    for index, raw_asset in enumerate(invocation.payload_assets):
        asset = normalize_one_payload_asset_fn(invocation, index, raw_asset)
        normalized_id = normalize_slug(asset.asset_id)
        if normalized_id in seen_ids:
            raise PackagerError(
                "duplicate_payload_asset",
                "payload asset id must normalize to one unique non-empty slug",
                {"asset_id": asset.asset_id},
            )
        seen_ids.add(normalized_id)
        assets.append(asset)
    return assets


def normalize_one_payload_asset(
    invocation: Any,
    index: int,
    raw_asset: Any,
    *,
    payload_asset_factory: Any,
    ensure_string: Any,
    normalize_slug: Any,
    ownership_classes: frozenset[str],
    normalize_payload_acquisition_mode_fn: Any,
    normalize_payload_paths_fn: Any,
    normalize_payload_exclude_fn: Any,
    normalize_payload_normalization_fn: Any,
    normalize_payload_overwrite_policy_fn: Any,
    normalize_template_parameters_fn: Any,
    validate_payload_mode_specific_fields_fn: Any,
    resolve_local_path: Any,
    validate_payload_source_path_fn: Any,
) -> Any:
    field_prefix = f"payload_assets[{index}]"
    if not isinstance(raw_asset, dict):
        raise PackagerError(
            "invalid_payload_asset",
            "payload asset must be a mapping",
            {"field": field_prefix, "value": raw_asset},
        )
    asset_id = ensure_string(
        raw_asset.get("id", f"asset-{index + 1}"), field=f"{field_prefix}.id"
    )
    if not normalize_slug(asset_id):
        raise PackagerError(
            "duplicate_payload_asset",
            "payload asset id must normalize to one unique non-empty slug",
            {"asset_id": asset_id},
        )
    acquisition_mode = normalize_payload_acquisition_mode_fn(raw_asset, field_prefix)
    source, source_glob, destination_path = normalize_payload_paths_fn(
        raw_asset, field_prefix
    )
    ownership_role = ensure_string(
        raw_asset.get("ownership_role"), field=f"{field_prefix}.ownership_role"
    )
    ownership_class = raw_asset.get("ownership_class")
    if ownership_class is not None:
        ownership_class = ensure_string(
            ownership_class, field=f"{field_prefix}.ownership_class"
        )
        if ownership_class not in ownership_classes:
            raise PackagerError(
                "invalid_payload_asset",
                "payload asset ownership_class is not supported",
                {
                    "field": f"{field_prefix}.ownership_class",
                    "ownership_class": ownership_class,
                    "allowed": sorted(ownership_classes),
                },
            )
    raw_exclude = normalize_payload_exclude_fn(raw_asset, field_prefix)
    normalization = normalize_payload_normalization_fn(
        asset_id, raw_asset, field_prefix
    )
    overwrite_policy = normalize_payload_overwrite_policy_fn(
        asset_id, raw_asset, field_prefix
    )
    provenance_path = raw_asset.get("provenance_path")
    if provenance_path is not None:
        provenance_path = ensure_string(
            provenance_path, field=f"{field_prefix}.provenance_path"
        )
    template_parameters = normalize_template_parameters_fn(raw_asset, field_prefix)
    validate_payload_mode_specific_fields_fn(
        asset_id,
        acquisition_mode,
        provenance_path,
        template_parameters,
        source_glob,
    )
    source_path = resolve_local_path(invocation.repository_root, source)
    validate_payload_source_path_fn(
        invocation, source_path, source, source_glob, field_prefix, asset_id
    )
    return payload_asset_factory(
        asset_id=asset_id,
        acquisition_mode=acquisition_mode,
        source=str(source_path.relative_to(invocation.repository_root)),
        source_glob=source_glob,
        destination=destination_path.as_posix(),
        ownership_role=ownership_role,
        ownership_class=ownership_class,
        exclude=tuple(raw_exclude),
        normalization=normalization,
        overwrite_policy=overwrite_policy,
        provenance_path=provenance_path,
        template_parameters={
            str(key): value for key, value in sorted(template_parameters.items())
        },
    )


def normalize_payload_acquisition_mode(
    raw_asset: dict[str, Any], field_prefix: str, *, ensure_string: Any
) -> str:
    acquisition_mode = ensure_string(
        raw_asset.get("acquisition_mode"),
        field=f"{field_prefix}.acquisition_mode",
    )
    if acquisition_mode not in {"copied", "pre_generated", "templated"}:
        raise PackagerError(
            "invalid_payload_asset",
            "payload asset acquisition_mode must be copied, pre_generated, or templated",
            {
                "field": f"{field_prefix}.acquisition_mode",
                "acquisition_mode": acquisition_mode,
            },
        )
    return acquisition_mode


def normalize_payload_paths(
    raw_asset: dict[str, Any], field_prefix: str, *, ensure_string: Any
) -> tuple[str, str | None, Path]:
    source = ensure_string(raw_asset.get("source"), field=f"{field_prefix}.source")
    source_glob = raw_asset.get("source_glob")
    if source_glob is not None:
        source_glob = ensure_string(source_glob, field=f"{field_prefix}.source_glob")
        glob_path = Path(source_glob)
        if glob_path.is_absolute() or ".." in glob_path.parts:
            raise PackagerError(
                "invalid_payload_asset",
                "payload asset source_glob must be relative to its source root",
                {"field": f"{field_prefix}.source_glob", "source_glob": source_glob},
            )
    destination = ensure_string(
        raw_asset.get("destination"), field=f"{field_prefix}.destination"
    )
    destination_path = Path(destination)
    if destination_path.is_absolute() or ".." in destination_path.parts:
        raise PackagerError(
            "invalid_payload_asset_destination",
            "payload asset destination must be a relative path under the plugin root",
            {"field": f"{field_prefix}.destination", "destination": destination},
        )
    return source, source_glob, destination_path


def normalize_payload_exclude(
    raw_asset: dict[str, Any], field_prefix: str
) -> list[str]:
    raw_exclude = raw_asset.get("exclude", [])
    if raw_exclude is None:
        raw_exclude = []
    if not isinstance(raw_exclude, list) or not all(
        isinstance(item, str) for item in raw_exclude
    ):
        raise PackagerError(
            "invalid_payload_asset",
            "payload asset exclude must be a list of strings",
            {"field": f"{field_prefix}.exclude", "exclude": raw_exclude},
        )
    return raw_exclude


def normalize_payload_normalization(
    asset_id: str,
    raw_asset: dict[str, Any],
    field_prefix: str,
    *,
    ensure_string: Any,
) -> str:
    normalization = ensure_string(
        raw_asset.get("normalization", "none"),
        field=f"{field_prefix}.normalization",
    )
    if normalization != "none":
        raise PackagerError(
            "unsupported_payload_normalization",
            "only normalization='none' is supported in the current Layer 1 slice",
            {"asset_id": asset_id, "normalization": normalization},
        )
    return normalization


def normalize_payload_overwrite_policy(
    asset_id: str,
    raw_asset: dict[str, Any],
    field_prefix: str,
    *,
    ensure_string: Any,
) -> str:
    overwrite_policy = ensure_string(
        raw_asset.get("overwrite_policy", "error"),
        field=f"{field_prefix}.overwrite_policy",
    )
    if overwrite_policy != "error":
        raise PackagerError(
            "unsupported_payload_overwrite_policy",
            "only overwrite_policy='error' is supported in the current Layer 1 slice",
            {"asset_id": asset_id, "overwrite_policy": overwrite_policy},
        )
    return overwrite_policy


def normalize_template_parameters(
    raw_asset: dict[str, Any], field_prefix: str
) -> dict[str, Any]:
    template_parameters = raw_asset.get("template_parameters", {})
    if template_parameters is None:
        template_parameters = {}
    if not isinstance(template_parameters, dict):
        raise PackagerError(
            "invalid_payload_asset",
            "payload asset template_parameters must be a mapping",
            {
                "field": f"{field_prefix}.template_parameters",
                "template_parameters": template_parameters,
            },
        )
    return template_parameters


def validate_payload_mode_specific_fields(
    asset_id: str,
    acquisition_mode: str,
    provenance_path: str | None,
    template_parameters: dict[str, Any],
    source_glob: str | None,
) -> None:
    if acquisition_mode == "pre_generated" and provenance_path is None:
        raise PackagerError(
            "pregenerated_missing_proof",
            "pre_generated payload assets require provenance_path",
            {"asset_id": asset_id},
        )
    if acquisition_mode == "templated" and not template_parameters:
        raise PackagerError(
            "templated_inputs_incomplete",
            "templated payload assets require template_parameters",
            {"asset_id": asset_id},
        )
    if acquisition_mode == "copied" and (
        provenance_path is not None or template_parameters
    ):
        raise PackagerError(
            "invalid_payload_asset",
            "copied payload assets may not declare provenance_path or template_parameters",
            {"asset_id": asset_id},
        )
    if acquisition_mode == "templated" and source_glob is not None:
        raise PackagerError(
            "invalid_payload_asset",
            "templated payload assets may not declare source_glob",
            {"asset_id": asset_id},
        )


def validate_payload_source_path(
    invocation: Any,
    source_path: Path,
    source: str,
    source_glob: str | None,
    field_prefix: str,
    asset_id: str,
    *,
    validate_relative_path: Any,
) -> None:
    validate_relative_path(invocation.repository_root, source_path, field_prefix)
    try:
        source_path.relative_to(invocation.output_root)
    except ValueError:
        pass
    else:
        raise PackagerError(
            "payload_source_under_output_root",
            "payload asset source may not resolve under the generated output_root",
            {
                "asset_id": asset_id,
                "source": str(source_path),
                "output_root": str(invocation.output_root),
            },
        )
    if not source_path.exists():
        raise PackagerError(
            "missing_payload_asset_source",
            "payload asset source does not exist",
            {"asset_id": asset_id, "source": source},
        )
    if source_path.is_symlink():
        raise PackagerError(
            "invalid_payload_asset",
            "payload asset source may not be a symlink",
            {"asset_id": asset_id, "source": source},
        )
    if source_glob is not None and not source_path.is_dir():
        raise PackagerError(
            "invalid_payload_asset",
            "payload asset source_glob requires source to resolve to a directory",
            {"asset_id": asset_id, "source": source},
        )
