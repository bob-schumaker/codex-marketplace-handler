from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketplace_installer import marketplace_publish as publisher
from marketplace_installer import router_plugin_first_user_flow as flow


PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\x0dIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)


def _skill(repo: Path, slug: str) -> None:
    root = repo / "skills" / slug
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        f"---\nname: {slug}\ndescription: {slug} skill\n---\n\n# {slug}\n",
        encoding="utf-8",
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ponytail"
    for slug in (
        "ponytail",
        "ponytail-audit",
        "ponytail-debt",
        "ponytail-gain",
        "ponytail-help",
        "ponytail-review",
    ):
        _skill(repo, slug)
    assets = repo / "assets"
    assets.mkdir()
    (assets / "logo.png").write_bytes(PNG)
    (assets / "logo-dark.png").write_bytes(PNG)
    (repo / "router-plugin-source.json").write_text(
        json.dumps(
            {
                "name": "ponytail",
                "version": "4.8.4",
                "description": "Minimal plugin workflows.",
                "author": {"name": "Ponytail"},
                "publication": {"category": "Productivity"},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return repo


def test_classify_requires_confirmation_without_writing_state(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    result = flow.classify(repo)

    assert result == {
        "command": "classify",
        "state": "confirmation_required",
        "candidate": {
            "plugin_kind": "skills_only",
            "source_root": "skills",
            "skill_ids": [
                "ponytail",
                "ponytail-audit",
                "ponytail-debt",
                "ponytail-gain",
                "ponytail-help",
                "ponytail-review",
            ],
        },
    }
    assert not (repo / ".codex-plugin").exists()


def test_bootstrap_writes_immutable_request_and_receipt_after_confirmation(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)

    result = flow.bootstrap(
        repo,
        confirmed=True,
        canonical_manifest="router-plugin-source.json",
    )

    request_path = repo / result["request_path"]
    receipt_path = repo / result["receipt_path"]
    request = json.loads(request_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert result["command"] == "bootstrap"
    assert request["schema"] == "router-plugin-request/v1"
    assert request["publication"] == {"category": "Productivity"}
    assert request["version_override"] == "4.8.4"
    assert request["branding_asset_overrides"] == {
        "composer_icon": "assets/logo.png",
        "dark_logo": "assets/logo-dark.png",
        "logo": "assets/logo.png",
    }
    assert receipt["schema"] == "router-plugin-receipt/v1"
    assert receipt["request_sha256"] == result["request_sha256"]
    assert receipt["input_digests"]["canonical_manifest"]
    assert receipt["input_digests"]["skills"]
    assert receipt["input_digests"]["branding_assets"]
    assert receipt["state"] == "bootstrapped"
    assert receipt["identity_evidence"]["version"] == {
        "source": "canonical_manifest",
        "value": "4.8.4",
    }
    assert receipt["owned_paths"]["native_manifest"] == ".codex-plugin/plugin.json"

    packaged = flow.package(repo, surface_id="ponytail")
    rendered_manifest = json.loads(
        (repo / packaged["output_root"] / ".codex-plugin/plugin.json").read_text(
            encoding="utf-8"
        )
    )
    assert rendered_manifest["author"] == {"name": "Ponytail"}
    assert rendered_manifest["description"] == "Minimal plugin workflows."


def test_bootstrap_requires_confirmation_and_explicit_manifest_designation(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    native = repo / ".codex-plugin"
    native.mkdir()
    (native / "plugin.json").write_text(
        json.dumps({"name": "nearby-native", "version": "1.0.0"}),
        encoding="utf-8",
    )

    result = flow.bootstrap(
        repo,
        confirmed=False,
        canonical_manifest="router-plugin-source.json",
    )

    assert result["state"] == "confirmation_required"
    assert not (repo / ".codex-plugin/router-plugin-packager").exists()
    try:
        flow.bootstrap(
            repo, confirmed=True, canonical_manifest=".codex-plugin/plugin.json"
        )
    except flow.FirstUserFlowError as exc:
        assert exc.error_code == "missing_manifest_evidence"
        assert exc.details == {"field": "publication.category"}
    else:
        raise AssertionError("a nearby native manifest must not be selected implicitly")


def test_bootstrap_rejects_files_that_only_claim_to_be_png_branding(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    (repo / "assets/logo.png").write_text("not a PNG\n", encoding="utf-8")

    with pytest.raises(flow.FirstUserFlowError, match="valid PNG or SVG") as error:
        flow.bootstrap(
            repo,
            confirmed=True,
            canonical_manifest="router-plugin-source.json",
        )

    assert error.value.error_code == "invalid_branding_asset"
    assert error.value.details == {"invalid_paths": ["assets/logo.png"]}


def test_bootstrap_preserves_prior_receipt_when_inputs_create_a_new_revision(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    first = flow.bootstrap(
        repo, confirmed=True, canonical_manifest="router-plugin-source.json"
    )
    source_manifest = repo / "router-plugin-source.json"
    payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    payload["version"] = "4.8.5"
    source_manifest.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    second = flow.bootstrap(
        repo, confirmed=True, canonical_manifest="router-plugin-source.json"
    )

    archived = (
        repo
        / ".codex-plugin/router-plugin-packager/receipts"
        / f"ponytail-{first['request_sha256']}.json"
    )
    assert first["request_sha256"] != second["request_sha256"]
    assert (
        json.loads(archived.read_text(encoding="utf-8"))["request_sha256"]
        == first["request_sha256"]
    )


def test_package_resumes_receipt_and_rejects_stale_bootstrap_inputs(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    flow.bootstrap(
        repo,
        confirmed=True,
        canonical_manifest="router-plugin-source.json",
    )

    packaged = flow.package(repo, surface_id="ponytail")
    receipt_path = repo / packaged["receipt_path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    output_root = repo / ".codex-plugin/router-plugin-packager/generated/ponytail"

    assert packaged["state"] == "packaged"
    assert receipt["state"] == "packaged"
    assert receipt["output_digests"]
    assert flow.inspect(repo, surface_id="ponytail")["state"] == "ready"
    assert flow.publish_handoff(repo, surface_id="ponytail") == {
        "command": "publish-handoff",
        "state": "publisher_required",
        "surface_id": "ponytail",
        "plugin_root": ".codex-plugin/router-plugin-packager/generated/ponytail",
        "publisher": "codex-marketplace-publish",
        "required_next_steps": ["dry_run", "apply_with_plan_digest"],
    }
    assert json.loads(
        (output_root / ".codex-plugin/publication-metadata.json").read_text(
            encoding="utf-8"
        )
    ) == {
        "category": "Productivity",
        "format": "router-plugin-publication-metadata-v1",
        "plugin_slug": "ponytail",
    }

    (repo / "skills/ponytail/SKILL.md").write_text("changed\n", encoding="utf-8")

    try:
        flow.package(repo, surface_id="ponytail")
    except flow.FirstUserFlowError as exc:
        assert exc.error_code == "stale_bootstrap_receipt"
        assert exc.details["changed_inputs"] == ["skills/ponytail/SKILL.md"]
    else:
        raise AssertionError("expected stale bootstrap receipt to be rejected")


def test_packaged_first_user_tree_publishes_to_a_disposable_marketplace(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    flow.bootstrap(repo, confirmed=True, canonical_manifest="router-plugin-source.json")
    packaged = flow.package(repo, surface_id="ponytail")
    plugin_root = repo / packaged["output_root"]
    marketplace = tmp_path / "marketplace"
    manifest = marketplace / ".agents/plugins/marketplace.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"name": "fixture-market", "plugins": []}) + "\n",
        encoding="utf-8",
    )

    preview = publisher.publish_generated_plugin(
        plugin_root=plugin_root,
        target_root=marketplace,
        marketplace_name="fixture-market",
        dry_run=True,
    )
    assert not (marketplace / "plugins/ponytail").exists()
    published = publisher.publish_generated_plugin(
        plugin_root=plugin_root,
        target_root=marketplace,
        marketplace_name="fixture-market",
        plan_digest=preview["plan_digest"],
    )

    assert published["wrote_manifest"] is True
    assert (marketplace / "plugins/ponytail/.codex-plugin/plugin.json").is_file()


def test_latest_release_uses_highest_exact_semver_and_peeled_annotated_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    responses = iter(
        [
            flow.subprocess.CompletedProcess(
                [], 0, "https://example.invalid/upstream\n", ""
            ),
            flow.subprocess.CompletedProcess([], 0, "", ""),
            flow.subprocess.CompletedProcess([], 0, "current-head\n", ""),
            flow.subprocess.CompletedProcess(
                [],
                0,
                "\n".join(
                    [
                        "old\trefs/tags/v1.2.3",
                        "peeled\trefs/tags/v1.2.3^{}",
                        "latest\trefs/tags/2.0.0",
                        "ignored\trefs/tags/v2.1.0-rc.1",
                    ]
                ),
                "",
            ),
        ]
    )
    monkeypatch.setattr(flow.subprocess, "run", lambda *args, **kwargs: next(responses))

    assert flow._latest_release(tmp_path, None) == {
        "remote": "origin",
        "tag": "2.0.0",
        "target": "latest",
        "version": "2.0.0",
        "current_head": "current-head",
        "head_differs_from_release": True,
    }


def test_latest_release_rejects_duplicate_normalized_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    responses = iter(
        [
            flow.subprocess.CompletedProcess([], 0, "", ""),
            flow.subprocess.CompletedProcess([], 0, "current-head\n", ""),
            flow.subprocess.CompletedProcess(
                [],
                0,
                "first\trefs/tags/v1.2.3\nsecond\trefs/tags/1.2.3\n",
                "",
            ),
        ]
    )
    monkeypatch.setattr(flow.subprocess, "run", lambda *args, **kwargs: next(responses))

    with pytest.raises(flow.FirstUserFlowError, match="multiple exact SemVer") as error:
        flow._latest_release(tmp_path, "origin")

    assert error.value.error_code == "ambiguous_release_version"


def test_latest_release_rejects_a_dirty_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        flow.subprocess,
        "run",
        lambda *args, **kwargs: flow.subprocess.CompletedProcess(
            [], 0, " M skills/example/SKILL.md\n", ""
        ),
    )

    with pytest.raises(flow.FirstUserFlowError, match="dirty worktree") as error:
        flow._latest_release(tmp_path, "origin")

    assert error.value.error_code == "dirty_worktree"
    assert error.value.details == {"remote": "origin"}


@pytest.mark.parametrize(
    "tags",
    [
        "",
        "head\trefs/tags/v1.2\n",
        "head\trefs/tags/v1.2.3-rc.1\n",
        "head\trefs/tags/v1.2.3+build.1\n",
    ],
)
def test_latest_release_rejects_when_no_exact_semver_tag_is_eligible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tags: str
) -> None:
    responses = iter(
        [
            flow.subprocess.CompletedProcess([], 0, "", ""),
            flow.subprocess.CompletedProcess([], 0, "current-head\n", ""),
            flow.subprocess.CompletedProcess([], 0, tags, ""),
        ]
    )
    monkeypatch.setattr(flow.subprocess, "run", lambda *args, **kwargs: next(responses))

    with pytest.raises(flow.FirstUserFlowError, match="no exact SemVer") as error:
        flow._latest_release(tmp_path, "origin")

    assert error.value.error_code == "no_eligible_release"
    assert error.value.details == {"remote": "origin"}


def test_changed_inputs_marks_a_moved_selected_release_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    receipt = {
        "input_digests": {
            "canonical_manifest": flow._sha256_file(repo / "router-plugin-source.json"),
            "skills": {
                path.name: flow._sha256_file(path / "SKILL.md")
                for path in (repo / "skills").iterdir()
            },
            "branding_assets": {
                "logo": flow._sha256_file(repo / "assets/logo.png"),
            },
        },
        "release_selection": {"remote": "origin", "tag": "1.2.3", "target": "old"},
    }
    request = {
        "canonical_manifest": "router-plugin-source.json",
        "skill_paths": [f"skills/{path.name}" for path in (repo / "skills").iterdir()],
        "branding_asset_overrides": {"logo": "assets/logo.png"},
    }
    monkeypatch.setattr(flow, "_release_is_current", lambda *_: False)

    assert flow._changed_inputs(repo, request, receipt) == ["source_remote:1.2.3"]
