# Project Brief

## Goal

Maintain `marketplace-installer` as the reusable Poetry library for v3 router
plugin packaging and local-marketplace assembly, while this repository's Copier
template renders a payload-bearing `marketplace-publisher` consumer.

## Required behavior

- The library packages, validates, and assembles router plugins into local
  marketplace trees; it retains direct legacy publication APIs and provides
  portable generated-payload assembly, staging, and publication APIs.
- The library wheel contains the complete v3 packager closure, integrity
  manifests, and runtime dependencies; its regression suite is the source of
  truth for that installer contract.
- A rendered product is self-contained at runtime and publishes only its
  embedded payload, with safe conflict handling and `--dry-run`, `--force`,
  `--json`, and `--verbose` behavior.
- The Copier template builds one canonical v3 marketplace tree from a consumer
  project's plugin inputs, stages that unchanged tree as package resources, and
  publishes the installed payload without requiring a source checkout.

## Source specifications

- `specs/001-embedded-local-marketplace.md` — archived v1 context only.
- `specs/002-marketplace-installer-library-and-baseline.md` — completed
  library/Copier separation and retained direct-library baseline.
- `specs/003-generated-plugin-copier-publisher.md` — current generated v3
  payload contract and implementation record.
