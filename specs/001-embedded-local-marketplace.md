# Embedded Local Marketplace Publisher

## Goal

Build a Poetry-managed Python project that ships a Codex local marketplace in
the installed package and exposes a default executable that publishes that
marketplace into the user's personal Codex marketplace.

The distribution's canonical marketplace name is `marketplace-publisher`.
The executable must look for the personal marketplace with that exact name,
merge the embedded marketplace into it when it exists, and otherwise install
the embedded marketplace unchanged.

## Scope

- Use Poetry and a `src/` package layout.
- Distribute the marketplace JSON and every referenced local plugin directory
  as package data; it must work from an installed wheel, not only from a source
  checkout.
- Register a console script as the package's default entry point. The command
  name should be `marketplace-publisher` and call
  `marketplace_publisher.__main__:main`.
- Target Codex's personal marketplace location:
  `~/.agents/plugins/marketplace.json`, with local plugin files rooted at
  `~/.codex/plugins/`.
- Use `importlib.resources` to read the bundled marketplace and plugins so
  package-resource access is independent of the current working directory.

## Embedded package layout

```text
src/marketplace_publisher/
  __main__.py
  publisher.py
  resources/
    marketplace.json
    plugins/
      <plugin-name>/
        .codex-plugin/plugin.json
        ...
```

`resources/marketplace.json` is a valid Codex marketplace document whose
top-level `name` is `marketplace-publisher`. Its local plugin entries use
`./.codex/plugins/<plugin-name>` paths relative to the personal marketplace
root (`~`). The embedded resource must pass the same structural validation
imposed on an existing marketplace before any user files are changed.

## Publishing behavior

1. Load and validate the embedded marketplace. Reject malformed JSON, a
   mismatched marketplace name, duplicate plugin names, non-local sources, or
   local paths that are not safe `./.codex/plugins/...` relative paths.
2. Read `~/.agents/plugins/marketplace.json` if it exists.
   - If it is missing, create parent directories, copy all bundled plugin
     directories into `~/.codex/plugins/`, and write the embedded marketplace
     document unchanged.
   - If it exists but its top-level `name` differs, leave it untouched, report
     the conflict, and exit non-zero. A marketplace JSON file can represent
     only one named marketplace, so silently replacing or co-mingling another
     marketplace would be unsafe.
   - If it exists with the same name, validate it and merge it as specified
     below.
3. Copy each embedded plugin to the destination named by its `source.path`.
   The destination is `~/.codex/plugins/<plugin-name>` for the required
   embedded layout. Copy recursively, replacing only files supplied by that
   plugin; do not delete destination files that are absent from the embedded
   version.
4. Persist the resulting JSON atomically: serialize to a temporary file in the
   destination directory, flush and fsync it, then replace `marketplace.json`.
   Apply restrictive owner-only file permissions where the platform supports
   them. If copying or writing fails, retain the previous marketplace JSON and
   return a useful error.

## Merge rules

The installed marketplace is the base document. Preserve its unknown top-level
fields, `interface` fields, and plugin entries unless a rule below changes
them.

| Existing entry with the same plugin `name` | Result |
| --- | --- |
| No | Add the embedded entry verbatim, retaining embedded list order after existing entries. |
| Yes, semantically identical | Keep the existing entry; update its plugin files from the embedded copy. |
| Yes, different | Replace the entry with the embedded entry and report that it was updated. |

Semantic identity is equality of the JSON objects after key-order-independent
parsing. The merged `plugins` array must contain each plugin name once. The
top-level marketplace `name` remains `marketplace-publisher`; when the
embedded document supplies an `interface`, it replaces the existing
`interface` so the installed marketplace carries the package's current
identity and display metadata.

## Command contract

`marketplace-publisher` takes no required arguments. It prints a concise
summary identifying whether it installed or merged the marketplace, plus the
number of plugin entries added, updated, and left unchanged. It exits zero on
success and non-zero for invalid resources, invalid/conflicting installed
marketplaces, filesystem errors, or interrupted publication. It must never
modify any marketplace with a different name.

The command should be safe to run repeatedly: once embedded files and entries
are already current, subsequent runs leave the JSON semantically unchanged and
report a no-op merge.

## Error handling and safety

- Do not follow or write through symlinks in bundled plugin resources or at
  destination plugin roots; fail rather than publishing outside the expected
  locations.
- Reject plugin paths that are absolute or contain `..`.
- Never invoke code from embedded plugins while publishing.
- Do not depend on the `codex` executable or require a Codex restart. The
  command only lays down the standard personal marketplace files; the user can
  restart or refresh their Codex surface afterwards if necessary.

## Tests

Unit tests must use a temporary home directory and cover:

- fresh installation creates the marketplace JSON and all plugin files;
- same-name installation preserves unrelated metadata and plugins, appends new
  plugins, and replaces changed same-name entries;
- repeated publication is a no-op at the JSON level;
- a different-name marketplace, malformed JSON, invalid embedded resource, and
  unsafe plugin path fail without modifying the existing JSON;
- a simulated copy or atomic-write failure does not corrupt the existing JSON;
- packaged-resource access works after building and installing a wheel.

## Acceptance criteria

After `poetry install` and `poetry run marketplace-publisher`, a valid
`~/.agents/plugins/marketplace.json` named `marketplace-publisher` exists and
all plugins referenced by its bundled entries exist under `~/.codex/plugins/`.
Running the command again preserves unrelated same-marketplace content, updates
the package-owned entries and files, and leaves no duplicate plugin names.
