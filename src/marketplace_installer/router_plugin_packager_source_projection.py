from __future__ import annotations

import stat
from pathlib import Path, PurePosixPath
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


FORMAT = "router-source-projection-v1"


def _error(code: str, message: str, **details: Any) -> None:
    raise PackagerError(code, message, details)


def _relative_path(value: Any, *, field: str, allow_dot: bool = False) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        _error(
            "source_projection_receipt_invalid",
            "receipt path must be a non-empty string",
            field=field,
        )
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or (not allow_dot and value == ".")
    ):
        _error(
            "source_projection_path_unsafe",
            "receipt path must be normalized and repository-relative",
            field=field,
            path=value,
        )
    if path.as_posix() != value or any(part in {"", "."} for part in path.parts):
        _error(
            "source_projection_path_unsafe",
            "receipt path must be normalized and repository-relative",
            field=field,
            path=value,
        )
    return path


def _regular_path(path: Path, *, code: str, field: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        _error(code, "source projection file is missing", field=field, path=str(path))
    except OSError as exc:
        _error(
            "source_projection_path_unsafe",
            "source projection path cannot be inspected safely",
            field=field,
            path=str(path),
            error=str(exc),
        )
    if not stat.S_ISREG(mode):
        _error(
            "source_projection_path_unsafe",
            "source projection paths must be regular non-symlinked files",
            field=field,
            path=str(path),
        )


def _directory_path(path: Path, *, field: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        _error(
            "source_projection_stale",
            "source projection root is missing",
            field=field,
            path=str(path),
        )
    except OSError as exc:
        _error(
            "source_projection_path_unsafe",
            "source projection root cannot be inspected safely",
            field=field,
            path=str(path),
            error=str(exc),
        )
    if not stat.S_ISDIR(mode):
        _error(
            "source_projection_path_unsafe",
            "source projection roots must be non-symlinked directories",
            field=field,
            path=str(path),
        )


def _under_root(root: Path, relative: PurePosixPath, *, field: str) -> Path:
    candidate = root.joinpath(*relative.parts)
    try:
        candidate.relative_to(root)
    except ValueError:
        _error(
            "source_projection_path_unsafe",
            "receipt path escapes its declared root",
            field=field,
            path=relative.as_posix(),
        )
    return candidate


def _reject_symlink_components(
    path: Path, repository_root: Path, *, field: str
) -> None:
    try:
        relative = path.relative_to(repository_root)
    except ValueError:
        _error(
            "source_projection_path_unsafe",
            "source projection path escapes the repository root",
            field=field,
            path=str(path),
        )
    current = repository_root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            _error(
                "source_projection_path_unsafe",
                "source projection paths may not traverse symlinks",
                field=field,
                path=str(current),
            )


def verify_source_projection(
    receipt_reference: str | None,
    repository_root: Path,
    *,
    load_json_bytes_fn: Any,
    hash_bytes_fn: Any,
) -> dict[str, Any] | None:
    if receipt_reference is None:
        return None
    receipt_rel = _relative_path(receipt_reference, field="source_projection_receipt")
    receipt_path = _under_root(
        repository_root, receipt_rel, field="source_projection_receipt"
    )
    _reject_symlink_components(
        receipt_path, repository_root, field="source_projection_receipt"
    )
    _regular_path(
        receipt_path,
        code="source_projection_receipt_missing",
        field="source_projection_receipt",
    )
    raw_receipt = receipt_path.read_bytes()
    try:
        receipt = load_json_bytes_fn(raw_receipt, path=receipt_path)
    except PackagerError as exc:
        _error(
            "source_projection_receipt_invalid",
            "receipt must contain valid JSON",
            error=exc.message,
        )
    if not isinstance(receipt, dict) or receipt.get("format") != FORMAT:
        _error(
            "source_projection_receipt_invalid",
            "receipt format is invalid",
            format=receipt.get("format") if isinstance(receipt, dict) else None,
        )
    canonical_root = _relative_path(
        receipt.get("canonical_root"), field="canonical_root", allow_dot=True
    )
    projection_root = _relative_path(
        receipt.get("projection_root"), field="projection_root", allow_dot=True
    )
    canonical_base = _under_root(
        repository_root, canonical_root, field="canonical_root"
    )
    projection_base = _under_root(
        repository_root, projection_root, field="projection_root"
    )
    _reject_symlink_components(canonical_base, repository_root, field="canonical_root")
    _reject_symlink_components(
        projection_base, repository_root, field="projection_root"
    )
    _directory_path(canonical_base, field="canonical_root")
    _directory_path(projection_base, field="projection_root")
    entries = receipt.get("entries")
    if not isinstance(entries, list) or not entries:
        _error(
            "source_projection_receipt_invalid",
            "receipt entries must be a non-empty list",
        )
    previous_path: str | None = None
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            _error(
                "source_projection_receipt_invalid",
                "receipt entries must be objects",
                index=index,
            )
        canonical_path = _relative_path(
            entry.get("canonical_path"), field="canonical_path"
        )
        projected_path = _relative_path(
            entry.get("projected_path"), field="projected_path"
        )
        declared_hash = entry.get("sha256")
        if (
            not isinstance(declared_hash, str)
            or len(declared_hash) != 71
            or not declared_hash.startswith("sha256:")
            or any(char not in "0123456789abcdef" for char in declared_hash[7:])
        ):
            _error(
                "source_projection_receipt_invalid",
                "entry sha256 must be sha256:<64-lowercase-hex>",
                index=index,
            )
        canonical_text = canonical_path.as_posix()
        if previous_path is not None and canonical_text <= previous_path:
            _error(
                "source_projection_receipt_invalid",
                "receipt entries must be sorted and unique by canonical_path",
                index=index,
                canonical_path=canonical_text,
            )
        previous_path = canonical_text
        canonical_file = _under_root(
            canonical_base, canonical_path, field="canonical_path"
        )
        projected_file = _under_root(
            projection_base, projected_path, field="projected_path"
        )
        _reject_symlink_components(
            canonical_file, repository_root, field="canonical_path"
        )
        _reject_symlink_components(
            projected_file, repository_root, field="projected_path"
        )
        _regular_path(
            canonical_file, code="source_projection_stale", field="canonical_path"
        )
        _regular_path(
            projected_file, code="source_projection_stale", field="projected_path"
        )
        if (
            f"sha256:{hash_bytes_fn(canonical_file.read_bytes())}" != declared_hash
            or f"sha256:{hash_bytes_fn(projected_file.read_bytes())}" != declared_hash
        ):
            _error(
                "source_projection_stale",
                "source projection content does not match its declared hash",
                index=index,
                canonical_path=canonical_text,
                projected_path=projected_path.as_posix(),
            )
    return {
        "receipt_digest": f"sha256:{hash_bytes_fn(raw_receipt)}",
        "verified_entry_count": len(entries),
    }
