import json
from pathlib import Path

import pytest

from marketplace_publisher.validation import (
    MarketplaceValidationError,
    parse_marketplace_json,
    resolve_plugin_directory,
)


def marketplace(*plugins: dict[str, object]) -> str:
    return json.dumps({"name": "example", "plugins": list(plugins)})


def plugin(name: str, path: str = "./plugins/example") -> dict[str, object]:
    return {
        "name": name,
        "source": {"source": "local", "path": path},
    }


def test_rejects_malformed_json() -> None:
    with pytest.raises(MarketplaceValidationError, match="valid JSON"):
        parse_marketplace_json("{")


@pytest.mark.parametrize("name", [None, "", "contains spaces"])
def test_rejects_missing_or_invalid_marketplace_name(name: object) -> None:
    with pytest.raises(MarketplaceValidationError, match="marketplace name"):
        parse_marketplace_json(json.dumps({"name": name, "plugins": []}))


def test_rejects_duplicate_plugin_names() -> None:
    with pytest.raises(MarketplaceValidationError, match="duplicate plugin"):
        parse_marketplace_json(marketplace(plugin("example"), plugin("example")))


def test_rejects_plugin_source_that_does_not_match_plugin_name() -> None:
    with pytest.raises(MarketplaceValidationError, match="plugin source"):
        parse_marketplace_json(marketplace(plugin("example", "./plugins/other")))


@pytest.mark.parametrize(
    "entry",
    [
        {"name": "example", "source": {"source": "url", "path": "./plugins/example"}},
        {"name": "example", "source": "./plugins/example"},
        plugin("example", "/plugins/example"),
        plugin("example", "./plugins/../outside"),
        plugin("example", "./.codex/plugins/example"),
    ],
)
def test_rejects_non_local_or_unsafe_plugin_source(entry: dict[str, object]) -> None:
    with pytest.raises(MarketplaceValidationError, match="plugin source"):
        parse_marketplace_json(marketplace(entry))


def test_resolves_plugin_directory_under_marketplace_root(tmp_path: Path) -> None:
    root = tmp_path / "example"
    plugin_root = root / "plugins" / "example"
    plugin_root.mkdir(parents=True)

    assert resolve_plugin_directory(root, "./plugins/example") == plugin_root


def test_rejects_symlinked_plugin_directory(tmp_path: Path) -> None:
    root = tmp_path / "example"
    target = tmp_path / "target"
    target.mkdir()
    (root / "plugins").mkdir(parents=True)
    (root / "plugins" / "example").symlink_to(target, target_is_directory=True)

    with pytest.raises(MarketplaceValidationError, match="symlink"):
        resolve_plugin_directory(root, "./plugins/example")
