import json
from pathlib import Path

import pytest

from marketplace_publisher.publisher import (
    MarketplaceConflictError,
    ModificationConflictError,
    PublisherError,
    publish_marketplace,
)


def write_embedded(
    resources: Path,
    plugins: dict[str, str],
    *,
    interface: dict[str, object] | None = None,
) -> None:
    resources.mkdir(parents=True, exist_ok=True)
    catalog: dict[str, object] = {
        "name": "example",
        "plugins": [
            {
                "name": name,
                "source": {"source": "local", "path": f"./plugins/{name}"},
            }
            for name in plugins
        ],
    }
    if interface is not None:
        catalog["interface"] = interface
    (resources / "marketplace.json").write_text(json.dumps(catalog))
    for name, content in plugins.items():
        plugin = resources / "plugins" / name
        (plugin / ".codex-plugin").mkdir(parents=True, exist_ok=True)
        (plugin / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"name": name, "version": "1.0.0"})
        )
        (plugin / "skill.md").write_text(content)


def target_root(home: Path) -> Path:
    return home / ".codex" / "local-marketplaces" / "example"


def target_catalog(home: Path) -> Path:
    return target_root(home) / ".agents" / "plugins" / "marketplace.json"


def test_fresh_publish_installs_catalog_plugins_and_state(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    home = tmp_path / "home"
    write_embedded(resources, {"alpha": "alpha"})

    result = publish_marketplace(resources, home)

    assert result.status == "installed"
    assert result.added == ("alpha",)
    assert json.loads(target_catalog(home).read_text())["name"] == "example"
    assert (target_root(home) / "plugins" / "alpha" / "skill.md").read_text() == "alpha"
    state = target_root(home) / ".marketplace-publisher" / "state.json"
    assert "skill.md" in json.loads(state.read_text())["plugins"]["alpha"]["files"]


def test_same_name_merge_preserves_unrelated_content_and_updates_owned_plugin(
    tmp_path: Path,
) -> None:
    resources = tmp_path / "resources"
    home = tmp_path / "home"
    write_embedded(resources, {"alpha": "first"}, interface={"displayName": "First"})
    publish_marketplace(resources, home)

    installed = json.loads(target_catalog(home).read_text())
    installed["custom"] = {"keep": True}
    installed["plugins"].append(
        {
            "name": "unrelated",
            "source": {"source": "local", "path": "./plugins/unrelated"},
        }
    )
    target_catalog(home).write_text(json.dumps(installed))
    (target_root(home) / "plugins" / "unrelated").mkdir(parents=True)
    write_embedded(
        resources,
        {"alpha": "updated", "beta": "new"},
        interface={"displayName": "Updated"},
    )

    result = publish_marketplace(resources, home)

    merged = json.loads(target_catalog(home).read_text())
    assert result.status == "merged"
    assert result.updated == ("alpha",)
    assert result.added == ("beta",)
    assert merged["custom"] == {"keep": True}
    assert merged["interface"] == {"displayName": "Updated"}
    assert {entry["name"] for entry in merged["plugins"]} == {
        "alpha",
        "beta",
        "unrelated",
    }
    assert (
        target_root(home) / "plugins" / "alpha" / "skill.md"
    ).read_text() == "updated"


def test_repeated_publish_is_a_noop(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    home = tmp_path / "home"
    write_embedded(resources, {"alpha": "alpha"})
    publish_marketplace(resources, home)
    before = target_catalog(home).read_text()

    result = publish_marketplace(resources, home)

    assert result.status == "noop"
    assert result.unchanged == ("alpha",)
    assert target_catalog(home).read_text() == before


def test_rejects_different_name_catalog_without_changes(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    home = tmp_path / "home"
    write_embedded(resources, {"alpha": "alpha"})
    catalog = target_catalog(home)
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps({"name": "different", "plugins": []}))

    with pytest.raises(MarketplaceConflictError, match="different name"):
        publish_marketplace(resources, home)

    assert json.loads(catalog.read_text())["name"] == "different"


def test_modified_owned_file_requires_force_and_preserves_extra_files(
    tmp_path: Path,
) -> None:
    resources = tmp_path / "resources"
    home = tmp_path / "home"
    write_embedded(resources, {"alpha": "original"})
    publish_marketplace(resources, home)
    destination = target_root(home) / "plugins" / "alpha"
    (destination / "skill.md").write_text("changed")
    (destination / "extra.txt").write_text("keep")

    with pytest.raises(ModificationConflictError, match="modified"):
        publish_marketplace(resources, home)

    result = publish_marketplace(resources, home, force=True)

    assert result.status == "merged"
    assert (destination / "skill.md").read_text() == "original"
    assert (destination / "extra.txt").read_text() == "keep"


def test_dry_run_does_not_write_files(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    home = tmp_path / "home"
    write_embedded(resources, {"alpha": "alpha"})

    result = publish_marketplace(resources, home, dry_run=True)

    assert result.dry_run is True
    assert result.status == "installed"
    assert not target_root(home).exists()


def test_rejects_symlinked_target_marketplace_root(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    home = tmp_path / "home"
    outside = tmp_path / "outside"
    write_embedded(resources, {"alpha": "alpha"})
    root = target_root(home)
    root.parent.mkdir(parents=True)
    outside.mkdir()
    root.symlink_to(outside, target_is_directory=True)

    with pytest.raises(PublisherError, match="symlink"):
        publish_marketplace(resources, home)

    assert list(outside.iterdir()) == []


def test_unmanaged_destination_requires_force(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    home = tmp_path / "home"
    write_embedded(resources, {"alpha": "alpha"})
    unmanaged = target_root(home) / "plugins" / "alpha"
    unmanaged.mkdir(parents=True)
    (unmanaged / "extra.txt").write_text("keep")

    with pytest.raises(ModificationConflictError, match="modified"):
        publish_marketplace(resources, home)

    publish_marketplace(resources, home, force=True)
    assert (unmanaged / "extra.txt").read_text() == "keep"
    assert (unmanaged / "skill.md").read_text() == "alpha"


def test_catalog_write_failure_preserves_existing_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resources = tmp_path / "resources"
    home = tmp_path / "home"
    write_embedded(resources, {"alpha": "first"})
    publish_marketplace(resources, home)
    before = target_catalog(home).read_text()
    state_path = target_root(home) / ".marketplace-publisher" / "state.json"
    state_before = state_path.read_text()
    write_embedded(resources, {"alpha": "second"})

    import marketplace_publisher.publisher as publisher

    original_write = publisher._atomic_write_json

    def fail_catalog_write(path: Path, document: dict[str, object]) -> None:
        if path == target_catalog(home):
            raise OSError("disk full")
        original_write(path, document)

    monkeypatch.setattr(publisher, "_atomic_write_json", fail_catalog_write)

    with pytest.raises(PublisherError, match="failed to publish"):
        publish_marketplace(resources, home)

    assert target_catalog(home).read_text() == before
    assert state_path.read_text() == state_before
