from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest


from marketplace_installer import mcp_plugin_packaging_customer_flow as customer_flow
from marketplace_installer import router_plugin_packager_setup as setup_helper
from marketplace_installer.router_plugin_packager_constants import (
    REQUIRED_MARKER_PREFIX,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_schema_bundle(root: Path) -> None:
    schemas = root / "schemas"
    schemas.mkdir(parents=True, exist_ok=True)
    (schemas / "jira.issue.update.input.json").write_text("{}", encoding="utf-8")
    (schemas / "sharepoint.site.read.output.json").write_text("{}", encoding="utf-8")


def _write_source_native_packaging_evidence(repo: Path) -> None:
    (repo / ".mise.toml").write_text(
        """[tools]
python = "3.14.6"
""",
        encoding="utf-8",
    )


def _write_completed_setup_contract(repo: Path, registry_root: Path) -> None:
    registry_relpath = registry_root.relative_to(repo).as_posix()
    _write_json(
        repo / customer_flow.MCP_CONFIG_PATH,
        {
            "format_version": 1,
            "plugin_kind": "mcp_based",
            "protocol_version": "1.0",
            "registry_root": registry_relpath,
            "surface_mode": "preserve_mcp_first",
            "input_manifest_path": f"{registry_relpath}/setup-input-manifest.json",
        },
    )
    _write_json(
        registry_root / "setup-input-manifest.json",
        {
            "format_version": 1,
            "config_path": customer_flow.MCP_CONFIG_PATH.as_posix(),
            "registry_root": registry_relpath,
            "required_inputs": [
                f"{registry_relpath}/manifest.json",
                f"{registry_relpath}/release-manifest.json",
                f"{registry_relpath}/operation-registry.json",
                f"{registry_relpath}/schemas",
            ],
        },
    )
    _write_json(
        registry_root / customer_flow.MCP_SCAFFOLD_REPORT_NAME,
        {
            "format_version": 1,
            "state": "complete",
            "required_marker_prefix": REQUIRED_MARKER_PREFIX,
            "registry_root": registry_relpath,
        },
    )
    (repo / "pyproject.toml").write_text(
        """[project]
name = "werner-mcp-tools"
version = "0.1.1"

[tool.poetry]

[[tool.poetry.source]]
name = "global-release-pypi"
url = "https://artifactory.oci.oraclecorp.com/api/pypi/global-release-pypi/simple"
priority = "primary"

[project.scripts]
oci-worktools-mcp = "werner_mcp_tools.mcp.server:main"
""",
        encoding="utf-8",
    )
    specs = repo / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / "03-oci-codex-plugin.md").write_text(
        """# Draft: OCI Codex plugin

```json
{
  "name": "oci-worktools",
  "version": "0.1.0",
  "description": "OCI tools for approved Artifactory, Atlassian, and SharePoint workflows.",
  "skills": "./skills/",
  "mcpServers": "./.mcp.json",
  "author": { "name": "Bob Schumaker" },
  "interface": {
    "displayName": "OCI Atlassian and Sharepoint Tools",
    "shortDescription": "Artifactory, Atlassian, and SharePoint workflows",
    "longDescription": "Use typed OCI MCP tools for approved enterprise reads and verified mutations.",
    "developerName": "Werner OCI",
    "category": "Productivity",
    "capabilities": ["Read", "Write"],
    "defaultPrompt": [
      "Find Jira issues assigned to me that are due this week."
    ]
  }
}
```
""",
        encoding="utf-8",
    )


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "werner-like"
    plugin_root = repo / "oci-worktools"
    (plugin_root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (plugin_root / "skills" / "oci-worktools").mkdir(parents=True, exist_ok=True)
    _write_json(
        plugin_root / ".codex-plugin" / "plugin.json",
        {
            "author": {"name": "Bob Schumaker"},
            "description": "OCI tools for approved Artifactory, Atlassian, and SharePoint workflows.",
            "interface": {
                "capabilities": ["Read", "Write"],
                "category": "Productivity",
                "defaultPrompt": [
                    "Find Jira issues assigned to me that are due this week."
                ],
                "developerName": "Werner OCI",
                "displayName": "OCI Atlassian and Sharepoint Tools",
                "longDescription": "Use typed OCI MCP tools for approved enterprise reads and verified mutations.",
                "shortDescription": "Artifactory, Atlassian, and SharePoint workflows",
            },
            "mcpServers": "./.mcp.json",
            "name": "oci-worktools",
            "skills": "./skills/",
            "version": "0.1.1",
        },
    )
    _write_json(
        plugin_root / ".mcp.json",
        {
            "mcpServers": {
                "oci-worktools": {
                    "command": "uvx",
                    "args": [
                        "--python",
                        "3.14.6",
                        "--default-index",
                        "https://artifactory.oci.oraclecorp.com/api/pypi/global-release-pypi/simple",
                        "--from",
                        "werner-mcp-tools",
                        "oci-worktools-mcp",
                        "--stdio",
                    ],
                }
            }
        },
    )
    (plugin_root / "skills" / "oci-worktools" / "SKILL.md").write_text(
        """---
name: oci-worktools
description: Use OCI Worktools MCP tools for approved enterprise reads and verified mutations.
---

# OCI Worktools

- Treat the active release manifest and matching capability/schema snapshot as the authority.
- Never invoke SharePoint write behavior; no SharePoint write tool is registered in this release.
- Do not claim that a disabled capability can be activated by changing credentials, tenants, endpoints, profiles, or approval settings.
""",
        encoding="utf-8",
    )
    registry_root = repo / customer_flow.MCP_REGISTRY_ROOT
    registry_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        registry_root / "manifest.json",
        {
            "format_version": 1,
            "release_asset_inventory": [
                "manifest.json",
                "release-manifest.json",
                "operation-registry.json",
                "schemas",
            ],
            "release_manifest_path": "release-manifest.json",
            "operation_registry_path": "operation-registry.json",
            "schemas_root": "schemas",
        },
    )
    _write_json(
        registry_root / "release-manifest.json",
        {
            "artifact_policy": {
                "plugin_id": "oci-worktools",
            },
            "name": "release",
            "package": {
                "entry_point": "oci-worktools-mcp",
                "name": "werner-mcp-tools",
                "version": "0.1.1",
            },
            "selected_operation_ids": [
                "jira.issue.update",
                "sharepoint.site.read",
            ],
        },
    )
    _write_json(
        registry_root / "operation-registry.json",
        {
            "operations": [
                {"operation_id": "jira.issue.update"},
                {"operation_id": "sharepoint.site.read"},
            ]
        },
    )
    _write_schema_bundle(registry_root)
    _write_source_native_packaging_evidence(repo)
    _write_completed_setup_contract(repo, registry_root)
    return repo


def test_preview_persists_invocation_and_report(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    result = customer_flow.execute("preview", repo)

    invocation_path = Path(result["invocation_path"])
    report_path = Path(result["derivation_report_path"])
    assert invocation_path.is_file()
    assert report_path.is_file()
    assert result["invocation"] == _load_json(invocation_path)
    assert result["derivation_report"] == _load_json(report_path)
    assert result["invocation"]["input_mode"] == "skill_list"
    assert result["invocation"]["plugin_kind"] == "mcp_based"
    assert result["derivation_report"]["mode"] == "reconciliation"


def test_unknown_override_key_is_rejected(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    overrides = repo / "overrides.json"
    _write_json(overrides, {"unknown_key": "value"})

    with pytest.raises(customer_flow.CustomerFlowError) as exc_info:
        customer_flow.execute("preview", repo, overrides_path=overrides)

    assert exc_info.value.error_code == "unknown_override_key"


def test_ambiguous_plugin_candidates_are_rejected(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    second = repo / "oci-worktools-copy"
    shutil.copytree(repo / "oci-worktools", second)

    with pytest.raises(customer_flow.CustomerFlowError) as exc_info:
        customer_flow.execute("preview", repo)

    assert exc_info.value.error_code == "ambiguous_candidates"


def test_client_authored_release_surface_needs_no_provenance_sidecars(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)
    result = customer_flow.execute("preview", repo)

    assert all(
        asset["acquisition_mode"] == "copied" and "provenance_path" not in asset
        for asset in result["invocation"]["payload_assets"]
    )


def test_customer_flow_rejects_missing_durable_registry(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)
    shutil.rmtree(repo / customer_flow.MCP_REGISTRY_ROOT)

    with pytest.raises(customer_flow.CustomerFlowError) as exc_info:
        customer_flow.execute("preview", repo, mode="bootstrap")

    assert exc_info.value.error_code == "mcp_setup_invalid"


def test_bootstrap_mode_accepts_client_authored_release_surface(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)
    result = customer_flow.execute("preview", repo, mode="bootstrap")

    assert result["command"] == "preview"


def test_bootstrap_mode_can_recreate_plugin_without_checked_in_wrapper(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)
    source_plugin_root = repo / "oci-worktools"
    expected_plugin_manifest = _load_json(
        source_plugin_root / ".codex-plugin" / "plugin.json"
    )
    expected_mcp = _load_json(source_plugin_root / ".mcp.json")
    expected_skill = (
        source_plugin_root / "skills" / "oci-worktools" / "SKILL.md"
    ).read_text(encoding="utf-8")
    shutil.rmtree(source_plugin_root / ".codex-plugin")
    (source_plugin_root / ".mcp.json").unlink()

    result = customer_flow.execute("apply", repo, mode="bootstrap")

    generated_root = Path(
        os.path.commonpath(result["packager"]["generated_output_paths"])
    )
    assert generated_root == (
        repo
        / ".codex-plugin"
        / "router-plugin-packager"
        / "generated"
        / "oci-worktools"
    )
    assert (
        _load_json(generated_root / ".codex-plugin" / "plugin.json")
        == expected_plugin_manifest
    )
    assert _load_json(generated_root / ".mcp.json") == expected_mcp
    assert (generated_root / "skills" / "oci-worktools" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == expected_skill


def test_plan_and_apply_use_persisted_invocation_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _fixture_repo(tmp_path)
    calls: list[tuple[str, Path, Path]] = []
    handoff_payloads: list[dict] = []

    def _fake_run(command: str, invocation_path: Path, repo_root: Path) -> dict:
        handoff_payloads.append(_load_json(invocation_path))
        calls.append((command, invocation_path, repo_root))
        return {"command": command, "invocation_path": str(invocation_path)}

    monkeypatch.setattr(customer_flow.router_packager, "run", _fake_run)

    planned = customer_flow.execute("plan", repo)
    applied = customer_flow.execute("apply", repo)

    assert calls[0][0] == "plan"
    assert calls[1][0] == "plan"
    assert calls[2][0] == "apply"
    assert calls[0][1] != Path(planned["invocation_path"])
    assert calls[1][1] != Path(applied["invocation_path"])
    assert calls[2][1] != Path(applied["invocation_path"])
    assert calls[0][1].parent == repo
    assert calls[1][1].parent == repo
    assert calls[2][1].parent == repo
    assert not calls[0][1].exists()
    assert not calls[1][1].exists()
    assert not calls[2][1].exists()
    assert calls[0][2] == repo.resolve()
    assert calls[1][2] == repo.resolve()
    assert calls[2][2] == repo.resolve()
    assert (
        handoff_payloads[0]["output_root"]
        == "./.codex-plugin/router-plugin-packager/generated/oci-worktools"
    )
    assert (
        handoff_payloads[1]["output_root"]
        == "./.codex-plugin/router-plugin-packager/generated/oci-worktools"
    )
    assert (
        handoff_payloads[2]["output_root"]
        == "./.codex-plugin/router-plugin-packager/generated/oci-worktools"
    )


def test_preview_apply_preview_ignores_wrapper_generated_plugin_copy(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)

    first = customer_flow.execute("preview", repo)
    applied = customer_flow.execute("apply", repo)
    second = customer_flow.execute("preview", repo)
    first_report = _load_json(Path(first["derivation_report_path"]))
    second_report = _load_json(Path(second["derivation_report_path"]))

    assert first["invocation"]["surface_id_override"] == "oci-worktools"
    assert applied["packager"]["surface_id"] == "oci-worktools"
    assert second["invocation"]["surface_id_override"] == "oci-worktools"
    assert first_report["selected_values"]["plugin_root"] == "oci-worktools"
    assert second_report["selected_values"]["plugin_root"] == "oci-worktools"
    assert first_report["source_evidence"]["candidate_source"] == "checked_in_plugin"
    assert second_report["source_evidence"]["candidate_source"] == "checked_in_plugin"


def test_changed_skill_content_changes_evidence_fingerprint(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)

    first = customer_flow.execute("preview", repo)
    first_report = _load_json(Path(first["derivation_report_path"]))

    skill_path = repo / "oci-worktools" / "skills" / "oci-worktools" / "SKILL.md"
    skill_path.write_text(
        skill_path.read_text(encoding="utf-8")
        + "\n- Keep enterprise reads narrowly scoped to the request.\n",
        encoding="utf-8",
    )

    second = customer_flow.execute("preview", repo)
    second_report = _load_json(Path(second["derivation_report_path"]))

    assert first_report["evidence_fingerprint"] != second_report["evidence_fingerprint"]


def test_changed_release_surface_changes_evidence_fingerprint(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)

    first = customer_flow.execute("preview", repo)
    first_report = _load_json(Path(first["derivation_report_path"]))

    manifest_path = repo / customer_flow.MCP_REGISTRY_ROOT / "manifest.json"
    payload = _load_json(manifest_path)
    payload["version"] = "1.1"
    _write_json(manifest_path, payload)

    second = customer_flow.execute("preview", repo)
    second_report = _load_json(Path(second["derivation_report_path"]))

    assert first_report["evidence_fingerprint"] != second_report["evidence_fingerprint"]


def test_customer_flow_accepts_client_completed_registry_without_provenance_coupling(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)
    release_manifest_path = (
        repo / customer_flow.MCP_REGISTRY_ROOT / "release-manifest.json"
    )
    release_manifest = _load_json(release_manifest_path)
    release_manifest["selected_operation_ids"].append("sharepoint.site.write")
    _write_json(release_manifest_path, release_manifest)

    result = customer_flow.execute("preview", repo)

    assert result["command"] == "preview"


def test_plan_runs_real_packager_and_returns_normalized_request(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)

    result = customer_flow.execute("plan", repo)

    assert result["packager"]["surface_id"] == "oci-worktools"
    assert result["packager"]["input_mode"] == "skill_list"
    assert result["packager"]["normalized_request"]["skill_ids"] == ["oci-worktools"]


def test_setup_helper_scaffolds_complete_mcp_draft_when_evidence_is_sufficient(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)

    result = setup_helper.execute(
        "scaffold", repo, plugin_kind="mcp_based", mcp_mode="reconciliation"
    )

    invocation = _load_json(repo / setup_helper.INVOCATION_PATH)
    report = _load_json(repo / setup_helper.COMPLETENESS_REPORT_PATH)
    derivation_report = _load_json(repo / setup_helper.MCP_DERIVATION_REPORT_PATH)
    helper_artifacts = _load_json(repo / setup_helper.HELPER_ARTIFACTS_PATH)

    assert result["plugin_kind"] == "mcp_based"
    assert report["status"] == "complete"
    assert invocation["plugin_kind"] == "mcp_based"
    assert invocation["mcp_packaging"]["plugin_artifact_contract"]["name"] == (
        "oci-worktools"
    )
    assert invocation["mcp_packaging"]["plugin_artifact_contract"]["author"] == {
        "name": "Bob Schumaker"
    }
    assert invocation["mcp_packaging"]["publication"] == {"category": "Productivity"}
    assert invocation["publication"] == {"category": "Productivity"}
    assert invocation["payload_assets"][0]["source"] == (
        "router-plugin-registry/manifest.json"
    )
    assert derivation_report["selected_values"]["registry_root"] == (
        "router-plugin-registry"
    )
    assert {artifact["artifact_id"] for artifact in helper_artifacts["artifacts"]} >= {
        "mcp_config",
        "mcp_derivation_report",
        "mcp_scaffold_report",
    }


def test_setup_helper_scaffolds_incomplete_mcp_draft_when_registry_evidence_is_missing(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)
    shutil.rmtree(repo / customer_flow.MCP_REGISTRY_ROOT)

    result = setup_helper.execute(
        "scaffold", repo, plugin_kind="mcp_based", mcp_mode="reconciliation"
    )

    invocation = _load_json(repo / setup_helper.INVOCATION_PATH)
    report = result["completeness_report"]

    assert report["status"] == "incomplete"
    assert invocation["plugin_kind"] == "mcp_based"
    assert invocation["display_name_override"] == "OCI Worktools"
    assert invocation["plugin_slug_override"] == "oci-worktools"
    assert invocation["surface_id_override"] == "oci-worktools"
    assert invocation["output_root"] == (
        "./.codex-plugin/router-plugin-packager/generated/oci-worktools"
    )
    assert invocation["mcp_packaging"].startswith(REQUIRED_MARKER_PREFIX)
    unresolved_fields = {item["field"] for item in report["unresolved_placeholders"]}
    assert "plugin_kind" not in unresolved_fields
    assert "mcp_packaging" in unresolved_fields


def test_customer_flow_rejects_marker_bearing_durable_scaffold_before_writes(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "empty-mcp-repo"
    repo.mkdir()
    setup_helper.execute(
        "scaffold", repo, plugin_kind="mcp_based", mcp_mode="bootstrap"
    )

    with pytest.raises(customer_flow.CustomerFlowError) as error:
        customer_flow.execute("preview", repo, mode="bootstrap")

    assert error.value.error_code == "mcp_setup_incomplete"
    assert not (repo / customer_flow.DERIVED_INVOCATIONS_DIR).exists()
    assert not (repo / customer_flow.DERIVATION_REPORTS_DIR).exists()


def test_package_scaffolds_once_then_reports_awaiting_completion(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "empty-mcp-repo"
    repo.mkdir()

    first = customer_flow.execute("package", repo, mode="bootstrap")
    config_bytes = (repo / customer_flow.MCP_CONFIG_PATH).read_bytes()
    second = customer_flow.execute("package", repo, mode="bootstrap")

    assert first["outcome"] == "scaffold_created"
    assert first["diagnostic_code"] == "mcp_setup_required"
    assert first["plugin_generated"] is False
    assert first["published"] is False
    assert first["installed"] is False
    assert _load_json(repo / customer_flow.MCP_CONFIG_PATH)["mcp_packaging"] == {
        "launch_contract": {
            "schema_version": 2,
            "environment": {},
            "environment_authority": "config",
        }
    }
    assert second["outcome"] == "awaiting_completion"
    assert second["diagnostic_code"] == "mcp_setup_incomplete"
    assert (repo / customer_flow.MCP_CONFIG_PATH).read_bytes() == config_bytes
    assert not (repo / customer_flow.DERIVED_INVOCATIONS_DIR).exists()


def test_package_rejects_legacy_state_without_scaffolding(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    legacy_root = repo / "src" / "werner_mcp_tools" / "generated_registry"
    legacy_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo / customer_flow.MCP_REGISTRY_ROOT, legacy_root)
    shutil.rmtree(repo / customer_flow.MCP_REGISTRY_ROOT)
    (repo / customer_flow.MCP_CONFIG_PATH).unlink()

    result = customer_flow.execute("package", repo, mode="bootstrap")

    assert result["outcome"] == "invalid"
    assert result["diagnostic_code"] == "mcp_setup_migration_required"
    assert not (repo / customer_flow.MCP_CONFIG_PATH).exists()


def test_package_rejects_orphaned_registry_without_scaffolding(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    (repo / customer_flow.MCP_CONFIG_PATH).unlink()

    result = customer_flow.execute("package", repo, mode="bootstrap")

    assert result["outcome"] == "invalid"
    assert result["diagnostic_code"] == "mcp_setup_invalid_state"
    assert not (repo / customer_flow.MCP_CONFIG_PATH).exists()


def test_package_runs_complete_flow_and_is_repeatable(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)

    first = customer_flow.execute("package", repo, mode="bootstrap")
    migrated_config_bytes = (repo / customer_flow.MCP_CONFIG_PATH).read_bytes()
    second = customer_flow.execute("package", repo, mode="bootstrap")

    generated = (
        repo
        / ".codex-plugin"
        / "router-plugin-packager"
        / "generated"
        / "oci-worktools"
    )
    assert first["outcome"] == "packaged"
    assert first["plugin_generated"] is True
    assert first["published"] is False
    assert first["installed"] is False
    assert second["outcome"] == "packaged"
    assert (generated / ".codex-plugin" / "plugin.json").is_file()
    assert (repo / customer_flow.MCP_CONFIG_PATH).read_bytes() == migrated_config_bytes
    assert _load_json(repo / customer_flow.MCP_CONFIG_PATH)["mcp_packaging"] == {
        "launch_contract": {
            "schema_version": 2,
            "environment": {},
            "environment_authority": "config",
        }
    }


def test_setup_helper_uses_display_name_and_version_for_incomplete_mcp_draft(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)
    shutil.rmtree(repo / customer_flow.MCP_REGISTRY_ROOT)

    setup_helper.execute(
        "scaffold",
        repo,
        plugin_kind="mcp_based",
        mcp_mode="reconciliation",
        display_name="OCI Worktools Custom",
        version="9.9.9",
    )

    invocation = _load_json(repo / setup_helper.INVOCATION_PATH)
    report = _load_json(repo / setup_helper.COMPLETENESS_REPORT_PATH)
    unresolved_fields = {item["field"] for item in report["unresolved_placeholders"]}

    assert invocation["display_name_override"] == "OCI Worktools Custom"
    assert invocation["plugin_slug_override"] == "oci-worktools-custom"
    assert invocation["surface_id_override"] == "oci-worktools-custom"
    assert invocation["output_root"] == (
        "./.codex-plugin/router-plugin-packager/generated/oci-worktools-custom"
    )
    assert invocation["version_override"] == "9.9.9"
    assert "display_name_override" not in unresolved_fields
    assert "version_override" not in unresolved_fields
    assert "mcp_packaging" in unresolved_fields


def test_setup_helper_uses_display_name_for_complete_mcp_slug_defaults(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)

    setup_helper.execute(
        "scaffold",
        repo,
        plugin_kind="mcp_based",
        mcp_mode="reconciliation",
        display_name="OCI Worktools Custom",
    )

    invocation = _load_json(repo / setup_helper.INVOCATION_PATH)

    assert invocation["display_name_override"] == "OCI Worktools Custom"
    assert invocation["plugin_slug_override"] == "oci-worktools-custom"
    assert invocation["surface_id_override"] == "oci-worktools-custom"
    assert invocation["output_root"] == (
        "./.codex-plugin/router-plugin-packager/generated/oci-worktools-custom"
    )


def test_setup_helper_writes_analysis_request_for_incomplete_mcp_draft(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)
    shutil.rmtree(repo / customer_flow.MCP_REGISTRY_ROOT)

    result = setup_helper.execute(
        "scaffold",
        repo,
        plugin_kind="mcp_based",
        mcp_mode="reconciliation",
        analyze=True,
    )

    analysis_request = _load_json(repo / setup_helper.ANALYSIS_REQUEST_PATH)
    helper_artifacts = _load_json(repo / setup_helper.HELPER_ARTIFACTS_PATH)

    assert result["analysis_requested"] is True
    assert analysis_request["plugin_kind"] == "mcp_based"
    assert analysis_request["mcp_mode"] == "reconciliation"
    assert "mcp_packaging" in analysis_request["current_unresolved_fields"]
    assert {artifact["artifact_id"] for artifact in helper_artifacts["artifacts"]} >= {
        "analysis_request",
        "mcp_derivation_report",
    }


def test_parse_launch_contract_preserves_extra_args_before_stdio() -> None:
    parsed = customer_flow._parse_launch_contract(
        {
            "mcpServers": {
                "sample": {
                    "command": "uvx",
                    "args": [
                        "--python",
                        "3.14.6",
                        "--default-index",
                        "https://packages.example.test/simple",
                        "--from",
                        "sample-package",
                        "sample-entrypoint",
                        "--verbose",
                        "--stdio",
                    ],
                }
            }
        }
    )

    assert parsed["extra_args"] == ["--verbose"]


def test_parse_launch_contract_preserves_native_environment() -> None:
    parsed = customer_flow._parse_launch_contract(
        {
            "mcpServers": {
                "sample": {
                    "command": "uvx",
                    "args": [
                        "--python",
                        "3.14.6",
                        "--default-index",
                        "https://packages.example.test/simple",
                        "--from",
                        "sample-package",
                        "sample-entrypoint",
                        "--stdio",
                    ],
                    "env": {"UV_INDEX_URL": "https://packages.example.test/simple"},
                }
            }
        }
    )

    assert parsed["schema_version"] == 2
    assert parsed["environment_authority"] == "native_descriptor"
    assert parsed["environment"] == {
        "UV_INDEX_URL": "https://packages.example.test/simple"
    }


@pytest.mark.parametrize(
    "mcp_json",
    [
        {},
        {"mcpServers": {}, "extra": {}},
        {"mcpServers": {"one": {}, "two": {}}},
        {"mcpServers": {"sample": {"command": "uvx", "args": [], "cwd": "."}}},
    ],
)
def test_parse_launch_contract_rejects_ambiguous_native_shapes(
    mcp_json: dict,
) -> None:
    with pytest.raises(customer_flow.CustomerFlowError) as exc_info:
        customer_flow._parse_launch_contract(mcp_json)

    assert exc_info.value.error_code == "insufficient_evidence"


def test_config_launch_environment_is_atomic_client_authority() -> None:
    environment = customer_flow._config_launch_environment(
        {
            "mcp_packaging": {
                "launch_contract": {
                    "environment": {
                        "UV_INDEX_URL": "https://packages.example.test/simple"
                    }
                }
            }
        }
    )

    assert environment == {"UV_INDEX_URL": "https://packages.example.test/simple"}


def test_config_launch_environment_rejects_non_environment_override() -> None:
    with pytest.raises(customer_flow.CustomerFlowError) as exc_info:
        customer_flow._config_launch_environment(
            {"mcp_packaging": {"launch_contract": {"command": "uvx"}}}
        )

    assert exc_info.value.error_code == "mcp_setup_invalid"


def test_preview_uses_config_environment_as_atomic_authority(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    config = _load_json(repo / customer_flow.MCP_CONFIG_PATH)
    config["mcp_packaging"] = {
        "launch_contract": {
            "environment": {"UV_INDEX_URL": "https://packages.example.test/simple"}
        }
    }
    _write_json(repo / customer_flow.MCP_CONFIG_PATH, config)

    result = customer_flow.execute("preview", repo)
    launch_contract = result["invocation"]["mcp_packaging"]["launch_contract"]

    assert launch_contract["schema_version"] == 2
    assert launch_contract["environment_authority"] == "config"
    assert launch_contract["environment"] == {
        "UV_INDEX_URL": "https://packages.example.test/simple"
    }


def test_apply_preserves_v3_config_package_version_selector(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    config_path = repo / customer_flow.MCP_CONFIG_PATH
    config = _load_json(config_path)
    config["mcp_packaging"] = {
        "launch_contract": {
            "schema_version": 3,
            "environment": {},
            "environment_authority": "config",
            "package_version": "0.1.1",
        }
    }
    _write_json(config_path, config)
    original_bytes = config_path.read_bytes()

    result = customer_flow.execute("apply", repo)

    assert config_path.read_bytes() == original_bytes
    launch_contract = result["invocation"]["mcp_packaging"]["launch_contract"]
    assert launch_contract["schema_version"] == 3
    assert launch_contract["package_version"] == "0.1.1"
    output_root = Path(result["packager"]["output_root"])
    descriptor = _load_json(output_root / ".mcp.json")["mcpServers"]["oci-worktools"]
    assert descriptor["args"][5] == "werner-mcp-tools==0.1.1"


def test_preview_reports_v1_config_migration_without_rewriting_config(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)
    config_path = repo / customer_flow.MCP_CONFIG_PATH
    original_bytes = config_path.read_bytes()

    result = customer_flow.execute("preview", repo)

    assert config_path.read_bytes() == original_bytes
    assert result["derivation_report"]["pending_config_migration"] == {
        "format": "mcp-launch-contract-config-migration-v1",
        "config_path": "router-plugin-config.json",
        "from": "v1_launch_contract",
        "to": {
            "schema_version": 2,
            "environment": {},
            "environment_authority": "config",
        },
    }


def test_apply_migrates_v1_config_before_generating_plugin(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)

    result = customer_flow.execute("apply", repo)

    config = _load_json(repo / customer_flow.MCP_CONFIG_PATH)
    assert config["mcp_packaging"]["launch_contract"] == {
        "schema_version": 2,
        "environment": {},
        "environment_authority": "config",
    }
    assert result["invocation"]["mcp_packaging"]["launch_contract"] == {
        **result["invocation"]["mcp_packaging"]["launch_contract"],
        "schema_version": 2,
        "environment": {},
        "environment_authority": "config",
    }
    output_root = Path(result["packager"]["output_root"])
    assert (
        "env"
        not in _load_json(output_root / ".mcp.json")["mcpServers"]["oci-worktools"]
    )


@pytest.mark.parametrize(
    "environment",
    [{}, {"UV_INDEX_URL": "https://packages.example.test/simple"}],
)
def test_apply_preserves_existing_v2_environment_config(
    tmp_path: Path, environment: dict[str, str]
) -> None:
    repo = _fixture_repo(tmp_path)
    config_path = repo / customer_flow.MCP_CONFIG_PATH
    config = _load_json(config_path)
    config["mcp_packaging"] = {
        "launch_contract": {
            "schema_version": 2,
            "environment": environment,
            "environment_authority": "config",
        }
    }
    _write_json(config_path, config)
    original_bytes = config_path.read_bytes()

    result = customer_flow.execute("apply", repo)

    assert config_path.read_bytes() == original_bytes
    assert result["derivation_report"]["pending_config_migration"] is None
    output_root = Path(result["packager"]["output_root"])
    descriptor = _load_json(output_root / ".mcp.json")["mcpServers"]["oci-worktools"]
    if environment:
        assert descriptor["env"] == environment
    else:
        assert "env" not in descriptor


def test_apply_upgrades_legacy_environment_override_to_v2(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    config_path = repo / customer_flow.MCP_CONFIG_PATH
    config = _load_json(config_path)
    config["mcp_packaging"] = {
        "launch_contract": {
            "environment": {"UV_INDEX_URL": "https://packages.example.test/simple"}
        }
    }
    _write_json(config_path, config)

    customer_flow.execute("apply", repo)

    assert _load_json(config_path)["mcp_packaging"]["launch_contract"] == {
        "schema_version": 2,
        "environment": {"UV_INDEX_URL": "https://packages.example.test/simple"},
        "environment_authority": "config",
    }


def test_apply_preflight_failure_leaves_v1_config_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _fixture_repo(tmp_path)
    config_path = repo / customer_flow.MCP_CONFIG_PATH
    original_bytes = config_path.read_bytes()

    def _failing_plan(command: str, _payload: dict, _repo_root: Path) -> dict:
        assert command == "plan"
        raise customer_flow.PackagerError("preflight_failed", "blocked", {})

    monkeypatch.setattr(customer_flow, "_run_packager_handoff", _failing_plan)

    with pytest.raises(customer_flow.PackagerError, match="blocked"):
        customer_flow.execute("apply", repo)

    assert config_path.read_bytes() == original_bytes
    assert not (repo / customer_flow.DERIVED_GENERATED_DIR).exists()


def test_apply_atomic_config_failure_leaves_v1_config_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _fixture_repo(tmp_path)
    config_path = repo / customer_flow.MCP_CONFIG_PATH
    original_bytes = config_path.read_bytes()

    monkeypatch.setattr(
        customer_flow,
        "_run_packager_handoff",
        lambda command, _payload, _repo_root: {"command": command},
    )

    def _replace_failure(_source: Path, _target: Path) -> None:
        raise OSError("replace blocked")

    monkeypatch.setattr(customer_flow.os, "replace", _replace_failure)

    with pytest.raises(OSError, match="replace blocked"):
        customer_flow.execute("apply", repo)

    assert config_path.read_bytes() == original_bytes
    assert not list(repo.glob(".router-plugin-config.json.*.tmp"))
    assert not (repo / customer_flow.DERIVED_GENERATED_DIR).exists()


@pytest.mark.parametrize(
    "source",
    ["config", "override"],
)
def test_preview_rejects_invalid_environment_before_derived_writes(
    tmp_path: Path, source: str
) -> None:
    repo = _fixture_repo(tmp_path)
    environment_override = {
        "mcp_packaging": {"launch_contract": {"environment": {"bad": "x"}}}
    }
    overrides_path = None
    if source == "config":
        config = _load_json(repo / customer_flow.MCP_CONFIG_PATH)
        config.update(environment_override)
        _write_json(repo / customer_flow.MCP_CONFIG_PATH, config)
    else:
        overrides_path = repo / "overrides.json"
        _write_json(overrides_path, environment_override)

    with pytest.raises(customer_flow.CustomerFlowError) as exc_info:
        customer_flow.execute("preview", repo, overrides_path=overrides_path)

    assert exc_info.value.error_code == "env_invalid_name"
    assert not (repo / customer_flow.DERIVED_INVOCATIONS_DIR).exists()
    assert not (repo / customer_flow.DERIVATION_REPORTS_DIR).exists()


def test_customer_flow_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"mcpServers": {}, "mcpServers": {}}', encoding="utf-8")

    with pytest.raises(customer_flow.CustomerFlowError) as exc_info:
        customer_flow._load_json(path)

    assert exc_info.value.error_code == "invalid_json_duplicate_key"


@pytest.mark.live
def test_bootstrap_rejects_real_legacy_werner_registry(tmp_path: Path) -> None:
    source_repo = Path("../werner-mcp-tools").resolve()
    if not source_repo.is_dir():
        pytest.skip("werner-mcp-tools repo is not available")
    if (source_repo / customer_flow.MCP_CONFIG_PATH).is_file() and not any(
        source_repo.rglob("generated_registry")
    ):
        pytest.skip("werner-mcp-tools repo is no longer in the legacy registry shape")

    repo = tmp_path / "werner-mcp-tools"
    shutil.copytree(source_repo, repo)

    with pytest.raises(customer_flow.CustomerFlowError) as exc_info:
        customer_flow.execute("apply", repo, mode="bootstrap")

    assert exc_info.value.error_code in {
        "mcp_setup_migration_required",
        "mcp_setup_invalid",
    }


def test_preview_rejects_legacy_tracked_generated_registry_without_config(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)
    canonical_root = repo / customer_flow.MCP_REGISTRY_ROOT
    legacy_root = repo / "src" / "werner_mcp_tools" / "generated_registry"
    legacy_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(canonical_root, legacy_root)
    shutil.rmtree(canonical_root)
    (repo / customer_flow.MCP_CONFIG_PATH).unlink()

    with pytest.raises(customer_flow.CustomerFlowError) as exc_info:
        customer_flow.execute("preview", repo)

    assert exc_info.value.error_code == "mcp_setup_migration_required"
