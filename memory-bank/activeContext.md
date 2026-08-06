# Active Context

## Current focus

The publisher implementation and Copier template are complete. This source
repository intentionally contains no embedded marketplace payload.

## Current status

- Done: main specification, technical plan, and TDD task list are authored.
- Done: Poetry developer tooling, package setup, and pre-commit hooks are
  configured.
- Done: repository-only importer, publisher, state checks, runtime CLI, and
  self-contained wheel verification are implemented through TDD.
- Done: a Copier template renders a custom-named, payload-free marketplace
  installer without this repository's memory-bank or specification artifacts.
- Done: an imported 15-plugin payload was verified in a built wheel and then
  removed; source control retains only empty resource-package markers.
- Done: local marketplace layout is confirmed under
  `~/.codex/local-marketplaces/<marketplace-name>/`.
- Done: package-resource exclusions keep Ruff and Rumdl from reformatting a
  future imported plugin payload.

## Next steps

1. In a product repository, use `poetry run python scripts/import_marketplace.py
   <marketplace-name>` to add a release payload intentionally.
2. Build and publish the resulting payload-bearing distribution when desired.
3. Use `poetry run copier copy copier-template <destination>` when a clean,
   custom-named installer repository is needed.
