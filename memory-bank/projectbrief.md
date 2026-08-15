# Project Brief

## Goal

Maintain `marketplace-installer` as the reusable Poetry library for v3 router
plugin packaging and local-marketplace assembly, while this repository's Copier
template renders a payload-bearing `marketplace-publisher` consumer.

## Required behavior

- The library packages, validates, and assembles router plugins into local
  marketplace trees; it also retains the existing embedded-marketplace API for
  current Copier products.
- The library wheel contains the complete v3 packager closure, integrity
  manifests, and runtime dependencies; its regression suite is the source of
  truth for that installer contract.
- A rendered product is self-contained at runtime and publishes only its
  embedded payload, with safe conflict handling and `--dry-run`, `--force`,
  `--json`, and `--verbose` behavior.
- The next template model builds one canonical v3 marketplace tree from a
  consumer project's plugin inputs, then stages that unchanged tree as package
  resources. It does not first require an installed or released marketplace.

## Source specifications

- `specs/001-embedded-local-marketplace.md` — legacy embedded-marketplace
  behavior retained until its replacement is complete.
- `specs/002-marketplace-installer-library-and-baseline.md` — completed
  library/Copier separation.
- `specs/003-generated-plugin-copier-publisher.md` — approved next migration
  to generated v3 payloads.
