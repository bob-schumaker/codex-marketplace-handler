from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


from marketplace_installer import router_plugin_packager as packager

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "router_plugin_packager"
CONTRACT = FIXTURES / "any-repo-contract"
SCHEMA_DIR = FIXTURES / "schemas"
MIRROR = FIXTURES / "contract"
LIVE_PONYTAIL_REPO = "https://github.com/DietrichGebert/ponytail.git"
LIVE_PONYTAIL_SKILLS = [
    "skills/ponytail",
    "skills/ponytail-audit",
    "skills/ponytail-debt",
    "skills/ponytail-gain",
    "skills/ponytail-help",
    "skills/ponytail-review",
]


def test_core_development_publish_invocation_declares_direct_publish_contract() -> None:
    invocation = _load_json(
        FIXTURES / "runtimes" / "codex" / "core-development-publish.json"
    )

    assert invocation == {
        "format_version": 1,
        "input_mode": "catalog",
        "repository_root": ".",
        "output_root": "../../.codex-plugin/router-plugin-packager/generated/core-development",
        "source_root": "corpus/capabilities",
        "cohort_catalog_path": "runtimes/codex/skill-cohorts.yaml",
        "router_catalog_path": "runtimes/codex/router-surface.yaml",
        "cohort_id": "core-development",
        "publisher_slug_override": "bob-schumaker-codex-support",
        "publication": {"category": "Productivity"},
    }


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative_file_map(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _clone_live_ponytail(tmp_path: Path) -> Path:
    repo = tmp_path / "ponytail-live"
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            LIVE_PONYTAIL_REPO,
            str(repo),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return repo


def _skill(repo: Path, root: str, slug: str, description: str) -> None:
    skill_root = repo / root / slug
    (skill_root / "references").mkdir(parents=True, exist_ok=True)
    (skill_root / "scripts").mkdir(parents=True, exist_ok=True)
    (skill_root / "SKILL.md").write_text(
        f"---\nname: {slug}\ndescription: {description}\n---\n\n# {slug}\n",
        encoding="utf-8",
    )
    (skill_root / "references" / "guide.md").write_text(
        f"# {slug} guide\n", encoding="utf-8"
    )
    (skill_root / "scripts" / "run.py").write_text(
        f"print('{slug}')\n", encoding="utf-8"
    )


def _skill_with_nested_support(
    repo: Path, root: str, slug: str, description: str
) -> None:
    _skill(repo, root, slug, description)
    skill_root = repo / root / slug
    (skill_root / "references" / "examples").mkdir(parents=True, exist_ok=True)
    (skill_root / "references" / "examples" / "detail.md").write_text(
        f"# {slug} detail\n", encoding="utf-8"
    )
    (skill_root / "templates" / "nested").mkdir(parents=True, exist_ok=True)
    (skill_root / "templates" / "nested" / "default.md").write_text(
        f"{slug} template\n", encoding="utf-8"
    )


def _ponytail_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ponytail"
    for slug, description in [
        ("ponytail", "Use Ponytail mode for this task."),
        ("ponytail-audit", "Whole-repo audit for over-engineering."),
        ("ponytail-debt", 'Harvest every "ponytail:" comment into a debt ledger.'),
        ("ponytail-gain", "Show Ponytail impact and measured wins."),
        ("ponytail-help", "Quick-reference card for all ponytail modes."),
        ("ponytail-review", "Review this diff for over-engineering."),
    ]:
        _skill(repo, "skills", slug, description)
    assets = repo / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "logo.png").write_text("logo\n", encoding="utf-8")
    (assets / "logo-dark.png").write_text("dark\n", encoding="utf-8")
    return repo


def _ponytail_catalog_repo(tmp_path: Path) -> Path:
    repo = _ponytail_repo(tmp_path)
    runtime = repo / "runtimes" / "codex"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "skill-cohorts.yaml").write_text(
        """version: 1
cohorts:
  - id: ponytail
    role: optional
    display_name: Ponytail
    members:
      - ponytail
      - ponytail-audit
      - ponytail-debt
      - ponytail-gain
      - ponytail-help
      - ponytail-review
""",
        encoding="utf-8",
    )
    (runtime / "router-surface.yaml").write_text(
        """version: 1
routers:
  - plugin: ponytail
    name: ponytail
    description: Use Ponytail mode for this task.
    members:
      - ponytail
  - plugin: ponytail
    name: ponytail-audit
    description: Whole-repo audit for over-engineering.
    members:
      - ponytail-audit
  - plugin: ponytail
    name: ponytail-debt
    description: Harvest every "ponytail:" comment into a debt ledger.
    members:
      - ponytail-debt
  - plugin: ponytail
    name: ponytail-gain
    description: Show Ponytail impact and measured wins.
    members:
      - ponytail-gain
  - plugin: ponytail
    name: ponytail-help
    description: Quick-reference card for all ponytail modes.
    members:
      - ponytail-help
  - plugin: ponytail
    name: ponytail-review
    description: Review this diff for over-engineering.
    members:
      - ponytail-review
""",
        encoding="utf-8",
    )
    return repo


def _native_plugin_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "native-plugin"
    plugin_root = repo / "plugins" / "caveman"
    _skill(plugin_root, "skills", "alpha", "Use alpha mode.")
    _skill(plugin_root, "skills", "beta", "Use beta mode.")
    assets = plugin_root / "assets"
    screenshots = plugin_root / "screenshots"
    assets.mkdir(parents=True, exist_ok=True)
    screenshots.mkdir(parents=True, exist_ok=True)
    (assets / "logo.png").write_text("logo\n", encoding="utf-8")
    (screenshots / "one.png").write_text("shot\n", encoding="utf-8")
    (plugin_root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    _write_json(
        plugin_root / ".codex-plugin" / "plugin.json",
        {
            "name": "caveman",
            "version": "1.2.3",
            "description": "Native caveman skills.",
            "author": {"name": "Cave Team"},
            "homepage": "https://example.com/caveman",
            "repository": "https://example.com/caveman.git",
            "license": "MIT",
            "keywords": ["caveman", "skills"],
            "interface": {
                "displayName": "Caveman",
                "developerName": "Cave Team",
                "brandColor": "#123456",
                "logo": "./assets/logo.png",
                "screenshots": ["./screenshots/one.png"],
            },
        },
    )
    return repo


def _write_native_router_catalog(repo: Path, *, members: list[str]) -> Path:
    runtime = repo / "runtimes" / "codex"
    runtime.mkdir(parents=True, exist_ok=True)
    members_yaml = "\n".join(f"      - {member}" for member in members)
    (runtime / "native-router-surface.yaml").write_text(
        "version: 1\n"
        "routers:\n"
        "  - plugin: caveman\n"
        "    name: caveman\n"
        "    description: Use caveman mode.\n"
        "    members:\n"
        f"{members_yaml}\n",
        encoding="utf-8",
    )
    return runtime / "native-router-surface.yaml"


def _clinerules_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "clinerules-roschuma"
    _skill(
        repo,
        "corpus/capabilities",
        "obsidian-memory",
        "Manage durable Obsidian memory with dedicated workflows.",
    )
    _skill(
        repo,
        "corpus/capabilities",
        "obsidian-vault",
        "Route Obsidian vault maintenance, note work, and wiki operations.",
    )
    _skill(
        repo,
        "corpus/capabilities",
        "ponytail-review",
        "Review diffs for over-engineering.",
    )
    _skill(
        repo,
        "corpus/capabilities",
        "ponytail-help",
        "Quick-reference card for ponytail modes.",
    )
    assets = repo / "assets" / "obsidian-workflows"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "logo.png").write_text("logo\n", encoding="utf-8")
    (assets / "logo-dark.png").write_text("dark\n", encoding="utf-8")
    (assets / "composer-icon.png").write_text("icon\n", encoding="utf-8")
    return repo


def _unfamiliar_layout_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "surprising-layout"
    _skill_with_nested_support(
        repo,
        "agent-skills",
        "alpha-mode",
        'Handle "alpha" tasks for the user.',
    )
    _skill(
        repo,
        "agent-skills",
        "beta-review",
        "Review beta changes for correctness.",
    )
    branding = repo / "branding"
    branding.mkdir(parents=True, exist_ok=True)
    (branding / "logo.png").write_text("logo\n", encoding="utf-8")
    (branding / "dark-logo.png").write_text("dark\n", encoding="utf-8")
    (branding / "composer-icon.png").write_text("icon\n", encoding="utf-8")
    return repo


def _payload_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "payload-repo"
    _skill(repo, "skills", "alpha", "Handle alpha workflows.")
    assets = repo / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "copied.txt").write_text("copied payload\n", encoding="utf-8")
    launcher = assets / "launch.sh"
    launcher.write_text("#!/bin/sh\necho payload\n", encoding="utf-8")
    launcher.chmod(0o755)
    hooks = assets / "hooks"
    hooks.mkdir()
    (hooks / "start.sh").write_text("#!/bin/sh\necho start\n", encoding="utf-8")
    (hooks / "start.sh").chmod(0o755)
    (hooks / "readme.txt").write_text("not a hook\n", encoding="utf-8")
    generated = repo / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    pregenerated = generated / "registry.json"
    pregenerated.write_text('{"ok": true}\n', encoding="utf-8")
    template = repo / "templates"
    template.mkdir(parents=True, exist_ok=True)
    (template / "config.txt.tmpl").write_text(
        "name={{name}}\nmode={{mode}}\n", encoding="utf-8"
    )
    digest = packager._hash_bytes(pregenerated.read_bytes())
    _write_json(
        generated / "registry.provenance.json",
        {
            "artifact_path": "generated/registry.json",
            "source_digest": digest,
            "generator_identity": "fixture-generator",
            "generator_version": "1.0",
            "generator_parameters": {"mode": "fixture"},
            "freshness_basis": "content-hash",
            "compatibility": {"source_root": "skills"},
        },
    )
    return repo


def test_fixture_mirror_matches_contract_artifact_set() -> None:
    contract_files = sorted(
        path.relative_to(CONTRACT) for path in CONTRACT.rglob("*") if path.is_file()
    )
    mirror_files = sorted(
        path.relative_to(MIRROR) for path in MIRROR.rglob("*") if path.is_file()
    )

    assert mirror_files == contract_files
    for relative_path in contract_files:
        assert (MIRROR / relative_path).read_text(encoding="utf-8") == (
            CONTRACT / relative_path
        ).read_text(encoding="utf-8")


def test_layer1_contract_schemas_are_machine_readable() -> None:
    expected = {
        "router-plugin-invocation.schema.json",
        "payload-manifest.schema.json",
        "release-metadata.schema.json",
        "pregenerated-provenance.schema.json",
    }

    assert expected <= {path.name for path in SCHEMA_DIR.glob("*.schema.json")}
    for name in expected:
        schema = _load_json(SCHEMA_DIR / name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["type"] == "object"


def test_v1_invocation_is_upgraded_in_memory_without_rewriting_source(
    tmp_path: Path,
) -> None:
    invocation_path = tmp_path / "legacy.json"
    payload = {
        "format_version": 1,
        "input_mode": "repo_bootstrap",
        "repository_root": ".",
        "output_root": "generated/legacy",
    }
    _write_json(invocation_path, payload)

    invocation = packager.parse_invocation(invocation_path, tmp_path)

    assert invocation.format_version == 2
    assert invocation.source_format_version == 1
    assert invocation.surface_mode == "legacy"
    assert _load_json(invocation_path) == payload


def test_v2_native_routed_invocation_requires_router_authority_contract(
    tmp_path: Path,
) -> None:
    invocation_path = tmp_path / "native-routed.json"
    _write_json(
        invocation_path,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": ["plugins/caveman/skills/caveman"],
                    }
                ]
            },
        },
    )

    invocation = packager.parse_invocation(invocation_path, tmp_path)

    assert invocation.format_version == 2
    assert invocation.source_format_version == 2
    assert invocation.surface_mode == "native_routed"
    assert invocation.input_mode == "native_routed"
    assert invocation.router_authority == {
        "routers": [
            {
                "name": "caveman",
                "description": "Use caveman mode.",
                "members": ["plugins/caveman/skills/caveman"],
            }
        ]
    }


def test_v2_native_routed_rejects_legacy_input_mode(tmp_path: Path) -> None:
    invocation_path = tmp_path / "native-routed.json"
    _write_json(
        invocation_path,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "input_mode": "skill_list",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "catalog": "caveman",
                "catalog_path": "router-catalog.json",
            },
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.parse_invocation(invocation_path, tmp_path)

    assert excinfo.value.error_code == "native_routed_rejects_legacy_input_mode"


def test_native_routed_apply_generates_routed_surface_from_native_plugin(
    tmp_path: Path,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    source_manifest_before = (
        repo / "plugins" / "caveman" / ".codex-plugin" / "plugin.json"
    ).read_text(encoding="utf-8")
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    applied = packager.run("apply", invocation, repo)
    output_root = Path(applied["output_root"])
    manifest = _load_json(output_root / ".codex-plugin" / "plugin.json")
    receipt = _load_json(output_root / ".router-plugin-packager-source-map.json")

    assert manifest["name"] == "caveman-routed"
    assert manifest["version"] == "1.2.3"
    assert manifest["description"] == "Native caveman skills."
    assert manifest["author"]["name"] == "Cave Team"
    assert manifest["homepage"] == "https://example.com/caveman"
    assert manifest["license"] == "MIT"
    assert manifest["keywords"] == ["caveman", "skills"]
    assert manifest["interface"]["displayName"] == "Caveman"
    assert manifest["interface"]["brandColor"] == "#123456"
    assert manifest["interface"]["logo"] == "./assets/logo.png"
    assert manifest["interface"]["screenshots"] == ["./screenshots/one.png"]
    assert (output_root / "assets" / "logo.png").is_file()
    assert (output_root / "screenshots" / "one.png").is_file()
    assert sorted(
        str(path.relative_to(output_root)) for path in output_root.rglob("SKILL.md")
    ) == ["skills/caveman/SKILL.md"]
    assert (
        output_root / "skills" / "caveman" / "references" / "modules" / "index.json"
    ).is_file()
    assert (
        output_root
        / "skills"
        / "caveman"
        / "references"
        / "modules"
        / "alpha"
        / "instructions.md"
    ).is_file()
    assert (
        output_root
        / "skills"
        / "caveman"
        / "references"
        / "modules"
        / "beta"
        / "instructions.md"
    ).is_file()
    assert receipt["version"] == "1.2.3"
    assert (
        receipt["normalized_request"]["decision_record"]["state_scope"]
        == "output_root_local"
    )
    assert (
        output_root / ".codex-plugin" / "native-routed-bootstrap-state.json"
    ).is_file()
    assert (
        output_root / ".codex-plugin" / "native-routed-decision-record.json"
    ).is_file()
    assert not (repo / ".codex-plugin" / "router-plugin-packager").exists()
    assert (repo / "plugins" / "caveman" / ".codex-plugin" / "plugin.json").read_text(
        encoding="utf-8"
    ) == source_manifest_before


def test_native_routed_rejects_output_root_nested_under_source_plugin(
    tmp_path: Path,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./plugins/caveman/generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "invalid_output_root"


def test_native_routed_rejects_output_root_containing_source_plugin(
    tmp_path: Path,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./plugins",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "invalid_output_root"


def test_native_routed_apply_supports_catalog_backed_router_authority(
    tmp_path: Path,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    catalog_path = _write_native_router_catalog(repo, members=["alpha", "beta"])
    invocation = repo / "native-routed-catalog.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed-catalog",
            "generated": {
                "name": "caveman-routed-catalog",
                "surface_id": "caveman-routed-catalog",
            },
            "router_authority": {
                "catalog": "caveman",
                "catalog_path": str(catalog_path.relative_to(repo)),
            },
        },
    )

    applied = packager.run("apply", invocation, repo)
    output_root = Path(applied["output_root"])
    receipt = _load_json(output_root / ".router-plugin-packager-source-map.json")

    assert sorted(applied["skill_ids"]) == ["alpha", "beta"]
    assert receipt["normalized_request"]["decision_record"]["router_authority"] == {
        "catalog": "caveman",
        "catalog_path": "runtimes/codex/native-router-surface.yaml",
    }
    assert (output_root / "skills" / "caveman" / "SKILL.md").is_file()


def test_native_routed_catalog_authority_requires_complete_member_coverage(
    tmp_path: Path,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    catalog_path = _write_native_router_catalog(repo, members=["alpha"])
    invocation = repo / "native-routed-catalog.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed-catalog",
            "generated": {
                "name": "caveman-routed-catalog",
                "surface_id": "caveman-routed-catalog",
            },
            "router_authority": {
                "catalog": "caveman",
                "catalog_path": str(catalog_path.relative_to(repo)),
            },
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "catalog_missing_member_ownership"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hooks", {"post_install": "./hooks/install.sh"}),
        ("apps", [{"name": "Caveman App"}]),
        ("mcpServers", "./.mcp.json"),
        ("agents", ["./agents/caveman.json"]),
    ],
)
def test_native_routed_rejects_unsupported_source_runtime_components(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    manifest_path = repo / "plugins" / "caveman" / ".codex-plugin" / "plugin.json"
    manifest = _load_json(manifest_path)
    manifest[field] = value
    _write_json(manifest_path, manifest)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "unsupported_native_plugin_component"
    assert excinfo.value.details["unsupported_fields"] == [field]


def test_native_routed_rejects_owned_output_with_mismatched_source_contract(
    tmp_path: Path,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    first = repo / "native-routed.json"
    second = repo / "native-routed-catalog.json"
    catalog_path = _write_native_router_catalog(repo, members=["alpha", "beta"])
    _write_json(
        first,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )
    _write_json(
        second,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "catalog": "caveman",
                "catalog_path": str(catalog_path.relative_to(repo)),
            },
        },
    )

    packager.run("apply", first, repo)

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("apply", second, repo)

    assert excinfo.value.error_code == "invalid_native_routed_receipt"
    assert excinfo.value.details["field"] == "router_authority"


def test_native_routed_rejects_owned_output_with_drifted_tree_digest(
    tmp_path: Path,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    first = packager.run("apply", invocation, repo)
    output_root = Path(first["output_root"])
    (output_root / "skills" / "caveman" / "SKILL.md").write_text(
        "tampered\n", encoding="utf-8"
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("apply", invocation, repo)

    assert excinfo.value.error_code == "invalid_native_routed_receipt"
    assert "actual_digest" in excinfo.value.details


def test_native_routed_rejects_owned_output_with_extra_unowned_file(
    tmp_path: Path,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    first = packager.run("apply", invocation, repo)
    output_root = Path(first["output_root"])
    (output_root / "manual-note.txt").write_text("unowned\n", encoding="utf-8")

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("apply", invocation, repo)

    assert excinfo.value.error_code == "invalid_native_routed_receipt"
    assert "actual_digest" in excinfo.value.details


def test_native_routed_rejects_owned_output_with_invalid_ownership_marker(
    tmp_path: Path,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    first = packager.run("apply", invocation, repo)
    output_root = Path(first["output_root"])
    receipt_path = output_root / ".router-plugin-packager-source-map.json"
    receipt = _load_json(receipt_path)
    receipt["native_routed"]["format"] = "wrong-format"
    _write_json(receipt_path, receipt)

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("apply", invocation, repo)

    assert excinfo.value.error_code == "invalid_native_routed_receipt"
    assert excinfo.value.details["expected_format"] == (
        "router-plugin-packager-native-routed-receipt-v1"
    )


@pytest.mark.parametrize(
    "missing_field",
    [
        "source_manifest",
        "source_plugin_version",
        "router_authority",
        "skill_paths",
        "state_scope",
    ],
)
def test_native_routed_rejects_owned_output_with_missing_receipt_contract_field(
    tmp_path: Path,
    missing_field: str,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    first = packager.run("apply", invocation, repo)
    output_root = Path(first["output_root"])
    receipt_path = output_root / ".router-plugin-packager-source-map.json"
    receipt = _load_json(receipt_path)
    del receipt["native_routed"][missing_field]
    _write_json(receipt_path, receipt)

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("apply", invocation, repo)

    assert excinfo.value.error_code == "invalid_native_routed_receipt"
    assert excinfo.value.details["field"] == missing_field


def test_native_routed_rejects_partial_owned_output_before_replacement(
    tmp_path: Path,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    first = packager.run("apply", invocation, repo)
    output_root = Path(first["output_root"])
    (output_root / ".codex-plugin" / "native-routed-decision-record.json").unlink()

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("apply", invocation, repo)

    assert excinfo.value.error_code == "invalid_native_routed_receipt"
    assert "actual_digest" in excinfo.value.details


def test_native_routed_plan_recovers_valid_backup_from_interrupted_promotion(
    tmp_path: Path,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    first = packager.run("apply", invocation, repo)
    output_root = Path(first["output_root"])
    original_receipt = _load_json(
        output_root / ".router-plugin-packager-source-map.json"
    )
    backup = output_root.parent / ".caveman-routed.backup-interrupted"
    stage = output_root.parent / ".caveman-routed.stage-interrupted"
    packager.os.replace(output_root, backup)
    receipt_path = (
        output_root.parent / ".caveman-routed.router-plugin-packager-promotion.json"
    )
    receipt_path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "target": str(output_root),
                "stage": str(stage),
                "backup": str(backup),
                "state": "backed_up",
            }
        ),
        encoding="utf-8",
    )

    planned = packager.run("plan", invocation, repo)

    assert Path(planned["output_root"]).is_dir()
    assert not backup.exists()
    assert not receipt_path.exists()
    restored_receipt = _load_json(
        output_root / ".router-plugin-packager-source-map.json"
    )
    assert restored_receipt["native_routed"] == original_receipt["native_routed"]


def test_native_routed_rejects_interrupted_recovery_without_valid_backup_receipt(
    tmp_path: Path,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    first = packager.run("apply", invocation, repo)
    output_root = Path(first["output_root"])
    backup = output_root.parent / ".caveman-routed.backup-interrupted"
    stage = output_root.parent / ".caveman-routed.stage-interrupted"
    packager.os.replace(output_root, backup)
    (backup / ".router-plugin-packager-source-map.json").unlink()
    receipt_path = (
        output_root.parent / ".caveman-routed.router-plugin-packager-promotion.json"
    )
    receipt_path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "target": str(output_root),
                "stage": str(stage),
                "backup": str(backup),
                "state": "backed_up",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "ambiguous_promotion_recovery"
    assert backup.is_dir()
    assert receipt_path.exists()


@pytest.mark.parametrize(
    ("state", "extra_path_name"),
    [
        ("staged", "backup"),
        ("promoted", "stage"),
    ],
)
def test_native_routed_rejects_ambiguous_interrupted_recovery_states(
    tmp_path: Path,
    state: str,
    extra_path_name: str,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    first = packager.run("apply", invocation, repo)
    output_root = Path(first["output_root"])
    backup = output_root.parent / ".caveman-routed.backup-interrupted"
    stage = output_root.parent / ".caveman-routed.stage-interrupted"
    if extra_path_name == "backup":
        backup.mkdir()
    else:
        stage.mkdir()
    receipt_path = (
        output_root.parent / ".caveman-routed.router-plugin-packager-promotion.json"
    )
    receipt_path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "target": str(output_root),
                "stage": str(stage),
                "backup": str(backup),
                "state": state,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "ambiguous_promotion_recovery"
    assert receipt_path.exists()


@pytest.mark.parametrize(
    ("receipt_overrides", "expected_error"),
    [
        ({"state": "unknown"}, "invalid_promotion_receipt"),
        ({"target": "/tmp/not-the-output-root"}, "invalid_promotion_receipt"),
    ],
)
def test_native_routed_rejects_invalid_interrupted_promotion_receipt(
    tmp_path: Path,
    receipt_overrides: dict[str, str],
    expected_error: str,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    first = packager.run("apply", invocation, repo)
    output_root = Path(first["output_root"])
    backup = output_root.parent / ".caveman-routed.backup-interrupted"
    stage = output_root.parent / ".caveman-routed.stage-interrupted"
    receipt = {
        "format_version": 1,
        "target": str(output_root),
        "stage": str(stage),
        "backup": str(backup),
        "state": "backed_up",
    }
    receipt.update(receipt_overrides)
    receipt_path = (
        output_root.parent / ".caveman-routed.router-plugin-packager-promotion.json"
    )
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == expected_error
    assert receipt_path.exists()


@pytest.mark.parametrize("symlink_target", ["stage", "backup"])
def test_native_routed_rejects_symlinked_interrupted_promotion_paths(
    tmp_path: Path,
    symlink_target: str,
) -> None:
    repo = _native_plugin_repo(tmp_path)
    invocation = repo / "native-routed.json"
    _write_json(
        invocation,
        {
            "format_version": 2,
            "surface_mode": "native_routed",
            "repository_root": ".",
            "source_manifest": "plugins/caveman/.codex-plugin/plugin.json",
            "output_root": "./generated/caveman-routed",
            "generated": {
                "name": "caveman-routed",
                "surface_id": "caveman-routed",
            },
            "router_authority": {
                "routers": [
                    {
                        "name": "caveman",
                        "description": "Use caveman mode.",
                        "members": [
                            "plugins/caveman/skills/alpha",
                            "plugins/caveman/skills/beta",
                        ],
                    }
                ]
            },
        },
    )

    first = packager.run("apply", invocation, repo)
    output_root = Path(first["output_root"])
    backup = output_root.parent / ".caveman-routed.backup-interrupted"
    stage = output_root.parent / ".caveman-routed.stage-interrupted"
    symlink_path = stage if symlink_target == "stage" else backup
    symlink_path.symlink_to(repo / "plugins" / "caveman")
    receipt_path = (
        output_root.parent / ".caveman-routed.router-plugin-packager-promotion.json"
    )
    receipt_path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "target": str(output_root),
                "stage": str(stage),
                "backup": str(backup),
                "state": "backed_up",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "invalid_promotion_receipt"
    assert receipt_path.exists()


def test_ponytail_repo_bootstrap_and_explicit_skill_list_are_equivalent() -> None:
    bootstrap = _load_json(
        MIRROR / "positive-repo-bootstrap" / "expected-normalized-request.json"
    )
    explicit = _load_json(
        MIRROR / "positive-skill-list-equivalent" / "expected-normalized-request.json"
    )

    assert bootstrap["source_root"] == explicit["source_root"] == "skills"
    assert bootstrap["repository_root"] == explicit["repository_root"] == "."
    assert (
        bootstrap["output_root"]
        == explicit["output_root"]
        == "./.codex-plugin/router-plugin-packager/generated/ponytail"
    )
    assert bootstrap["surface_id"] == explicit["surface_id"] == "ponytail"
    assert bootstrap["skill_ids"] == explicit["skill_ids"]
    assert bootstrap["plugin_metadata"] == explicit["plugin_metadata"]

    assert bootstrap["decision_record"]["input_mode"] == "repo_bootstrap"
    assert explicit["decision_record"]["input_mode"] == "skill_list"


def test_clinerules_skill_list_fixture_is_ready_for_repeated_group_runs() -> None:
    invocation = _load_json(
        MIRROR / "positive-clinerules-skill-list" / "invocation.json"
    )
    normalized = _load_json(
        MIRROR / "positive-clinerules-skill-list" / "expected-normalized-request.json"
    )

    assert invocation["input_mode"] == "skill_list"
    assert invocation["surface_id_override"] == "obsidian-workflows"
    assert invocation["skill_paths"] == [
        "corpus/capabilities/obsidian-memory",
        "corpus/capabilities/obsidian-vault",
    ]

    assert normalized["surface_id"] == "obsidian-workflows"
    assert normalized["skill_ids"] == ["obsidian-memory", "obsidian-vault"]
    assert normalized["plugin_metadata"]["plugin_slug"] == "obsidian-workflows"
    assert normalized["decision_record"]["skill_ids_source"] == "explicit"


def test_negative_fixtures_cover_required_fail_closed_cases() -> None:
    duplicate_visible = _load_json(
        MIRROR / "negative-duplicate-visible-skill" / "expected-error.json"
    )
    ambiguous_branding = _load_json(
        MIRROR / "negative-ambiguous-branding-asset" / "expected-error.json"
    )

    assert duplicate_visible["error_code"] == "duplicate_visible_skill"
    assert duplicate_visible["details"]["skill_id"] == "ponytail"

    assert ambiguous_branding["error_code"] == "ambiguous_branding_asset"
    assert ambiguous_branding["details"]["slot"] == "logo"


def test_contract_readme_describes_exactly_two_bootstrap_versions() -> None:
    readme = (CONTRACT / "README.md").read_text(encoding="utf-8")

    assert "1. `repo_bootstrap`" in readme
    assert "2. `skill_list`" in readme
    assert "equivalent `repo_bootstrap` and `skill_list`" in readme


def test_semantic_router_frontmatter_description_prefers_member_trigger_language() -> (
    None
):
    router = packager.Router(
        router_slug="ponytail",
        description="Route ponytail workflows.",
        member_skill_ids=["ponytail"],
    )
    modules = [
        {
            "slug": "ponytail",
            "description": (
                'Use Ponytail mode for this task. Trigger "lazy senior developer '
                'mode" when the user wants the smallest correct implementation.'
            ),
            "path": "references/modules/ponytail/instructions.md",
        }
    ]

    description = packager._semantic_router_frontmatter_description(router, modules)

    assert description.startswith("Use Ponytail mode for this task.")
    assert "Trigger: lazy senior developer mode." in description
    assert description != "Route ponytail workflows."


def test_semantic_router_frontmatter_description_mentions_multiple_domains() -> None:
    router = packager.Router(
        router_slug="ponytail-suite",
        description="Route ponytail-suite workflows.",
        member_skill_ids=["ponytail-audit", "ponytail-help"],
    )
    modules = [
        {
            "slug": "ponytail-audit",
            "description": "Whole-repo audit for over-engineering.",
            "path": "references/modules/ponytail-audit/instructions.md",
        },
        {
            "slug": "ponytail-help",
            "description": "Quick-reference card for all ponytail modes.",
            "path": "references/modules/ponytail-help/instructions.md",
        },
    ]

    description = packager._semantic_router_frontmatter_description(router, modules)

    assert "Whole-repo audit for over-engineering" in description
    assert "Quick-reference card for all ponytail modes" in description
    assert description != "Route ponytail-suite workflows."


def test_repo_bootstrap_and_equivalent_skill_list_emit_same_normalized_request(
    tmp_path: Path,
) -> None:
    repo = _ponytail_repo(tmp_path)
    bootstrap = repo / "repo-bootstrap.json"
    explicit = repo / "skill-list.json"
    _write_json(
        bootstrap,
        {
            "format_version": 1,
            "input_mode": "repo_bootstrap",
            "repository_root": ".",
            "output_root": "./generated/ponytail",
            "publisher_slug_override": "bob-schumaker-codex-support",
            "plugin_slug_override": "ponytail",
            "display_name_override": "Ponytail",
            "surface_id_override": "ponytail",
            "branding_asset_overrides": {
                "logo": "assets/logo.png",
                "dark_logo": "assets/logo-dark.png",
                "composer_icon": "assets/logo.png",
            },
        },
    )
    _write_json(
        explicit,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/ponytail",
            "skill_paths": [
                "skills/ponytail",
                "skills/ponytail-audit",
                "skills/ponytail-debt",
                "skills/ponytail-gain",
                "skills/ponytail-help",
                "skills/ponytail-review",
            ],
            "publisher_slug_override": "bob-schumaker-codex-support",
            "plugin_slug_override": "ponytail",
            "display_name_override": "Ponytail",
            "surface_id_override": "ponytail",
            "branding_asset_overrides": {
                "logo": "assets/logo.png",
                "dark_logo": "assets/logo-dark.png",
                "composer_icon": "assets/logo.png",
            },
        },
    )

    planned_bootstrap = packager.run("plan", bootstrap, repo)
    planned_explicit = packager.run("plan", explicit, repo)

    assert (
        planned_bootstrap["surface_id"] == planned_explicit["surface_id"] == "ponytail"
    )
    assert planned_bootstrap["plugin_id"] == planned_explicit["plugin_id"]
    assert (
        planned_bootstrap["normalized_request"]["plugin_metadata"]
        == planned_explicit["normalized_request"]["plugin_metadata"]
    )
    assert planned_bootstrap["normalized_request"]["skill_ids"] == [
        "ponytail",
        "ponytail-audit",
        "ponytail-debt",
        "ponytail-gain",
        "ponytail-help",
        "ponytail-review",
    ]


def test_repo_bootstrap_and_equivalent_skill_list_emit_same_output_tree(
    tmp_path: Path,
) -> None:
    repo = _ponytail_repo(tmp_path)
    bootstrap = repo / "repo-bootstrap.json"
    explicit = repo / "skill-list.json"
    _write_json(
        bootstrap,
        {
            "format_version": 1,
            "input_mode": "repo_bootstrap",
            "repository_root": ".",
            "output_root": "./generated/from-bootstrap",
            "publisher_slug_override": "bob-schumaker-codex-support",
            "plugin_slug_override": "ponytail",
            "display_name_override": "Ponytail",
            "surface_id_override": "ponytail",
            "branding_asset_overrides": {
                "logo": "assets/logo.png",
                "dark_logo": "assets/logo-dark.png",
                "composer_icon": "assets/logo.png",
            },
        },
    )
    _write_json(
        explicit,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/from-explicit",
            "skill_paths": [
                "skills/ponytail",
                "skills/ponytail-audit",
                "skills/ponytail-debt",
                "skills/ponytail-gain",
                "skills/ponytail-help",
                "skills/ponytail-review",
            ],
            "publisher_slug_override": "bob-schumaker-codex-support",
            "plugin_slug_override": "ponytail",
            "display_name_override": "Ponytail",
            "surface_id_override": "ponytail",
            "branding_asset_overrides": {
                "logo": "assets/logo.png",
                "dark_logo": "assets/logo-dark.png",
                "composer_icon": "assets/logo.png",
            },
        },
    )

    bootstrap_apply = packager.run("apply", bootstrap, repo)
    explicit_apply = packager.run("apply", explicit, repo)

    bootstrap_files = {
        key: value
        for key, value in _relative_file_map(
            Path(bootstrap_apply["output_root"])
        ).items()
        if key != ".router-plugin-packager-source-map.json"
    }
    explicit_files = {
        key: value
        for key, value in _relative_file_map(
            Path(explicit_apply["output_root"])
        ).items()
        if key != ".router-plugin-packager-source-map.json"
    }
    assert bootstrap_files == explicit_files


def test_skill_list_apply_writes_router_pattern_plugin(tmp_path: Path) -> None:
    repo = _clinerules_repo(tmp_path)
    _write_json(
        repo / ".codex-plugin" / "plugin.json",
        {
            "name": "obsidian-workflows",
            "version": "1.0.0",
            "description": "Focused Obsidian workflows.",
            "author": {"name": "Example Team", "url": "https://example.com"},
            "homepage": "https://example.com/obsidian-workflows",
            "repository": "https://example.com/source/obsidian-workflows",
            "license": "MIT",
            "keywords": ["obsidian", "knowledge"],
            "interface": {
                "shortDescription": "Obsidian workflows",
                "developerName": "Example Team",
                "category": "Productivity",
                "capabilities": ["Instructions"],
                "websiteURL": "https://example.com/obsidian-workflows",
                "defaultPrompt": ["Help me organize my Obsidian vault."],
            },
        },
    )
    invocation = repo / "skill-list.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/obsidian-workflows",
            "skill_paths": [
                "corpus/capabilities/obsidian-memory",
                "corpus/capabilities/obsidian-vault",
            ],
            "publisher_slug_override": "bob-schumaker-codex-support",
            "plugin_slug_override": "obsidian-workflows",
            "display_name_override": "Obsidian Workflows",
            "surface_id_override": "obsidian-workflows",
            "publication": {"category": "Productivity"},
            "branding_asset_overrides": {
                "logo": "assets/obsidian-workflows/logo.png",
                "dark_logo": "assets/obsidian-workflows/logo-dark.png",
                "composer_icon": "assets/obsidian-workflows/composer-icon.png",
            },
        },
    )

    applied = packager.run("apply", invocation, repo)
    output_root = Path(applied["output_root"])
    manifest = _load_json(output_root / ".codex-plugin" / "plugin.json")
    router_frontmatter = packager._parse_markdown_frontmatter(
        output_root / "skills" / "obsidian-memory" / "SKILL.md"
    )

    assert manifest == {
        "author": {"name": "Example Team", "url": "https://example.com"},
        "description": "Focused Obsidian workflows.",
        "homepage": "https://example.com/obsidian-workflows",
        "interface": {
            "capabilities": ["Instructions"],
            "category": "Productivity",
            "composerIcon": "./assets/obsidian-workflows/composer-icon.png",
            "defaultPrompt": ["Help me organize my Obsidian vault."],
            "developerName": "Example Team",
            "displayName": "Obsidian Workflows",
            "logo": "./assets/obsidian-workflows/logo.png",
            "logoDark": "./assets/obsidian-workflows/logo-dark.png",
            "shortDescription": "Obsidian workflows",
            "websiteURL": "https://example.com/obsidian-workflows",
        },
        "keywords": ["obsidian", "knowledge"],
        "license": "MIT",
        "name": "obsidian-workflows",
        "repository": "https://example.com/source/obsidian-workflows",
        "skills": "./skills/",
        "version": manifest["version"],
    }
    assert router_frontmatter["description"] == (
        "Manage durable Obsidian memory with dedicated workflows."
    )
    router_skill = (output_root / "skills" / "obsidian-memory" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Resolve only the earliest request that still needs module selection" in (
        router_skill
    )
    assert "do not read a second listed module from the same turn" in router_skill
    assert "When a turn only frames context" in router_skill
    assert "classification alone is incomplete" in router_skill
    assert (
        "After opening that earliest matched module, stop for that turn" in router_skill
    )
    assert "instead of restating the route" in router_skill
    assert "do not ask the user to resend, relabel, or restate it" in router_skill
    assert "the module may ask for the missing details" in router_skill
    assert "its listed modules, or its plugin are unavailable" in router_skill
    assert (
        output_root
        / "skills"
        / "obsidian-memory"
        / "references"
        / "modules"
        / "obsidian-memory"
        / "instructions.md"
    ).is_file()
    assert (
        output_root
        / "skills"
        / "obsidian-vault"
        / "references"
        / "modules"
        / "obsidian-vault"
        / "scripts"
        / "run.py"
    ).is_file()
    assert Path(applied["bootstrap_state_path"]).is_file()
    assert Path(applied["decision_state_path"]).is_file()
    assert _load_json(output_root / ".codex-plugin" / "publication-metadata.json") == {
        "category": "Productivity",
        "format": "router-plugin-publication-metadata-v1",
        "plugin_slug": "obsidian-workflows",
    }
    receipt = _load_json(output_root / ".router-plugin-packager-source-map.json")
    assert ".codex-plugin/publication-metadata.json" in receipt["generated_paths"]
    assert receipt["normalized_request"]["publication"] == {"category": "Productivity"}


def test_mcp_packaging_requires_explicit_mcp_based_plugin_kind(tmp_path: Path) -> None:
    repo = _clinerules_repo(tmp_path)
    invocation = repo / "mcp-missing-plugin-kind.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/obsidian-workflows",
            "skill_paths": [
                "corpus/capabilities/obsidian-memory",
            ],
            "mcp_packaging": {
                "plugin_artifact_contract": {
                    "name": "obsidian-workflows",
                    "description": "Example MCP packaging contract.",
                    "author": {"name": "Example"},
                    "interface": {},
                    "skills_path": "./skills/",
                    "mcp_servers_path": "./.mcp.json",
                },
                "launch_contract": {
                    "schema_version": 1,
                    "server_id": "obsidian-workflows",
                    "transport": "stdio",
                    "command": "uvx",
                    "python_version": "3.14.6",
                    "package_index": "https://example.invalid/simple",
                    "package_name": "example-package",
                    "entrypoint": "example-mcp",
                    "extra_args": [],
                    "forbidden_arg_fragments": [],
                },
                "release_surface": {
                    "registry_manifest_asset_id": "registry-manifest",
                    "release_manifest_asset_id": "release-manifest",
                    "operation_registry_asset_id": "operation-registry",
                    "schema_bundle_asset_id": "schema-bundle",
                },
                "skill_release_contract": {
                    "skill_id": "obsidian-memory",
                    "advertised_operation_ids": [],
                    "required_phrases": [],
                    "forbidden_phrases": [],
                },
                "staging_contract": {
                    "format_version": 1,
                    "marketplace_name": "local",
                    "plugin_relpath": "plugins/obsidian-workflows",
                    "version_suffix_source": "cachebuster",
                    "allowed_mutations": [],
                    "required_byte_preserved_paths": [],
                },
            },
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "mcp_packaging_requires_explicit_plugin_kind"


def test_mcp_based_plugin_kind_requires_mcp_packaging(tmp_path: Path) -> None:
    repo = _clinerules_repo(tmp_path)
    invocation = repo / "mcp-missing-contract.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "plugin_kind": "mcp_based",
            "repository_root": ".",
            "output_root": "./generated/obsidian-workflows",
            "skill_paths": [
                "corpus/capabilities/obsidian-memory",
            ],
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "missing_invocation_field"
    assert excinfo.value.details["field"] == "mcp_packaging"


def test_plan_and_apply_report_same_scope_for_identical_inputs(tmp_path: Path) -> None:
    repo = _clinerules_repo(tmp_path)
    invocation = repo / "skill-list.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/obsidian-workflows",
            "skill_paths": [
                "corpus/capabilities/obsidian-memory",
                "corpus/capabilities/obsidian-vault",
            ],
            "publisher_slug_override": "bob-schumaker-codex-support",
            "plugin_slug_override": "obsidian-workflows",
            "display_name_override": "Obsidian Workflows",
            "surface_id_override": "obsidian-workflows",
            "branding_asset_overrides": {
                "logo": "assets/obsidian-workflows/logo.png",
                "dark_logo": "assets/obsidian-workflows/logo-dark.png",
                "composer_icon": "assets/obsidian-workflows/composer-icon.png",
            },
        },
    )

    planned = packager.run("plan", invocation, repo)
    applied = packager.run("apply", invocation, repo)

    assert planned["generated_output_paths"] == applied["generated_output_paths"]
    assert planned["stale_generated_paths"] == applied["stale_generated_paths"] == []
    assert planned["preserved_paths"] == applied["preserved_paths"] == []
    assert planned["bootstrap_state_path"] == applied["bootstrap_state_path"]
    assert planned["decision_state_path"] == applied["decision_state_path"]


def test_repeated_skill_list_runs_reuse_bootstrap_state_and_keep_surface_records(
    tmp_path: Path,
) -> None:
    repo = _clinerules_repo(tmp_path)
    first = repo / "obsidian.json"
    second = repo / "ponytail.json"
    _write_json(
        first,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/obsidian-workflows",
            "skill_paths": [
                "corpus/capabilities/obsidian-memory",
                "corpus/capabilities/obsidian-vault",
            ],
            "publisher_slug_override": "bob-schumaker-codex-support",
            "plugin_slug_override": "obsidian-workflows",
            "display_name_override": "Obsidian Workflows",
            "surface_id_override": "obsidian-workflows",
            "branding_asset_overrides": {
                "logo": "assets/obsidian-workflows/logo.png",
                "dark_logo": "assets/obsidian-workflows/logo-dark.png",
                "composer_icon": "assets/obsidian-workflows/composer-icon.png",
            },
        },
    )
    _write_json(
        second,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/ponytail-tools",
            "skill_paths": [
                "corpus/capabilities/ponytail-help",
                "corpus/capabilities/ponytail-review",
            ],
            "plugin_slug_override": "ponytail-tools",
            "display_name_override": "Ponytail Tools",
            "surface_id_override": "ponytail-tools",
            "branding_asset_overrides": {
                "dark_logo": "assets/obsidian-workflows/logo-dark.png",
                "composer_icon": "assets/obsidian-workflows/composer-icon.png",
            },
        },
    )

    first_applied = packager.run("apply", first, repo)
    second_applied = packager.run("apply", second, repo)

    bootstrap_state = _load_json(Path(first_applied["bootstrap_state_path"]))
    second_state = _load_json(Path(second_applied["decision_state_path"]))

    assert (
        first_applied["bootstrap_state_path"] == second_applied["bootstrap_state_path"]
    )
    assert bootstrap_state["publisher_slug"] == "bob-schumaker-codex-support"
    assert (
        bootstrap_state["branding_assets"]["logo"]
        == "assets/obsidian-workflows/logo.png"
    )
    assert second_state["surface_id"] == "ponytail-tools"
    assert second_state["decision_record"]["bootstrap_state_reused"] is True
    assert Path(first_applied["output_root"]) != Path(second_applied["output_root"])
    assert Path(first_applied["decision_state_path"]).is_file()
    assert Path(second_applied["decision_state_path"]).is_file()


def test_missing_bootstrap_branding_asset_forces_reresolution(
    tmp_path: Path,
) -> None:
    repo = _clinerules_repo(tmp_path)
    first = repo / "first.json"
    second = repo / "second.json"
    _write_json(
        first,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/obsidian-workflows",
            "skill_paths": [
                "corpus/capabilities/obsidian-memory",
                "corpus/capabilities/obsidian-vault",
            ],
            "publisher_slug_override": "bob-schumaker-codex-support",
            "plugin_slug_override": "obsidian-workflows",
            "display_name_override": "Obsidian Workflows",
            "surface_id_override": "obsidian-workflows",
            "branding_asset_overrides": {
                "logo": "assets/obsidian-workflows/logo.png",
                "dark_logo": "assets/obsidian-workflows/logo-dark.png",
                "composer_icon": "assets/obsidian-workflows/composer-icon.png",
            },
        },
    )
    packager.run("apply", first, repo)

    old_logo = repo / "assets" / "obsidian-workflows" / "logo.png"
    old_logo.unlink()
    stronger_logo = repo / "logo.png"
    stronger_logo.write_text("replacement\n", encoding="utf-8")
    _write_json(
        second,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/ponytail-tools",
            "skill_paths": [
                "corpus/capabilities/ponytail-help",
                "corpus/capabilities/ponytail-review",
            ],
            "plugin_slug_override": "ponytail-tools",
            "display_name_override": "Ponytail Tools",
            "surface_id_override": "ponytail-tools",
            "branding_asset_overrides": {
                "dark_logo": "assets/obsidian-workflows/logo-dark.png",
                "composer_icon": "assets/obsidian-workflows/composer-icon.png",
            },
        },
    )

    second_applied = packager.run("apply", second, repo)
    bootstrap_state = _load_json(Path(second_applied["bootstrap_state_path"]))

    assert bootstrap_state["branding_assets"]["logo"] == "logo.png"


def test_skill_list_fails_closed_on_invalid_support_file_ownership(
    tmp_path: Path,
) -> None:
    repo = _clinerules_repo(tmp_path)
    invalid = repo / "corpus" / "capabilities" / "obsidian-memory" / "notes"
    invalid.mkdir(parents=True, exist_ok=True)
    (invalid / "scratch.md").write_text("# invalid\n", encoding="utf-8")
    invocation = repo / "skill-list.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/obsidian-workflows",
            "skill_paths": [
                "corpus/capabilities/obsidian-memory",
                "corpus/capabilities/obsidian-vault",
            ],
            "publisher_slug_override": "bob-schumaker-codex-support",
            "plugin_slug_override": "obsidian-workflows",
            "display_name_override": "Obsidian Workflows",
            "surface_id_override": "obsidian-workflows",
            "branding_asset_overrides": {
                "logo": "assets/obsidian-workflows/logo.png",
                "dark_logo": "assets/obsidian-workflows/logo-dark.png",
                "composer_icon": "assets/obsidian-workflows/composer-icon.png",
            },
        },
    )

    try:
        packager.run("plan", invocation, repo)
    except packager.PackagerError as exc:
        assert exc.error_code == "invalid_support_file_ownership"
        assert exc.details["skill_id"] == "obsidian-memory"
    else:
        raise AssertionError("expected invalid_support_file_ownership")


def test_apply_fails_closed_when_output_root_receipt_belongs_to_other_surface(
    tmp_path: Path,
) -> None:
    repo = _clinerules_repo(tmp_path)
    first = repo / "first.json"
    second = repo / "second.json"
    _write_json(
        first,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/shared-output",
            "skill_paths": [
                "corpus/capabilities/obsidian-memory",
                "corpus/capabilities/obsidian-vault",
            ],
            "publisher_slug_override": "bob-schumaker-codex-support",
            "plugin_slug_override": "obsidian-workflows",
            "display_name_override": "Obsidian Workflows",
            "surface_id_override": "obsidian-workflows",
            "branding_asset_overrides": {
                "logo": "assets/obsidian-workflows/logo.png",
                "dark_logo": "assets/obsidian-workflows/logo-dark.png",
                "composer_icon": "assets/obsidian-workflows/composer-icon.png",
            },
        },
    )
    _write_json(
        second,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/shared-output",
            "skill_paths": [
                "corpus/capabilities/ponytail-help",
                "corpus/capabilities/ponytail-review",
            ],
            "publisher_slug_override": "bob-schumaker-codex-support",
            "plugin_slug_override": "ponytail-tools",
            "display_name_override": "Ponytail Tools",
            "surface_id_override": "ponytail-tools",
            "branding_asset_overrides": {
                "logo": "assets/obsidian-workflows/logo.png",
                "dark_logo": "assets/obsidian-workflows/logo-dark.png",
                "composer_icon": "assets/obsidian-workflows/composer-icon.png",
            },
        },
    )

    packager.run("apply", first, repo)

    try:
        packager.run("apply", second, repo)
    except packager.PackagerError as exc:
        assert exc.error_code == "existing_receipt_surface_mismatch"
        assert exc.details["existing_surface_id"] == "obsidian-workflows"
        assert exc.details["surface_id"] == "ponytail-tools"
    else:
        raise AssertionError("expected existing_receipt_surface_mismatch")


def test_repo_bootstrap_fails_closed_on_ambiguous_branding_assets(
    tmp_path: Path,
) -> None:
    repo = _ponytail_repo(tmp_path)
    duplicate = repo / "assets" / "ponytail"
    duplicate.mkdir(parents=True, exist_ok=True)
    (duplicate / "logo.png").write_text("dup\n", encoding="utf-8")
    invocation = repo / "repo-bootstrap.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "repo_bootstrap",
            "repository_root": ".",
            "output_root": "./generated/ponytail",
        },
    )

    try:
        packager.run("plan", invocation, repo)
    except packager.PackagerError as exc:
        assert exc.error_code == "ambiguous_branding_asset"
        assert exc.details["slot"] == "logo"
    else:
        raise AssertionError("expected ambiguous_branding_asset")


def test_repo_bootstrap_ignores_hidden_candidate_source_roots(tmp_path: Path) -> None:
    repo = _ponytail_repo(tmp_path)
    hidden_root = repo / ".openclaw" / "skills"
    _skill(
        repo,
        ".openclaw/skills",
        "ponytail-shadow",
        "Hidden skill copy that must not affect repo_bootstrap discovery.",
    )
    assert (hidden_root / "ponytail-shadow" / "SKILL.md").is_file()

    invocation = repo / "repo-bootstrap.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "repo_bootstrap",
            "repository_root": ".",
            "output_root": "./generated/ponytail",
        },
    )

    planned = packager.run("plan", invocation, repo)

    assert planned["source_root"] == "skills"
    assert planned["skill_ids"] == [
        "ponytail",
        "ponytail-audit",
        "ponytail-debt",
        "ponytail-gain",
        "ponytail-help",
        "ponytail-review",
    ]


def test_repo_bootstrap_prefers_png_over_svg_for_dark_logo(tmp_path: Path) -> None:
    repo = _ponytail_repo(tmp_path)
    (repo / "assets" / "logo-dark.svg").write_text("<svg/>\n", encoding="utf-8")
    invocation = repo / "repo-bootstrap.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "repo_bootstrap",
            "repository_root": ".",
            "output_root": "./generated/ponytail",
        },
    )

    planned = packager.run("plan", invocation, repo)

    assert (
        planned["normalized_request"]["plugin_metadata"]["branding_assets"]["dark_logo"]
        == "assets/logo-dark.png"
    )


@pytest.mark.live
def test_live_ponytail_repo_bootstrap_works_without_overrides(tmp_path: Path) -> None:
    repo = _clone_live_ponytail(tmp_path)
    bootstrap = repo / "repo-bootstrap.json"
    _write_json(
        bootstrap,
        {
            "format_version": 1,
            "input_mode": "repo_bootstrap",
            "repository_root": ".",
            "output_root": "./generated/live-repo-bootstrap",
        },
    )

    applied = packager.run("apply", bootstrap, repo)

    assert applied["source_root"] == "skills"
    assert applied["skill_ids"] == [
        "ponytail",
        "ponytail-audit",
        "ponytail-debt",
        "ponytail-gain",
        "ponytail-help",
        "ponytail-review",
    ]
    assert (
        applied["normalized_request"]["plugin_metadata"]["branding_assets"]["dark_logo"]
        == "assets/logo-dark.png"
    )


@pytest.mark.live
def test_live_ponytail_repo_bootstrap_and_skill_list_emit_same_output_tree(
    tmp_path: Path,
) -> None:
    repo = _clone_live_ponytail(tmp_path)
    bootstrap = repo / "repo-bootstrap.json"
    explicit = repo / "skill-list.json"
    _write_json(
        bootstrap,
        {
            "format_version": 1,
            "input_mode": "repo_bootstrap",
            "repository_root": ".",
            "output_root": "./generated/live-repo-bootstrap",
        },
    )
    _write_json(
        explicit,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/live-skill-list",
            "skill_paths": LIVE_PONYTAIL_SKILLS,
        },
    )

    bootstrap_apply = packager.run("apply", bootstrap, repo)
    explicit_apply = packager.run("apply", explicit, repo)

    bootstrap_files = {
        key: value
        for key, value in _relative_file_map(
            Path(bootstrap_apply["output_root"])
        ).items()
        if key != ".router-plugin-packager-source-map.json"
    }
    explicit_files = {
        key: value
        for key, value in _relative_file_map(
            Path(explicit_apply["output_root"])
        ).items()
        if key != ".router-plugin-packager-source-map.json"
    }

    assert (
        bootstrap_apply["skill_ids"]
        == explicit_apply["skill_ids"]
        == [
            "ponytail",
            "ponytail-audit",
            "ponytail-debt",
            "ponytail-gain",
            "ponytail-help",
            "ponytail-review",
        ]
    )
    assert bootstrap_apply["source_root"] == explicit_apply["source_root"] == "skills"
    assert (
        bootstrap_apply["normalized_request"]["plugin_metadata"]
        == explicit_apply["normalized_request"]["plugin_metadata"]
    )
    assert bootstrap_files == explicit_files


def test_catalog_mode_apply_writes_declared_router_surface(tmp_path: Path) -> None:
    repo = _ponytail_catalog_repo(tmp_path)
    invocation = repo / "catalog.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "catalog",
            "repository_root": ".",
            "source_root": "skills",
            "output_root": "./generated/ponytail",
            "cohort_catalog_path": "runtimes/codex/skill-cohorts.yaml",
            "router_catalog_path": "runtimes/codex/router-surface.yaml",
            "cohort_id": "ponytail",
        },
    )

    applied = packager.run("apply", invocation, repo)
    output_root = Path(applied["output_root"])
    manifest = _load_json(output_root / ".codex-plugin" / "plugin.json")

    assert applied["skill_ids"] == LIVE_PONYTAIL_SKILLS_TO_IDS
    assert manifest["name"] == "ponytail"
    assert (
        applied["normalized_request"]["decision_record"]["cohort_catalog_path"]
        == "runtimes/codex/skill-cohorts.yaml"
    )
    assert (output_root / "skills" / "ponytail-review" / "SKILL.md").is_file()
    assert (
        output_root
        / "skills"
        / "ponytail-review"
        / "references"
        / "modules"
        / "ponytail-review"
        / "instructions.md"
    ).is_file()


def test_router_skill_content_adds_workflow_router_follow_up_guidance() -> None:
    router = packager.Router(
        router_slug="workflow-router",
        description="Route workflow ownership requests.",
        member_skill_ids=["workflow-router"],
    )

    rendered = packager._router_skill_content(
        router,
        [{"slug": "workflow-router", "description": "Route workflow ownership."}],
        "Route workflow ownership requests.",
    )

    assert "Resolve only the earliest request that still needs module selection" in (
        rendered
    )
    assert "classification alone is incomplete" in rendered
    assert "After opening that earliest matched module, stop for that turn" in rendered
    assert "instead of restating the route" in rendered
    assert "do not ask the user to resend, relabel, or restate it" in rendered
    assert (
        "treat that as a concrete request for the `workflow-router` module" in rendered
    )
    assert "Do not stop at meta-routing commentary" in rendered


def test_router_skill_content_adds_router_specific_non_entrypoint_guidance() -> None:
    scenarios = {
        "research-and-writing": (
            "Route academic-paper markdown, empirical review, and idea intake.",
            [{"slug": "academic-paper-markdown", "description": "Paper markdown."}],
            "do not ask the user to send, resend, or restate that first request",
        ),
        "obsidian-memory": (
            "Manage durable Obsidian memory.",
            [{"slug": "obsidian-memory", "description": "Obsidian memory."}],
            "never say that no `obsidian-memory` module or plugin is available",
        ),
        "agent-development": (
            "Route agent design and evaluation work.",
            [{"slug": "agent-development", "description": "Agent development."}],
            "do not ask the user to send the first request again",
        ),
    }

    for slug, (description, modules, needle) in scenarios.items():
        router = packager.Router(
            router_slug=slug,
            description=description,
            member_skill_ids=[slug],
        )
        rendered = packager._router_skill_content(router, modules, description)
        assert needle in rendered


LIVE_PONYTAIL_SKILLS_TO_IDS = [
    "ponytail",
    "ponytail-audit",
    "ponytail-debt",
    "ponytail-gain",
    "ponytail-help",
    "ponytail-review",
]


def test_catalog_mode_fails_closed_on_duplicate_member_ownership(
    tmp_path: Path,
) -> None:
    repo = _ponytail_catalog_repo(tmp_path)
    (repo / "runtimes" / "codex" / "router-surface.yaml").write_text(
        """version: 1
routers:
  - plugin: ponytail
    name: ponytail
    description: Use Ponytail mode for this task.
    members:
      - ponytail
      - ponytail-audit
  - plugin: ponytail
    name: ponytail-audit
    description: Whole-repo audit for over-engineering.
    members:
      - ponytail-audit
""",
        encoding="utf-8",
    )
    invocation = repo / "catalog.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "catalog",
            "repository_root": ".",
            "source_root": "skills",
            "output_root": "./generated/ponytail",
            "cohort_catalog_path": "runtimes/codex/skill-cohorts.yaml",
            "router_catalog_path": "runtimes/codex/router-surface.yaml",
            "cohort_id": "ponytail",
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "catalog_duplicate_member_ownership"
    assert excinfo.value.details["skill_id"] == "ponytail-audit"


def test_catalog_mode_fails_closed_on_missing_member_ownership(tmp_path: Path) -> None:
    repo = _ponytail_catalog_repo(tmp_path)
    (repo / "runtimes" / "codex" / "router-surface.yaml").write_text(
        """version: 1
routers:
  - plugin: ponytail
    name: ponytail
    description: Use Ponytail mode for this task.
    members:
      - ponytail
  - plugin: ponytail
    name: ponytail-review
    description: Review this diff for over-engineering.
    members:
      - ponytail-review
""",
        encoding="utf-8",
    )
    invocation = repo / "catalog.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "catalog",
            "repository_root": ".",
            "source_root": "skills",
            "output_root": "./generated/ponytail",
            "cohort_catalog_path": "runtimes/codex/skill-cohorts.yaml",
            "router_catalog_path": "runtimes/codex/router-surface.yaml",
            "cohort_id": "ponytail",
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "catalog_missing_member_ownership"
    assert "ponytail-audit" in excinfo.value.details["skill_ids"]


def test_catalog_mode_plan_and_apply_are_deterministic_and_parity_matched(
    tmp_path: Path,
) -> None:
    repo = _ponytail_catalog_repo(tmp_path)
    invocation = repo / "catalog.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "catalog",
            "repository_root": ".",
            "source_root": "skills",
            "output_root": "./generated/ponytail",
            "cohort_catalog_path": "runtimes/codex/skill-cohorts.yaml",
            "router_catalog_path": "runtimes/codex/router-surface.yaml",
            "cohort_id": "ponytail",
        },
    )

    first_plan = packager.run("plan", invocation, repo)
    second_plan = packager.run("plan", invocation, repo)
    applied = packager.run("apply", invocation, repo)

    assert first_plan["generated_output_paths"] == second_plan["generated_output_paths"]
    assert first_plan["normalized_request"] == second_plan["normalized_request"]
    assert first_plan["generated_output_paths"] == applied["generated_output_paths"]
    assert first_plan["stale_generated_paths"] == applied["stale_generated_paths"] == []
    assert first_plan["preserved_paths"] == applied["preserved_paths"] == []


def test_catalog_mode_incomplete_router_entry_stops_before_manifest_generation(
    tmp_path: Path,
) -> None:
    repo = _ponytail_catalog_repo(tmp_path)
    (repo / "runtimes" / "codex" / "router-surface.yaml").write_text(
        """version: 1
routers:
  - plugin: ponytail
    name: ponytail
    description: Use Ponytail mode for this task.
""",
        encoding="utf-8",
    )
    invocation = repo / "catalog.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "catalog",
            "repository_root": ".",
            "source_root": "skills",
            "output_root": "./generated/ponytail",
            "cohort_catalog_path": "runtimes/codex/skill-cohorts.yaml",
            "router_catalog_path": "runtimes/codex/router-surface.yaml",
            "cohort_id": "ponytail",
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("apply", invocation, repo)

    assert excinfo.value.error_code == "invalid_catalog_shape"
    assert not (
        repo / "generated" / "ponytail" / ".codex-plugin" / "plugin.json"
    ).exists()


def test_skill_list_copies_nested_support_files(tmp_path: Path) -> None:
    repo = tmp_path / "nested-support"
    _skill_with_nested_support(
        repo,
        "skills",
        "alpha-mode",
        "Handle nested support correctly.",
    )
    assets = repo / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "logo.png").write_text("logo\n", encoding="utf-8")
    (assets / "logo-dark.png").write_text("dark\n", encoding="utf-8")
    invocation = repo / "skill-list.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/alpha-mode",
            "skill_paths": ["skills/alpha-mode"],
        },
    )

    applied = packager.run("apply", invocation, repo)
    output_root = Path(applied["output_root"])

    assert (
        output_root
        / "skills"
        / "alpha-mode"
        / "references"
        / "modules"
        / "alpha-mode"
        / "references"
        / "examples"
        / "detail.md"
    ).is_file()
    assert (
        output_root
        / "skills"
        / "alpha-mode"
        / "references"
        / "modules"
        / "alpha-mode"
        / "templates"
        / "nested"
        / "default.md"
    ).is_file()


def test_skill_list_excludes_generated_cache_support_files(tmp_path: Path) -> None:
    repo = tmp_path / "nested-support"
    _skill_with_nested_support(
        repo,
        "skills",
        "alpha-mode",
        "Handle nested support correctly.",
    )
    pycache = repo / "skills" / "alpha-mode" / "scripts" / "__pycache__"
    pycache.mkdir(parents=True, exist_ok=True)
    (pycache / "run.cpython-314.pyc").write_bytes(b"compiled")
    assets = repo / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "logo.png").write_text("logo\n", encoding="utf-8")
    (assets / "logo-dark.png").write_text("dark\n", encoding="utf-8")
    invocation = repo / "skill-list.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/alpha-mode",
            "skill_paths": ["skills/alpha-mode"],
        },
    )

    applied = packager.run("apply", invocation, repo)
    output_root = Path(applied["output_root"])

    assert not (
        output_root
        / "skills"
        / "alpha-mode"
        / "references"
        / "modules"
        / "alpha-mode"
        / "scripts"
        / "__pycache__"
        / "run.cpython-314.pyc"
    ).exists()


def test_skill_list_packages_unfamiliar_layout_repo(tmp_path: Path) -> None:
    repo = _unfamiliar_layout_repo(tmp_path)
    invocation = repo / "skill-list.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "source_root": "agent-skills",
            "output_root": "./out/router-plugin",
            "skill_paths": ["agent-skills/alpha-mode", "agent-skills/beta-review"],
            "branding_asset_overrides": {
                "logo": "branding/logo.png",
                "dark_logo": "branding/dark-logo.png",
                "composer_icon": "branding/composer-icon.png",
            },
        },
    )

    applied = packager.run("apply", invocation, repo)
    output_root = Path(applied["output_root"])
    manifest = _load_json(output_root / ".codex-plugin" / "plugin.json")

    assert applied["source_root"] == "agent-skills"
    assert applied["skill_ids"] == ["alpha-mode", "beta-review"]
    assert manifest["interface"]["logo"] == "./branding/logo.png"
    assert manifest["interface"] == {
        "composerIcon": "./branding/composer-icon.png",
        "displayName": "Surprising Layout",
        "logo": "./branding/logo.png",
        "logoDark": "./branding/dark-logo.png",
    }
    assert (output_root / "skills" / "beta-review" / "SKILL.md").is_file()


def test_skill_list_payload_assets_emit_payload_manifest_and_release_metadata(
    tmp_path: Path,
) -> None:
    repo = _payload_repo(tmp_path)
    invocation = repo / "payload.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/plugin",
            "skill_paths": ["skills/alpha"],
            "payload_assets": [
                {
                    "id": "copied-doc",
                    "acquisition_mode": "copied",
                    "source": "assets/copied.txt",
                    "destination": "payload/copied.txt",
                    "ownership_role": "runtime-asset",
                    "ownership_class": "immutable-runtime-artifact",
                },
                {
                    "id": "copied-launcher",
                    "acquisition_mode": "copied",
                    "source": "assets/launch.sh",
                    "destination": "payload/launch.sh",
                    "ownership_role": "runtime-launcher",
                    "ownership_class": "immutable-runtime-artifact",
                },
                {
                    "id": "hook-glob",
                    "acquisition_mode": "copied",
                    "source": "assets",
                    "source_glob": "hooks/*.sh",
                    "destination": "payload",
                    "ownership_role": "runtime-launcher",
                    "ownership_class": "immutable-runtime-artifact",
                },
                {
                    "id": "pre-generated-registry",
                    "acquisition_mode": "pre_generated",
                    "source": "generated/registry.json",
                    "destination": "payload/registry.json",
                    "ownership_role": "runtime-asset",
                    "ownership_class": "replaceable-upgrade-artifact",
                    "provenance_path": "generated/registry.provenance.json",
                },
                {
                    "id": "templated-config",
                    "acquisition_mode": "templated",
                    "source": "templates/config.txt.tmpl",
                    "destination": "payload/config.txt",
                    "ownership_role": "runtime-config",
                    "ownership_class": "owned-integration-artifact",
                    "template_parameters": {"name": "alpha", "mode": "test"},
                },
            ],
            "runtime_compatibility_version": "2026.07",
            "migration_contract_version": "v1",
            "rollback_compatibility_hints": {"compatible": True},
            "control_surface": {"skill_id": "alpha", "operations": ["verify"]},
            "owned_integration_root": "managed-boundary",
            "integration_points": [
                {
                    "id": "hook-a",
                    "mode": "verify-only",
                    "target_relpath": "managed-boundary/hook-a",
                }
            ],
            "verification_targets": [{"id": "smoke", "path": "payload/config.txt"}],
        },
    )

    applied = packager.run("apply", invocation, repo)
    output_root = Path(applied["output_root"])
    assert (output_root / "payload" / "copied.txt").read_text(encoding="utf-8") == (
        "copied payload\n"
    )
    assert (output_root / "payload" / "launch.sh").stat().st_mode & 0o777 == 0o755
    assert (output_root / "payload" / "hooks" / "start.sh").is_file()
    assert not (output_root / "payload" / "hooks" / "readme.txt").exists()
    assert (output_root / "payload" / "registry.json").read_text(encoding="utf-8") == (
        '{"ok": true}\n'
    )
    assert (output_root / "payload" / "config.txt").read_text(encoding="utf-8") == (
        "name=alpha\nmode=test\n"
    )

    payload_manifest = _load_json(
        output_root / ".codex-plugin" / "payload-manifest.json"
    )
    assert payload_manifest["format_version"] == 1
    assert payload_manifest["payload_fingerprint"]
    manifest_paths = {
        entry["relative_output_path"] for entry in payload_manifest["entries"]
    }
    assert "payload/copied.txt" in manifest_paths
    assert "payload/registry.json" in manifest_paths
    assert "payload/config.txt" in manifest_paths
    copied_entry = next(
        entry
        for entry in payload_manifest["entries"]
        if entry["relative_output_path"] == "payload/copied.txt"
    )
    assert copied_entry["file_mode"] == "0o644"
    assert copied_entry["ownership_class"] == "immutable-runtime-artifact"

    release_metadata = _load_json(
        output_root / ".codex-plugin" / "release-metadata.json"
    )
    assert release_metadata["runtime_compatibility_version"] == "2026.07"
    assert release_metadata["migration_contract_version"] == "v1"
    assert release_metadata["rollback_compatibility_hints"] == {"compatible": True}
    assert release_metadata["control_surface"]["skill_id"] == "alpha"
    assert release_metadata["owned_integration_root"] == "managed-boundary"
    assert release_metadata["integration_points"] == [
        {
            "id": "hook-a",
            "mode": "verify-only",
            "target_relpath": "managed-boundary/hook-a",
        }
    ]
    assert release_metadata["verification_targets"] == [
        {"id": "smoke", "path": "payload/config.txt"}
    ]

    receipt = _load_json(output_root / ".router-plugin-packager-source-map.json")
    assert receipt["payload_fingerprint"] == payload_manifest["payload_fingerprint"]
    assert any(
        entry["path"] == "payload/registry.json"
        and entry["acquisition_mode"] == "pre_generated"
        and entry["provenance_reference"] == "generated/registry.provenance.json"
        for entry in receipt["entries"]
    )
    assert applied["normalized_request"]["payload_assets"][0]["id"] == "copied-doc"


def test_skill_list_pre_generated_payload_requires_matching_provenance(
    tmp_path: Path,
) -> None:
    repo = _payload_repo(tmp_path)
    provenance = _load_json(repo / "generated" / "registry.provenance.json")
    provenance["source_digest"] = "wrong"
    _write_json(repo / "generated" / "registry.provenance.json", provenance)
    invocation = repo / "payload.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/plugin",
            "skill_paths": ["skills/alpha"],
            "payload_assets": [
                {
                    "id": "pre-generated-registry",
                    "acquisition_mode": "pre_generated",
                    "source": "generated/registry.json",
                    "destination": "payload/registry.json",
                    "ownership_role": "runtime-asset",
                    "provenance_path": "generated/registry.provenance.json",
                }
            ],
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "pregenerated_stale_proof"


def test_skill_list_pre_generated_payload_rejects_incompatible_source_root(
    tmp_path: Path,
) -> None:
    repo = _payload_repo(tmp_path)
    provenance = _load_json(repo / "generated" / "registry.provenance.json")
    provenance["compatibility"]["source_root"] = "different-root"
    _write_json(repo / "generated" / "registry.provenance.json", provenance)
    invocation = repo / "payload.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/plugin",
            "skill_paths": ["skills/alpha"],
            "payload_assets": [
                {
                    "id": "pre-generated-registry",
                    "acquisition_mode": "pre_generated",
                    "source": "generated/registry.json",
                    "destination": "payload/registry.json",
                    "ownership_role": "runtime-asset",
                    "provenance_path": "generated/registry.provenance.json",
                }
            ],
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "pregenerated_incompatible"


def test_skill_list_templated_payload_requires_parameters(tmp_path: Path) -> None:
    repo = _payload_repo(tmp_path)
    invocation = repo / "payload.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/plugin",
            "skill_paths": ["skills/alpha"],
            "payload_assets": [
                {
                    "id": "templated-config",
                    "acquisition_mode": "templated",
                    "source": "templates/config.txt.tmpl",
                    "destination": "payload/config.txt",
                    "ownership_role": "runtime-config",
                }
            ],
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "templated_inputs_incomplete"


def test_payload_source_glob_requires_at_least_one_file(tmp_path: Path) -> None:
    repo = _payload_repo(tmp_path)
    invocation = repo / "payload.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/plugin",
            "skill_paths": ["skills/alpha"],
            "payload_assets": [
                {
                    "id": "missing-glob",
                    "acquisition_mode": "copied",
                    "source": "assets",
                    "source_glob": "hooks/*.missing",
                    "destination": "payload",
                    "ownership_role": "runtime-asset",
                }
            ],
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "empty_payload_asset_glob"


def test_payload_asset_rejects_unknown_ownership_class(tmp_path: Path) -> None:
    repo = _payload_repo(tmp_path)
    invocation = repo / "payload.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/plugin",
            "skill_paths": ["skills/alpha"],
            "payload_assets": [
                {
                    "id": "owned-asset",
                    "acquisition_mode": "copied",
                    "source": "assets/copied.txt",
                    "destination": "payload/copied.txt",
                    "ownership_role": "runtime-asset",
                    "ownership_class": "arbitrary-owner",
                }
            ],
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "invalid_payload_asset"


def test_control_surface_must_name_a_visible_packaged_skill(tmp_path: Path) -> None:
    repo = _payload_repo(tmp_path)
    invocation = repo / "payload.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/plugin",
            "skill_paths": ["skills/alpha"],
            "control_surface": {
                "skill_id": "not-visible",
                "operations": ["verify"],
            },
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "invalid_control_surface"


def test_integration_point_must_stay_under_its_owned_boundary(tmp_path: Path) -> None:
    repo = _payload_repo(tmp_path)
    invocation = repo / "payload.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/plugin",
            "skill_paths": ["skills/alpha"],
            "owned_integration_root": "owned",
            "integration_points": [{"id": "outside", "target_relpath": "outside/hook"}],
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "invalid_invocation_field"


def test_skill_list_payload_rejects_unsupported_normalization(tmp_path: Path) -> None:
    repo = _payload_repo(tmp_path)
    invocation = repo / "payload.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/plugin",
            "skill_paths": ["skills/alpha"],
            "payload_assets": [
                {
                    "id": "copied-doc",
                    "acquisition_mode": "copied",
                    "source": "assets/copied.txt",
                    "destination": "payload/copied.txt",
                    "ownership_role": "runtime-asset",
                    "normalization": "strip-trailing-whitespace",
                }
            ],
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "unsupported_payload_normalization"


def test_skill_list_rejects_payload_sources_under_output_root(tmp_path: Path) -> None:
    repo = _payload_repo(tmp_path)
    generated_output_source = repo / "generated-output" / "plugin" / "seed.txt"
    generated_output_source.parent.mkdir(parents=True, exist_ok=True)
    generated_output_source.write_text("bad source\n", encoding="utf-8")
    invocation = repo / "payload.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated-output/plugin",
            "skill_paths": ["skills/alpha"],
            "payload_assets": [
                {
                    "id": "bad-source",
                    "acquisition_mode": "copied",
                    "source": "generated-output/plugin/seed.txt",
                    "destination": "payload/seed.txt",
                    "ownership_role": "runtime-asset",
                }
            ],
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "payload_source_under_output_root"


def test_skill_list_payload_rejects_duplicate_destination_paths(tmp_path: Path) -> None:
    repo = _payload_repo(tmp_path)
    invocation = repo / "payload.json"
    _write_json(
        invocation,
        {
            "format_version": 1,
            "input_mode": "skill_list",
            "repository_root": ".",
            "output_root": "./generated/plugin",
            "skill_paths": ["skills/alpha"],
            "payload_assets": [
                {
                    "id": "copied-doc",
                    "acquisition_mode": "copied",
                    "source": "assets/copied.txt",
                    "destination": "payload/shared.txt",
                    "ownership_role": "runtime-asset",
                },
                {
                    "id": "templated-config",
                    "acquisition_mode": "templated",
                    "source": "templates/config.txt.tmpl",
                    "destination": "payload/shared.txt",
                    "ownership_role": "runtime-config",
                    "template_parameters": {"name": "alpha", "mode": "test"},
                },
            ],
        },
    )

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("plan", invocation, repo)

    assert excinfo.value.error_code == "duplicate_destination_path"


def test_file_backed_payload_fixture_exercises_layer1_contract(tmp_path: Path) -> None:
    repo = tmp_path / "payload-fixture"
    _copy_tree(FIXTURES / "payload_repo", repo)

    applied = packager.run("apply", repo / "invocation.json", repo)
    output_root = Path(applied["output_root"])

    assert (output_root / ".codex-plugin" / "payload-manifest.json").is_file()
    assert (output_root / ".codex-plugin" / "release-metadata.json").is_file()
    assert (output_root / ".codex-plugin" / "plugin.json").is_file()
    assert (
        output_root
        / "skills"
        / "alpha"
        / "references"
        / "modules"
        / "alpha"
        / "instructions.md"
    ).is_file()
    assert (output_root / "payload" / "registry.json").is_file()


def test_apply_preserves_unowned_generic_scaffold(tmp_path: Path) -> None:
    repo = tmp_path / "payload-fixture"
    _copy_tree(FIXTURES / "payload_repo", repo)
    output_root = repo / "generated-output" / "plugin"
    (output_root / ".codex-plugin").mkdir(parents=True)
    scaffold = output_root / ".codex-plugin" / "plugin.json"
    scaffold.write_text('{"name": "scaffold"}\n', encoding="utf-8")

    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("apply", repo / "invocation.json", repo)

    assert excinfo.value.error_code == "unowned_output_root"
    assert scaffold.read_text(encoding="utf-8") == '{"name": "scaffold"}\n'


def test_apply_restores_valid_output_when_promotion_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "payload-fixture"
    _copy_tree(FIXTURES / "payload_repo", repo)
    first = packager.run("apply", repo / "invocation.json", repo)
    output_root = Path(first["output_root"])
    original_receipt = (
        output_root / ".router-plugin-packager-source-map.json"
    ).read_bytes()
    original_replace = packager.os.replace

    def fail_stage_promotion(source: str | Path, destination: str | Path) -> None:
        if ".stage-" in Path(source).name and Path(destination) == output_root:
            raise OSError("injected stage promotion failure")
        original_replace(source, destination)

    monkeypatch.setattr(packager.os, "replace", fail_stage_promotion)
    with pytest.raises(packager.PackagerError) as excinfo:
        packager.run("apply", repo / "invocation.json", repo)

    assert excinfo.value.error_code == "output_promotion_failed"
    assert (output_root / ".router-plugin-packager-source-map.json").read_bytes() == (
        original_receipt
    )
    assert not list(output_root.parent.glob(".plugin.stage-*"))
    assert not list(output_root.parent.glob(".plugin.backup-*"))
    assert not (
        output_root.parent / ".plugin.router-plugin-packager-promotion.json"
    ).exists()


def test_plan_recovers_valid_backup_from_interrupted_promotion(tmp_path: Path) -> None:
    repo = tmp_path / "payload-fixture"
    _copy_tree(FIXTURES / "payload_repo", repo)
    first = packager.run("apply", repo / "invocation.json", repo)
    output_root = Path(first["output_root"])
    backup = output_root.parent / ".plugin.backup-interrupted"
    stage = output_root.parent / ".plugin.stage-interrupted"
    packager.os.replace(output_root, backup)
    receipt_path = output_root.parent / ".plugin.router-plugin-packager-promotion.json"
    receipt_path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "target": str(output_root),
                "stage": str(stage),
                "backup": str(backup),
                "state": "backed_up",
            }
        ),
        encoding="utf-8",
    )

    planned = packager.run("plan", repo / "invocation.json", repo)

    assert Path(planned["output_root"]).is_dir()
    assert not backup.exists()
    assert not receipt_path.exists()


def test_payload_bearing_output_tree_remains_publish_flow_compatible(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "payload-fixture"
    _copy_tree(FIXTURES / "payload_repo", repo)

    applied = packager.run("apply", repo / "invocation.json", repo)
    output_root = Path(applied["output_root"])
    manifest = _load_json(output_root / ".codex-plugin" / "plugin.json")

    assert manifest["skills"] == "./skills/"
    assert manifest["author"]["name"] == "local"
    assert (output_root / ".router-plugin-packager-source-map.json").is_file()
    assert (output_root / ".codex-plugin" / "payload-manifest.json").is_file()
    assert (output_root / ".codex-plugin" / "release-metadata.json").is_file()

    skill_files = sorted(
        str(path.relative_to(output_root)) for path in output_root.rglob("SKILL.md")
    )
    assert skill_files == ["skills/alpha/SKILL.md"]
