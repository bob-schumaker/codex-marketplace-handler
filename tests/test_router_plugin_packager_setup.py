from __future__ import annotations

import json
from pathlib import Path


from marketplace_installer import router_plugin_packager as packager
from marketplace_installer import router_plugin_packager_setup as setup_helper
from marketplace_installer.router_plugin_packager_constants import (
    REQUIRED_MARKER_PREFIX,
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _skill(repo: Path, slug: str, description: str) -> None:
    skill_root = repo / "skills" / slug
    skill_root.mkdir(parents=True, exist_ok=True)
    (skill_root / "SKILL.md").write_text(
        f"---\nname: {slug}\ndescription: {description}\n---\n\n# {slug}\n",
        encoding="utf-8",
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ponytail"
    _skill(repo, "ponytail", "Use Ponytail mode for this task.")
    _skill(repo, "ponytail-review", "Review this diff for over-engineering.")
    assets = repo / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "logo.png").write_text("logo\n", encoding="utf-8")
    (assets / "logo-dark.png").write_text("dark\n", encoding="utf-8")
    return repo


def _ambiguous_branding_repo(tmp_path: Path) -> Path:
    repo = _repo(tmp_path)
    alt = repo / "branding"
    alt.mkdir(parents=True, exist_ok=True)
    (alt / "logo.png").write_text("other-logo\n", encoding="utf-8")
    return repo


def _catalog_repo(tmp_path: Path) -> Path:
    repo = _repo(tmp_path)
    runtime = repo / "runtimes" / "codex"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "skill-cohorts.yaml").write_text(
        """version: 1
cohorts:
  - id: ponytail
    display_name: Ponytail
    members:
      - ponytail
      - ponytail-review
""",
        encoding="utf-8",
    )
    (runtime / "router-surface.yaml").write_text(
        """version: 1
routers:
  - plugin: ponytail
    name: ponytail
    description: '__REQUIRED__: choose router description'
    members:
      - ponytail
      - ponytail-review
""",
        encoding="utf-8",
    )
    return repo


def test_scaffold_writes_complete_draft_for_unambiguous_repo(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    result = setup_helper.execute("scaffold", repo)

    invocation = _load_json(repo / setup_helper.INVOCATION_PATH)
    report = _load_json(repo / setup_helper.COMPLETENESS_REPORT_PATH)
    manifest = _load_json(repo / setup_helper.HELPER_ARTIFACTS_PATH)
    review_notes = (repo / setup_helper.REVIEW_NOTES_PATH).read_text(encoding="utf-8")

    assert result["completeness_report"]["status"] == "complete"
    assert report["status"] == "complete"
    assert invocation == {
        "display_name_override": "Ponytail",
        "format_version": 1,
        "input_mode": "skill_list",
        "output_root": "./.codex-plugin/router-plugin-packager/generated/ponytail",
        "plugin_kind": "skills_only",
        "plugin_slug_override": "ponytail",
        "repository_root": ".",
        "skill_paths": ["skills/ponytail", "skills/ponytail-review"],
        "source_root": "skills",
        "branding_asset_overrides": {
            "dark_logo": "assets/logo-dark.png",
            "logo": "assets/logo.png",
        },
    }
    assert manifest["artifacts"][0]["consumed_by_packaging"] is True
    assert "## Inferred values" in review_notes
    assert "`skill_paths`: `skills/ponytail`, `skills/ponytail-review`" in review_notes


def test_scaffold_reports_ambiguous_branding_as_incomplete(tmp_path: Path) -> None:
    repo = _ambiguous_branding_repo(tmp_path)

    result = setup_helper.execute("scaffold", repo)

    invocation = _load_json(repo / setup_helper.INVOCATION_PATH)
    report = result["completeness_report"]

    assert report["status"] == "incomplete"
    assert invocation["branding_asset_overrides"]["logo"].startswith(
        REQUIRED_MARKER_PREFIX
    )
    assert report["unresolved_placeholders"] == [
        {
            "artifact_id": "invocation",
            "field": "branding_asset_overrides.logo",
            "path": ".codex-plugin/router-plugin-packager/drafts/invocation.json",
            "value": invocation["branding_asset_overrides"]["logo"],
        }
    ]

    with Path(repo / setup_helper.INVOCATION_PATH).open("r", encoding="utf-8"):
        pass
    try:
        packager.run("plan", repo / setup_helper.INVOCATION_PATH, repo)
    except packager.PackagerError as exc:
        assert exc.error_code == "incomplete_scaffold"
    else:
        raise AssertionError("expected placeholder-bearing invocation to be rejected")


def test_scaffold_accepts_display_name_and_version_inputs(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    setup_helper.execute(
        "scaffold",
        repo,
        display_name="Ponytail Custom",
        version="1.2.3",
    )

    invocation = _load_json(repo / setup_helper.INVOCATION_PATH)

    assert invocation["display_name_override"] == "Ponytail Custom"
    assert invocation["version_override"] == "1.2.3"


def test_scaffold_writes_analysis_request_when_requested(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    result = setup_helper.execute("scaffold", repo, analyze=True)

    analysis_request = _load_json(repo / setup_helper.ANALYSIS_REQUEST_PATH)
    helper_artifacts = _load_json(repo / setup_helper.HELPER_ARTIFACTS_PATH)

    assert result["analysis_requested"] is True
    assert analysis_request["analysis_kind"] == "model_review_request"
    assert analysis_request["plugin_kind"] == "skills_only"
    assert analysis_request["inputs"]["invocation_path"] == (
        ".codex-plugin/router-plugin-packager/drafts/invocation.json"
    )
    assert analysis_request["current_unresolved_fields"] == []
    assert helper_artifacts["artifacts"][-1]["artifact_id"] == "analysis_request"


def test_mcp_scaffold_creates_durable_registry_root_without_plugin_artifact(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "empty-mcp-repo"
    repo.mkdir()

    result = setup_helper.execute(
        "scaffold", repo, plugin_kind="mcp_based", mcp_mode="bootstrap"
    )

    config = _load_json(repo / "router-plugin-config.json")
    registry_root = repo / "router-plugin-registry"
    scaffold_report = _load_json(registry_root / "scaffold-report.json")
    completeness = result["completeness_report"]

    assert config["registry_root"] == "router-plugin-registry"
    assert config["plugin_kind"] == "mcp_based"
    assert config["surface_mode"].startswith(REQUIRED_MARKER_PREFIX)
    assert "generator" not in config
    assert scaffold_report["state"] == "scaffolded"
    assert scaffold_report["required_marker_prefix"] == REQUIRED_MARKER_PREFIX
    assert {
        "manifest.json",
        "release-manifest.json",
        "operation-registry.json",
        "scaffold-report.json",
    } <= {path.name for path in registry_root.iterdir()}
    assert (registry_root / "schemas").is_dir()
    assert completeness["status"] == "incomplete"
    assert not (repo / ".codex-plugin" / "plugin.json").exists()
    assert not (repo / ".mcp.json").exists()


def test_validate_reports_missing_required_artifact(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    setup_helper.execute("scaffold", repo)
    (repo / setup_helper.INVOCATION_PATH).unlink()

    result = setup_helper.execute("validate", repo)

    assert result["completeness_report"]["status"] == "incomplete"
    assert result["completeness_report"]["missing_required_files"] == [
        {
            "artifact_id": "invocation",
            "path": ".codex-plugin/router-plugin-packager/drafts/invocation.json",
        }
    ]


def test_packager_rejects_placeholder_bearing_catalog_inputs(tmp_path: Path) -> None:
    repo = _catalog_repo(tmp_path)
    invocation_path = repo / "catalog-invocation.json"
    invocation_path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "input_mode": "catalog",
                "plugin_kind": "skills_only",
                "repository_root": ".",
                "output_root": "./.codex-plugin/router-plugin-packager/generated/ponytail",
                "source_root": "skills",
                "cohort_catalog_path": "runtimes/codex/skill-cohorts.yaml",
                "router_catalog_path": "runtimes/codex/router-surface.yaml",
                "cohort_id": "ponytail",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        packager.run("plan", invocation_path, repo)
    except packager.PackagerError as exc:
        assert exc.error_code == "incomplete_scaffold"
        assert exc.details["router_placeholders"] == [
            {
                "field": "routers[0].description",
                "value": "__REQUIRED__: choose router description",
            }
        ]
    else:
        raise AssertionError("expected placeholder-bearing catalog to be rejected")
