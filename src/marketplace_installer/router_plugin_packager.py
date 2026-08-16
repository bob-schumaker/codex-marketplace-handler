#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["packaging==26.3", "PyYAML==6.0.3"]
# ///
"""Public CLI facade for the router-plugin packager."""

from __future__ import annotations

from pathlib import Path as _Path
from typing import Any as _Any

from marketplace_installer.router_plugin_packager_engine import main as _engine_main
from marketplace_installer.router_plugin_packager_engine import run as _engine_run
from marketplace_installer.router_plugin_packager_errors import PackagerError


__all__ = ["PackagerError", "main", "run"]


def run(command: str, invocation_path: _Path, repo_root: _Path) -> dict[str, _Any]:
    """Run the documented router-plugin packager operation."""
    return _engine_run(command, invocation_path, repo_root)


def main(argv: list[str] | None = None) -> int:
    """Run the router-plugin-packager command-line interface."""
    return _engine_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
