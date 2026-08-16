"""Shared router-packager constants for shipped toolchain scripts."""

from __future__ import annotations

from pathlib import Path


__all__ = [
    "DECISION_STATE_DIR",
    "PUBLICATION_METADATA_NAME",
    "RECEIPT_NAME",
    "REQUIRED_MARKER_PREFIX",
]


RECEIPT_NAME = ".router-plugin-packager-source-map.json"
PUBLICATION_METADATA_NAME = ".codex-plugin/publication-metadata.json"
DECISION_STATE_DIR = Path(".codex-plugin") / "router-plugin-packager"
REQUIRED_MARKER_PREFIX = "__REQUIRED__:"
