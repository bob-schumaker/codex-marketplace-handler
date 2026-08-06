import json
from pathlib import Path

import pytest

from marketplace_publisher import cli, importer
from marketplace_publisher.publisher import PublishResult, PublisherError


def publish_result(*, dry_run: bool = False) -> PublishResult:
    return PublishResult(
        status="installed",
        marketplace="example",
        dry_run=dry_run,
        added=("alpha",),
        updated=(),
        unchanged=(),
    )


def test_runtime_cli_emits_one_json_result_and_passes_flags(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    received: dict[str, object] = {}

    def publish(home: Path, *, dry_run: bool, force: bool) -> PublishResult:
        received.update({"home": home, "dry_run": dry_run, "force": force})
        return publish_result(dry_run=dry_run)

    monkeypatch.setattr(cli, "publish_embedded_marketplace", publish)

    exit_code = cli.main(["--dry-run", "--force", "--json"], home=tmp_path)

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert received == {"home": tmp_path, "dry_run": True, "force": True}
    assert output["status"] == "installed"
    assert output["plugins"]["added"] == ["alpha"]


def test_runtime_cli_reports_expected_error_as_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(home: Path, *, dry_run: bool, force: bool) -> PublishResult:
        raise PublisherError("bad marketplace")

    monkeypatch.setattr(cli, "publish_embedded_marketplace", fail)

    exit_code = cli.main(["--json"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["status"] == "error"
    assert output["errors"] == ["bad marketplace"]


def test_runtime_cli_writes_verbose_diagnostics_to_standard_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli, "publish_embedded_marketplace", lambda *args, **kwargs: publish_result()
    )

    exit_code = cli.main(["--verbose"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Publishing embedded marketplace" in captured.err
    assert "installed marketplace example" in captured.out


def test_repository_importer_uses_named_local_root(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    resources = tmp_path / "repository" / "src" / "marketplace_publisher" / "resources"
    received: dict[str, object] = {}

    def import_payload(
        source: Path,
        destination: Path,
        selected_plugins: list[str],
        expected_name: str,
    ) -> object:
        received.update(
            {
                "source": source,
                "destination": destination,
                "selected_plugins": selected_plugins,
                "expected_name": expected_name,
            }
        )
        return type("Marketplace", (), {"name": "example", "plugins": ()})()

    monkeypatch.setattr(importer, "import_marketplace", import_payload)

    exit_code = importer.main(
        ["example", "alpha"], home=tmp_path, package_resources=resources
    )

    assert exit_code == 0
    assert received == {
        "source": tmp_path / ".codex" / "local-marketplaces" / "example",
        "destination": resources,
        "selected_plugins": ["alpha"],
        "expected_name": "example",
    }
    assert "Imported marketplace example" in capsys.readouterr().out
