from __future__ import annotations

import json
from typing import Any


def plugin_id(metadata: Any, surface_id: str, *, normalize_slug: Any) -> str:
    return "/".join(
        (
            normalize_slug(metadata.publisher_slug),
            normalize_slug(metadata.plugin_slug),
            normalize_slug(surface_id),
        )
    )


def interface_asset_path(path: str) -> str:
    return path if path.startswith("./") else f"./{path}"


def plugin_manifest(
    metadata: Any,
    surface_id: str,
    version: str,
    branding_assets: dict[str, str],
    *,
    normalize_slug: Any,
    mcp_packaging: Any = None,
) -> dict[str, Any]:
    if mcp_packaging is not None:
        return {
            "author": {"name": mcp_packaging.author_name},
            "description": mcp_packaging.description,
            "interface": mcp_packaging.interface,
            "mcpServers": mcp_packaging.mcp_servers_path,
            "name": mcp_packaging.artifact_name,
            "skills": mcp_packaging.skills_path,
            "version": version,
        }
    interface = {"displayName": metadata.display_name, **metadata.interface}
    if "logo" not in interface and "logo" in branding_assets:
        interface["logo"] = interface_asset_path(branding_assets["logo"])
    if "composerIcon" not in interface and "composer_icon" in branding_assets:
        interface["composerIcon"] = interface_asset_path(
            branding_assets["composer_icon"]
        )
    if "logoDark" not in interface and "dark_logo" in branding_assets:
        interface["logoDark"] = interface_asset_path(branding_assets["dark_logo"])
    payload: dict[str, Any] = {
        "name": normalize_slug(metadata.plugin_slug),
        "version": version,
        "description": metadata.description,
        "author": metadata.author,
        "skills": "./skills/",
        "interface": interface,
    }
    payload.update(metadata.host_metadata)
    return payload


def compute_version(
    request: Any,
    outputs: dict[str, bytes],
    *,
    plugin_id_fn: Any,
    normalize_slug: Any,
    hash_bytes: Any,
    hash_text: Any,
) -> tuple[str, str]:
    computed_plugin_id = plugin_id_fn(
        request.plugin_metadata,
        request.surface_id,
        normalize_slug=normalize_slug,
    )
    version_seed = json.dumps(
        {
            "plugin_id": computed_plugin_id,
            "display_name": request.plugin_metadata.display_name,
            "entries": [
                {"path": path, "hash": hash_bytes(outputs[path])}
                for path in sorted(outputs)
            ],
        },
        sort_keys=True,
    )
    version = request.version_override or f"0.1.0+router.{hash_text(version_seed)[:12]}"
    return computed_plugin_id, version
