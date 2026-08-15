import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from test_router_plugin_packager_layer3 import _mcp_fixture_repo


def copy_template(
    repository: Path, destination: Path, *data: str
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "copier", "copy", "--defaults"]
    for value in data:
        command.extend(["--data", value])
    command.extend([str(repository), str(destination)])
    return subprocess.run(command, text=True, capture_output=True, check=False)


def test_root_copier_template_renders_the_default_publisher(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    destination = tmp_path / "publisher"

    completed = copy_template(repository, destination)

    assert completed.returncode == 0, completed.stderr
    project = tomllib.loads((destination / "pyproject.toml").read_text())
    assert project["project"]["name"] == "marketplace-publisher"
    assert project["project"]["dependencies"] == ["marketplace-installer>=0.1.1,<0.2.0"]
    assert project["project"]["scripts"] == {
        "marketplace-publisher": "marketplace_publisher.__main__:main"
    }
    assert (destination / "scripts" / "build_marketplace.py").is_file()
    assert not (destination / "scripts" / "import_marketplace.py").exists()
    package = destination / "src" / "marketplace_publisher"
    assert package.is_dir()
    assert not (destination / "memory-bank").exists()
    assert not (destination / "specs").exists()
    assert not (destination / "poetry.lock").exists()
    assert not list(package.glob("models.py"))
    assert not list(package.glob("paths.py"))
    assert not list(package.glob("validation.py"))
    assert "marketplace_installer" in (package / "publisher.py").read_text()
    publisher = (package / "publisher.py").read_text()
    assert "marketplace_installer.marketplace_publish" in publisher
    assert not (package / "importer.py").exists()


def test_root_copier_template_renders_a_custom_publisher(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    destination = tmp_path / "acme-publisher"

    completed = copy_template(
        repository,
        destination,
        "project_name=Acme Marketplace Publisher",
        "project_slug=acme-marketplace-publisher",
    )

    assert completed.returncode == 0, completed.stderr
    project = tomllib.loads((destination / "pyproject.toml").read_text())
    assert project["project"]["name"] == "acme-marketplace-publisher"
    assert (destination / "src" / "acme_marketplace_publisher").is_dir()
    publisher = (
        destination / "src" / "acme_marketplace_publisher" / "publisher.py"
    ).read_text()
    assert 'f"{__package__}.resources"' in publisher
    assert "marketplace_publisher.resources" not in publisher


def test_rendered_product_unit_tests_use_the_v3_adapter(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    destination = tmp_path / "publisher"
    completed = copy_template(repository, destination)

    assert completed.returncode == 0, completed.stderr
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_cli.py",
            "tests/test_build_marketplace.py",
            "tests/test_packaging.py",
        ],
        cwd=destination,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                [str(destination / "src"), str(repository / "src")]
            ),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_rendered_build_script_generates_and_stages_a_v3_payload(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[1]
    destination = tmp_path / "publisher"
    source_repository = _mcp_fixture_repo(tmp_path)
    foreign_directory = tmp_path / "foreign"
    foreign_directory.mkdir()
    completed = copy_template(repository, destination)

    assert completed.returncode == 0, completed.stderr
    result = subprocess.run(
        [
            sys.executable,
            str(destination / "scripts" / "build_marketplace.py"),
            "--repository-root",
            os.path.relpath(source_repository, foreign_directory),
            "--invocation",
            os.path.relpath(source_repository / "mcp.json", foreign_directory),
            "--marketplace-name",
            "fixture-marketplace",
        ],
        cwd=foreign_directory,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "HOME": str(tmp_path / "empty-home"),
            "PYTHONPATH": os.pathsep.join(
                [str(destination / "src"), str(repository / "src")]
            ),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    resources = destination / "src" / "marketplace_publisher" / "resources"
    assert (resources / ".agents" / "plugins" / "marketplace.json").is_file()
    assert (resources / ".marketplace-assembly-receipt.json").is_file()
    assert (
        resources
        / "plugins"
        / "sample-mcp-surface"
        / ".router-plugin-packager-source-map.json"
    ).is_file()
    assert not (destination / ".build" / "marketplace-assembly").exists()
    assert not (tmp_path / "empty-home" / ".codex").exists()


@pytest.mark.parametrize(
    "data",
    [
        "project_slug=marketplace-installer",
        "project_slug=marketplace--installer",
        "project_slug=marketplace_installer",
    ],
)
def test_root_copier_template_rejects_library_distribution_collisions(
    tmp_path: Path, data: str
) -> None:
    completed = copy_template(Path(__file__).parents[1], tmp_path / "invalid", data)

    assert completed.returncode != 0


def test_root_copier_template_rejects_library_package_collision(tmp_path: Path) -> None:
    completed = copy_template(
        Path(__file__).parents[1],
        tmp_path / "invalid",
        "project_slug=valid-publisher",
        "package_name=marketplace_installer",
    )

    assert completed.returncode != 0
    assert "must not be marketplace_installer" in completed.stderr


def test_vcs_render_records_full_template_commit(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    template = tmp_path / "template"
    product = tmp_path / "product"
    cache = tmp_path / "copier-cache"
    shutil.copytree(
        repository,
        template,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"),
    )
    subprocess.run(["git", "init", "-q"], cwd=template, check=True)
    subprocess.run(["git", "add", "-A"], cwd=template, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=template,
        check=True,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=template,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            "--vcs-ref",
            commit,
            f"git+file://{template}",
            str(product),
        ],
        text=True,
        capture_output=True,
        env={**os.environ, "COPIER_CACHE_DIR": str(cache)},
    )

    assert completed.returncode == 0, completed.stderr
    answers = (product / ".copier-answers.yml").read_text()
    assert f"_commit: {commit}" in answers
    assert re.search(r"^_commit: [0-9a-f]{40}$", answers, re.MULTILINE)
    assert f'_src_path: "git+file://{template}"' in answers
