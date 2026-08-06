# Implementation Plan: Embedded Local Marketplace Publisher

## Purpose

Implement the behavior defined in
`001-embedded-local-marketplace.md` as a Python 3.11 Poetry package. This
plan does not add a Codex integration or any marketplace payload; the importer
provides the payload from the user's personal marketplace.

## Package structure

```text
src/marketplace_publisher/
  __init__.py
  __main__.py
  cli.py
  importer.py
  publisher.py
  models.py
  paths.py
  validation.py
  filesystem.py
  resources/
    __init__.py
    marketplace.json
    plugins/
tests/
  fixtures/
  test_validation.py
  test_importer.py
  test_publisher.py
  test_cli.py
  test_packaging.py
```

Add runtime and import console scripts in `[project.scripts]`. Configure Poetry
to include every file below `src/marketplace_publisher/resources/` in wheels and
sdists, including `.codex-plugin/plugin.json` files.

## Components and responsibilities

| Component | Responsibility |
| --- | --- |
| `models.py` | Immutable typed values for marketplace data, plugin entries, publication results, and publisher state. |
| `paths.py` | Resolve marketplace-root paths from an injected home directory and target name; expose the catalog, plugin root, and state path. |
| `validation.py` | Parse JSON and validate marketplace names, unique plugin names, local source types, and safe plugin paths. |
| `filesystem.py` | Safe recursive file enumeration/copying, SHA-256 manifests, symlink rejection, temporary staging, and atomic JSON writes. |
| `importer.py` | Select and validate a personal marketplace payload, stage the filtered resources, then replace package resources. |
| `publisher.py` | Load package resources, evaluate conflicts, merge entries, copy allowed plugin files, and persist JSON/state. |
| `cli.py` | Parse arguments, select human or JSON reporting, and map expected domain errors to non-zero exits. |
| `__main__.py` | Delegate to the runtime CLI. |

The importer and publisher use the same parser and path validator. Runtime
resource reads use `importlib.resources.files`; development imports use regular
filesystem paths only.

## Data and file contracts

### Marketplace model

Keep the decoded marketplace document as a `dict[str, object]` to preserve
unknown fields. Extract a validated plugin index keyed by plugin `name` for
merge and duplicate detection. Semantic equality compares parsed JSON values,
not serialized formatting.

Only accept local entries whose `source` object declares `source: local` and
whose `path` is exactly under `./plugins/`. Resolve the suffix against the
marketplace root and verify it remains below the expected plugin root. Reject
absolute paths, `..`, empty path segments, duplicate names, and symlinked
plugin roots.

### Publisher state

Persist a JSON state document at:

```text
~/.codex/local-marketplaces/<marketplace-name>/.marketplace-publisher/state.json
```

It contains the target marketplace name and, for each package-owned plugin, a
mapping of relative file paths to SHA-256 digests. It records only files copied
by the publisher. Extra files in a destination plugin directory are neither
tracked nor deleted.

For an existing destination, compare every tracked file to state before any
write. A missing state file means the destination is unmanaged. Any mismatch or
unmanaged destination is a conflict unless `--force` is present.

### Result model

Build one result model for both output modes. It includes `status`,
`marketplace`, `dry_run`, and plugin lists named `added`, `updated`,
`unchanged`, and `conflicts`, plus an `errors` list. JSON output serializes this
model as exactly one object on standard output; verbose diagnostics use standard
error.

## Execution flows

### Import

1. Resolve the named marketplace-root catalog and load it without mutation.
2. Validate that its name equals the requested name and build the plugin index.
3. Select all entries or the requested subset; reject unknown names.
4. Validate and stage the selected plugin trees and a filtered marketplace JSON
   in a temporary sibling directory under package resources.
5. Replace the package resource payload only after staging completes. Leave the
   existing payload unchanged on validation or staging failure.

### Publish

1. Load and validate the embedded marketplace using `importlib.resources`.
2. Resolve the target marketplace root from the effective home directory and
   embedded name.
3. Load the installed catalog when present; fail on a different name and
   validate a same-name document.
4. Build the merged marketplace document and a planned plugin action list.
5. Hash and stage every embedded plugin. Before mutation, load state and check
   tracked destination files and unmanaged destinations.
6. In dry-run mode, return the plan without creating directories or files.
7. Copy permitted plugin files, preserve unowned files, write replacement state,
   and atomically replace marketplace JSON last.

The state file is written only after all plugin copies succeed. If a copy fails,
the old marketplace JSON and state remain intact; report that some plugin files
may need manual recovery only if the filesystem reports an unrecoverable
mid-copy failure.

## Error and CLI design

Use small typed exceptions for validation, marketplace-name conflict,
modification conflict, and filesystem failure. The CLI catches only those
expected exceptions, writes a concise message or JSON error result, and exits
non-zero. Let unexpected exceptions retain a traceback during development.

Use `argparse` and four runtime flags: `--dry-run`, `--force`, `--json`, and
`--verbose`. The importer accepts positional marketplace and plugin names and
does not share runtime publishing flags.

## Test strategy

Use pytest fixtures that create a temporary home directory and marketplace
trees. Inject paths and resources instead of patching global home-directory
state. Use a helper to create valid plugin manifests and marketplace documents.

Tests are grouped by behavior:

- parser and path validation;
- importer selection and staged replacement;
- publisher fresh install, merge, conflict, force, and dry-run behavior;
- CLI human and JSON result behavior;
- wheel installation and resource access in an isolated virtual environment.

Every behavior task follows the repository RED, GREEN, REFACTOR policy. The
wheel test is the final integration gate because it verifies package-data
configuration, console scripts, and `importlib.resources` together.

## Validation sequence

During implementation, run the smallest affected pytest target for each TDD
cycle. Before handoff, run:

```sh
poetry run ruff format --check .
poetry run ruff check .
poetry run rumdl fmt --check .
poetry run rumdl check .
poetry run pytest
poetry build
```

Run `pre-commit run --all-files` after the tooling is installed. Record exact
RED, GREEN, refactor, and final-validation output in the implementation
handoff.

## Risks and boundaries

- Do not add support for repository, remote, or multiple personal marketplaces.
- Do not run plugin code or call the `codex` executable.
- Do not infer ownership from file names; state manifests are the ownership
  record.
- Do not claim complete filesystem rollback after an operating-system copy
  failure. Preserve JSON and state, stage first, and report the residual risk.
- Do not select or commit a marketplace payload until the user supplies one
  through the importer workflow.
