import hashlib
import json
import subprocess
import sys
from pathlib import Path


def file_digests(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != ".copier-answers.yml"
    }


def test_copier_template_render_matches_frozen_manifest_except_allowed_extraction(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[1]
    manifest = json.loads(
        (
            repository
            / "tests"
            / "fixtures"
            / "copier-template"
            / "migration-manifest.json"
        ).read_text()
    )
    destination = tmp_path / "publisher"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            str(repository),
            str(destination),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert not (destination / "memory-bank").exists()
    assert not (destination / "specs").exists()
    assert all({"source", "reason"} <= move.keys() for move in manifest["moves"])
    assert all(
        ("target" in move) ^ ("disposition" in move) for move in manifest["moves"]
    )

    frozen = manifest["files"]
    current = file_digests(destination)
    allowed = manifest["allowed_changes"]
    changed = {
        path
        for path in set(frozen) | set(current)
        if frozen.get(path) != current.get(path)
    }
    assert changed == set(allowed)
