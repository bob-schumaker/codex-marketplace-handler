# System Patterns

## Package resources

Load bundled marketplace files through `importlib.resources`, never relative
to the caller's working directory. A product payload consists of the
marketplace JSON and complete selected plugin directories, contains no absolute
source-marketplace paths, and remains usable after distribution as a wheel.

This source repository intentionally carries only empty resource-package
markers. The repository-only importer is the supported way to add a selected
marketplace payload for a product build; only catalog entries define payload
ownership.

## Marketplace identity

Each local marketplace is rooted at
`~/.codex/local-marketplaces/<marketplace-name>/`. Its catalog is
`.agents/plugins/marketplace.json`, and local plugin entries use
`./plugins/<plugin-name>` relative to that root.

## Merge contract

- Treat the installed same-name marketplace as the base document.
- Preserve unknown top-level metadata and unrelated plugin entries.
- Add absent embedded plugins, leave identical entries, and replace changed
  entries with the embedded versions.
- Replace embedded `interface` metadata when it is supplied.
- Maintain one entry per plugin name and update only package-supplied plugin
  files without deleting extra destination files.

## Safety

Validate JSON and safe local paths before mutation; reject symlinks and paths
that escape the expected plugin root. Write marketplace JSON atomically and do
not run plugin code while publishing.

## Copier bootstrap

`copier-template/` is a self-contained source template. It renders a named
distribution, console script, and Python package while retaining the
repository-only importer and empty resource-package markers. It intentionally
does not render `memory-bank/`, `specs/`, or any marketplace payload.

## Payload formatting boundary

Imported plugin trees are copied as-is. Ruff and Rumdl exclude the package
resource tree so project quality checks do not rewrite bundled plugin source or
documentation. The Copier template renders matching exclusions for future
payload-bearing installers.
