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
- Repository-local memory-bank routing and core context files are present.

## In flight

- A release payload has not yet been selected or embedded.

## Remaining

- Select and import a real marketplace payload with the repository-only script.
- Build and verify the final release wheel installs that selected payload.

## Risks and follow-ups

- Keep embedded `source.path` values relative to each local marketplace root.
- Preserve the spec's staged-copy, state-manifest, and no-cross-marketplace
  guarantees during implementation.
- Do not select or commit a user's marketplace payload without an explicit
  target-name and plugin-selection decision.
- Keep the Copier template's source tree aligned with publisher changes; its
  rendered project has its own package name and console-script contract.
