"""The packaged installer carries the complete v3 router-packager closure."""

from __future__ import annotations

import importlib
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from marketplace_installer import codex_packaging_toolchain_launcher


PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "marketplace_installer"
ENTRYPOINT_MATRIX = (
    Path(__file__).parent / "fixtures" / "toolchain-entrypoint-matrix.json"
)

V3_MODULES = (
    "codex_packaging_toolchain_launcher",
    "mcp_plugin_packaging_customer_flow",
    "marketplace_publish",
    "plugin_runtime_lifecycle",
    "router_plugin_first_user_flow",
    "router_plugin_packager",
    "router_plugin_packager_authority",
    "router_plugin_packager_branding",
    "router_plugin_packager_catalog",
    "router_plugin_packager_constants",
    "router_plugin_packager_engine",
    "router_plugin_packager_control",
    "router_plugin_packager_errors",
    "router_plugin_packager_hashing",
    "router_plugin_packager_invocation",
    "router_plugin_packager_io",
    "router_plugin_packager_manifest",
    "router_plugin_packager_mcp",
    "router_plugin_packager_mcp_normalization",
    "router_plugin_packager_metadata",
    "router_plugin_packager_native",
    "router_plugin_packager_normalization",
    "router_plugin_packager_outputs",
    "router_plugin_packager_parsing",
    "router_plugin_packager_payloads",
    "router_plugin_packager_receipts",
    "router_plugin_packager_release",
    "router_plugin_packager_runtime",
    "router_plugin_packager_script_loading",
    "router_plugin_packager_source",
    "router_plugin_packager_source_projection",
    "router_plugin_packager_staging",
    "router_plugin_packager_text",
    "router_plugin_packager_setup",
)


def test_v3_router_packager_closure_is_packaged_without_source_repo_imports() -> None:
    for module_name in V3_MODULES:
        source = PACKAGE_ROOT / f"{module_name}.py"
        assert source.is_file(), source
        assert "from installers." not in source.read_text(encoding="utf-8")
        importlib.import_module(f"marketplace_installer.{module_name}")


def test_v3_toolchain_manifest_is_package_data() -> None:
    assert (PACKAGE_ROOT / "codex-packaging-toolchain-manifest.json").is_file()
    manifest = codex_packaging_toolchain_launcher._load_manifest(PACKAGE_ROOT)
    codex_packaging_toolchain_launcher._validate(PACKAGE_ROOT, manifest)


def test_router_packager_facade_exports_only_the_documented_seam() -> None:
    facade = PACKAGE_ROOT / "router_plugin_packager.py"
    tree = ast.parse(facade.read_text(encoding="utf-8"), filename=str(facade))
    public_import_bindings = {
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if (alias.asname or alias.name) != "annotations"
        and not (alias.asname or alias.name).startswith("_")
    }
    public_definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    }

    module = importlib.import_module("marketplace_installer.router_plugin_packager")
    assert module.__all__ == ["PackagerError", "main", "run"]
    assert public_import_bindings == {"PackagerError"}
    assert public_definitions == {"main", "run"}


def test_projected_toolchain_runs_every_declared_entrypoint(
    tmp_path: Path,
) -> None:
    matrix = json.loads(ENTRYPOINT_MATRIX.read_text(encoding="utf-8"))
    manifest = json.loads(
        (PACKAGE_ROOT / "toolchain-manifest.json").read_text(encoding="utf-8")
    )
    assert matrix["format_version"] == 1
    assert set(matrix["entries"]) == set(manifest["dependency_closures"])
    assert all(
        {
            "failure_argv",
            "failure_exit_code",
            "failure_stderr_contains",
            "fixture",
            "projected_argv",
            "projected_module",
            "stdout_kind",
            "success_stdout_contains",
            "wheel_argv",
            "wheel_command",
        }
        <= set(entry)
        for entry in matrix["entries"].values()
    )

    projected_root = tmp_path / "projected"
    projected_package = projected_root / "marketplace_installer"
    projected_package.mkdir(parents=True)
    for entry in manifest["files"]:
        source = PACKAGE_ROOT / entry["path"]
        destination = projected_package / entry["path"]
        shutil.copy2(source, destination)
    for manifest_name in (
        "toolchain-manifest.json",
        "codex-packaging-toolchain-manifest.json",
    ):
        shutil.copy2(PACKAGE_ROOT / manifest_name, projected_package / manifest_name)

    environment = {
        key: value for key, value in os.environ.items() if key != "PYTHONPATH"
    }
    for name, entry in matrix["entries"].items():
        command = [
            sys.executable,
            "-m",
            entry["projected_module"],
            *entry["projected_argv"],
        ]
        completed = subprocess.run(
            command,
            cwd=projected_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (name, completed.stderr)
        assert entry["success_stdout_contains"] in completed.stdout

        failed = subprocess.run(
            [
                sys.executable,
                "-m",
                entry["projected_module"],
                *entry["failure_argv"],
            ],
            cwd=projected_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert failed.returncode == entry["failure_exit_code"], (name, failed.stderr)
        assert entry["failure_stderr_contains"] in failed.stderr
