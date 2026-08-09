# Progress

## Working

- A complete implementation specification exists at
  `specs/001-embedded-local-marketplace.md`.
- The specification requires an installed `__main__.py` so
  `python -m marketplace_publisher` shares the console command's behavior and
  exit status.
- The specification has an implementation plan and TDD task list.
- Poetry configuration and Ruff/Rumdl pre-commit tooling are configured.
- The importer, publisher, state protection, CLI, and self-contained wheel
  integration test are implemented and passing.
- A tested Copier template creates custom-named installer repositories with no
  embedded marketplace payload, memory bank, or specifications.
- This source repository retains only empty resource-package markers; a final
  product repository supplies its own marketplace catalog and plugin trees.
- A representative 15-plugin payload was built, installed, and published into
  an isolated local marketplace root before its source-repo cleanup.
- Repository-local memory-bank routing and core context files are present.

## In flight

- No implementation work is in flight.

## Remaining

- Create a product repository with Copier or add a selected payload here when a
  release is explicitly desired.

## Risks and follow-ups

- Keep embedded `source.path` values relative to each local marketplace root.
- Preserve the spec's staged-copy, state-manifest, and no-cross-marketplace
  guarantees during implementation.
- Do not add a marketplace or plugin selection to this source repository
  without an explicit release decision.
- Keep the Copier template's source tree aligned with publisher changes; its
  rendered project has its own package name and console-script contract.
