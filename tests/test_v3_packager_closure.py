"""The packaged installer carries the complete v3 router-packager closure."""

from __future__ import annotations

import importlib
from pathlib import Path

from marketplace_installer import codex_packaging_toolchain_launcher


PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "marketplace_installer"

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
    "router_plugin_packager_source",
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
