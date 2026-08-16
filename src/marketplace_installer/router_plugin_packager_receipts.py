from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


def validate_existing_destination(destination: Path) -> None:
    if destination.is_symlink():
        raise PackagerError(
            "invalid_existing_destination",
            "planned destination may not be a symlink",
            {"path": str(destination)},
        )
    if destination.exists() and not destination.is_file():
        raise PackagerError(
            "invalid_existing_destination",
            "planned destination collides with a non-file path",
            {"path": str(destination)},
        )


def load_existing_receipt(
    output_root: Path, *, receipt_name: str, load_json: Any
) -> dict[str, Any] | None:
    receipt_path = output_root / receipt_name
    if not receipt_path.exists():
        return None
    validate_existing_destination(receipt_path)
    return load_json(receipt_path)


def stale_generated_paths(
    *,
    request: Any,
    planned_paths: set[Path],
    load_existing_receipt_fn: Any,
    validate_existing_destination_fn: Any,
) -> list[str]:
    receipt = load_existing_receipt_fn(request.output_root)
    if receipt is None:
        return []
    receipt_surface = receipt.get("surface_id")
    if receipt_surface != request.surface_id:
        raise PackagerError(
            "existing_receipt_surface_mismatch",
            "existing output receipt belongs to a different surface_id",
            {
                "output_root": str(request.output_root),
                "existing_surface_id": receipt_surface,
                "surface_id": request.surface_id,
            },
        )
    stale: list[str] = []
    for relative_path in receipt.get("generated_paths", []):
        absolute = request.output_root / relative_path
        if absolute in planned_paths or not absolute.exists():
            continue
        validate_existing_destination_fn(absolute)
        stale.append(str(absolute))
    return sorted(stale)


def preserved_paths(
    output_root: Path, planned_paths: set[Path], stale_paths: set[Path]
) -> list[str]:
    if not output_root.exists():
        return []
    preserved: list[str] = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file():
            continue
        if path in planned_paths or path in stale_paths:
            continue
        preserved.append(str(path))
    return preserved


def summary(
    *,
    request: Any,
    outputs: dict[str, bytes],
    state: dict[str, Any],
    version: str,
    stale_generated_paths_fn: Any,
    preserved_paths_fn: Any,
) -> dict[str, Any]:
    output_paths = sorted(str(request.output_root / rel) for rel in outputs)
    planned_paths = {request.output_root / rel for rel in outputs}
    stale_paths = stale_generated_paths_fn(request, planned_paths)
    stale_path_set = {Path(path) for path in stale_paths}
    payload = {
        "input_mode": request.input_mode,
        "surface_id": request.surface_id,
        "skill_ids": request.skill_ids,
        "source_root": request.source_root_text,
        "repository_root": str(request.repository_root),
        "output_root": str(request.output_root),
        "bootstrap_state_path": str(state["bootstrap_state_path"]),
        "generated_output_paths": output_paths,
        "decision_state_path": str(state["decision_state_path"]),
        "preserved_paths": preserved_paths_fn(
            request.output_root, planned_paths, stale_path_set
        ),
        "stale_generated_paths": stale_paths,
        "version": version,
        "plugin_id": state["plugin_id"],
        "normalized_request": state["normalized_request"],
    }
    return payload


def summarize_outputs(
    *,
    request: Any,
    outputs: dict[str, bytes],
    state: dict[str, Any],
    version: str,
    receipt_name: str,
    load_json_fn: Any,
    validate_existing_destination_fn: Any,
) -> dict[str, Any]:
    def load_existing_receipt_for_request(output_root: Path) -> dict[str, Any] | None:
        return load_existing_receipt(
            output_root, receipt_name=receipt_name, load_json=load_json_fn
        )

    return summary(
        request=request,
        outputs=outputs,
        state=state,
        version=version,
        stale_generated_paths_fn=lambda req, planned: stale_generated_paths(
            request=req,
            planned_paths=planned,
            load_existing_receipt_fn=load_existing_receipt_for_request,
            validate_existing_destination_fn=validate_existing_destination_fn,
        ),
        preserved_paths_fn=preserved_paths,
    )


def summarize_outputs_for_packager(
    *,
    request: Any,
    outputs: dict[str, bytes],
    state: dict[str, Any],
    version: str,
    receipt_name: str,
    load_json_fn: Any,
    validate_existing_destination_fn: Any,
) -> dict[str, Any]:
    return summarize_outputs(
        request=request,
        outputs=outputs,
        state=state,
        version=version,
        receipt_name=receipt_name,
        load_json_fn=load_json_fn,
        validate_existing_destination_fn=validate_existing_destination_fn,
    )


def recover_interrupted_promotion_for_packager(
    output_root: Path,
    *,
    suffix: str,
    load_json_fn: Any,
    receipt_name: str,
) -> None:
    def load_existing_receipt_for_output(root: Path) -> dict[str, Any] | None:
        return load_existing_receipt(
            root, receipt_name=receipt_name, load_json=load_json_fn
        )

    recover_interrupted_promotion(
        output_root,
        suffix=suffix,
        load_json_fn=load_json_fn,
        load_existing_receipt_fn=load_existing_receipt_for_output,
    )


def validate_output_ownership_for_packager(
    request: Any,
    *,
    receipt_name: str,
    load_json_fn: Any,
    native_receipt_format: str,
    native_receipt_contract_fn: Any,
    native_generated_tree_digest_from_disk_fn: Any,
) -> None:
    def load_existing_receipt_for_output(root: Path) -> dict[str, Any] | None:
        return load_existing_receipt(
            root, receipt_name=receipt_name, load_json=load_json_fn
        )

    validate_output_ownership(
        request,
        load_existing_receipt_fn=load_existing_receipt_for_output,
        native_receipt_format=native_receipt_format,
        native_receipt_contract_fn=native_receipt_contract_fn,
        native_generated_tree_digest_from_disk_fn=native_generated_tree_digest_from_disk_fn,
    )


def remove_stale_paths_for_packager(
    paths: list[str], *, validate_existing_destination_fn: Any
) -> None:
    remove_stale_paths(
        paths, validate_existing_destination_fn=validate_existing_destination_fn
    )


def remove_stale_paths(
    paths: list[str], *, validate_existing_destination_fn: Any
) -> None:
    for raw_path in paths:
        path = Path(raw_path)
        validate_existing_destination_fn(path)
        if path.exists():
            path.unlink()


def promotion_receipt_path(output_root: Path, *, suffix: str) -> Path:
    return output_root.parent / f".{output_root.name}{suffix}"


def recover_interrupted_promotion(  # noqa: C901
    output_root: Path,
    *,
    suffix: str,
    load_json_fn: Any,
    load_existing_receipt_fn: Any,
) -> None:
    """Restore a valid backup after a process stops during promotion."""

    receipt_path = promotion_receipt_path(output_root, suffix=suffix)
    if not receipt_path.exists():
        return
    receipt = load_json_fn(receipt_path)
    stage = Path(receipt.get("stage", ""))
    backup = Path(receipt.get("backup", ""))
    state = receipt.get("state")
    expected_prefix = f".{output_root.name}"
    if (
        receipt.get("target") != str(output_root)
        or stage.parent != output_root.parent
        or backup.parent != output_root.parent
        or not stage.name.startswith(f"{expected_prefix}.stage-")
        or not backup.name.startswith(f"{expected_prefix}.backup-")
        or state not in {"staged", "backed_up", "promoted"}
    ):
        raise PackagerError(
            "invalid_promotion_receipt",
            "interrupted promotion receipt is invalid",
            {"receipt_path": str(receipt_path)},
        )
    if stage.exists() and stage.is_symlink() or backup.exists() and backup.is_symlink():
        raise PackagerError(
            "invalid_promotion_receipt",
            "interrupted promotion contains a symlinked staging path",
            {"receipt_path": str(receipt_path)},
        )
    if state == "backed_up":
        if output_root.exists() or not backup.is_dir() or stage.exists():
            raise PackagerError(
                "ambiguous_promotion_recovery",
                "cannot safely recover interrupted output promotion",
                {"receipt_path": str(receipt_path)},
            )
        if load_existing_receipt_fn(backup) is None:
            raise PackagerError(
                "ambiguous_promotion_recovery",
                "interrupted output backup has no valid ownership receipt",
                {"receipt_path": str(receipt_path)},
            )
        os.replace(backup, output_root)
    elif state == "staged":
        if not output_root.is_dir() or backup.exists():
            raise PackagerError(
                "ambiguous_promotion_recovery",
                "cannot safely recover staged output promotion",
                {"receipt_path": str(receipt_path)},
            )
        if stage.exists():
            shutil.rmtree(stage)
    else:
        if not output_root.is_dir() or stage.exists():
            raise PackagerError(
                "ambiguous_promotion_recovery",
                "cannot safely recover promoted output",
                {"receipt_path": str(receipt_path)},
            )
        if backup.exists():
            shutil.rmtree(backup)
    receipt_path.unlink()


def validate_output_ownership(  # noqa: C901
    request: Any,
    *,
    load_existing_receipt_fn: Any,
    native_receipt_format: str,
    native_receipt_contract_fn: Any,
    native_generated_tree_digest_from_disk_fn: Any,
) -> None:
    """Reject scaffolds and hand-maintained files before staging a replacement."""

    output_root = request.output_root
    if not output_root.exists():
        return
    if output_root.is_symlink() or not output_root.is_dir():
        raise PackagerError(
            "invalid_output_root",
            "output_root must be a regular directory when it already exists",
            {"output_root": str(output_root)},
        )
    receipt = load_existing_receipt_fn(output_root)
    files = [path for path in output_root.rglob("*") if path.is_file()]
    if receipt is None:
        if files:
            raise PackagerError(
                "unowned_output_root",
                "nonempty output_root is not owned by the router packager",
                {"output_root": str(output_root)},
            )
        return
    if receipt.get("surface_id") != request.surface_id:
        return
    if request.input_mode == "native_routed":
        native_receipt = receipt.get("native_routed")
        if not isinstance(native_receipt, dict):
            raise PackagerError(
                "invalid_native_routed_receipt",
                "existing native-routed output lacks the required native receipt contract",
                {"output_root": str(output_root)},
            )
        if native_receipt.get("format") != native_receipt_format:
            raise PackagerError(
                "invalid_native_routed_receipt",
                "existing native-routed output receipt has an invalid ownership marker",
                {
                    "output_root": str(output_root),
                    "expected_format": native_receipt_format,
                    "actual_format": native_receipt.get("format"),
                },
            )
        expected = native_receipt_contract_fn(request)
        for key, value in expected.items():
            if native_receipt.get(key) != value:
                raise PackagerError(
                    "invalid_native_routed_receipt",
                    "existing native-routed output receipt does not match the requested source contract",
                    {
                        "output_root": str(output_root),
                        "field": key,
                        "expected": value,
                        "actual": native_receipt.get(key),
                    },
                )
        actual_digest = native_generated_tree_digest_from_disk_fn(output_root)
        if native_receipt.get("generated_tree_digest") != actual_digest:
            raise PackagerError(
                "invalid_native_routed_receipt",
                "existing native-routed output tree does not match its recorded digest",
                {
                    "output_root": str(output_root),
                    "expected_digest": native_receipt.get("generated_tree_digest"),
                    "actual_digest": actual_digest,
                },
            )
    generated = {
        str(output_root / relative_path)
        for relative_path in receipt.get("generated_paths", [])
        if isinstance(relative_path, str)
    }
    unowned = sorted(str(path) for path in files if str(path) not in generated)
    if unowned:
        raise PackagerError(
            "unowned_output_root",
            "output_root contains files not owned by the router packager",
            {"output_root": str(output_root), "unowned_paths": unowned},
        )
