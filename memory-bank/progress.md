# Progress

## Working

- A complete implementation specification exists at
  `specs/001-embedded-local-marketplace.md`.
- Repository-local memory-bank routing and core context files are present.

## In flight

- No code implementation has begun.

## Remaining

- Create the Poetry package and embedded assets.
- Implement the publisher command and merge semantics.
- Add and run tests, including built-wheel resource verification.

## Risks and follow-ups

- Keep embedded `source.path` values aligned with Codex's personal marketplace
  root and plugin cache conventions.
- Preserve the spec's transactional and no-cross-marketplace guarantees during
  implementation.
