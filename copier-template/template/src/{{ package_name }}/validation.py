"""Validation for marketplace documents and local plugin paths."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from .models import Marketplace, PluginEntry

_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class MarketplaceValidationError(ValueError):
    """Raised when marketplace data cannot be safely imported or published."""


def parse_marketplace_json(raw: str) -> Marketplace:
    """Parse and validate a marketplace JSON document."""
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise MarketplaceValidationError("marketplace must be valid JSON") from error

    return validate_marketplace_document(document)


def validate_marketplace_document(document: object) -> Marketplace:
    """Validate document structure while preserving unrecognized metadata."""
    if not isinstance(document, dict):
        raise MarketplaceValidationError("marketplace must be a JSON object")

    name = document.get("name")
    if not _is_valid_name(name):
        raise MarketplaceValidationError("invalid marketplace name")

    plugins_data = document.get("plugins")
    if not isinstance(plugins_data, list):
        raise MarketplaceValidationError("marketplace plugins must be a list")

    seen_names: set[str] = set()
    plugins: list[PluginEntry] = []
    for entry in plugins_data:
        plugin = _validate_plugin_entry(entry)
        if plugin.name in seen_names:
            raise MarketplaceValidationError(f"duplicate plugin name: {plugin.name}")
        seen_names.add(plugin.name)
        plugins.append(plugin)

    return Marketplace(name=name, data=document, plugins=tuple(plugins))


def resolve_plugin_directory(marketplace_root: Path, source_path: str) -> Path:
    """Resolve a safe local plugin source without following symlinks."""
    _validate_plugin_source_path(source_path)
    relative_path = PurePosixPath(source_path.removeprefix("./"))
    plugin_path = marketplace_root.joinpath(*relative_path.parts)

    checked_paths = (marketplace_root, marketplace_root / "plugins", plugin_path)
    if any(path.is_symlink() for path in checked_paths):
        raise MarketplaceValidationError("plugin source must not contain a symlink")

    return plugin_path


def _validate_plugin_entry(entry: object) -> PluginEntry:
    if not isinstance(entry, dict):
        raise MarketplaceValidationError("plugin entry must be an object")

    name = entry.get("name")
    if not _is_valid_name(name):
        raise MarketplaceValidationError("invalid plugin name")

    source = entry.get("source")
    if not isinstance(source, dict) or source.get("source") != "local":
        raise MarketplaceValidationError("invalid plugin source")

    source_path = source.get("path")
    if not isinstance(source_path, str):
        raise MarketplaceValidationError("invalid plugin source")
    _validate_plugin_source_path(source_path)
    if source_path != f"./plugins/{name}":
        raise MarketplaceValidationError("invalid plugin source path")

    return PluginEntry(name=name, source_path=source_path, data=entry)


def _validate_plugin_source_path(source_path: str) -> None:
    path = PurePosixPath(source_path)
    parts = source_path.split("/")
    if (
        len(parts) != 3
        or parts[:2] != [".", "plugins"]
        or not parts[2]
        or path.is_absolute()
        or ".." in path.parts
    ):
        raise MarketplaceValidationError("invalid plugin source path")


def _is_valid_name(value: Any) -> bool:
    return isinstance(value, str) and bool(_NAME_PATTERN.fullmatch(value))
