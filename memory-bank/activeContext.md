# Active Context

## Current focus

Implementation-ready specification; production code has not started.

## Current status

- Done: main specification, technical plan, and TDD task list are authored.
- Done: Poetry developer tooling and pre-commit hooks are configured.
- Done: local marketplace layout is confirmed under
  `~/.codex/local-marketplaces/<marketplace-name>/`.
- Not started: package scaffold, importer, publisher, embedded resources, and
  tests.

## Next steps

1. Complete the package-bootstrap tasks using pytest fixtures and Poetry script
   registration.
2. Implement validation and the development importer through focused TDD
   cycles.
3. Implement publishing, state-based modification checks, and runtime CLI
   behavior through focused TDD cycles.
4. Verify an installed wheel can access imported package resources.
