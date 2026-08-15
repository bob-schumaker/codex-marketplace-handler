# Technical Context

## Current stack

- Poetry package: `marketplace-installer` version `0.1.1`.
- Python `>=3.12,<4.0`; runtime dependencies `packaging==26.3` and
  `PyYAML==6.0.3`.
- Source package: `src/marketplace_installer/`.
- Console commands include `marketplace-installer`, `router-plugin-packager`,
  first-user, MCP customer/setup, runtime-lifecycle, and toolchain launcher
  flows.
- Copier source is rooted by `copier.yml` with `_subdirectory:
  copier-template`; rendered products require Python 3.12 and declare
  `marketplace-installer>=0.1.1,<0.2.0` through normal PyPI resolution.
- Pytest, Ruff, Rumdl, pre-commit, Copier, and `packaging` are development
  tooling.

## Verification expectations

- Run targeted tests first, then `poetry run pytest`; the current suite covers
  library APIs, v3 packager flows, Copier rendering, and wheel isolation.
- Build wheels with Poetry and verify isolated installations with a temporary
  virtual environment, scrubbed `PYTHONPATH`, and `pip check`.
- V3 manifests and package data must be present in the built wheel and validate
  from the installed package.
- Root and rendered Ruff targets are `py312`. The generated-payload lower bound
  is `0.1.1`; rendered metadata contains no custom source, credentials, path,
  or editable dependency.
