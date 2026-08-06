# System Patterns

## Package resources

Load bundled marketplace files through `importlib.resources`, never relative
to the caller's working directory. Package resources include the marketplace
JSON and complete selected plugin directories. This embedded installation
payload is the sole runtime source; it contains no absolute source-marketplace
paths and remains usable after distribution as a wheel.

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
