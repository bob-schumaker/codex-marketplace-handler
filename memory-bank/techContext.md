# Technical Context

## Planned stack

- Python project managed with Poetry.
- Python 3.11.
- `src/` layout with package import name `marketplace_publisher`.
- Console command: `marketplace-publisher`, mapped to
  `marketplace_publisher.__main__:main`.
- Repository-only importer command:
  `poetry run python scripts/import_marketplace.py`.
- Standard-library resource access via `importlib.resources`.
- Ruff formats and lints Python; Rumdl formats and lints Markdown; pytest is
  the test runner; pre-commit runs Ruff and Rumdl hooks.
- Copier is a development dependency. `copier-template/copier.yml` derives a
  Python package name from a custom project slug and renders the installer.
- `rumdl.toml` and Ruff's `extend-exclude` omit package resources from project
  formatting checks so a product's imported third-party plugin trees remain
  byte-preserved.

## Verification expectations

Use temporary home directories for publishing tests. Cover fresh install,
same-name merge, idempotency, validation failures, safe failure behavior, and
wheel-installed resource access without the original imported marketplace.
Use RED, GREEN, and REFACTOR for every behavior-changing implementation task,
with documented exceptions only when no repeatable automated check is feasible.

For a release, build the payload-bearing wheel after importing its selected
marketplace, install it with `pip --no-deps` into a temporary virtual
environment, and run `marketplace-publisher --json` with an isolated `HOME`.
