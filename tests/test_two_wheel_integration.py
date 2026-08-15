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

from marketplace_installer import import_marketplace


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


def write_marketplace(root: Path) -> None:
    catalog = root / ".agents" / "plugins" / "marketplace.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(
        json.dumps(
            {
                "name": "wheel-example",
                "plugins": [
                    {
                        "name": "alpha",
                        "source": {"source": "local", "path": "./plugins/alpha"},
                    }
                ],
            }
        )
    )
    plugin = root / "plugins" / "alpha"
    (plugin / ".codex-plugin").mkdir(parents=True)
    (plugin / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"name": "alpha", "version": "1.0.0"})
    )
    (plugin / "skill.md").write_text("# Alpha\n")


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
    source_marketplace = tmp_path / "source-marketplace"
    environment = tmp_path / "environment"
    home = tmp_path / "home"
    work_directory = tmp_path / "work"
    work_directory.mkdir()

    copy_template(repository, product)
    write_marketplace(source_marketplace)
    import_marketplace(
        source_marketplace,
        product / "src" / "marketplace_publisher" / "resources",
        expected_name="wheel-example",
    )
    project = tomllib.loads((product / "pyproject.toml").read_text())
    assert project["project"]["dependencies"] == ["marketplace-installer>=0.1.0,<0.2.0"]

    run(["poetry", "build", "--output", str(library_dist)], cwd=repository)
    run(["poetry", "build", "--output", str(product_dist)], cwd=product)
    library_wheel = next(library_dist.glob("*.whl"))
    library_sdist = next(library_dist.glob("*.tar.gz"))
    product_wheel = next(product_dist.glob("*.whl"))
    requirement = metadata_requirement(product_wheel)
    assert requirement.extras == set()
    assert requirement.marker is None
    assert requirement.specifier == SpecifierSet(">=0.1.0,<0.2.0")

    with zipfile.ZipFile(library_wheel) as archive:
        names = archive.namelist()
        assert any(name.startswith("marketplace_installer/") for name in names)
        assert not any(name.startswith("marketplace_publisher/") for name in names)
        assert not any("resources/" in name for name in names)
        entry_points = next(name for name in names if name.endswith("entry_points.txt"))
        commands = archive.read(entry_points).decode("utf-8")
        assert "marketplace-installer=" in commands
        assert "router-plugin-packager=" in commands
        assert "mcp-plugin-packaging-customer-flow=" in commands
    with tarfile.open(library_sdist) as archive:
        names = archive.getnames()
        assert any("/src/marketplace_installer/" in name for name in names)
        assert not any("marketplace_publisher" in name for name in names)
        assert not any("/resources/" in name for name in names)

    run([sys.executable, "-m", "venv", str(environment)], cwd=work_directory)
    binaries = environment / ("Scripts" if os.name == "nt" else "bin")
    pip = binaries / "pip"
    python = binaries / "python"
    run([str(pip), "install", str(library_wheel)], cwd=work_directory)
    run([str(pip), "install", "--no-deps", str(product_wheel)], cwd=work_directory)
    run([str(pip), "check"], cwd=work_directory)

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
    run(
        [
            str(python),
            "-c",
            (
                "from marketplace_installer import (ImportError, Marketplace, "
                "MarketplaceConflictError, ModificationConflictError, PluginEntry, "
                "PublishResult, PublisherError, UnmanagedPluginConflictError, "
                "import_marketplace, publish_embedded_marketplace, publish_marketplace)"
            ),
        ],
        cwd=work_directory,
        env=clean_environment,
    )
    run(
        [
            str(python),
            "-c",
            (
                "from marketplace_publisher.importer import ImportError, Marketplace, "
                "PluginEntry, import_marketplace; "
                "from marketplace_publisher.publisher import MarketplaceConflictError, "
                "ModificationConflictError, PublishResult, PublisherError, "
                "UnmanagedPluginConflictError, publish_embedded_marketplace, "
                "publish_marketplace"
            ),
        ],
        cwd=work_directory,
        env=clean_environment,
    )
    output = run(
        [str(binaries / "marketplace-publisher"), "--json"],
        cwd=work_directory,
        env=clean_environment,
    )
    result = json.loads(output)
    assert result["status"] == "installed"
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
