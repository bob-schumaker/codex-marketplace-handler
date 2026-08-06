# Marketplace Publisher

`marketplace-publisher` is a source repository for generating a custom Codex
local-marketplace installer. It intentionally contains no marketplace catalog
or plugin payload. Use the Copier template to create a product repository,
then add the marketplace that product will publish.

## Create an installer repository

From this repository, run:

```sh
poetry install
poetry run copier copy copier-template /path/to/my-marketplace-installer
```

Copier prompts for:

- `project_name`: the human-readable project name.
- `project_slug`: the lowercase package distribution and installed command
  name; use letters, digits, and hyphens.
- `package_name`: the Python import name, derived from the slug by default.

For example, a slug of `team-tools-installer` produces the command
`team-tools-installer` and the package name `team_tools_installer`.

## Add the marketplace payload

Change to the generated repository. Import every catalog-listed plugin from a
local Codex marketplace:

```sh
poetry run python scripts/import_marketplace.py MARKETPLACE_NAME
```

Or import only named plugins:

```sh
poetry run python scripts/import_marketplace.py MARKETPLACE_NAME PLUGIN_NAME [...]
```

The importer reads from `~/.codex/local-marketplaces/MARKETPLACE_NAME/` and
copies the marketplace catalog and selected plugin trees into package data. It
is repository-local: it is not installed as a public command.

## Build and use the installer

In the generated repository, verify and build the payload-bearing package:

```sh
poetry run pytest
poetry build
```

Install the resulting wheel in the intended Python environment, then run its
generated command:

```sh
PROJECT_SLUG [--dry-run] [--force] [--json] [--verbose]
```

The installed command derives the marketplace name from the embedded catalog.
It installs the embedded marketplace if absent, or safely merges it into the
same-name marketplace already under `~/.codex/local-marketplaces/`.

`--dry-run` makes no changes, `--json` emits machine-readable status, and
`--force` permits replacement when an existing managed plugin has
user-modified files.
