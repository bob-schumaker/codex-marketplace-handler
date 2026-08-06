# Active Context

## Current focus

Implementation is complete and verified; a real marketplace payload has not
yet been selected for the release artifact.

## Current status

- Done: main specification, technical plan, and TDD task list are authored.
- Done: Poetry developer tooling, package setup, and pre-commit hooks are
  configured.
- Done: repository-only importer, publisher, state checks, runtime CLI, and
  self-contained wheel verification are implemented through TDD.
- Done: local marketplace layout is confirmed under
  `~/.codex/local-marketplaces/<marketplace-name>/`.
- Pending: select and import the marketplace payload to embed in the release
  package.

## Next steps

1. Obtain the marketplace name and optional plugin selection from the user.
2. Run `poetry run python scripts/import_marketplace.py` with that selection.
3. Build and inspect the final wheel, then run the installed runtime command.
