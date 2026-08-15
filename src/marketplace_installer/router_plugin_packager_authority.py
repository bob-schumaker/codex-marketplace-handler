from __future__ import annotations

from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


def mcp_authority_identity(
    request: Any,
    *,
    config_name: str,
    load_json: Any,
    resolve_local_path: Any,
    validate_relative_path: Any,
    hash_bytes: Any,
    hash_tree: Any,
    toolchain_manifest_candidates: tuple[Path, ...],
) -> dict[str, str] | None:
    """Bind a standard MCP output to its durable, client-owned authority."""

    config_path = request.repository_root / config_name
    if not config_path.is_file():
        return None
    config = load_json(config_path)
    registry_root_value = config.get("registry_root")
    if not isinstance(registry_root_value, str) or not registry_root_value:
        raise PackagerError(
            "invalid_mcp_authority",
            "router-plugin-config.json must declare registry_root",
            {"path": str(config_path)},
        )
    registry_root = resolve_local_path(request.repository_root, registry_root_value)
    validate_relative_path(request.repository_root, registry_root, "registry_root")
    if not registry_root.is_dir() or registry_root.is_symlink():
        raise PackagerError(
            "invalid_mcp_authority",
            "router-plugin-config.json registry_root must be a regular directory",
            {"path": str(registry_root)},
        )
    toolchain_manifest = next(
        (path for path in toolchain_manifest_candidates if path.is_file()), None
    )
    if toolchain_manifest is None:
        raise PackagerError(
            "toolchain_manifest_missing",
            "packager toolchain manifest is unavailable",
            {"candidates": [str(path) for path in toolchain_manifest_candidates]},
        )
    return {
        "format": "router-plugin-mcp-authority-v1",
        "config_path": config_name,
        "config_digest": hash_bytes(config_path.read_bytes()),
        "registry_root": registry_root.relative_to(request.repository_root).as_posix(),
        "registry_digest": hash_tree(registry_root),
        "toolchain_manifest_digest": hash_bytes(toolchain_manifest.read_bytes()),
    }
