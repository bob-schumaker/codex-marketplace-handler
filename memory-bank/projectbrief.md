# Project Brief

## Goal

Create a Poetry-based Python package that imports, embeds, and publishes a
Codex local marketplace.

## Required behavior

- The development importer selects a named local marketplace and optionally a
  plugin subset, then embeds its catalog and plugin files as package data.
- The runtime executable derives the target name from embedded data and
  publishes to `~/.codex/local-marketplaces/<marketplace-name>/`.
- If the target catalog exists with the same name, merge package-owned entries
  and plugin files into it; otherwise install the embedded marketplace.
- Detect modified or unmanaged package-owned plugin files and require
  `--force` before overwriting them.
- Support `--dry-run`, `--json`, and `--verbose`; never modify a marketplace
  outside the named local-marketplace root.

## Source specification

- `specs/001-embedded-local-marketplace.md`
