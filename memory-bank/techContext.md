# Technical Context

## Planned stack

- Python project managed with Poetry.
- `src/` layout with package import name `marketplace_publisher`.
- Console command: `marketplace-publisher`, mapped to
  `marketplace_publisher.__main__:main`.
- Standard-library resource access via `importlib.resources`.

## Verification expectations

Use temporary home directories for publishing tests. Cover fresh install,
same-name merge, idempotency, validation failures, safe failure behavior, and
wheel-installed resource access.
