from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest


from marketplace_installer import marketplace_publish as publish_lib
from marketplace_installer import router_plugin_packager as packager
from marketplace_installer import router_plugin_packager_engine as packager_engine
from marketplace_installer.router_plugin_packager_constants import RECEIPT_NAME
from marketplace_installer.router_plugin_packager_hashing import (
    canonical_json_bytes,
    hash_bytes,
    hash_tree,
)
from marketplace_installer.router_plugin_packager_mcp import (
    validate_mcp_descriptor_round_trip,
)
from marketplace_installer.router_plugin_packager_mcp_normalization import (
    normalize_mcp_launch_contract,
)
from marketplace_installer.router_plugin_packager_parsing import load_json

LIVE_WERNER_ROOT = Path("../werner-mcp-tools").resolve()
LIVE_OCI_PLUGIN_ROOT = LIVE_WERNER_ROOT / "oci-worktools"
LIVE_RUNTIME_EQUIVALENT_PATHS = {
    ".codex-plugin/plugin.json",
    ".mcp.json",
    "skills/oci-worktools/SKILL.md",
}
RELEASE_SURFACE_REQUIRED_PATHS = [
    "release-surface/manifest.json",
    "release-surface/release-manifest.json",
    "release-surface/operation-registry.json",
]
CANONICAL_GENERATED_REGISTRY_ROOT = (
    ".codex-plugin/router-plugin-packager/generated-registry"
)
LEGACY_GENERATED_REGISTRY_ROOT = "src/werner_mcp_tools/generated_registry"
LIVE_ARTIFACT_COMPLETE_MINIMUM_PATHS = {
    ".codex-plugin/payload-manifest.json",
    ".codex-plugin/release-metadata.json",
    ".codex-plugin/staging-plan.json",
    ".router-plugin-packager-source-map.json",
    *RELEASE_SURFACE_REQUIRED_PATHS,
}

FIXTURE_PLUGIN_SLUG = "sample-mcp-surface"
FIXTURE_SERVER_ID = "sample-mcp-server"
FIXTURE_PACKAGE_NAME = "sample-mcp-package"
FIXTURE_ENTRYPOINT = "sample-mcp-entrypoint"
FIXTURE_SKILL_ID = "sample-mcp-surface"
MCP_LAUNCH_SCHEMA = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "router_plugin_packager"
    / "schemas"
    / "mcp-launch-contract.schema.json"
)


FIXTURE_INTERFACE = {
    "capabilities": ["Read", "Write"],
    "category": "Productivity",
    "defaultPrompt": ["Find Jira issues assigned to me that are due this week."],
    "developerName": "Example Developer",
    "displayName": "Sample MCP Surface",
    "longDescription": "Use typed MCP tools for approved enterprise reads and verified mutations.",
    "shortDescription": "Sample governed MCP workflow",
}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_mcp_launch_contract_schema_is_machine_readable() -> None:
    schema = _load_json(MCP_LAUNCH_SCHEMA)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"] == {
        "type": "integer",
        "enum": [1, 2, 3],
    }
    assert schema["properties"]["transport"] == {"const": "stdio"}
    assert schema["properties"]["command"] == {"const": "uvx"}


def test_mcp_launch_contract_normalizes_v1_to_empty_v2_environment() -> None:
    contract = normalize_mcp_launch_contract(
        _mcp_packaging_contract(
            interface=FIXTURE_INTERFACE,
            required_byte_preserved_paths=[],
        )["launch_contract"]
    )

    assert contract.schema_version == 2
    assert contract.input_schema_version == 1
    assert contract.environment == ()
    assert contract.environment_authority == "legacy_empty"


def test_mcp_launch_contract_v2_emits_environment_and_receipt_proof(
    tmp_path: Path,
) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    invocation = _load_json(repo / "mcp.json")
    launch_contract = invocation["mcp_packaging"]["launch_contract"]
    launch_contract.update(
        {
            "schema_version": 2,
            "environment": {
                "UV_INDEX_URL": "https://packages.example.test/simple",
                "UV_MARKER": "value%20literal",
            },
            "environment_authority": "config",
        }
    )
    _write_json(repo / "mcp.json", invocation)

    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])
    descriptor = _load_json(output_root / ".mcp.json")
    receipt = _load_json(output_root / RECEIPT_NAME)
    proof = receipt["normalized_request"]["mcp_packaging"]

    assert descriptor["mcpServers"][FIXTURE_SERVER_ID]["env"] == {
        "UV_INDEX_URL": "https://packages.example.test/simple",
        "UV_MARKER": "value%20literal",
    }
    assert proof["launch_contract"]["input_schema_version"] == 2
    assert proof["launch_contract"]["resolved_schema_version"] == 2
    assert proof["launch_contract"]["environment_authority"] == "config"
    assert "package_version" not in proof["launch_contract"]
    assert proof["mcp_descriptor_bytes_sha256"] == hash_bytes(
        (output_root / ".mcp.json").read_bytes()
    )
    assert proof["mcp_descriptor_canonical_sha256"] == hash_bytes(
        canonical_json_bytes(descriptor)
    )

    staging_plan = _load_json(output_root / ".codex-plugin" / "staging-plan.json")
    installed = packager_engine.validate_staged_marketplace_install(
        output_root,
        staging_plan,
        repo / "staging-sandbox",
        "environment-proof",
    )
    cache_root = Path(installed["cache_plugin_root"])
    assert _load_json(cache_root / ".mcp.json") == descriptor
    assert (
        _load_json(cache_root / RECEIPT_NAME)["normalized_request"]["mcp_packaging"]
        == proof
    )


@pytest.mark.parametrize(
    ("package_version", "expected_selector"),
    [("", FIXTURE_PACKAGE_NAME), ("1.0.0", f"{FIXTURE_PACKAGE_NAME}==1.0.0")],
)
def test_mcp_launch_contract_v3_renders_package_selector_and_provenance(
    tmp_path: Path, package_version: str, expected_selector: str
) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    invocation = _load_json(repo / "mcp.json")
    launch_contract = invocation["mcp_packaging"]["launch_contract"]
    launch_contract.update(
        {
            "schema_version": 3,
            "environment": {},
            "environment_authority": "config",
            "package_version": package_version,
        }
    )
    _write_json(repo / "mcp.json", invocation)

    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])
    descriptor = _load_json(output_root / ".mcp.json")
    proof = _load_json(output_root / RECEIPT_NAME)["normalized_request"][
        "mcp_packaging"
    ]["launch_contract"]

    assert descriptor["mcpServers"][FIXTURE_SERVER_ID]["args"][5] == expected_selector
    assert proof["schema_version"] == 3
    assert proof["resolved_schema_version"] == 3
    assert proof["package_version"] == package_version


@pytest.mark.parametrize(
    "package_version",
    [" 1.0.0", "v1.0", "1.0+local", ">=1.0", "latest", None],
)
def test_mcp_launch_contract_v3_rejects_noncanonical_package_versions(
    package_version: object,
) -> None:
    launch_contract = _mcp_packaging_contract(
        interface=FIXTURE_INTERFACE,
        required_byte_preserved_paths=[],
    )["launch_contract"]
    launch_contract.update(
        {
            "schema_version": 3,
            "environment": {},
            "environment_authority": "config",
            "package_version": package_version,
        }
    )

    with pytest.raises(packager.PackagerError) as exc_info:
        normalize_mcp_launch_contract(launch_contract)

    assert exc_info.value.error_code == "invalid_mcp_launch_contract"


@pytest.mark.parametrize(
    "package_name",
    ["sample @ https://example.test/pkg", "sample[extra]", " sample", "sample>=1"],
)
def test_mcp_launch_contract_v3_rejects_non_distribution_package_name(
    package_name: str,
) -> None:
    launch_contract = _mcp_packaging_contract(
        interface=FIXTURE_INTERFACE,
        required_byte_preserved_paths=[],
        package_name=package_name,
    )["launch_contract"]
    launch_contract.update(
        {
            "schema_version": 3,
            "environment": {},
            "environment_authority": "config",
            "package_version": "1.0.0",
        }
    )

    with pytest.raises(packager.PackagerError) as exc_info:
        normalize_mcp_launch_contract(launch_contract)

    assert exc_info.value.error_code == "invalid_mcp_launch_contract"


@pytest.mark.parametrize("schema_version", [True, False, 3.0, "3", None, 4])
def test_mcp_launch_contract_rejects_non_integer_or_unsupported_schema_version(
    schema_version: object,
) -> None:
    launch_contract = _mcp_packaging_contract(
        interface=FIXTURE_INTERFACE,
        required_byte_preserved_paths=[],
    )["launch_contract"]
    launch_contract["schema_version"] = schema_version

    with pytest.raises(packager.PackagerError) as exc_info:
        normalize_mcp_launch_contract(launch_contract)

    assert exc_info.value.error_code == "invalid_mcp_launch_contract"


@pytest.mark.parametrize(
    ("environment", "error_code"),
    [
        (None, "env_invalid_type"),
        ({"lowercase": "value"}, "env_invalid_name"),
        ({"UV_VALUE": ""}, "env_invalid_value"),
        ({"UV_VALUE": "line\nbreak"}, "env_invalid_value"),
    ],
)
def test_mcp_launch_contract_rejects_invalid_environment(
    environment: object, error_code: str
) -> None:
    launch_contract = _mcp_packaging_contract(
        interface=FIXTURE_INTERFACE,
        required_byte_preserved_paths=[],
    )["launch_contract"]
    launch_contract.update({"schema_version": 2, "environment": environment})

    with pytest.raises(packager.PackagerError) as exc_info:
        normalize_mcp_launch_contract(launch_contract)

    assert exc_info.value.error_code == error_code


def test_mcp_launch_contract_v2_requires_environment() -> None:
    launch_contract = _mcp_packaging_contract(
        interface=FIXTURE_INTERFACE,
        required_byte_preserved_paths=[],
    )["launch_contract"]
    launch_contract["schema_version"] = 2

    with pytest.raises(packager.PackagerError) as exc_info:
        normalize_mcp_launch_contract(launch_contract)

    assert exc_info.value.error_code == "invalid_mcp_launch_contract"


def test_mcp_launch_contract_invalid_environment_preserves_existing_output(
    tmp_path: Path,
) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    invocation = _load_json(repo / "mcp.json")
    output_root = repo / "generated" / FIXTURE_PLUGIN_SLUG
    output_root.mkdir(parents=True)
    sentinel = output_root / "existing.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    launch_contract = invocation["mcp_packaging"]["launch_contract"]
    launch_contract.update({"schema_version": 2, "environment": {"bad": "x"}})
    _write_json(repo / "mcp.json", invocation)

    with pytest.raises(packager.PackagerError) as exc_info:
        packager.run("apply", repo / "mcp.json", repo)

    assert exc_info.value.error_code == "env_invalid_name"
    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert _relative_file_set(output_root) == {"existing.txt"}


def test_invalid_staged_environment_fails_before_staging_or_cache_creation(
    tmp_path: Path,
) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])
    descriptor_path = output_root / ".mcp.json"
    descriptor = _load_json(descriptor_path)
    descriptor["mcpServers"][FIXTURE_SERVER_ID]["env"] = {"bad": "x"}
    _write_json(descriptor_path, descriptor)
    staging_plan = _load_json(output_root / ".codex-plugin" / "staging-plan.json")
    staged_root = repo / "staged"
    sandbox_root = repo / "sandbox"

    with pytest.raises(packager.PackagerError) as exc_info:
        packager_engine.apply_staging_plan_for_validation(
            output_root, staging_plan, staged_root, "environment-proof"
        )

    assert exc_info.value.error_code == "env_invalid_name"
    assert not staged_root.exists()

    with pytest.raises(packager.PackagerError) as exc_info:
        packager_engine.validate_staged_marketplace_install(
            output_root, staging_plan, sandbox_root, "environment-proof"
        )

    assert exc_info.value.error_code == "env_invalid_name"
    assert not sandbox_root.exists()


def test_packager_rejects_duplicate_invocation_keys(tmp_path: Path) -> None:
    invocation = tmp_path / "duplicate.json"
    invocation.write_text(
        '{"format_version": 1, "format_version": 2}', encoding="utf-8"
    )

    with pytest.raises(packager.PackagerError) as exc_info:
        load_json(invocation)

    assert exc_info.value.error_code == "invalid_json_duplicate_key"


def _relative_file_set(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}


def _mcp_payload_assets(registry_root: str) -> list[dict]:
    return [
        {
            "id": "registry-manifest",
            "acquisition_mode": "pre_generated",
            "source": f"{registry_root}/manifest.json",
            "destination": "release-surface/manifest.json",
            "ownership_role": "registry-manifest",
            "ownership_class": "immutable-runtime-artifact",
            "provenance_path": f"{registry_root}/manifest.provenance.json",
        },
        {
            "id": "release-manifest",
            "acquisition_mode": "pre_generated",
            "source": f"{registry_root}/release-manifest.json",
            "destination": "release-surface/release-manifest.json",
            "ownership_role": "release-manifest",
            "ownership_class": "immutable-runtime-artifact",
            "provenance_path": f"{registry_root}/release-manifest.provenance.json",
        },
        {
            "id": "operation-registry",
            "acquisition_mode": "pre_generated",
            "source": f"{registry_root}/operation-registry.json",
            "destination": "release-surface/operation-registry.json",
            "ownership_role": "operation-registry",
            "ownership_class": "immutable-runtime-artifact",
            "provenance_path": f"{registry_root}/operation-registry.provenance.json",
        },
        {
            "id": "schema-bundle",
            "acquisition_mode": "pre_generated",
            "source": f"{registry_root}/schemas",
            "destination": "release-surface/schemas",
            "ownership_role": "schema-bundle",
            "ownership_class": "immutable-runtime-artifact",
            "provenance_path": f"{registry_root}/schemas.provenance.json",
        },
    ]


def _required_byte_preserved_paths(
    *, skill_id: str, extra_paths: list[str] | None = None
) -> list[str]:
    paths = [
        ".mcp.json",
        f"skills/{skill_id}/SKILL.md",
        *RELEASE_SURFACE_REQUIRED_PATHS,
    ]
    if extra_paths:
        paths.extend(extra_paths)
    return paths


def _mcp_packaging_contract(
    *,
    interface: dict,
    required_byte_preserved_paths: list[str],
    plugin_slug: str = FIXTURE_PLUGIN_SLUG,
    description: str = "Sample tools for governed MCP workflows.",
    author_name: str = "Example Tools",
    server_id: str = FIXTURE_SERVER_ID,
    package_name: str = FIXTURE_PACKAGE_NAME,
    entrypoint: str = FIXTURE_ENTRYPOINT,
    skill_id: str = FIXTURE_SKILL_ID,
) -> dict:
    return {
        "plugin_artifact_contract": {
            "name": plugin_slug,
            "description": description,
            "author": {"name": author_name},
            "interface": interface,
            "skills_path": "./skills/",
            "mcp_servers_path": "./.mcp.json",
        },
        "launch_contract": {
            "schema_version": 1,
            "server_id": server_id,
            "transport": "stdio",
            "command": "uvx",
            "python_version": "3.14.6",
            "package_index": "https://artifactory.oci.oraclecorp.com/api/pypi/global-release-pypi/simple",
            "package_name": package_name,
            "entrypoint": entrypoint,
            "extra_args": [],
            "forbidden_arg_fragments": [
                "auth",
                "credential",
                "endpoint",
                "profile",
                "tenant",
            ],
        },
        "release_surface": {
            "registry_manifest_asset_id": "registry-manifest",
            "release_manifest_asset_id": "release-manifest",
            "operation_registry_asset_id": "operation-registry",
            "schema_bundle_asset_id": "schema-bundle",
        },
        "skill_release_contract": {
            "skill_id": skill_id,
            "advertised_operation_ids": [
                "jira.issue.update",
                "sharepoint.site.read",
            ],
            "required_phrases": [
                "Treat the active release manifest and matching capability/schema snapshot as the authority.",
                "Never invoke SharePoint write behavior; no SharePoint write tool is registered in this release.",
            ],
            "forbidden_phrases": [
                "you can activate a disabled capability by changing credentials"
            ],
        },
        "publication": {
            "category": "Productivity",
        },
        "staging_contract": {
            "format_version": 1,
            "marketplace_name": "bob-schumaker-codex-support",
            "plugin_relpath": f"plugins/{plugin_slug}",
            "version_suffix_source": "cachebuster",
            "allowed_mutations": [
                {
                    "path": ".codex-plugin/plugin.json",
                    "field_path": "version",
                    "transform": "append-version-suffix",
                }
            ],
            "required_byte_preserved_paths": required_byte_preserved_paths,
        },
    }


def _mcp_invocation(
    *,
    source_root: str | None,
    output_root: str,
    skill_paths: list[str],
    registry_root: str,
    interface: dict,
    required_byte_preserved_paths: list[str],
    plugin_slug: str = FIXTURE_PLUGIN_SLUG,
    display_name: str = "Sample MCP Surface",
    surface_id: str = FIXTURE_PLUGIN_SLUG,
    description: str = "Sample tools for governed MCP workflows.",
    author_name: str = "Example Tools",
    server_id: str = FIXTURE_SERVER_ID,
    package_name: str = FIXTURE_PACKAGE_NAME,
    entrypoint: str = FIXTURE_ENTRYPOINT,
    skill_id: str = FIXTURE_SKILL_ID,
) -> dict:
    payload = {
        "format_version": 1,
        "input_mode": "skill_list",
        "plugin_kind": "mcp_based",
        "repository_root": ".",
        "output_root": output_root,
        "skill_paths": skill_paths,
        "plugin_slug_override": plugin_slug,
        "display_name_override": display_name,
        "surface_id_override": surface_id,
        "publisher_slug_override": "bob-schumaker-codex-support",
        "version_override": "0.1.1",
        "payload_assets": _mcp_payload_assets(registry_root),
        "mcp_packaging": _mcp_packaging_contract(
            interface=interface,
            required_byte_preserved_paths=required_byte_preserved_paths,
            plugin_slug=plugin_slug,
            description=description,
            author_name=author_name,
            server_id=server_id,
            package_name=package_name,
            entrypoint=entrypoint,
            skill_id=skill_id,
        ),
    }
    if source_root is not None:
        payload["source_root"] = source_root
    return payload


def _write_registry_provenance(
    repo: Path, *, registry_root: str, source_root_text: str, generator_identity: str
) -> None:
    registry_path = repo / registry_root
    for relative in [
        "manifest.json",
        "release-manifest.json",
        "operation-registry.json",
    ]:
        source = registry_path / relative
        _write_json(
            source.with_name(f"{source.stem}.provenance.json"),
            {
                "artifact_path": f"{registry_root}/{relative}",
                "source_digest": hash_bytes(source.read_bytes()),
                "generator_identity": generator_identity,
                "generator_version": "0.1.0"
                if generator_identity == "werner-registry"
                else "1.0",
                "generator_parameters": {
                    "mode": "reference"
                    if generator_identity == "werner-registry"
                    else "fixture"
                },
                "freshness_basis": "content-hash",
                "compatibility": {"source_root": source_root_text},
            },
        )
    schemas = registry_path / "schemas"
    _write_json(
        registry_path / "schemas.provenance.json",
        {
            "artifact_path": f"{registry_root}/schemas",
            "source_digest": hash_tree(schemas),
            "generator_identity": generator_identity,
            "generator_version": "0.1.0"
            if generator_identity == "werner-registry"
            else "1.0",
            "generator_parameters": {
                "mode": "reference"
                if generator_identity == "werner-registry"
                else "fixture"
            },
            "freshness_basis": "tree-hash",
            "compatibility": {"source_root": source_root_text},
        },
    )


def _mcp_fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "mcp-repo"
    skill_root = repo / "skills" / FIXTURE_SKILL_ID
    skill_root.mkdir(parents=True, exist_ok=True)
    (skill_root / "SKILL.md").write_text(
        """---
name: sample-mcp-surface
description: Use sample governed MCP tools for approved enterprise reads and verified mutations.
---

# Sample MCP Surface

- Treat the active release manifest and matching capability/schema snapshot as the authority.
- Do not pass raw credentials, endpoint URLs, profile names, tenant identifiers, credential file paths, or alternate authentication strategies.
- Never invoke SharePoint write behavior; no SharePoint write tool is registered in this release.
""",
        encoding="utf-8",
    )
    generated_root = repo / CANONICAL_GENERATED_REGISTRY_ROOT
    generated_root.mkdir(parents=True, exist_ok=True)
    (generated_root / "manifest.json").write_text(
        json.dumps(
            {
                "generator_version": "0.1.0",
                "mcp_tool_definitions": [{"tool_id": "jira_issue_update"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (generated_root / "release-manifest.json").write_text(
        json.dumps(
            {
                "package": {
                    "entry_point": FIXTURE_ENTRYPOINT,
                    "name": FIXTURE_PACKAGE_NAME,
                    "version": "1.0.0",
                },
                "selected_operation_ids": ["jira.issue.update", "sharepoint.site.read"],
                "selected_tools": [
                    {"tool_id": "jira_issue_update", "kind": "provider"},
                    {"tool_id": "sharepoint_site_read", "kind": "provider"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (generated_root / "operation-registry.json").write_text(
        json.dumps(
            {
                "operations": [
                    {"operation_id": "jira.issue.update"},
                    {"operation_id": "sharepoint.site.read"},
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    schemas = generated_root / "schemas"
    schemas.mkdir(parents=True, exist_ok=True)
    (schemas / "jira.issue.update.input.schema.json").write_text(
        '{"title":"jira.issue.update.input"}\n', encoding="utf-8"
    )
    _write_registry_provenance(
        repo,
        registry_root=CANONICAL_GENERATED_REGISTRY_ROOT,
        source_root_text="skills",
        generator_identity="fixture-generator",
    )
    _write_json(
        repo / "router-plugin-config.json",
        {"registry_root": CANONICAL_GENERATED_REGISTRY_ROOT},
    )
    invocation = repo / "mcp.json"
    _write_json(
        invocation,
        _mcp_invocation(
            source_root=None,
            output_root=f"./generated/{FIXTURE_PLUGIN_SLUG}",
            skill_paths=[f"skills/{FIXTURE_SKILL_ID}"],
            registry_root=CANONICAL_GENERATED_REGISTRY_ROOT,
            interface=FIXTURE_INTERFACE,
            required_byte_preserved_paths=_required_byte_preserved_paths(
                skill_id=FIXTURE_SKILL_ID,
                extra_paths=[
                    "release-surface/schemas/jira.issue.update.input.schema.json"
                ],
            ),
        ),
    )
    return repo


def _branded_skills_only_fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "branded-skills-only-repo"
    skill_root = repo / "skills" / "branded-skill"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: branded-skill\ndescription: Branded fixture skill.\n---\n",
        encoding="utf-8",
    )
    assets = repo / "assets"
    assets.mkdir()
    (assets / "logo.png").write_bytes(b"light-logo\x00")
    (assets / "logo-dark.png").write_bytes(b"dark-logo\x00")
    _write_json(
        repo / ".codex-plugin" / "plugin.json",
        {
            "name": "branded-skills-only",
            "version": "1.0.0",
            "description": "A branded skills-only fixture.",
            "author": {"name": "Fixture Team"},
            "interface": {
                "category": "Productivity",
                "logo": "./assets/logo.png",
                "logoDark": "./assets/logo-dark.png",
            },
        },
    )
    _write_json(
        repo / "skills-only.json",
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/branded-skills-only",
            "skill_paths": ["skills/branded-skill"],
            "plugin_slug_override": "branded-skills-only",
            "display_name_override": "Branded Skills Only",
            "surface_id_override": "branded-skills-only",
            "branding_asset_overrides": {
                "logo": "assets/logo.png",
                "dark_logo": "assets/logo-dark.png",
            },
            "publication": {"category": "Productivity"},
        },
    )
    return repo


def test_mcp_packaging_generates_codex_artifact_shape(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)

    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])
    plugin_manifest = _load_json(output_root / ".codex-plugin" / "plugin.json")
    mcp_descriptor = _load_json(output_root / ".mcp.json")
    staging_plan = _load_json(output_root / ".codex-plugin" / "staging-plan.json")

    assert plugin_manifest["name"] == FIXTURE_PLUGIN_SLUG
    assert plugin_manifest["mcpServers"] == "./.mcp.json"
    assert plugin_manifest["skills"] == "./skills/"
    assert plugin_manifest["version"] == "0.1.1"
    assert mcp_descriptor == {
        "mcpServers": {
            FIXTURE_SERVER_ID: {
                "command": "uvx",
                "args": [
                    "--python",
                    "3.14.6",
                    "--default-index",
                    "https://artifactory.oci.oraclecorp.com/api/pypi/global-release-pypi/simple",
                    "--from",
                    FIXTURE_PACKAGE_NAME,
                    FIXTURE_ENTRYPOINT,
                    "--stdio",
                ],
            }
        }
    }
    assert staging_plan["allowed_mutations"] == [
        {
            "field_path": "version",
            "path": ".codex-plugin/plugin.json",
            "transform": "append-version-suffix",
        }
    ]
    assert (output_root / "release-surface" / "manifest.json").is_file()
    assert (
        output_root
        / "release-surface"
        / "schemas"
        / "jira.issue.update.input.schema.json"
    ).is_file()
    assert (
        applied["normalized_request"]["mcp_packaging"]["launch_contract"]["server_id"]
        == FIXTURE_SERVER_ID
    )


def test_mcp_packaging_rejects_incomplete_launch_contract(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    payload = _load_json(repo / "mcp.json")
    del payload["mcp_packaging"]["launch_contract"]["entrypoint"]
    _write_json(repo / "mcp.json", payload)

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", repo / "mcp.json", repo)

    assert excinfo.value.error_code == "invalid_invocation_field"


def test_mcp_packaging_rejects_forbidden_launch_argument(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    payload = _load_json(repo / "mcp.json")
    payload["mcp_packaging"]["launch_contract"]["extra_args"] = ["--tenant", "prod"]
    _write_json(repo / "mcp.json", payload)

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", repo / "mcp.json", repo)

    assert excinfo.value.error_code == "forbidden_mcp_launch_argument"


def test_mcp_packaging_rejects_launch_release_package_mismatch(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    release_manifest_path = (
        repo / CANONICAL_GENERATED_REGISTRY_ROOT / "release-manifest.json"
    )
    release_manifest = _load_json(release_manifest_path)
    release_manifest["package"]["entry_point"] = "wrong-entrypoint"
    _write_json(release_manifest_path, release_manifest)
    _write_registry_provenance(
        repo,
        registry_root=CANONICAL_GENERATED_REGISTRY_ROOT,
        source_root_text="skills",
        generator_identity="fixture-generator",
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", repo / "mcp.json", repo)

    assert excinfo.value.error_code == "mcp_launch_release_mismatch"


def test_mcp_packaging_rejects_v3_release_package_version_mismatch(
    tmp_path: Path,
) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    payload = _load_json(repo / "mcp.json")
    payload["mcp_packaging"]["launch_contract"].update(
        {
            "schema_version": 3,
            "environment": {},
            "environment_authority": "config",
            "package_version": "1.0.1",
        }
    )
    _write_json(repo / "mcp.json", payload)

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", repo / "mcp.json", repo)

    assert excinfo.value.error_code == "mcp_launch_release_mismatch"


@pytest.mark.parametrize("release_version", [None, "v1.0.0", "1.0+local"])
def test_mcp_packaging_rejects_invalid_v3_release_package_version(
    tmp_path: Path, release_version: object
) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    payload = _load_json(repo / "mcp.json")
    payload["mcp_packaging"]["launch_contract"].update(
        {
            "schema_version": 3,
            "environment": {},
            "environment_authority": "config",
            "package_version": "1.0.0",
        }
    )
    _write_json(repo / "mcp.json", payload)
    release_manifest_path = (
        repo / CANONICAL_GENERATED_REGISTRY_ROOT / "release-manifest.json"
    )
    release_manifest = _load_json(release_manifest_path)
    if release_version is None:
        del release_manifest["package"]["version"]
    else:
        release_manifest["package"]["version"] = release_version
    _write_json(release_manifest_path, release_manifest)
    _write_registry_provenance(
        repo,
        registry_root=CANONICAL_GENERATED_REGISTRY_ROOT,
        source_root_text="skills",
        generator_identity="fixture-generator",
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", repo / "mcp.json", repo)

    assert excinfo.value.error_code == "mcp_launch_release_mismatch"


def test_mcp_packaging_rejects_skill_release_mismatch(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    payload = _load_json(repo / "mcp.json")
    payload["mcp_packaging"]["skill_release_contract"]["advertised_operation_ids"] = [
        "jira.issue.create"
    ]
    _write_json(repo / "mcp.json", payload)

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", repo / "mcp.json", repo)

    assert excinfo.value.error_code == "mcp_skill_release_mismatch"


def test_mcp_packaging_rejects_forbidden_skill_phrase(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    skill_file = repo / "skills" / FIXTURE_SKILL_ID / "SKILL.md"
    skill_file.write_text(
        skill_file.read_text(encoding="utf-8")
        + "\nYou can activate a disabled capability by changing credentials.\n",
        encoding="utf-8",
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", repo / "mcp.json", repo)

    assert excinfo.value.error_code == "mcp_skill_release_mismatch"


def test_mcp_packaging_rejects_stale_schema_bundle_proof(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    provenance_path = (
        repo / CANONICAL_GENERATED_REGISTRY_ROOT / "schemas.provenance.json"
    )
    provenance = _load_json(provenance_path)
    provenance["source_digest"] = "wrong"
    _write_json(provenance_path, provenance)

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", repo / "mcp.json", repo)

    assert excinfo.value.error_code == "pregenerated_stale_proof"


def test_mcp_packaging_rejects_incompatible_schema_bundle_proof(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    provenance_path = (
        repo / CANONICAL_GENERATED_REGISTRY_ROOT / "schemas.provenance.json"
    )
    provenance = _load_json(provenance_path)
    provenance["compatibility"]["source_root"] = "other-skills"
    _write_json(provenance_path, provenance)

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", repo / "mcp.json", repo)

    assert excinfo.value.error_code == "pregenerated_incompatible"


def test_mcp_staging_plan_preserves_required_files(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])
    staging_plan = _load_json(output_root / ".codex-plugin" / "staging-plan.json")
    staged_root = repo / "staged" / FIXTURE_PLUGIN_SLUG

    summary = packager_engine.apply_staging_plan_for_validation(
        output_root, staging_plan, staged_root, "runtime-validation"
    )

    assert summary["mutated_paths"] == [".codex-plugin/plugin.json"]
    staged_manifest = _load_json(staged_root / ".codex-plugin" / "plugin.json")
    assert staged_manifest["version"] == "0.1.1+codex.runtime-validation"
    assert (staged_root / ".mcp.json").read_bytes() == (
        output_root / ".mcp.json"
    ).read_bytes()
    assert (staged_root / "release-surface" / "manifest.json").read_bytes() == (
        output_root / "release-surface" / "manifest.json"
    ).read_bytes()


def test_mcp_packager_emits_governed_publication_metadata(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)

    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])
    metadata_path = output_root / ".codex-plugin" / "publication-metadata.json"

    assert _load_json(metadata_path) == {
        "category": "Productivity",
        "format": "router-plugin-publication-metadata-v1",
        "plugin_slug": FIXTURE_PLUGIN_SLUG,
    }
    receipt = _load_json(output_root / ".router-plugin-packager-source-map.json")
    assert ".codex-plugin/publication-metadata.json" in receipt["generated_paths"]
    assert receipt["mcp_authority"] == {
        "format": "router-plugin-mcp-authority-v1",
        "config_path": "router-plugin-config.json",
        "config_digest": hash_bytes((repo / "router-plugin-config.json").read_bytes()),
        "registry_root": CANONICAL_GENERATED_REGISTRY_ROOT,
        "registry_digest": hash_tree(repo / CANONICAL_GENERATED_REGISTRY_ROOT),
        "toolchain_manifest_digest": hash_bytes(
            (
                Path(packager_engine.__file__).parent
                / "codex-packaging-toolchain-manifest.json"
            ).read_bytes()
        ),
    }


def test_mcp_packager_requires_governed_publication_category(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    payload = _load_json(repo / "mcp.json")
    del payload["mcp_packaging"]["publication"]["category"]
    _write_json(repo / "mcp.json", payload)

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", repo / "mcp.json", repo)

    assert excinfo.value.error_code == "invalid_invocation_field"


def test_mcp_staging_harness_validates_disposable_marketplace_install(
    tmp_path: Path,
) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])
    staging_plan = _load_json(output_root / ".codex-plugin" / "staging-plan.json")

    result = packager_engine.validate_staged_marketplace_install(
        output_root,
        staging_plan,
        repo / "staging-sandbox",
        "runtime-validation",
    )

    cache_plugin_root = Path(result["cache_plugin_root"])
    assert result["plugin_name"] == FIXTURE_PLUGIN_SLUG
    assert result["version"] == "0.1.1+codex.runtime-validation"
    assert (
        Path(result["marketplace_root"]) / ".agents/plugins/marketplace.json"
    ).is_file()
    assert (cache_plugin_root / ".codex-plugin" / "plugin.json").is_file()
    assert (cache_plugin_root / ".mcp.json").read_bytes() == (
        output_root / ".mcp.json"
    ).read_bytes()


def test_mcp_staging_plan_rejects_disallowed_mutation_transform(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])
    staging_plan = _load_json(output_root / ".codex-plugin" / "staging-plan.json")
    staging_plan["allowed_mutations"][0]["transform"] = "rewrite-version"

    with pytest.raises(packager.PackagerError) as excinfo:
        packager_engine.apply_staging_plan_for_validation(
            output_root,
            staging_plan,
            repo / "staged" / f"{FIXTURE_PLUGIN_SLUG}-invalid",
            "runtime-validation",
        )

    assert excinfo.value.error_code == "invalid_staging_plan"


def test_mcp_descriptor_round_trip_rejects_invalid_shape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    invocation = _load_json(repo / "mcp.json")
    contract = normalize_mcp_launch_contract(
        invocation["mcp_packaging"]["launch_contract"]
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        validate_mcp_descriptor_round_trip(
            contract, mcp_descriptor_payload_fn=lambda _contract: {"mcpServers": {}}
        )

    assert excinfo.value.error_code == "invalid_mcp_descriptor_round_trip"


def test_mcp_output_tree_remains_publish_flow_compatible(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])

    source_marketplace = repo / "source-marketplace"
    plugin_root = source_marketplace / "plugins" / FIXTURE_PLUGIN_SLUG
    shutil.copytree(output_root, plugin_root)
    _write_json(
        source_marketplace / ".agents" / "plugins" / "marketplace.json",
        {
            "name": "layer3-source",
            "interface": {"displayName": "Layer3 Source"},
            "plugins": [
                {
                    "name": FIXTURE_PLUGIN_SLUG,
                    "source": {
                        "source": "local",
                        "path": f"./plugins/{FIXTURE_PLUGIN_SLUG}",
                    },
                    "policy": {
                        "installation": "AVAILABLE",
                        "authentication": "ON_INSTALL",
                    },
                    "category": "Productivity",
                }
            ],
        },
    )

    target_root = repo / "target-marketplace"
    preview = publish_lib.publish_marketplace(
        source_root=source_marketplace,
        target_root=target_root,
        marketplace_name="bob-schumaker-codex-support",
        dry_run=True,
    )
    result = publish_lib.publish_marketplace(
        source_root=source_marketplace,
        target_root=target_root,
        marketplace_name="bob-schumaker-codex-support",
        plan_digest=preview["plan_digest"],
    )

    assert result["source_plugins"] == [FIXTURE_PLUGIN_SLUG]
    copied_root = target_root / "plugins" / FIXTURE_PLUGIN_SLUG
    assert _load_json(copied_root / ".codex-plugin" / "plugin.json") == _load_json(
        output_root / ".codex-plugin" / "plugin.json"
    )
    assert (copied_root / ".mcp.json").read_bytes() == (
        output_root / ".mcp.json"
    ).read_bytes()
    assert (copied_root / "skills" / FIXTURE_SKILL_ID / "SKILL.md").read_bytes() == (
        output_root / "skills" / FIXTURE_SKILL_ID / "SKILL.md"
    ).read_bytes()
    assert (copied_root / "release-surface" / "release-manifest.json").read_bytes() == (
        output_root / "release-surface" / "release-manifest.json"
    ).read_bytes()


def test_mcp_output_tree_publishes_directly_without_marketplace_wrapper(
    tmp_path: Path,
) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])
    before = hash_tree(output_root)

    target_root = repo / "target-marketplace"
    preview = publish_lib.publish_generated_plugin(
        plugin_root=output_root,
        target_root=target_root,
        marketplace_name="bob-schumaker-codex-support",
        dry_run=True,
    )
    result = publish_lib.publish_generated_plugin(
        plugin_root=output_root,
        target_root=target_root,
        marketplace_name="bob-schumaker-codex-support",
        plan_digest=preview["plan_digest"],
    )

    assert result["source_shape"] == "generated-plugin-tree"
    assert result["source_plugins"] == [FIXTURE_PLUGIN_SLUG]
    assert hash_tree(output_root) == before
    copied_root = target_root / "plugins" / FIXTURE_PLUGIN_SLUG
    assert _load_json(copied_root / ".codex-plugin" / "plugin.json") == _load_json(
        output_root / ".codex-plugin" / "plugin.json"
    )
    marketplace = _load_json(target_root / ".agents" / "plugins" / "marketplace.json")
    assert marketplace["plugins"] == [
        {
            "category": "Productivity",
            "name": FIXTURE_PLUGIN_SLUG,
            "policy": {
                "authentication": "ON_INSTALL",
                "installation": "AVAILABLE",
            },
            "source": {
                "path": f"./plugins/{FIXTURE_PLUGIN_SLUG}",
                "source": "local",
            },
        }
    ]


def test_branded_skills_only_output_publishes_directly(tmp_path: Path) -> None:
    repo = _branded_skills_only_fixture_repo(tmp_path)
    applied = packager.run("apply", repo / "skills-only.json", repo)
    output_root = Path(applied["output_root"])
    before = hash_tree(output_root)

    metadata = _load_json(output_root / ".codex-plugin" / "publication-metadata.json")
    manifest = _load_json(output_root / ".codex-plugin" / "plugin.json")
    receipt = _load_json(output_root / RECEIPT_NAME)
    assert metadata["plugin_slug"] == manifest["name"]
    assert ".codex-plugin/publication-metadata.json" in receipt["generated_paths"]

    target_root = repo / "target-marketplace"
    preview = publish_lib.publish_generated_plugin(
        plugin_root=output_root,
        target_root=target_root,
        marketplace_name="bob-schumaker-codex-support",
        dry_run=True,
    )
    result = publish_lib.publish_generated_plugin(
        plugin_root=output_root,
        target_root=target_root,
        marketplace_name="bob-schumaker-codex-support",
        plan_digest=preview["plan_digest"],
    )

    assert result["source_plugins"] == ["branded-skills-only"]
    assert hash_tree(output_root) == before
    copied_root = target_root / "plugins" / "branded-skills-only"
    copied_manifest = _load_json(copied_root / ".codex-plugin" / "plugin.json")
    assert copied_manifest == manifest
    for key in ("logo", "logoDark"):
        relative = copied_manifest["interface"][key].removeprefix("./")
        assert (copied_root / relative).is_file()
        assert (copied_root / relative).read_bytes() == (
            output_root / relative
        ).read_bytes()


@pytest.mark.parametrize(
    "update",
    [
        {"format": "wrong-format"},
        {"plugin_slug": "wrong-slug"},
        {"category": "Other"},
    ],
)
def test_direct_publish_rejects_invalid_skills_only_publication_metadata(
    tmp_path: Path, update: dict[str, str]
) -> None:
    repo = _branded_skills_only_fixture_repo(tmp_path)
    applied = packager.run("apply", repo / "skills-only.json", repo)
    output_root = Path(applied["output_root"])
    metadata_path = output_root / ".codex-plugin" / "publication-metadata.json"
    metadata = _load_json(metadata_path)
    metadata.update(update)
    _write_json(metadata_path, metadata)

    target_root = repo / "target-marketplace"
    with pytest.raises(
        publish_lib.MarketplacePublishError,
        match="generated publication metadata is invalid",
    ):
        publish_lib.publish_generated_plugin(
            plugin_root=output_root,
            target_root=target_root,
            marketplace_name="bob-schumaker-codex-support",
            dry_run=True,
        )
    assert not target_root.exists()


def test_direct_publish_rejects_changed_mcp_authority_after_preview(
    tmp_path: Path,
) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])
    target_root = repo / "target-marketplace"

    preview = publish_lib.publish_generated_plugin(
        plugin_root=output_root,
        target_root=target_root,
        marketplace_name="bob-schumaker-codex-support",
        dry_run=True,
    )
    _write_json(
        repo / "router-plugin-config.json",
        {"registry_root": "changed-registry-root"},
    )

    with pytest.raises(
        publish_lib.MarketplacePublishError, match="MCP authority is stale"
    ):
        publish_lib.publish_generated_plugin(
            plugin_root=output_root,
            target_root=target_root,
            marketplace_name="bob-schumaker-codex-support",
            plan_digest=preview["plan_digest"],
        )
    assert not (target_root / "plugins" / FIXTURE_PLUGIN_SLUG).exists()


def test_direct_publish_rejects_changed_source_inventory_after_preview(
    tmp_path: Path,
) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])
    target_root = repo / "target-marketplace"

    preview = publish_lib.publish_generated_plugin(
        plugin_root=output_root,
        target_root=target_root,
        marketplace_name="bob-schumaker-codex-support",
        dry_run=True,
    )
    skill_path = repo / "skills" / FIXTURE_SKILL_ID / "SKILL.md"
    skill_path.write_text(
        skill_path.read_text(encoding="utf-8") + "\nChanged after packaging.\n",
        encoding="utf-8",
    )

    with pytest.raises(
        publish_lib.MarketplacePublishError, match="source inventory is stale"
    ):
        publish_lib.publish_generated_plugin(
            plugin_root=output_root,
            target_root=target_root,
            marketplace_name="bob-schumaker-codex-support",
            plan_digest=preview["plan_digest"],
        )
    assert not (target_root / "plugins" / FIXTURE_PLUGIN_SLUG).exists()


def test_generated_plugin_default_selection_is_single_candidate(tmp_path: Path) -> None:
    repo = _mcp_fixture_repo(tmp_path)
    applied = packager.run("apply", repo / "mcp.json", repo)
    output_root = Path(applied["output_root"])
    generated_parent = repo / ".codex-plugin" / "router-plugin-packager" / "generated"
    shutil.copytree(output_root, generated_parent / FIXTURE_PLUGIN_SLUG)

    assert publish_lib.resolve_generated_plugin_root(repo) == (
        generated_parent / FIXTURE_PLUGIN_SLUG
    )

    malformed = generated_parent / "malformed-plugin"
    shutil.copytree(output_root, malformed)
    (malformed / ".codex-plugin" / "publication-metadata.json").write_text(
        "{}\n", encoding="utf-8"
    )
    assert publish_lib.resolve_generated_plugin_root(repo) == (
        generated_parent / FIXTURE_PLUGIN_SLUG
    )

    shutil.copytree(output_root, generated_parent / "another-plugin")
    with pytest.raises(publish_lib.MarketplacePublishError, match="ambiguous"):
        publish_lib.resolve_generated_plugin_root(repo)


@pytest.mark.live
def test_live_oci_worktools_reference_can_be_recreated_from_declared_inputs(
    tmp_path: Path,
) -> None:
    source_skill = (
        LIVE_WERNER_ROOT / "oci-worktools" / "skills" / "oci-worktools" / "SKILL.md"
    )
    if not source_skill.is_file():
        pytest.skip("werner-mcp-tools OCI reference fixture is not available")
    repo = tmp_path / "werner-copy"
    shutil.copytree(LIVE_WERNER_ROOT, repo)
    invocation = repo / "oci-layer3-reference.json"
    skill_text = (
        repo / "oci-worktools" / "skills" / "oci-worktools" / "SKILL.md"
    ).read_text(encoding="utf-8")
    normalized_skill_text = " ".join(skill_text.split())
    assert (
        "Treat the active release manifest and matching capability/schema snapshot as the authority."
        in normalized_skill_text
    )
    _write_json(
        invocation,
        _mcp_invocation(
            source_root="oci-worktools/skills",
            output_root="./generated/oci-worktools",
            skill_paths=["oci-worktools/skills/oci-worktools"],
            registry_root=(
                CANONICAL_GENERATED_REGISTRY_ROOT
                if (repo / CANONICAL_GENERATED_REGISTRY_ROOT).exists()
                else LEGACY_GENERATED_REGISTRY_ROOT
            ),
            interface=_load_json(
                repo / "oci-worktools" / ".codex-plugin" / "plugin.json"
            )["interface"],
            required_byte_preserved_paths=_required_byte_preserved_paths(
                skill_id="oci-worktools"
            ),
            plugin_slug="oci-worktools",
            display_name="OCI Atlassian and Sharepoint Tools",
            surface_id="oci-worktools",
            description="OCI tools for approved Artifactory, Atlassian, and SharePoint workflows.",
            author_name="OCI Worktools",
            server_id="oci-worktools",
            package_name="werner-mcp-tools",
            entrypoint="oci-worktools-mcp",
            skill_id="oci-worktools",
        ),
    )
    _write_registry_provenance(
        repo,
        registry_root=(
            CANONICAL_GENERATED_REGISTRY_ROOT
            if (repo / CANONICAL_GENERATED_REGISTRY_ROOT).exists()
            else LEGACY_GENERATED_REGISTRY_ROOT
        ),
        source_root_text="oci-worktools/skills",
        generator_identity="werner-registry",
    )

    applied = packager.run("apply", invocation, repo)
    output_root = Path(applied["output_root"])
    generated_files = _relative_file_set(output_root)
    reference_files = _relative_file_set(repo / "oci-worktools")

    # runtime-equivalent proof against the checked-in reference plugin
    assert _load_json(output_root / ".mcp.json") == _load_json(
        repo / "oci-worktools" / ".mcp.json"
    )
    assert _load_json(output_root / ".codex-plugin" / "plugin.json") == _load_json(
        repo / "oci-worktools" / ".codex-plugin" / "plugin.json"
    )
    assert (output_root / "skills" / "oci-worktools" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == (repo / "oci-worktools" / "skills" / "oci-worktools" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert reference_files == LIVE_RUNTIME_EQUIVALENT_PATHS

    # artifact-complete proof for the generated Layer 3 output set
    assert LIVE_ARTIFACT_COMPLETE_MINIMUM_PATHS <= generated_files
    assert any(path.startswith("release-surface/schemas/") for path in generated_files)
    assert reference_files < generated_files
