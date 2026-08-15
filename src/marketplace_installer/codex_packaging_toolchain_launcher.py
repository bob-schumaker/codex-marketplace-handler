#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyYAML==6.0.3", "packaging==26.3"]
# ///
"""Validate and dispatch the projected Codex packaging toolchain."""

from __future__ import annotations

import hashlib
import json
import os
import runpy
import site
import sys
import sysconfig
from pathlib import Path
from typing import Any


ENTRYPOINTS = {
    "router-packager": "router_plugin_packager.py",
    "router-first-user-flow": "router_plugin_first_user_flow.py",
    "mcp-customer-flow": "mcp_plugin_packaging_customer_flow.py",
    "mcp-setup": "router_plugin_packager_setup.py",
    "runtime-lifecycle": "plugin_runtime_lifecycle.py",
}
LAYER1_PROTOCOL_VERSION = "1.0.0"


class ToolchainError(Exception):
    """Raised when the projected toolchain is incomplete or unsafe."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / "toolchain-manifest.json"
    if not path.is_file() or path.is_symlink():
        raise ToolchainError(
            "toolchain_manifest_missing", "toolchain manifest is missing"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ToolchainError(
            "toolchain_manifest_invalid", "toolchain manifest is invalid"
        ) from error
    if not isinstance(payload, dict) or payload.get("format_version") != 1:
        raise ToolchainError(
            "toolchain_manifest_invalid", "toolchain manifest format is unsupported"
        )
    if payload.get("layer1_protocol_version") != LAYER1_PROTOCOL_VERSION:
        raise ToolchainError(
            "toolchain_protocol_incompatible", "toolchain protocol is unsupported"
        )
    files = payload.get("files")
    if not isinstance(files, list):
        raise ToolchainError(
            "toolchain_manifest_invalid", "toolchain file inventory is invalid"
        )
    return payload


def _validate(root: Path, manifest: dict[str, Any]) -> None:
    if root != root.resolve() or root.is_symlink():
        raise ToolchainError(
            "toolchain_root_invalid", "toolchain root must be canonical"
        )
    listed: set[str] = set()
    for item in manifest["files"]:
        if not isinstance(item, dict):
            raise ToolchainError(
                "toolchain_manifest_invalid", "toolchain entry is invalid"
            )
        name = item.get("path")
        digest = item.get("sha256")
        candidate_path = Path(name) if isinstance(name, str) else None
        if (
            candidate_path is None
            or candidate_path.is_absolute()
            or any(part == ".." for part in candidate_path.parts)
            or not candidate_path.parts
            or candidate_path.as_posix() in listed
        ):
            raise ToolchainError(
                "toolchain_manifest_invalid", "toolchain path is invalid"
            )
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise ToolchainError(
                "toolchain_manifest_invalid", "toolchain digest is invalid"
            )
        expected_digest = digest.removeprefix("sha256:")
        if len(expected_digest) != 64:
            raise ToolchainError(
                "toolchain_manifest_invalid", "toolchain digest is invalid"
            )
        candidate = root / candidate_path
        if (
            not candidate.is_file()
            or candidate.is_symlink()
            or _sha256(candidate) != expected_digest
        ):
            raise ToolchainError(
                "toolchain_integrity_mismatch",
                f"toolchain file is invalid: {candidate_path.as_posix()}",
            )
        listed.add(candidate_path.as_posix())
    required = set(ENTRYPOINTS.values()) | {Path(__file__).name}
    if not required.issubset(listed):
        raise ToolchainError(
            "toolchain_manifest_incomplete", "toolchain inventory is incomplete"
        )


def _version_in_range(version: str, version_range: str) -> bool:
    """Evaluate the intentionally small comparator grammar used by the bundle."""

    try:
        value = tuple(int(part) for part in version.split("."))
        constraints = [part.strip() for part in version_range.split(",")]
        for constraint in constraints:
            if constraint.startswith(">="):
                if value < tuple(int(part) for part in constraint[2:].split(".")):
                    return False
            elif constraint.startswith("<"):
                if value >= tuple(int(part) for part in constraint[1:].split(".")):
                    return False
            else:
                return False
    except ValueError:
        return False
    return bool(constraints)


def _validate_entrypoint_compatibility(
    manifest: dict[str, Any], entrypoint: str
) -> None:
    for item in manifest["files"]:
        if item.get("path") != entrypoint:
            continue
        version_range = item.get("layer1_protocol")
        if version_range is None:
            return
        if not isinstance(version_range, str) or not _version_in_range(
            LAYER1_PROTOCOL_VERSION, version_range
        ):
            raise ToolchainError(
                "toolchain_extension_incompatible",
                "toolchain extension is incompatible with the Layer 1 protocol",
            )
        return
    raise ToolchainError(
        "toolchain_manifest_incomplete", "toolchain entrypoint is missing"
    )


def _runtime_import_paths() -> list[str]:
    """Retain interpreter-owned libraries while excluding consumer/checkout paths."""

    candidates = {
        sysconfig.get_path("stdlib"),
        sysconfig.get_path("platstdlib"),
        sysconfig.get_config_var("DESTSHARED"),
        *site.getsitepackages(),
    }
    return [str(Path(path).resolve()) for path in sorted(candidates) if path]


def _run(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in ENTRYPOINTS:
        raise ToolchainError(
            "toolchain_usage",
            "choose router-packager, router-first-user-flow, mcp-customer-flow, "
            "mcp-setup, or runtime-lifecycle",
        )
    root = Path(__file__).resolve().parent
    manifest = _load_manifest(root)
    _validate(root, manifest)
    entrypoint = root / ENTRYPOINTS[argv[1]]
    _validate_entrypoint_compatibility(manifest, entrypoint.name)
    os.environ.pop("PYTHONPATH", None)
    sys.path[:] = [str(root), *_runtime_import_paths()]
    sys.argv = [str(entrypoint), *argv[2:]]
    runpy.run_path(str(entrypoint), run_name="__main__")
    return 0


def main() -> int:
    try:
        return _run(sys.argv)
    except ToolchainError as error:
        print(
            json.dumps({"error_code": error.code, "message": error.message}),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
