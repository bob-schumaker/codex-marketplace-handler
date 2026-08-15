# Memory Bank

This directory records durable context for future work on
`marketplace-publisher`.

## Core Files

- `projectbrief.md` — project goal, scope, and requirements
- `productContext.md` — problem and user outcome
- `activeContext.md` — current focus and next actions
- `systemPatterns.md` — intended architecture and merge rules
- `techContext.md` — tooling and runtime constraints
- `progress.md` — implemented state and remaining milestones

## Conventions

- Keep these notes concise, factual, and current; they are not a chat log.
- Treat `memory-bank/` as the project-local memory source; use Obsidian memory
  only for an explicitly requested Obsidian-vault task.
- Start resumed work with `activeContext.md` and `progress.md`.
- Refresh the smallest affected set after a meaningful implementation or
  product-direction change.
- Treat [specs/003-generated-plugin-copier-publisher.md](../specs/003-generated-plugin-copier-publisher.md)
  as the current generated-payload product contract. Specs 001 and its task
  artifacts are archived history; spec 002 records the completed two-artifact
  and retained direct-library baseline.
