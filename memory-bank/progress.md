# Progress

## Working

- `marketplace-installer` `0.1.1` is a Poetry-built v3 router-plugin installer
  library with canonical assembly, portable payload validation/staging, and
  embedded generated-marketplace publication.
- The complete v3 regression suite is maintained in this repository: core
  packager, layer-3 marketplace publication, MCP customer flow, setup, runtime
  lifecycle, closure, Copier, and wheel tests.
- `copier-template/` renders a payload-bearing publisher that builds a v3
  payload through `scripts/build_marketplace.py` and consumes the library as a
  normal bounded dependency.
- Specs 002 and 003 are committed implementation contracts for the completed
  two-artifact layout and generated-payload workflow; 001 is archived history.

## In flight

- No code migration is in flight. The generated-payload implementation is
  complete and awaiting a separately authorized release/adoption decision.

## Remaining

1. Publish `marketplace-installer` `0.1.1` before downstream product adoption.
2. Perform downstream adoption and any future corporate package-source work
   under separate authorization.
3. Maintain direct, rendered-product, and two-wheel coverage for shared
   contract changes.

## Risks and follow-ups

- Treat the v3 installer as a shared contract: this repository must own and
  validate compatibility changes before downstream consumers adopt them.
- Keep the direct operational path and Copier path on one canonical payload;
  do not introduce a template-specific marketplace representation.
- Preserve isolated-wheel tests and avoid path/editable dependencies in
  rendered product metadata.
