"""Typed marketplace values used by import and publish workflows."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PluginEntry:
    """A validated local plugin entry from a marketplace document."""

    name: str
    source_path: str
    data: dict[str, Any]


@dataclass(frozen=True)
class Marketplace:
    """A validated marketplace document that preserves unknown fields."""

    name: str
    data: dict[str, Any]
    plugins: tuple[PluginEntry, ...]
