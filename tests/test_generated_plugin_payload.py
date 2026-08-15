from __future__ import annotations

import hashlib
import importlib
import json
import shutil
from pathlib import Path

import pytest

from marketplace_installer import marketplace_publish as publish
from marketplace_installer import router_plugin_packager as packager
from test_router_plugin_packager_layer3 import _mcp_fixture_repo


def _digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _generated_plugin(root: Path, plugin_name: str = "example-plugin") -> Path:
    plugin_root = root / plugin_name
    (plugin_root / ".codex-plugin").mkdir(parents=True)
    (plugin_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": plugin_name}) + "\n", encoding="utf-8"
    )
    (plugin_root / ".codex-plugin" / "publication-metadata.json").write_text(
        json.dumps(
            {
                "category": "Productivity",
                "format": "router-plugin-publication-metadata-v1",
                "plugin_slug": plugin_name,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plugin_root / "README.md").write_text("example\n", encoding="utf-8")
    (plugin_root / ".router-plugin-packager-source-map.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "entries": [
                    {
                        "path": "README.md",
                        "content_hash": hashlib.sha256(b"example\n").hexdigest(),
                    }
                ],
                "generated_paths": [".router-plugin-packager-source-map.json"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return plugin_root


def _tree_files(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _digest(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_assemble_and_stage_generated_plugin_creates_portable_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_root = _generated_plugin(tmp_path / "source")
    assembly_root = tmp_path / "assembly"
    resources = tmp_path / "package" / "resources"
    resources.mkdir(parents=True)
    marker = resources / "__init__.py"
    marker.write_text("# package marker\n", encoding="utf-8")

    monkeypatch.setattr(
        publish,
        "_validate_generated_plugin_root",
        lambda path: ("example-plugin", "sha256:router", None, {}),
    )

    assembled = publish.assemble_generated_plugin(
        plugin_root=plugin_root,
        assembly_root=assembly_root,
        marketplace_name="example-marketplace",
    )
    staged = publish.stage_marketplace_payload(assembly_root, resources)

    receipt = json.loads(
        (assembly_root / ".marketplace-assembly-receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert assembled == {
        "assembly_root": str(assembly_root.absolute()),
        "marketplace_name": "example-marketplace",
        "plugin_name": "example-plugin",
    }
    assert receipt["format"] == "marketplace-assembly-receipt-v1"
    assert receipt["plugin_name"] == "example-plugin"
    assert staged["destination_resources"] == str(resources.absolute())
    assert marker.read_text(encoding="utf-8") == "# package marker\n"
    assert _tree_files(assembly_root) == {
        path: digest
        for path, digest in _tree_files(resources).items()
        if path != "__init__.py"
    }


def test_stage_rejects_tampered_portable_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_root = _generated_plugin(tmp_path / "source")
    assembly_root = tmp_path / "assembly"

    monkeypatch.setattr(
        publish,
        "_validate_generated_plugin_root",
        lambda path: ("example-plugin", "sha256:router", None, {}),
    )
    publish.assemble_generated_plugin(
        plugin_root=plugin_root,
        assembly_root=assembly_root,
        marketplace_name="example-marketplace",
    )
    receipt_path = assembly_root / ".marketplace-assembly-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["marketplace_name"] = "tampered"
    receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")

    with pytest.raises(publish.MarketplacePublishError):
        publish.stage_marketplace_payload(assembly_root, tmp_path / "resources")


def test_stage_rolls_back_resources_when_replacement_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_root = _generated_plugin(tmp_path / "source")
    assembly_root = tmp_path / "assembly"
    resources = tmp_path / "package" / "resources"
    resources.mkdir(parents=True)
    (resources / "previous.txt").write_text("previous\n", encoding="utf-8")
    monkeypatch.setattr(
        publish,
        "_validate_generated_plugin_root",
        lambda path: ("example-plugin", "sha256:router", None, {}),
    )
    publish.assemble_generated_plugin(
        plugin_root=plugin_root,
        assembly_root=assembly_root,
        marketplace_name="example-marketplace",
    )
    original_replace = publish.os.replace
    calls = 0

    def fail_second_replace(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected replacement failure")
        original_replace(source, destination)

    monkeypatch.setattr(publish.os, "replace", fail_second_replace)

    with pytest.raises(OSError, match="injected replacement failure"):
        publish.stage_marketplace_payload(assembly_root, resources)

    assert (resources / "previous.txt").read_text(encoding="utf-8") == "previous\n"


def test_publish_embedded_payload_previews_then_installs_without_source_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_root = _generated_plugin(tmp_path / "source")
    assembly_root = tmp_path / "assembly"
    package_parent = tmp_path / "installed"
    resources = package_parent / "payload_fixture" / "resources"
    resources.mkdir(parents=True)
    (package_parent / "payload_fixture" / "__init__.py").write_text(
        "", encoding="utf-8"
    )
    (resources / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        publish,
        "_validate_generated_plugin_root",
        lambda path: ("example-plugin", "sha256:router", None, {}),
    )
    publish.assemble_generated_plugin(
        plugin_root=plugin_root,
        assembly_root=assembly_root,
        marketplace_name="example-marketplace",
    )
    publish.stage_marketplace_payload(assembly_root, resources)
    monkeypatch.syspath_prepend(str(package_parent))
    importlib.invalidate_caches()
    shutil.rmtree(plugin_root.parent)

    preview = publish.publish_embedded_generated_marketplace(
        "payload_fixture.resources", home=tmp_path / "home", dry_run=True
    )
    installed = publish.publish_embedded_generated_marketplace(
        "payload_fixture.resources", home=tmp_path / "home"
    )
    repeated = publish.publish_embedded_generated_marketplace(
        "payload_fixture.resources", home=tmp_path / "home"
    )

    assert preview == {
        "status": "preview",
        "marketplace": "example-marketplace",
        "dry_run": True,
        "added": ["example-plugin"],
        "updated": [],
        "unchanged": [],
        "conflicts": [],
    }
    assert installed == {
        **preview,
        "status": "installed",
        "dry_run": False,
    }
    assert repeated["unchanged"] == ["example-plugin"]
    assert (
        tmp_path
        / "home"
        / ".codex"
        / "local-marketplaces"
        / "example-marketplace"
        / "plugins"
        / "example-plugin"
        / "README.md"
    ).read_text(encoding="utf-8") == "example\n"


def test_publish_embedded_payload_requires_force_for_changed_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_root = _generated_plugin(tmp_path / "source")
    assembly_root = tmp_path / "assembly"
    package_parent = tmp_path / "installed"
    resources = package_parent / "force_fixture" / "resources"
    resources.mkdir(parents=True)
    (package_parent / "force_fixture" / "__init__.py").write_text("", encoding="utf-8")
    (resources / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        publish,
        "_validate_generated_plugin_root",
        lambda path: ("example-plugin", "sha256:router", None, {}),
    )
    publish.assemble_generated_plugin(
        plugin_root=plugin_root,
        assembly_root=assembly_root,
        marketplace_name="example-marketplace",
    )
    publish.stage_marketplace_payload(assembly_root, resources)
    monkeypatch.syspath_prepend(str(package_parent))
    importlib.invalidate_caches()
    home = tmp_path / "home"
    publish.publish_embedded_generated_marketplace("force_fixture.resources", home=home)
    installed_readme = (
        home
        / ".codex"
        / "local-marketplaces"
        / "example-marketplace"
        / "plugins"
        / "example-plugin"
        / "README.md"
    )
    installed_readme.write_text("changed\n", encoding="utf-8")

    preview = publish.publish_embedded_generated_marketplace(
        "force_fixture.resources", home=home, dry_run=True
    )
    with pytest.raises(publish.MarketplacePublishError, match="conflicts"):
        publish.publish_embedded_generated_marketplace(
            "force_fixture.resources", home=home
        )
    forced = publish.publish_embedded_generated_marketplace(
        "force_fixture.resources", home=home, force=True
    )

    assert preview["conflicts"] == ["example-plugin"]
    assert installed_readme.read_text(encoding="utf-8") == "example\n"
    assert forced["updated"] == ["example-plugin"]


def test_real_packager_output_assembles_and_stages_as_a_portable_payload(
    tmp_path: Path,
) -> None:
    repository = _mcp_fixture_repo(tmp_path)
    plugin_root = Path(
        packager.run("apply", repository / "mcp.json", repository)["output_root"]
    )
    assembly_root = tmp_path / "assembly"
    resources = tmp_path / "publisher" / "resources"
    resources.mkdir(parents=True)
    (resources / "__init__.py").write_text("", encoding="utf-8")

    assembled = publish.assemble_generated_plugin(
        plugin_root=plugin_root,
        assembly_root=assembly_root,
        marketplace_name="fixture-marketplace",
    )
    publish.stage_marketplace_payload(assembly_root, resources)

    assert assembled["plugin_name"] == "sample-mcp-surface"
    assert _tree_files(assembly_root) == {
        path: digest
        for path, digest in _tree_files(resources).items()
        if path != "__init__.py"
    }
