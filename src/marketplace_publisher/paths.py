"""Safe paths for one Codex local marketplace root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MarketplacePaths:
    """Resolved paths for a named local marketplace under one home directory."""

    home: Path
    marketplace_name: str

    @property
    def root(self) -> Path:
        return self.home / ".codex" / "local-marketplaces" / self.marketplace_name

    @property
    def catalog(self) -> Path:
        return self.root / ".agents" / "plugins" / "marketplace.json"

    @property
    def plugins(self) -> Path:
        return self.root / "plugins"

    @property
    def state(self) -> Path:
        return self.root / ".marketplace-publisher" / "state.json"

    def assert_safe_for_writes(self) -> None:
        """Reject symlinked target components before publication writes."""
        components = (
            self.home / ".codex",
            self.home / ".codex" / "local-marketplaces",
            self.root,
            self.root / ".agents",
            self.catalog.parent,
            self.plugins,
            self.state.parent,
        )
        if any(path.is_symlink() for path in components):
            raise PathSafetyError("target marketplace path must not contain a symlink")


class PathSafetyError(RuntimeError):
    """Raised when a local marketplace path could escape its expected root."""
