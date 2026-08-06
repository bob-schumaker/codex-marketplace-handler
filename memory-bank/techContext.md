# Technical Context

## Planned stack

- Python project managed with Poetry.
- Python 3.11.
- `src/` layout with package import name `marketplace_publisher`.
- Console command: `marketplace-publisher`, mapped to
  `marketplace_publisher.__main__:main`.
- Development importer command: `marketplace-publisher-import`.
- Standard-library resource access via `importlib.resources`.
- Ruff formats and lints Python; Rumdl formats and lints Markdown; pytest is
  the test runner; pre-commit runs Ruff and Rumdl hooks.

## Verification expectations

Use temporary home directories for publishing tests. Cover fresh install,
same-name merge, idempotency, validation failures, safe failure behavior, and
wheel-installed resource access. Use RED, GREEN, and REFACTOR for every
behavior-changing implementation task, with documented exceptions only when no
repeatable automated check is feasible.
