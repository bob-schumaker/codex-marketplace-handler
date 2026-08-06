import os
import subprocess
import sys
import tomllib
from pathlib import Path


def test_copier_template_renders_a_custom_marketplace_installer(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    destination = tmp_path / "acme-installer"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            "--data",
            "project_name=Acme Marketplace Installer",
            "--data",
            "project_slug=acme-marketplace-installer",
            str(repository / "copier-template"),
            str(destination),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    project = tomllib.loads((destination / "pyproject.toml").read_text())
    assert project["project"]["name"] == "acme-marketplace-installer"
    assert project["project"]["scripts"] == {
        "acme-marketplace-installer": "acme_marketplace_installer.__main__:main"
    }
    assert (destination / "scripts" / "import_marketplace.py").is_file()
    assert (destination / "src" / "acme_marketplace_installer").is_dir()
    assert not (destination / "memory-bank").exists()
    assert not (destination / "specs").exists()
    assert not list(destination.rglob("__pycache__"))
    assert not list(destination.rglob("*.pyc"))

    completed = subprocess.run(
        [sys.executable, "-c", "import acme_marketplace_installer"],
        check=False,
        text=True,
        capture_output=True,
        cwd=destination,
        env={
            **os.environ,
            "PYTHONPATH": str(destination / "src"),
        },
    )

    assert completed.returncode == 0, completed.stderr
