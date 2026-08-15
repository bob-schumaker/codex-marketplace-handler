from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_plugin_metadata(
    invocation: Any,
    repository_root: Path,
    bootstrap_state: dict[str, Any] | None,
    *,
    resolve_branding_assets_fn: Any,
    normalize_slug: Any,
    display_name_from_slug: Any,
    load_source_plugin_manifest: Any,
    plugin_metadata_factory: Any,
    plugin_slug_default: str | None = None,
    display_name_default: str | None = None,
    role_default: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    branding_assets, branding_info = resolve_branding_assets_fn(
        invocation, repository_root, bootstrap_state
    )
    repo_slug = normalize_slug(repository_root.name)
    plugin_slug = normalize_slug(
        invocation.plugin_slug_override or plugin_slug_default or repo_slug
    )
    display_name = (
        invocation.display_name_override
        or display_name_default
        or display_name_from_slug(plugin_slug)
    )
    bootstrap_publisher = None
    if bootstrap_state:
        raw = bootstrap_state.get("publisher_slug")
        if isinstance(raw, str) and raw.strip():
            bootstrap_publisher = raw
    publisher_slug = normalize_slug(
        invocation.publisher_slug_override or bootstrap_publisher or "local"
    )
    source_manifest = load_source_plugin_manifest(
        repository_root, invocation.source_manifest
    )
    source_description = source_manifest.get("description")
    description = (
        source_description.strip()
        if isinstance(source_description, str) and source_description.strip()
        else f"{display_name} skills."
    )
    source_author = source_manifest.get("author")
    author = (
        dict(source_author)
        if isinstance(source_author, dict)
        and isinstance(source_author.get("name"), str)
        and source_author["name"].strip()
        else {"name": publisher_slug}
    )
    host_metadata = {
        key: source_manifest[key]
        for key in ("homepage", "repository", "license", "keywords")
        if key in source_manifest
    }
    source_interface = source_manifest.get("interface")
    metadata = plugin_metadata_factory(
        publisher_slug=publisher_slug,
        plugin_slug=plugin_slug,
        display_name=display_name,
        description=description,
        author=author,
        host_metadata=host_metadata,
        packaging_mode="router-surface",
        role=role_default,
        branding_assets=branding_assets,
        interface=dict(source_interface) if isinstance(source_interface, dict) else {},
    )
    sources = {
        "publisher_slug": "override"
        if invocation.publisher_slug_override
        else ("bootstrap_state" if bootstrap_publisher else "default"),
        "plugin_slug": "override" if invocation.plugin_slug_override else "derived",
        "display_name": "override" if invocation.display_name_override else "derived",
        "host_metadata": "source_plugin_manifest" if source_manifest else "default",
        "branding_assets": branding_info["sources"]["branding_assets"],
    }
    return metadata, {
        "plugin_metadata_sources": sources,
        "rejected_candidates": branding_info["rejected_candidates"],
    }
