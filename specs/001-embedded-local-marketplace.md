# Embedded Local Marketplace Publisher

## Goal

Build a Poetry-managed Python project that packages an imported Codex personal
local marketplace and publishes it back to the user's personal Codex
marketplace.

The embedded marketplace's top-level `name` is the authoritative target name.
The publisher discovers that name from its packaged `marketplace.json`, merges
the package's contents into an installed marketplace with the same name, and
installs the marketplace unchanged when the personal marketplace file does not
exist.

## Scope

- Use Python 3.11, Poetry, and a `src/` package layout.
- Use anonymous package metadata and do not publish repository metadata while
  the repository remains private.
- Use Ruff for Python linting and formatting, Rumdl for Markdown linting and
  formatting, and pytest for tests.
- Distribute the marketplace JSON and every selected local plugin directory as
  package data; it must work from an installed wheel, not only from a source
  checkout.
- Register `marketplace-publisher` as the runtime console script, mapped to
  `marketplace_publisher.__main__:main`.
- Provide `scripts/import_marketplace.py` as a repository-only development
  script that imports a marketplace payload into package resources. Do not
  expose it as an installed console script.
- Support only Codex local marketplace roots at
  `~/.codex/local-marketplaces/<marketplace-name>/`. Each root contains
  `.agents/plugins/marketplace.json` and a `plugins/` directory.
- Use `importlib.resources` to read packaged resources so runtime behavior is
  independent of the current working directory.

## Self-contained distribution

The import command produces the package's complete installation payload:

- the filtered `marketplace.json`, including the target marketplace name and
  every selected plugin entry;
- every file in each selected plugin tree; and
- only root-relative `./plugins/...` source paths, never paths to the original
  local marketplace or any other user-specific absolute path.

At runtime, the publisher reads this payload exclusively from the installed
distribution with `importlib.resources`. It must not read the marketplace from
which the package was imported, invoke Codex, download plugin content, or rely
on a source checkout. A published wheel therefore contains all information and
files needed to install its targeted marketplace and plugins.

## Importing package data

The repository-local command has this interface:

```sh
poetry run python scripts/import_marketplace.py MARKETPLACE_NAME [PLUGIN_NAME ...]
```

The command is a repository-development tool. It reads the marketplace document
at
`~/.codex/local-marketplaces/MARKETPLACE_NAME/.agents/plugins/marketplace.json`
and requires its top-level `name` to equal `MARKETPLACE_NAME`.

After validation, it copies the filtered installation payload to these package
data locations:

| Local marketplace source | Package-data destination |
| --- | --- |
| `.agents/plugins/marketplace.json` | `src/marketplace_publisher/resources/marketplace.json` |
| `plugins/<plugin-name>/` | `src/marketplace_publisher/resources/plugins/<plugin-name>/` |

- With no plugin names, import every marketplace entry.
- With plugin names, retain only those entries in the embedded
  `marketplace.json` and copy only their directories.
- Fail without changing package resources if a requested plugin is absent,
  entries are duplicated or malformed, a source is not a safe local
  `./plugins/...` path, a plugin directory is missing, or an embedded
  resource replacement would traverse a symlink.
- Replace the existing embedded payload as one operation. The imported
  marketplace JSON and copied plugin directories must agree exactly.

The script exists only in the source repository and must not be included as a
wheel entry point or otherwise made executable from an installed package. Its
import-time source paths never become runtime dependencies: only the copied
package data is used by a published wheel.

The command is intentionally a development tool: it does not publish to Codex,
does not invoke plugin code, and does not mutate the source marketplace.

## Embedded package layout

```text
src/marketplace_publisher/
  __main__.py
  publisher.py
  importer.py
  resources/
    marketplace.json
    plugins/
      <plugin-name>/
        .codex-plugin/plugin.json
        ...
```

`resources/marketplace.json` is a valid Codex marketplace document. Its
top-level `name` determines the runtime target name. Its local plugin entries
use `./plugins/<plugin-name>` paths relative to the marketplace root. The
embedded resource must pass the same structural validation imposed on an
installed marketplace before any user files are changed.

## Publishing behavior

1. Load and validate the embedded marketplace. Reject malformed JSON, a missing
   or invalid marketplace name, duplicate plugin names, non-local sources, or
   paths that are not safe `./plugins/...` relative paths.
2. Read the target catalog at
   `~/.codex/local-marketplaces/<marketplace-name>/.agents/plugins/marketplace.json`
   if it exists.
   - If it is missing, create the marketplace root and parent directories, copy
     all bundled plugin directories into its `plugins/` directory, and write
     the embedded marketplace document unchanged.
   - If its top-level `name` differs from the embedded target name, leave it
     untouched, report the conflict, and exit non-zero. A personal marketplace
     JSON file represents one marketplace; support for other marketplace
     locations is out of scope.
   - If it has the same name, validate it and merge it as specified below.
3. Before changing an existing embedded plugin destination, check its publisher
   state manifest. If a previously published, package-owned file is missing or
   has a different SHA-256 digest, fail before mutation unless `--force` is
   supplied. If the destination exists but has no state record for that plugin,
   treat it as an unmanaged conflict and likewise require `--force`. Report
   unmanaged conflicts distinctly from modified package-owned files.
4. Copy each embedded plugin to the destination named by its `source.path`.
   The destination is
   `~/.codex/local-marketplaces/<marketplace-name>/plugins/<plugin-name>`.
   Copy recursively,
   overwriting package-owned files only when permitted by the modification
   check. Preserve destination files that are not supplied by the package.
5. On each successful publication, write publisher state under
   `~/.codex/local-marketplaces/<marketplace-name>/.marketplace-publisher/state.json`.
   It records the SHA-256 digests of package-owned plugin files after
   publication and is not treated as plugin content. State is marketplace-wide:
   retain valid records for plugins not supplied by the current package and
   replace records only for plugins that it supplies.
6. Persist the marketplace JSON atomically: serialize to a temporary file in
   the destination directory, flush and fsync it, then replace
   `marketplace.json`. Apply restrictive owner-only permissions where the
   platform supports them. If copying or writing fails, retain the previous
   marketplace JSON and return a useful error. Stage and validate all plugin
   source files before changing any destination files.

## Merge rules

The installed same-name marketplace is the base document. Preserve its unknown
top-level fields and unrelated plugin entries unless a rule below changes them.

| Existing entry with the same plugin `name` | Result |
| --- | --- |
| No | Add the embedded entry verbatim, retaining embedded list order after existing entries. |
| Yes, semantically identical | Keep the existing entry; update its plugin files if modification checks permit. |
| Yes, different | Replace the entry with the embedded entry and report that it was updated. |

Semantic identity is equality of parsed JSON objects with object-key order
ignored. The merged `plugins` array must contain each plugin name once. When
the embedded document supplies an `interface`, it replaces the installed
`interface` so the marketplace carries the packaged display metadata.

## Runtime command contract

```text
marketplace-publisher [--dry-run] [--force] [--json] [--verbose]
```

- `--dry-run` performs every read, validation, merge, and modification check
  but writes no marketplace, plugin, or publisher-state files.
- `--force` permits replacement of package-owned modified files and unmanaged
  destination plugin directories; it never deletes extra destination files.
- `--json` writes one JSON result object to standard output and no human status
  lines. It includes `status`, `marketplace`, `dry_run`, `plugins` (added,
  updated, unchanged, conflicts), and `errors`.
- `--verbose` adds diagnostic progress messages to standard error. It does not
  expose file contents or sensitive user data.

Without `--json`, print a concise summary identifying whether the marketplace
was installed, merged, or left unchanged, plus plugin counts. Exit zero on
success and non-zero for invalid resources, invalid or conflicting installed
marketplaces, modification conflicts, filesystem errors, or interrupted
publication. It must never modify a different-name marketplace.

The command is idempotent: once embedded files and entries are current,
subsequent runs leave marketplace JSON semantically unchanged and report a
no-op merge.

## Error handling and safety

- Do not follow or write through symlinks in bundled plugin resources or at
  destination plugin roots; fail rather than publishing outside expected
  locations.
- Reject plugin paths that are absolute or contain `..`.
- Never invoke code from embedded plugins while importing or publishing.
- Do not depend on the `codex` executable or require a Codex restart. The
  commands only read and write the standard personal marketplace files; the
  user can restart or refresh Codex afterwards if necessary.

## Tests and quality checks

Use pytest and temporary home directories. Tests must cover:

- importer behavior for all plugins, a selected plugin subset, absent requested
  plugins, malformed source data, and source marketplace-name mismatch;
- fresh publication creates marketplace JSON, state, and all plugin files;
- same-name publication preserves unrelated metadata and plugins, appends new
  plugins, and replaces changed same-name entries;
- repeated publication is a JSON-level no-op;
- a different-name marketplace, malformed JSON, invalid embedded resource, and
  unsafe plugin path fail without changing existing JSON;
- a changed package-owned file and an unmanaged destination both fail unless
  `--force`; errors distinguish those conflict types, and forced publication
  preserves unrelated destination files;
- independently generated packages targeting the same marketplace can publish
  different plugins in either order; their state records coexist, and rerunning
  either package does not report the other package's plugin as unmanaged;
- publishing one package updates only its plugin state records and preserves
  records for plugins owned by other packages;
- `--dry-run` makes no writes, and `--json` returns the documented result
  shape;
- a simulated copy or atomic-write failure does not corrupt the existing JSON;
- an installed wheel publishes correctly after the original source marketplace
  is absent, proving the embedded payload is self-contained.

Every behavior-changing implementation task follows RED, GREEN, and REFACTOR:

1. Add the smallest focused pytest test for one approved requirement and run it
   to confirm the expected failure before production-code changes.
2. Make the smallest change that passes the targeted test and rerun it.
3. Refactor only after the test is green, then rerun it and any nearby relevant
   checks.

Record the exact RED, GREEN, and refactor commands and observed outcomes in the
implementation handoff. If no repeatable automated check is feasible, record
the reason and use the strongest available alternative validation; this is an
explicit exception, not a completed TDD cycle.

The project quality commands are:

```sh
poetry run ruff format --check .
poetry run ruff check .
poetry run rumdl fmt --check .
poetry run rumdl check .
poetry run pytest
poetry build
```

## Acceptance criteria

Given a valid personal marketplace named `example`, when
`poetry run marketplace-publisher-import example` succeeds, then package
resources contain that marketplace document and every referenced plugin.

Given a packaged marketplace, when `poetry run marketplace-publisher` runs and
its target local marketplace root is absent, then a valid marketplace root with
the packaged target name, its plugin files, and a publisher state manifest are
created.

Given a same-name marketplace with unrelated content, when publication runs,
then unrelated content is preserved and package-owned entries are added or
updated without duplication.

Given a different-name catalog at the target marketplace root, when publication
runs, then it exits non-zero and makes no changes.

Given a package-owned plugin file changed after publication, when publication
runs without `--force`, then it exits non-zero and makes no changes; with
`--force`, package-owned files are restored and unrelated destination files are
preserved.

Given two packages for different plugins in the same marketplace, when they
publish successfully in either order, then the state manifest contains records
for both plugins. When either package runs again without file changes, then it
does not report the other package's plugin as unmanaged.

Given an existing plugin directory without a state record, when publication
runs without `--force`, then it reports an unmanaged-plugin conflict rather
than a modified package-owned-file conflict and makes no changes.

Given `--dry-run`, when any publication outcome is evaluated, then no files are
written. Given `--json`, the command emits one result object matching the
runtime command contract.

## Implementation artifacts

- [Technical plan](001-embedded-local-marketplace.plan.md)
- [TDD task list](001-embedded-local-marketplace.tasks.md)
