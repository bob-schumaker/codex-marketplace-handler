# Technical Context

## Current stack

- Poetry package: `marketplace-installer` version `0.1.0`.
- Python `>=3.12,<4.0`; runtime dependencies `packaging==26.3` and
  `PyYAML==6.0.3`.
- Source package: `src/marketplace_installer/`.
- Console commands include `marketplace-installer`, `router-plugin-packager`,
  first-user, MCP customer/setup, runtime-lifecycle, and toolchain launcher
  flows.
- Copier source is rooted by `copier.yml` with `_subdirectory:
  copier-template`; rendered products currently declare a normal PyPI
  `marketplace-installer` dependency.
- Pytest, Ruff, Rumdl, pre-commit, Copier, and `packaging` are development
  tooling.

## Verification expectations

- Run targeted tests first, then `poetry run pytest`; the current suite covers
  library APIs, v3 packager flows, Copier rendering, and wheel isolation.
- Build wheels with Poetry and verify isolated installations with a temporary
  virtual environment, scrubbed `PYTHONPATH`, and `pip check`.
- V3 manifests and package data must be present in the built wheel and validate
  from the installed package.
- The root package already requires Python 3.12, but its current Ruff target is
  `py311`. Spec 003 raises both root and rendered Ruff targets to `py312`, uses
  an exact future library lower bound, and keeps path/editable dependencies out
  of rendered metadata.
