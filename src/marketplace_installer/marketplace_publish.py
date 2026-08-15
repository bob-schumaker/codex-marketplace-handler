from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import tomllib
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class MarketplacePublishError(RuntimeError):
    """Raised when marketplace publication inputs are invalid."""


SOURCE_OUTPUT_MANIFEST_NAME = ".agent-corpus-source-map.json"
SOURCE_OUTPUT_MANIFEST_FORMAT = "agent-corpus-source-to-output-v1"
ROUTER_PLUGIN_RECEIPT_NAME = ".router-plugin-packager-source-map.json"
PUBLICATION_METADATA_NAME = ".codex-plugin/publication-metadata.json"
PUBLICATION_METADATA_FORMAT = "router-plugin-publication-metadata-v1"
DEFAULT_MARKETPLACE_POLICY = {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL",
}
DEFAULT_GENERATED_PLUGIN_PARENT = Path(".codex-plugin/router-plugin-packager/generated")
TRANSACTION_SUFFIX = ".codex-marketplace-publish"
PUBLISH_PLAN_FORMAT = "marketplace-publish-plan-v1"
TRANSACTION_ROOT_NAME = ".codex-marketplace-publish-transaction"
RECEIPT_ROOT_NAME = ".codex-marketplace-publish-receipts"
PUBLISH_RECEIPT_FORMAT = "marketplace-publish-receipt-v1"


@dataclass(frozen=True)
class ResolvedMarketplace:
    name: str
    root: Path

    @property
    def manifest_path(self) -> Path:
        return self.root / ".agents" / "plugins" / "marketplace.json"


def default_codex_config_path(home: Path | None = None) -> Path:
    resolved_home = home or Path.home()
    return resolved_home / ".codex" / "config.toml"


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MarketplacePublishError(f"invalid JSON object: {path}") from error
    if not isinstance(payload, dict):
        raise MarketplacePublishError(f"JSON value must be an object: {path}")
    return payload


def marketplace_entries_from_config(config_path: Path) -> dict[str, dict[str, Any]]:
    try:
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise MarketplacePublishError(f"invalid Codex config: {config_path}") from error
    marketplaces = payload.get("marketplaces")
    if not isinstance(marketplaces, dict):
        raise MarketplacePublishError(
            f"Codex config has no marketplaces: {config_path}"
        )
    result: dict[str, dict[str, Any]] = {}
    for name, entry in marketplaces.items():
        if isinstance(name, str) and isinstance(entry, dict):
            result[name] = entry
    return result


def local_marketplace_root_from_entry(
    configured_name: str, entry: dict[str, Any]
) -> Path:
    source_type = entry.get("source_type")
    source = entry.get("source")
    if source_type != "local" or not isinstance(source, str) or not source:
        raise MarketplacePublishError(
            f"marketplace {configured_name} is not a local configured source"
        )
    return Path(source)


def configured_marketplace_display_name(root: Path) -> str | None:
    manifest_path = source_marketplace_manifest_path(root)
    if not manifest_path.is_file():
        return None
    payload = read_json_object(manifest_path)
    interface = payload.get("interface")
    if not isinstance(interface, dict):
        return None
    display_name = interface.get("displayName")
    if not isinstance(display_name, str) or not display_name.strip():
        return None
    return display_name.strip()


def resolve_marketplace_root(
    config_path: Path, marketplace_name: str
) -> ResolvedMarketplace:
    marketplaces = marketplace_entries_from_config(config_path)
    requested_name = marketplace_name.strip()
    entry = marketplaces.get(requested_name)
    if entry is not None:
        return ResolvedMarketplace(
            name=requested_name,
            root=local_marketplace_root_from_entry(requested_name, entry),
        )
    for configured_name, configured_entry in marketplaces.items():
        root = local_marketplace_root_from_entry(configured_name, configured_entry)
        if configured_marketplace_display_name(root) == requested_name:
            return ResolvedMarketplace(name=configured_name, root=root)
    raise MarketplacePublishError(
        f"configured marketplace not found: {marketplace_name}"
    )


def marketplace_plugin_names(manifest: dict[str, Any]) -> set[str]:
    """Return the distinct plugin names declared by a marketplace manifest."""

    plugins = manifest.get("plugins")
    if not isinstance(plugins, list):
        raise MarketplacePublishError("marketplace plugins must be a list")
    names: set[str] = set()
    for entry in plugins:
        if not isinstance(entry, dict):
            raise MarketplacePublishError("marketplace plugin entry must be an object")
        name = entry.get("name")
        if (
            not isinstance(name, str)
            or not name
            or Path(name).name != name
            or name in {".", ".."}
        ):
            raise MarketplacePublishError("marketplace plugin entry must have a name")
        if name in names:
            raise MarketplacePublishError(f"duplicate plugin entry: {name}")
        names.add(name)
    return names


def resolve_existing_local_marketplace(
    config_path: Path, plugin_names: set[str]
) -> ResolvedMarketplace:
    """Resolve the sole local marketplace that already contains every plugin."""

    if not plugin_names:
        raise MarketplacePublishError(
            "marketplace name is required when the publish payload has no plugins"
        )
    candidates: list[ResolvedMarketplace] = []
    for configured_name, entry in marketplace_entries_from_config(config_path).items():
        if entry.get("source_type") != "local":
            continue
        root = local_marketplace_root_from_entry(configured_name, entry)
        manifest_path = source_marketplace_manifest_path(root)
        if not manifest_path.is_file():
            continue
        existing_names = marketplace_plugin_names(load_marketplace_manifest(root))
        if plugin_names.issubset(existing_names):
            candidates.append(ResolvedMarketplace(name=configured_name, root=root))
    requested = ", ".join(sorted(plugin_names))
    if not candidates:
        raise MarketplacePublishError(
            "no configured local marketplace contains plugin(s): "
            f"{requested}; provide --marketplace-name"
        )
    if len(candidates) != 1:
        names = ", ".join(candidate.name for candidate in candidates)
        raise MarketplacePublishError(
            "ambiguous existing local marketplace for plugin(s): "
            f"{requested}; matches {names}; provide --marketplace-name"
        )
    return candidates[0]


def source_marketplace_manifest_path(source_root: Path) -> Path:
    return source_root / ".agents" / "plugins" / "marketplace.json"


def load_marketplace_manifest(root: Path) -> dict[str, Any]:
    manifest_path = source_marketplace_manifest_path(root)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise MarketplacePublishError(
            f"marketplace manifest is missing: {manifest_path}"
        )
    payload = read_json_object(manifest_path)
    plugins = payload.get("plugins")
    if not isinstance(plugins, list):
        raise MarketplacePublishError(
            f"marketplace plugins must be a list: {manifest_path}"
        )
    return payload


def validated_plugin_map(
    root: Path, manifest: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    plugins = manifest.get("plugins")
    if not isinstance(plugins, list):
        raise MarketplacePublishError("marketplace plugins must be a list")
    result: dict[str, dict[str, Any]] = {}
    for entry in plugins:
        if not isinstance(entry, dict):
            raise MarketplacePublishError("marketplace plugin entry must be an object")
        name = entry.get("name")
        source = entry.get("source")
        if (
            not isinstance(name, str)
            or not name
            or Path(name).name != name
            or name in {".", ".."}
        ):
            raise MarketplacePublishError("marketplace plugin entry must have a name")
        if name in result:
            raise MarketplacePublishError(f"duplicate plugin entry: {name}")
        if not isinstance(source, dict):
            raise MarketplacePublishError(
                f"marketplace plugin entry is missing source: {name}"
            )
        expected_source = {"source": "local", "path": f"./plugins/{name}"}
        if source != expected_source:
            raise MarketplacePublishError(
                f"marketplace source is invalid for {name}: {source!r}"
            )
        if entry.get("policy") != DEFAULT_MARKETPLACE_POLICY or not isinstance(
            entry.get("category"), str
        ):
            raise MarketplacePublishError(f"marketplace policy is invalid for {name}")
        plugin_dir = root / "plugins" / name
        if not plugin_dir.is_dir():
            raise MarketplacePublishError(
                f"source plugin directory is missing: {plugin_dir}"
            )
        result[name] = entry
    return result


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _unprefixed_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _tree_digest(root: Path) -> str:
    """Digest regular-file bytes and ordinary modes without following links."""

    _validate_regular_tree(root)
    inventory: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        mode = path.stat(follow_symlinks=False).st_mode & 0o7777
        if mode & 0o7000:
            raise MarketplacePublishError(f"unsafe file mode in plugin tree: {path}")
        inventory.append(
            {
                "path": path.relative_to(root).as_posix(),
                "mode": mode,
                "content_hash": _unprefixed_sha256(path),
            }
        )
    return _sha256_bytes(_canonical_json_bytes({"entries": inventory}))


def _optional_tree_digest(path: Path) -> str | None:
    if not path.exists():
        return None
    return _tree_digest(path)


def _content_tree_digest(root: Path) -> str:
    """Match the packager's authority digest without running its code."""

    _validate_regular_tree(root)
    entries = [
        f"{path.relative_to(root).as_posix()}:{_unprefixed_sha256(path)}"
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
    return hashlib.sha256(
        json.dumps(entries, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _validate_mcp_authority(
    plugin_root: Path, receipt: dict[str, Any]
) -> dict[str, str] | None:
    authority = receipt.get("mcp_authority")
    if authority is None:
        return None
    if not isinstance(authority, dict) or set(authority) != {
        "format",
        "config_path",
        "config_digest",
        "registry_root",
        "registry_digest",
        "toolchain_manifest_digest",
    }:
        raise MarketplacePublishError("generated MCP authority receipt is invalid")
    if authority.get("format") != "router-plugin-mcp-authority-v1":
        raise MarketplacePublishError(
            "generated MCP authority receipt format is invalid"
        )
    config_path = authority.get("config_path")
    registry_root = authority.get("registry_root")
    toolchain_manifest_digest = authority.get("toolchain_manifest_digest")
    if (
        not isinstance(config_path, str)
        or not isinstance(registry_root, str)
        or not isinstance(toolchain_manifest_digest, str)
    ):
        raise MarketplacePublishError("generated MCP authority receipt is invalid")
    config_relative = Path(config_path)
    registry_relative = Path(registry_root)
    if (
        config_relative.is_absolute()
        or registry_relative.is_absolute()
        or ".." in config_relative.parts
        or ".." in registry_relative.parts
    ):
        raise MarketplacePublishError("generated MCP authority receipt is unsafe")
    for repository_root in plugin_root.parents:
        config = repository_root / config_relative
        registry = repository_root / registry_relative
        if config.is_file() and registry.is_dir():
            if (
                _unprefixed_sha256(config) != authority["config_digest"]
                or _content_tree_digest(registry) != authority["registry_digest"]
                or _installed_toolchain_manifest_digest() != toolchain_manifest_digest
            ):
                raise MarketplacePublishError(
                    "generated MCP authority is stale; repackage before publishing"
                )
            return {key: authority[key] for key in sorted(authority)}
    raise MarketplacePublishError(
        "generated MCP authority is unavailable; publish from its source repository"
    )


def _installed_toolchain_manifest_digest() -> str:
    candidates = (
        Path(__file__).parent / "toolchain-manifest.json",
        Path(__file__).parent / "codex-packaging-toolchain-manifest.json",
    )
    for candidate in candidates:
        if candidate.is_file() and not candidate.is_symlink():
            return _unprefixed_sha256(candidate)
    raise MarketplacePublishError("publisher toolchain manifest is unavailable")


def _validate_current_source_inventory(  # noqa: C901
    plugin_root: Path, entries: list[Any]
) -> dict[str, str]:
    """Recheck receipt-declared copied files against the source repository."""

    inventory: list[tuple[Path, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = entry.get("source_reference")
        source_hash = entry.get("source_hash")
        if source_hash is None:
            continue
        if not isinstance(source, str) or not isinstance(source_hash, str):
            raise MarketplacePublishError("generated source receipt is invalid")
        if source.startswith("generated:"):
            raise MarketplacePublishError("generated source receipt is invalid")
        relative = Path(source)
        if relative.is_absolute() or ".." in relative.parts:
            raise MarketplacePublishError("generated source receipt is unsafe")
        inventory.append((relative, source_hash))
    if not inventory:
        return {}
    for repository_root in plugin_root.parents:
        candidates = [repository_root / relative for relative, _digest in inventory]
        if not all(path.is_file() and not path.is_symlink() for path in candidates):
            continue
        current = {
            relative.as_posix(): _unprefixed_sha256(repository_root / relative)
            for relative, _digest in inventory
        }
        expected = {relative.as_posix(): digest for relative, digest in inventory}
        if current != expected:
            raise MarketplacePublishError(
                "generated source inventory is stale; repackage before publishing"
            )
        return current
    raise MarketplacePublishError(
        "generated source inventory is unavailable; publish from its source repository"
    )


def _validate_regular_tree(root: Path) -> None:
    if not root.is_dir() or root.is_symlink():
        raise MarketplacePublishError(f"generated plugin root is invalid: {root}")
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise MarketplacePublishError(
                f"generated plugin contains unsafe path: {path}"
            )


def _validate_generated_plugin_root(
    plugin_root: Path,
) -> tuple[str, str, dict[str, str] | None, dict[str, str]]:
    """Validate one router-packager output before adapting it for publication."""

    _validate_regular_tree(plugin_root)
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    metadata_path = plugin_root / PUBLICATION_METADATA_NAME
    receipt_path = plugin_root / ROUTER_PLUGIN_RECEIPT_NAME
    manifest = read_json_object(manifest_path)
    metadata = read_json_object(metadata_path)
    receipt = read_json_object(receipt_path)
    plugin_name = manifest.get("name")
    if not isinstance(plugin_name, str) or not plugin_name:
        raise MarketplacePublishError(
            f"generated plugin manifest has no name: {manifest_path}"
        )
    if metadata != {
        "category": "Productivity",
        "format": PUBLICATION_METADATA_FORMAT,
        "plugin_slug": plugin_name,
    }:
        raise MarketplacePublishError(
            f"generated publication metadata is invalid: {metadata_path}"
        )
    entries = receipt.get("entries")
    paths = receipt.get("generated_paths")
    if (
        receipt.get("format_version") != 1
        or not isinstance(entries, list)
        or not isinstance(paths, list)
        or ROUTER_PLUGIN_RECEIPT_NAME not in paths
    ):
        raise MarketplacePublishError(
            f"generated plugin receipt is invalid: {receipt_path}"
        )
    for entry in entries:
        if not isinstance(entry, dict):
            raise MarketplacePublishError(
                f"generated plugin receipt is invalid: {receipt_path}"
            )
        relative = entry.get("path")
        digest = entry.get("content_hash")
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise MarketplacePublishError(
                f"generated plugin receipt is invalid: {receipt_path}"
            )
        output = plugin_root / relative
        if (
            Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not output.is_file()
            or output.is_symlink()
            or _unprefixed_sha256(output) != digest
        ):
            raise MarketplacePublishError(f"generated plugin output is stale: {output}")
    source_inventory = _validate_current_source_inventory(plugin_root, entries)
    return (
        plugin_name,
        _sha256(receipt_path),
        _validate_mcp_authority(plugin_root, receipt),
        source_inventory,
    )


def resolve_generated_plugin_root(repository_root: Path) -> Path:
    """Resolve the one generated plugin eligible for wrapper-free publication."""

    parent = repository_root / DEFAULT_GENERATED_PLUGIN_PARENT
    if not parent.is_dir() or parent.is_symlink():
        raise MarketplacePublishError(
            f"generated plugin selection required: {parent} is unavailable"
        )
    candidates: list[Path] = []
    for child in sorted(parent.iterdir()):
        if (
            not child.is_dir()
            or child.is_symlink()
            or not (child / ROUTER_PLUGIN_RECEIPT_NAME).is_file()
            or not (child / PUBLICATION_METADATA_NAME).is_file()
        ):
            continue
        try:
            _validate_generated_plugin_root(child)
        except MarketplacePublishError:
            continue
        candidates.append(child)
    if not candidates:
        raise MarketplacePublishError(
            f"generated plugin selection required: no generated plugin under {parent}"
        )
    if len(candidates) != 1:
        raise MarketplacePublishError(
            f"ambiguous generated plugin selection: {parent} contains {len(candidates)} candidates"
        )
    return candidates[0]


def verify_projected_plugin_freshness(
    plugin_root: Path, plugin_name: str
) -> str | None:
    """Verify a projected plugin has not drifted since its source-map receipt."""

    receipt_path = plugin_root / SOURCE_OUTPUT_MANIFEST_NAME
    if not receipt_path.is_file():
        return None
    receipt = read_json_object(receipt_path)
    if (
        receipt.get("format") != SOURCE_OUTPUT_MANIFEST_FORMAT
        or receipt.get("plugin") != plugin_name
        or not isinstance(receipt.get("entries"), list)
        or not receipt["entries"]
    ):
        raise MarketplacePublishError(
            f"projected plugin source map is invalid: {receipt_path}"
        )
    for entry in receipt["entries"]:
        if not isinstance(entry, dict):
            raise MarketplacePublishError(
                f"projected plugin source map entry is invalid: {receipt_path}"
            )
        destination = entry.get("destination")
        expected_hash = entry.get("content_hash")
        if not isinstance(destination, str) or not isinstance(expected_hash, str):
            raise MarketplacePublishError(
                f"projected plugin source map entry is incomplete: {receipt_path}"
            )
        relative = Path(destination)
        if relative.is_absolute() or ".." in relative.parts:
            raise MarketplacePublishError(
                f"projected plugin source map destination is unsafe: {receipt_path}"
            )
        output = plugin_root / relative
        if (
            not output.is_file()
            or output.is_symlink()
            or _sha256(output) != expected_hash
        ):
            raise MarketplacePublishError(f"projected plugin output is stale: {output}")
    return _sha256(receipt_path)


def merge_marketplace_payload(
    existing: dict[str, Any],
    desired: dict[str, Any],
    *,
    marketplace_name: str,
) -> dict[str, Any]:
    existing_plugins = existing.get("plugins")
    desired_plugins = desired.get("plugins")
    if not isinstance(existing_plugins, list) or not isinstance(desired_plugins, list):
        raise MarketplacePublishError("marketplace plugins must be a list")
    desired_names = {
        entry["name"]
        for entry in desired_plugins
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    preserved = [
        entry
        for entry in existing_plugins
        if not isinstance(entry, dict) or entry.get("name") not in desired_names
    ]
    merged = {**existing, "plugins": [*preserved, *desired_plugins]}
    merged["name"] = marketplace_name
    desired_interface = desired.get("interface")
    existing_interface = existing.get("interface")
    if isinstance(desired_interface, dict):
        if isinstance(existing_interface, dict):
            merged["interface"] = {**existing_interface, **desired_interface}
        else:
            merged["interface"] = desired_interface
    elif isinstance(existing_interface, dict):
        merged["interface"] = existing_interface
    return merged


def default_backup_dir(marketplace_name: str) -> Path:
    return Path(tempfile.gettempdir()) / "codex-marketplace-backups" / marketplace_name


def backup_manifest(
    manifest_path: Path, marketplace_name: str, backup_dir: Path | None
) -> Path:
    directory = backup_dir or default_backup_dir(marketplace_name)
    directory.mkdir(parents=True, exist_ok=True)
    backup_path = directory / f"marketplace.{time.strftime('%Y%m%d%H%M%S')}.json"
    shutil.copy2(manifest_path, backup_path)
    return backup_path


def _transaction_paths(target_root: Path) -> tuple[Path, Path]:
    transaction_root = target_root / TRANSACTION_ROOT_NAME
    return target_root / f"{TRANSACTION_SUFFIX}.lock", transaction_root / "journal.json"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _safe_remove_owned_tree(path: Path) -> None:
    if not path.exists():
        return
    if path.is_symlink() or not path.is_dir():
        raise MarketplacePublishError(f"transaction path is unsafe: {path}")
    _validate_regular_tree(path)
    shutil.rmtree(path)


def _safe_remove_owned_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_symlink():
        raise MarketplacePublishError(f"transaction path is unsafe: {path}")
    if path.is_file():
        path.unlink()
        return
    _safe_remove_owned_tree(path)


def _validate_transaction_path(target_root: Path, path: Path, *, label: str) -> Path:
    candidate = path.absolute()
    target_root = target_root.absolute()
    prefix = f".{target_root.name}{TRANSACTION_SUFFIX}.{label}-"
    if candidate.parent != target_root.parent or not candidate.name.startswith(prefix):
        raise MarketplacePublishError(f"transaction {label} path is unsafe: {path}")
    return candidate


def _validate_no_symlink_ancestors(path: Path) -> None:
    for ancestor in (path.absolute(), *path.absolute().parents):
        if ancestor.is_symlink():
            raise MarketplacePublishError(f"marketplace path is unsafe: {ancestor}")


@contextmanager
def _marketplace_lock(target_root: Path):
    try:
        import fcntl
    except ModuleNotFoundError as error:  # pragma: no cover - Unix host contract.
        raise MarketplacePublishError("marketplace locking is unavailable") from error
    _validate_no_symlink_ancestors(target_root)
    target_root.mkdir(parents=True, exist_ok=True)
    lock_path, _journal_path = _transaction_paths(target_root)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists() and (lock_path.is_symlink() or not lock_path.is_file()):
        raise MarketplacePublishError(f"marketplace lock is unsafe: {lock_path}")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise MarketplacePublishError(
                f"marketplace is locked: {target_root}"
            ) from error
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _recover_interrupted_transaction(target_root: Path) -> None:  # noqa: C901
    _lock_path, journal_path = _transaction_paths(target_root)
    if not journal_path.exists():
        return
    journal = read_json_object(journal_path)
    transaction_root = target_root / TRANSACTION_ROOT_NAME
    if (
        journal.get("format") != "codex-marketplace-transaction-v2"
        or journal.get("target") != str(target_root)
        or journal_path.parent != transaction_root
        or transaction_root.is_symlink()
    ):
        raise MarketplacePublishError(f"transaction journal is invalid: {journal_path}")
    state = journal.get("state")
    states = {
        "prepared",
        "backed_up",
        "plugin_promoted",
        "manifest_promoted",
        "committed_pending_receipt",
        "receipt_persisted",
        "completed",
    }
    if state not in states:
        raise MarketplacePublishError(f"transaction state is invalid: {journal_path}")
    operations = journal.get("operations")
    if not isinstance(operations, list):
        raise MarketplacePublishError(
            f"transaction operations are invalid: {journal_path}"
        )

    def owned_path(raw: Any) -> Path:
        if not isinstance(raw, str):
            raise MarketplacePublishError(
                f"transaction path is invalid: {journal_path}"
            )
        candidate = Path(raw).absolute()
        if transaction_root not in candidate.parents:
            raise MarketplacePublishError(f"transaction path is unsafe: {candidate}")
        return candidate

    if state in {"committed_pending_receipt", "receipt_persisted", "completed"}:
        if state == "committed_pending_receipt":
            raise MarketplacePublishError(
                f"committed without receipt: {journal_path} requires operator recovery"
            )
        for operation in operations:
            if not isinstance(operation, dict):
                raise MarketplacePublishError(
                    f"transaction operation is invalid: {journal_path}"
                )
            for key in ("stage", "backup"):
                path = owned_path(operation.get(key))
                if path.exists():
                    _safe_remove_owned_path(path)
        journal_path.unlink()
        _fsync_directory(transaction_root)
        return

    for operation in operations:
        if not isinstance(operation, dict):
            raise MarketplacePublishError(
                f"transaction operation is invalid: {journal_path}"
            )
        target = Path(operation.get("target", "")).absolute()
        if target_root not in target.parents:
            raise MarketplacePublishError(
                f"transaction target path is unsafe: {target}"
            )
        stage = owned_path(operation.get("stage"))
        backup = owned_path(operation.get("backup"))
        existed = operation.get("existed")
        if not isinstance(existed, bool):
            raise MarketplacePublishError(
                f"transaction presence is invalid: {journal_path}"
            )
        if backup.exists():
            if target.exists():
                _safe_remove_owned_path(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(backup, target)
            _fsync_directory(target.parent)
        elif not existed and target.exists():
            _safe_remove_owned_path(target)
        if stage.exists():
            _safe_remove_owned_path(stage)
    journal_path.unlink()
    _fsync_directory(transaction_root)


def _manifest_digest(path: Path) -> str | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise MarketplacePublishError(f"marketplace manifest is unsafe: {path}")
    return _sha256(path)


def build_publish_plan(
    *,
    source_root: Path,
    target_root: Path,
    marketplace_name: str,
    source_shape: str,
    source_authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the canonical, non-authorizing publication plan for one source."""

    source_root = source_root.absolute()
    target_root = target_root.absolute()
    _validate_no_symlink_ancestors(target_root)
    source_manifest = load_marketplace_manifest(source_root)
    source_plugins = validated_plugin_map(source_root, source_manifest)
    source_freshness = {
        name: verify_projected_plugin_freshness(source_root / "plugins" / name, name)
        for name in sorted(source_plugins)
    }
    target_manifest_path = source_marketplace_manifest_path(target_root)
    if target_manifest_path.exists():
        existing_manifest = read_json_object(target_manifest_path)
        existing_plugins = existing_manifest.get("plugins")
        if not isinstance(existing_plugins, list):
            raise MarketplacePublishError(
                f"marketplace plugins must be a list: {target_manifest_path}"
            )
    else:
        existing_manifest = {"name": marketplace_name, "plugins": []}
    target_entries: dict[str, dict[str, Any] | None] = {}
    for plugin_name in sorted(source_plugins):
        matches = [
            entry
            for entry in existing_manifest["plugins"]
            if isinstance(entry, dict) and entry.get("name") == plugin_name
        ]
        if len(matches) > 1:
            raise MarketplacePublishError(
                f"target marketplace has duplicate plugin entry: {plugin_name}"
            )
        target_entry = matches[0] if matches else None
        target_tree = target_root / "plugins" / plugin_name
        target_tree_digest = _optional_tree_digest(target_tree)
        if target_entry is None and target_tree_digest is not None:
            raise MarketplacePublishError(
                f"target marketplace has an orphaned plugin tree: {plugin_name}"
            )
        if target_entry is not None and target_tree_digest is None:
            raise MarketplacePublishError(
                f"target marketplace has a one-sided plugin entry: {plugin_name}"
            )
        if target_entry is not None and target_entry.get("source") != {
            "source": "local",
            "path": f"./plugins/{plugin_name}",
        }:
            raise MarketplacePublishError(
                f"target marketplace source is invalid for {plugin_name}"
            )
        target_entries[plugin_name] = target_entry
    plan = {
        "format": PUBLISH_PLAN_FORMAT,
        "marketplace_name": marketplace_name,
        "source_shape": source_shape,
        "source_plugins": {
            name: {
                "entry": source_plugins[name],
                "tree_digest": _tree_digest(source_root / "plugins" / name),
                "freshness_digest": source_freshness[name],
            }
            for name in sorted(source_plugins)
        },
        "source_authority": source_authority or {},
        "target": {
            "root": str(target_root),
            "manifest_digest": _manifest_digest(target_manifest_path),
            "plugins": {
                name: {
                    "entry": target_entries[name],
                    "tree_digest": _optional_tree_digest(
                        target_root / "plugins" / name
                    ),
                }
                for name in sorted(source_plugins)
            },
        },
    }
    return {**plan, "plan_digest": _sha256_bytes(_canonical_json_bytes(plan))}


def _require_matching_plan(
    *,
    expected_plan_digest: str | None,
    source_root: Path,
    target_root: Path,
    marketplace_name: str,
    source_shape: str,
    source_authority: dict[str, Any] | None,
) -> dict[str, Any]:
    plan = build_publish_plan(
        source_root=source_root,
        target_root=target_root,
        marketplace_name=marketplace_name,
        source_shape=source_shape,
        source_authority=source_authority,
    )
    if expected_plan_digest is None:
        raise MarketplacePublishError(
            "publish plan digest is required; preview and retry with plan_digest"
        )
    if expected_plan_digest != plan["plan_digest"]:
        raise MarketplacePublishError("repreview required: publish plan changed")
    return plan


def publish_marketplace(  # noqa: C901
    *,
    source_root: Path,
    target_root: Path,
    marketplace_name: str,
    backup_dir: Path | None = None,
    dry_run: bool = False,
    plan_digest: str | None = None,
    source_shape: str = "marketplace-source",
    source_authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_root = source_root.absolute()
    target_root = target_root.absolute()
    plan = build_publish_plan(
        source_root=source_root,
        target_root=target_root,
        marketplace_name=marketplace_name,
        source_shape=source_shape,
        source_authority=source_authority,
    )
    source_manifest = load_marketplace_manifest(source_root)
    source_plugins = validated_plugin_map(source_root, source_manifest)
    source_freshness = {
        name: plan["source_plugins"][name]["freshness_digest"]
        for name in sorted(source_plugins)
    }
    target_manifest_path = source_marketplace_manifest_path(target_root)
    if target_manifest_path.exists():
        existing_manifest = read_json_object(target_manifest_path)
        existing_plugins = existing_manifest.get("plugins")
        if not isinstance(existing_plugins, list):
            raise MarketplacePublishError(
                f"marketplace plugins must be a list: {target_manifest_path}"
            )
    else:
        existing_manifest = {"name": marketplace_name, "plugins": []}
    merged_manifest = merge_marketplace_payload(
        existing_manifest,
        source_manifest,
        marketplace_name=marketplace_name,
    )
    replacing = sorted(
        set(source_plugins)
        & {
            entry.get("name")
            for entry in existing_manifest.get("plugins", [])
            if isinstance(entry, dict)
        }
    )
    preserving = sorted(
        entry.get("name")
        for entry in existing_manifest.get("plugins", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("name"), str)
        and entry["name"] not in source_plugins
    )
    result = {
        "marketplace_name": marketplace_name,
        "source_root": str(source_root),
        "target_root": str(target_root),
        "source_plugins": sorted(source_plugins),
        "source_freshness": source_freshness,
        "replacing_plugins": replacing,
        "preserving_plugins": preserving,
        "backup_path": None,
        "wrote_manifest": not dry_run,
        "plan": plan,
        "plan_digest": plan["plan_digest"],
    }
    if dry_run:
        return result

    with _marketplace_lock(target_root):
        _recover_interrupted_transaction(target_root)
        _require_matching_plan(
            expected_plan_digest=plan_digest,
            source_root=source_root,
            target_root=target_root,
            marketplace_name=marketplace_name,
            source_shape=source_shape,
            source_authority=source_authority,
        )
        target_manifest_path = source_marketplace_manifest_path(target_root)
        if target_root.exists():
            _validate_regular_tree(target_root)
            existing_manifest = (
                read_json_object(target_manifest_path)
                if target_manifest_path.exists()
                else {"name": marketplace_name, "plugins": []}
            )
        else:
            existing_manifest = {"name": marketplace_name, "plugins": []}
        merged_manifest = merge_marketplace_payload(
            existing_manifest,
            source_manifest,
            marketplace_name=marketplace_name,
        )
        token = uuid.uuid4().hex
        transaction_root = target_root / TRANSACTION_ROOT_NAME
        transaction_root.mkdir(exist_ok=True)
        operation_root = transaction_root / token
        stage_root = operation_root / "stage"
        backup_root = operation_root / "backup"
        stage_root.mkdir(parents=True)
        backup_root.mkdir(parents=True)
        _lock_path, journal_path = _transaction_paths(target_root)
        stage_plugins_root = stage_root / "plugins"
        stage_plugins_root.mkdir(parents=True, exist_ok=True)
        operations: list[dict[str, Any]] = []
        for plugin_name in sorted(source_plugins):
            src = source_root / "plugins" / plugin_name
            _validate_regular_tree(src)
            dst = stage_plugins_root / plugin_name
            shutil.copytree(src, dst)
            target_plugin = target_root / "plugins" / plugin_name
            operations.append(
                {
                    "kind": "plugin",
                    "target": str(target_plugin),
                    "stage": str(dst),
                    "backup": str(backup_root / "plugins" / plugin_name),
                    "existed": target_plugin.exists(),
                }
            )
        stage_manifest_path = source_marketplace_manifest_path(stage_root)
        _write_json_atomic(stage_manifest_path, merged_manifest)
        operations.append(
            {
                "kind": "manifest",
                "target": str(target_manifest_path),
                "stage": str(stage_manifest_path),
                "backup": str(backup_root / "marketplace.json"),
                "existed": target_manifest_path.exists(),
            }
        )
        journal = {
            "format": "codex-marketplace-transaction-v2",
            "state": "prepared",
            "target": str(target_root),
            "operations": operations,
            "plan_digest": plan["plan_digest"],
        }
        _write_json_atomic(journal_path, journal)
        backup_path: Path | None = None
        receipt_path: Path | None = None
        try:
            if target_manifest_path.exists():
                backup_path = backup_manifest(
                    target_manifest_path,
                    marketplace_name=marketplace_name,
                    backup_dir=backup_dir,
                )
            for operation in operations:
                target = Path(operation["target"])
                backup = Path(operation["backup"])
                if target.exists():
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(target, backup)
                    _fsync_directory(target.parent)
            journal["state"] = "backed_up"
            _write_json_atomic(journal_path, journal)
            for operation in operations:
                if operation["kind"] != "plugin":
                    continue
                target = Path(operation["target"])
                stage = Path(operation["stage"])
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(stage, target)
                _fsync_directory(target.parent)
            journal["state"] = "plugin_promoted"
            _write_json_atomic(journal_path, journal)
            manifest_operation = operations[-1]
            target_manifest = Path(manifest_operation["target"])
            target_manifest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(Path(manifest_operation["stage"]), target_manifest)
            _fsync_directory(target_manifest.parent)
            journal["state"] = "manifest_promoted"
            _write_json_atomic(journal_path, journal)
            journal["state"] = "committed_pending_receipt"
            _write_json_atomic(journal_path, journal)
            receipt_path = (
                target_root / RECEIPT_ROOT_NAME / token / "publish-receipt.json"
            )
            receipt = {
                "format": PUBLISH_RECEIPT_FORMAT,
                "plan_digest": plan["plan_digest"],
                "source_shape": source_shape,
                "source_plugins": sorted(source_plugins),
                "source_authority": source_authority or {},
                "staged_tree_digests": {
                    name: _tree_digest(target_root / "plugins" / name)
                    for name in sorted(source_plugins)
                },
                "target_manifest_digest": _sha256(target_manifest),
                "target_root": str(target_root),
                "transaction_state": "receipt_persisted",
                "merge_result": {
                    "replacing_plugins": replacing,
                    "preserving_plugins": preserving,
                },
            }
            _write_json_atomic(receipt_path, receipt)
            journal["state"] = "receipt_persisted"
            _write_json_atomic(journal_path, journal)
            for operation in operations:
                _safe_remove_owned_path(Path(operation["backup"]))
                _safe_remove_owned_path(Path(operation["stage"]))
            journal["state"] = "completed"
            _write_json_atomic(journal_path, journal)
            journal_path.unlink()
            _fsync_directory(transaction_root)
        except Exception:
            _recover_interrupted_transaction(target_root)
            raise
    result["backup_path"] = str(backup_path) if backup_path is not None else None
    result["publish_receipt_path"] = str(receipt_path) if receipt_path else None
    return result


def publish_generated_plugin(
    *,
    plugin_root: Path,
    target_root: Path,
    marketplace_name: str,
    backup_dir: Path | None = None,
    dry_run: bool = False,
    plan_digest: str | None = None,
) -> dict[str, Any]:
    """Publish one validated router-packager output without a client wrapper."""

    plugin_root = plugin_root.absolute()
    (
        plugin_name,
        receipt_digest,
        mcp_authority,
        source_inventory,
    ) = _validate_generated_plugin_root(plugin_root)
    publication_metadata_digest = _sha256(plugin_root / PUBLICATION_METADATA_NAME)
    generated_tree_digest = _tree_digest(plugin_root)
    source_authority = {
        "selected_plugin_root": str(plugin_root),
        "generated_tree_digest": generated_tree_digest,
        "router_receipt_digest": receipt_digest,
        "publication_metadata_digest": publication_metadata_digest,
        "source_inventory": source_inventory,
    }
    if mcp_authority is not None:
        source_authority["mcp_authority"] = mcp_authority
    with tempfile.TemporaryDirectory(prefix="codex-marketplace-source-") as temp_dir:
        source_root = Path(temp_dir)
        staged_root = source_root / "plugins" / plugin_name
        staged_root.parent.mkdir(parents=True)
        shutil.copytree(plugin_root, staged_root, symlinks=False)
        manifest_path = source_marketplace_manifest_path(source_root)
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "name": marketplace_name,
                    "plugins": [
                        {
                            "name": plugin_name,
                            "source": {
                                "source": "local",
                                "path": f"./plugins/{plugin_name}",
                            },
                            "policy": DEFAULT_MARKETPLACE_POLICY,
                            "category": "Productivity",
                        }
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        result = publish_marketplace(
            source_root=source_root,
            target_root=target_root,
            marketplace_name=marketplace_name,
            backup_dir=backup_dir,
            dry_run=dry_run,
            plan_digest=plan_digest,
            source_shape="generated-plugin-tree",
            source_authority=source_authority,
        )
    return {
        **result,
        "source_shape": "generated-plugin-tree",
        "selected_plugin_root": str(plugin_root),
        "router_receipt_digest": receipt_digest,
        "publication_metadata_digest": publication_metadata_digest,
        "generated_tree_digest": generated_tree_digest,
    }
