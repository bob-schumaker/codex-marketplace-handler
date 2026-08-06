# Progress

## Working

- A complete implementation specification exists at
  `specs/001-embedded-local-marketplace.md`.
- The specification has an implementation plan and TDD task list.
- Poetry configuration and Ruff/Rumdl pre-commit tooling are configured.
- The importer, publisher, state protection, CLI, and self-contained wheel
  integration test are implemented and passing.
- A tested Copier template creates custom-named installer repositories with no
  embedded marketplace payload, memory bank, or specifications.
- The real `bob-schumaker-codex-support` payload is embedded: 15 catalog
  entries, 15 plugin directories, and 639 regular plugin files.
- The actual built wheel installed and published all 15 embedded plugins into
  an isolated local marketplace root.
- Repository-local memory-bank routing and core context files are present.

## In flight

- No implementation work is in flight.

## Remaining

- Publish a release when desired.
- Refresh the embedded marketplace intentionally when its source changes.

## Risks and follow-ups

- Keep embedded `source.path` values relative to each local marketplace root.
- Preserve the spec's staged-copy, state-manifest, and no-cross-marketplace
  guarantees during implementation.
- Do not change the embedded marketplace or its plugin selection without an
  explicit release decision.
- Keep the Copier template's source tree aligned with publisher changes; its
  rendered project has its own package name and console-script contract.
