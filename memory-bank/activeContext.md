# Active Context

## Current focus

The embedded `bob-schumaker-codex-support` marketplace release payload is
complete and verified.

## Current status

- Done: main specification, technical plan, and TDD task list are authored.
- Done: Poetry developer tooling, package setup, and pre-commit hooks are
  configured.
- Done: repository-only importer, publisher, state checks, runtime CLI, and
  self-contained wheel verification are implemented through TDD.
- Done: a Copier template renders a custom-named, payload-free marketplace
  installer without this repository's memory-bank or specification artifacts.
- Done: all 15 catalog-selected plugins from the personal
  `bob-schumaker-codex-support` marketplace are embedded as package data.
- Done: an installed wheel published the real embedded payload into an isolated
  home directory.
- Done: local marketplace layout is confirmed under
  `~/.codex/local-marketplaces/<marketplace-name>/`.
- Done: package-resource exclusions keep Ruff and Rumdl from reformatting
  imported plugin payload files.

## Next steps

1. Use `poetry run python scripts/import_marketplace.py
   bob-schumaker-codex-support` to refresh the embedded payload intentionally.
2. Build and publish the verified distribution when a release is desired.
3. Use `poetry run copier copy copier-template <destination>` when a clean,
   custom-named installer repository is needed.
