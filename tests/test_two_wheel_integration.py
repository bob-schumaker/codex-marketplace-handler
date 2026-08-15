from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from marketplace_installer import marketplace_publish


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout


def copy_template(repository: Path, destination: Path) -> None:
    run(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            str(repository),
            str(destination),
        ],
        cwd=repository,
    )


def write_canonical_payload(destination: Path) -> None:
    """Create a portable v3 payload that stands in for a prior build step."""

    canonical = destination.parent / "canonical"
    plugin = canonical / "plugins" / "alpha"
    metadata = plugin / ".codex-plugin" / "publication-metadata.json"
    manifest = canonical / ".agents" / "plugins" / "marketplace.json"
    metadata.parent.mkdir(parents=True)
    (plugin / ".codex-plugin" / "plugin.json").write_text(
        '{"name":"alpha"}\n', encoding="utf-8"
    )
    metadata.write_text(
        '{"category":"Productivity","format":"router-plugin-publication-metadata-v1","plugin_slug":"alpha"}\n',
        encoding="utf-8",
    )
    (plugin / "skill.md").write_text("# Alpha\n", encoding="utf-8")
    source_map = plugin / ".router-plugin-packager-source-map.json"
    source_map.write_text(
        json.dumps(
            {
                "format_version": 1,
                "entries": [
                    {
                        "path": "skill.md",
                        "content_hash": hashlib.sha256(b"# Alpha\n").hexdigest(),
                    }
                ],
                "generated_paths": [".router-plugin-packager-source-map.json"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "name": "wheel-example",
                "plugins": [
                    {
                        "name": "alpha",
                        "source": {"source": "local", "path": "./plugins/alpha"},
                        "policy": marketplace_publish.DEFAULT_MARKETPLACE_POLICY,
                        "category": "Productivity",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    receipt = {
        "format": "marketplace-assembly-receipt-v1",
        "marketplace_name": "wheel-example",
        "plugin_name": "alpha",
        "plugin_tree_digest": marketplace_publish._tree_digest(plugin),
        "marketplace_manifest_digest": marketplace_publish._sha256(manifest),
    }
    (canonical / ".marketplace-assembly-receipt.json").write_text(
        json.dumps(receipt) + "\n", encoding="utf-8"
    )
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "__init__.py").write_text("", encoding="utf-8")
    marketplace_publish.stage_marketplace_payload(canonical, destination)


def metadata_requirement(wheel: Path) -> Requirement:
    with zipfile.ZipFile(wheel) as archive:
        metadata = next(
            name for name in archive.namelist() if name.endswith("METADATA")
        )
        requirements = [
            Requirement(line.removeprefix("Requires-Dist: "))
            for line in archive.read(metadata).decode().splitlines()
            if line.startswith("Requires-Dist: ")
        ]
    matching = [
        requirement
        for requirement in requirements
        if requirement.name.lower().replace("_", "-") == "marketplace-installer"
    ]
    assert len(matching) == 1
    return matching[0]


def test_library_and_rendered_product_wheels_are_isolated(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    product = tmp_path / "product"
    library_dist = tmp_path / "library-dist"
    product_dist = tmp_path / "product-dist"
    wheelhouse = tmp_path / "wheelhouse"
    environment = tmp_path / "environment"
    install_report = tmp_path / "library-install-report.json"
    home = tmp_path / "home"
    work_directory = tmp_path / "work"
    work_directory.mkdir()

    copy_template(repository, product)
    write_canonical_payload(product / "src" / "marketplace_publisher" / "resources")
    root_project = tomllib.loads((repository / "pyproject.toml").read_text())
    project = tomllib.loads((product / "pyproject.toml").read_text())
    assert root_project["project"]["version"] == "0.1.1"
    assert root_project["tool"]["ruff"]["target-version"] == "py312"
    assert project["project"]["dependencies"] == ["marketplace-installer>=0.1.1,<0.2.0"]
    assert project["project"]["requires-python"] == ">=3.12,<4.0"
    assert project["tool"]["ruff"]["target-version"] == "py312"

    run(["poetry", "build", "--output", str(library_dist)], cwd=repository)
    run(["poetry", "build", "--output", str(product_dist)], cwd=product)
    library_wheel = next(library_dist.glob("*.whl"))
    library_digest = hashlib.sha256(library_wheel.read_bytes()).hexdigest()
    library_sdist = next(library_dist.glob("*.tar.gz"))
    product_wheel = next(product_dist.glob("*.whl"))
    requirement = metadata_requirement(product_wheel)
    assert requirement.extras == set()
    assert requirement.marker is None
    assert requirement.specifier == SpecifierSet(">=0.1.1,<0.2.0")

    with zipfile.ZipFile(library_wheel) as archive:
        names = archive.namelist()
        assert any(name.startswith("marketplace_installer/") for name in names)
        assert not any(name.startswith("marketplace_publisher/") for name in names)
        assert not any("resources/" in name for name in names)
    with tarfile.open(library_sdist) as archive:
        names = archive.getnames()
        assert any("/src/marketplace_installer/" in name for name in names)
        assert not any("marketplace_publisher" in name for name in names)
    with zipfile.ZipFile(product_wheel) as archive:
        names = archive.namelist()
        prefix = "marketplace_publisher/resources/"
        assert prefix + ".agents/plugins/marketplace.json" in names
        assert prefix + ".marketplace-assembly-receipt.json" in names
        assert prefix + "plugins/alpha/.router-plugin-packager-source-map.json" in names
        assert "scripts/build_marketplace.py" not in names
        assert not any("/.build/" in name for name in names)

    wheelhouse.mkdir()
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--dest",
            str(wheelhouse),
            "packaging==26.3",
            "PyYAML==6.0.3",
        ],
        cwd=work_directory,
    )
    runtime_wheels = sorted(wheelhouse.glob("*.whl"))
    assert runtime_wheels
    runtime_hashes = {
        wheel.name: hashlib.sha256(wheel.read_bytes()).hexdigest()
        for wheel in runtime_wheels
    }
    assert all(len(digest) == 64 for digest in runtime_hashes.values())

    run([sys.executable, "-m", "venv", str(environment)], cwd=work_directory)
    binaries = environment / ("Scripts" if os.name == "nt" else "bin")
    pip = binaries / "pip"
    python = binaries / "python"
    run(
        [
            str(pip),
            "install",
            "--no-index",
            "--no-cache-dir",
            "--find-links",
            str(wheelhouse),
            "--report",
            str(install_report),
            str(library_wheel),
        ],
        cwd=work_directory,
    )
    run(
        [str(pip), "install", "--no-deps", "--no-index", str(product_wheel)],
        cwd=work_directory,
    )
    run([str(pip), "check"], cwd=work_directory)
    install_report_payload = json.loads(install_report.read_text(encoding="utf-8"))
    installed_library = next(
        item
        for item in install_report_payload["install"]
        if item["metadata"]["name"] == "marketplace-installer"
    )
    assert installed_library["metadata"]["version"] == root_project["project"]["version"]
    assert installed_library["download_info"]["archive_info"]["hash"] == (
        f"sha256={library_digest}"
    )

    clean_environment = dict(os.environ)
    clean_environment.pop("PYTHONPATH", None)
    clean_environment["HOME"] = str(home)
    locations = run(
        [
            str(python),
            "-c",
            (
                "import marketplace_installer, marketplace_publisher; "
                "print(marketplace_installer.__file__); "
                "print(marketplace_publisher.__file__)"
            ),
        ],
        cwd=work_directory,
        env=clean_environment,
    ).splitlines()
    assert all("site-packages" in location for location in locations)
    output = run(
        [str(binaries / "marketplace-publisher"), "--json"],
        cwd=work_directory,
        env=clean_environment,
    )
    result = json.loads(output)
    assert result["status"] == "installed"
    assert result["plugins"]["added"] == ["alpha"]
    catalog = (
        home
        / ".codex"
        / "local-marketplaces"
        / "wheel-example"
        / ".agents"
        / "plugins"
        / "marketplace.json"
    )
    assert json.loads(catalog.read_text())["name"] == "wheel-example"
