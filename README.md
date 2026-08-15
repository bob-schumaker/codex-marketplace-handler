# Marketplace Publisher

`marketplace-publisher` contains two related artifacts: the reusable
`marketplace-installer` library and a Copier baseline for payload-bearing
`marketplace-publisher` product repositories. The library deliberately
contains no marketplace catalog or plugin payload.

## Create an installer repository

From this repository, run:

```sh
poetry install
poetry run copier copy . /path/to/my-marketplace-publisher
```

Copier prompts for:

- `project_name`: the human-readable product name.
- `project_slug`: the lowercase product distribution and installed command
  name; use letters, digits, and hyphens.
- `package_name`: the Python import name, derived from the slug by default.

For example, a slug of `team-tools-publisher` produces the command
`team-tools-publisher` and the package name `team_tools_publisher`.
The generated product depends on `marketplace-installer >=0.1.0,<0.2.0` from
PyPI; publishing the library is separate release work.

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
user-modified files or when adopting an existing plugin directory that has no
publisher-state record. State is shared by installers for the same marketplace,
so each installer retains ownership records for plugins supplied by the others.
