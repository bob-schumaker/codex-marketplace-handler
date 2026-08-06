# AGENTS.md

Repository operating instructions for coding agents.

## Operating principles

- Work from evidence: read relevant files and run the applicable checks.
- Never invent paths, APIs, commit hashes, command results, or completion
  status.
- Make the smallest change that fully satisfies the request. Avoid speculative
  features, unrelated refactors, and broad reformatting.
- Follow established repository patterns unless the task explicitly calls for a
  change.
- Treat every changed line as reviewable: it must trace directly to the
  requested outcome.

## Project

- Purpose: package and publish an embedded Codex local marketplace safely.
- Stack: Python, Poetry, and a `src/` package layout.
- Key architecture: package resources are the source for the marketplace and
  plugins; publishing merges only a same-name personal marketplace.

## Build, test, and quality checks

- Use these commands after the Poetry project is scaffolded:

  ```sh
  poetry run ruff format --check .
  poetry run ruff check .
  poetry run rumdl fmt --check .
  poetry run rumdl check .
  poetry run pytest
  poetry build
  ```

- State concrete success criteria for non-trivial work before editing.
- Prefer the narrowest relevant test during iteration; run required broader
  checks before handoff.
- For a defect, reproduce it with a test or other verification when practical.
- Read command output and report what was actually verified, including checks
  not run or failures that remain.

## Test-driven development

- Use test-driven development for every behavior-changing implementation:
  RED, GREEN, then REFACTOR.
- Before changing production behavior, add or update the smallest focused test
  for one approved requirement and run it to confirm it fails for the expected
  reason.
- Make the smallest implementation change that turns that test green; refactor
  only after the targeted test passes, then rerun it.
- Keep a short test list when an implementation has multiple scenarios or edge
  cases, and complete one behavior per cycle.
- Record the exact RED, GREEN, and refactor commands and observed outcomes in
  the handoff.
- An exception is allowed only when no repeatable automated check is feasible.
  State why and run the strongest available alternative validation; never claim
  a TDD cycle occurred when it did not.

## Architecture and boundaries

- Treat `specs/001-embedded-local-marketplace.md` as the current implementation
  contract.
- Preserve unknown same-marketplace metadata and unrelated plugin entries.
- Never modify a local marketplace outside
  `~/.codex/local-marketplaces/<marketplace-name>/`, or one whose name differs
  from the packaged marketplace's target name.
- Validate marketplace data and plugin paths before publishing; reject
  symlinks and paths that escape the expected plugin root.
- Do not execute embedded plugin code during publication.

## Security and data handling

- Never commit secrets, credentials, tokens, or private keys.
- Do not log or expose sensitive user filesystem data.
- Keep marketplace updates atomic and report failures without claiming a
  successful publication.

## Clarification and decision-making

- Proceed when ambiguity is resolvable from repository context or the change
  is trivial and reversible.
- Ask before proceeding when two plausible interpretations materially change
  the outcome, when a load-bearing resource is affected, or when required
  access is missing.
- Surface material assumptions and tradeoffs instead of silently choosing a
  consequential approach.

## Git and delivery

- Keep commits small and single-purpose.
- Do not overwrite, discard, or reformat unrelated user changes.
- Include a concise handoff: outcome, files changed, and verification
  performed.

## Directory-specific instructions

- Check for nested `AGENTS.md` files before editing a subdirectory.
- More-specific instructions apply within their directory subtree.
- Put reusable, task-specific workflows in `SKILL.md`; keep this file limited
  to repository-wide operating context.

<!-- BEGIN MANAGED AGENTS.LOCAL INSTRUCTION -->
Also read `AGENTS.local.md` before every task when it exists; it contains
repository-local instructions that supplement this file.
<!-- END MANAGED AGENTS.LOCAL INSTRUCTION -->
