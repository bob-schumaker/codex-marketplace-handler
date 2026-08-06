# Project Brief

## Goal

Create a Poetry-based Python package that contains a Codex local marketplace
and publishes it to the user's personal Codex location.

## Required behavior

- The distribution embeds `marketplace.json` and each referenced plugin.
- Its default executable finds the installed personal marketplace.
- If the existing marketplace has the same name, merge package-owned entries
  and plugin files into it.
- If it does not exist, install the embedded marketplace unchanged.
- Never modify a marketplace with a different name.

## Source specification

- `specs/001-embedded-local-marketplace.md`
