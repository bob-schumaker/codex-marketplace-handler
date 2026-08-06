"""Repository-only marketplace import support."""

from __future__ import annotations

import copy
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from .models import Marketplace, PluginEntry
from .validation import (
    MarketplaceValidationError,
    parse_marketplace_json,
    resolve_plugin_directory,
)


class ImportError(RuntimeError):
    """Raised when a marketplace cannot be safely embedded as package data."""


def main(
    argv: Sequence[str] | None = None,
    *,
    home: Path | None = None,
    package_resources: Path | None = None,
) -> int:
    """Run the repository-only marketplace import command."""
    parser = argparse.ArgumentParser(prog="import_marketplace.py")
    parser.add_argument("marketplace_name")
    parser.add_argument("plugins", nargs="*")
    args = parser.parse_args(argv)

    effective_home = home or Path.home()
    source_root = (
        effective_home / ".codex" / "local-marketplaces" / args.marketplace_name
    )
    destination = package_resources or _repository_package_resources()
    try:
        marketplace = import_marketplace(
            source_root,
            destination,
            selected_plugins=args.plugins,
            expected_name=args.marketplace_name,
        )
    except ImportError as error:
        print(f"import_marketplace.py: {error}", file=sys.stderr)
        return 1

    print(f"Imported marketplace {marketplace.name} into {destination}")
    return 0


def import_marketplace(
    marketplace_root: Path,
    package_resources: Path,
    selected_plugins: Sequence[str] | None = None,
    expected_name: str | None = None,
) -> Marketplace:
    """Copy a local marketplace payload into repository package resources."""
    catalog_path = marketplace_root / ".agents" / "plugins" / "marketplace.json"
    try:
        raw_catalog = catalog_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ImportError(
            f"marketplace catalog does not exist: {catalog_path}"
        ) from error

    try:
        marketplace = parse_marketplace_json(raw_catalog)
    except MarketplaceValidationError as error:
        raise ImportError(str(error)) from error

    if expected_name is not None and marketplace.name != expected_name:
        raise ImportError(
            f"marketplace name does not match requested name: {expected_name}"
        )

    selected_entries = _select_entries(marketplace, selected_plugins)
    _validate_source_trees(marketplace_root, selected_entries)
    _replace_package_resources(
        package_resources,
        _filtered_catalog(marketplace, selected_entries),
        selected_entries,
        marketplace_root,
    )
    return marketplace


def _select_entries(
    marketplace: Marketplace, selected_plugins: Sequence[str] | None
) -> tuple[PluginEntry, ...]:
    if not selected_plugins:
        return marketplace.plugins

    by_name = {entry.name: entry for entry in marketplace.plugins}
    unknown = [name for name in selected_plugins if name not in by_name]
    if unknown:
        raise ImportError(f"unknown plugin: {unknown[0]}")
    return tuple(
        entry for entry in marketplace.plugins if entry.name in selected_plugins
    )


def _validate_source_trees(
    marketplace_root: Path, entries: Sequence[PluginEntry]
) -> None:
    for entry in entries:
        try:
            plugin_directory = resolve_plugin_directory(
                marketplace_root, entry.source_path
            )
        except MarketplaceValidationError as error:
            raise ImportError(str(error)) from error
        if not plugin_directory.is_dir():
            raise ImportError(f"plugin directory does not exist: {plugin_directory}")
        _assert_regular_tree(plugin_directory)


def _filtered_catalog(
    marketplace: Marketplace, entries: Sequence[PluginEntry]
) -> dict[str, object]:
    document = copy.deepcopy(marketplace.data)
    document["plugins"] = [entry.data for entry in entries]
    return document


def _replace_package_resources(
    destination: Path,
    catalog: dict[str, object],
    entries: Sequence[PluginEntry],
    marketplace_root: Path,
) -> None:
    if destination.is_symlink():
        raise ImportError("package resources must not be a symlink")

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
    )
    staged_resources = staging_parent / destination.name
    try:
        staged_resources.mkdir()
        (staged_resources / "plugins").mkdir()
        _copy_resource_package_marker(destination, staged_resources)
        (staged_resources / "marketplace.json").write_text(
            json.dumps(catalog, indent=2) + "\n", encoding="utf-8"
        )
        for entry in entries:
            source = resolve_plugin_directory(marketplace_root, entry.source_path)
            _copy_regular_tree(source, staged_resources / "plugins" / entry.name)
        _atomically_replace_directory(staged_resources, destination)
    except OSError as error:
        raise ImportError(
            f"failed to copy marketplace package data: {error}"
        ) from error
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)


def _copy_resource_package_marker(destination: Path, staged_resources: Path) -> None:
    marker = destination / "__init__.py"
    if not marker.exists():
        return
    if marker.is_symlink() or not marker.is_file():
        raise ImportError("resource package marker must be a regular file")
    shutil.copy2(marker, staged_resources / "__init__.py")


def _atomically_replace_directory(staged: Path, destination: Path) -> None:
    backup = destination.parent / f".{destination.name}-backup"
    if backup.exists():
        shutil.rmtree(backup)
    if destination.exists():
        destination.replace(backup)
    try:
        staged.replace(destination)
    except OSError:
        if backup.exists() and not destination.exists():
            backup.replace(destination)
        raise
    else:
        shutil.rmtree(backup, ignore_errors=True)


def _assert_regular_tree(root: Path) -> None:
    if root.is_symlink():
        raise ImportError("plugin source must not contain a symlink")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ImportError("plugin source must not contain a symlink")
        if not path.is_dir() and not path.is_file():
            raise ImportError(f"plugin source contains unsupported file: {path}")


def _copy_regular_tree(source: Path, destination: Path) -> None:
    _assert_regular_tree(source)
    destination.mkdir(parents=True)
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir()
        else:
            shutil.copy2(path, target)


def _repository_package_resources() -> Path:
    return Path(__file__).parents[2] / "src" / "marketplace_publisher" / "resources"
