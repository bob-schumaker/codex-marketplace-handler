from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


__all__ = ["canonical_json_bytes", "hash_bytes", "hash_tree"]


def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def hash_text(content: str) -> str:
    return hash_bytes(content.encode("utf-8"))


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def hash_tree(root: Path) -> str:
    entries: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PackagerError(
                "invalid_payload_asset",
                "pre_generated source tree may not contain symlinks",
                {"path": str(path.relative_to(root))},
            )
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        entries.append(f"{relative}:{hash_bytes(path.read_bytes())}")
    return hash_text(json.dumps(entries, sort_keys=True))
