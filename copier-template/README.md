# Marketplace Installer Copier Template

Render a clean, custom-named marketplace-installer repository with Copier:

```sh
poetry run copier copy copier-template /path/to/new-installer
```

Copier asks for a human-readable project name and a lowercase distribution / CLI
slug. It derives a valid Python package name from that slug.

The generated repository contains the publisher implementation, its tests,
Poetry configuration, and the repository-only marketplace importer. It excludes
this repository's `memory-bank/` and `specs/` directories and contains no
marketplace payload. Add one later with the generated repository's
`scripts/import_marketplace.py` command.
