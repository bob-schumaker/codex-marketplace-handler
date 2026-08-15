# Progress

## Working

- `marketplace-installer` is a Poetry-built v3 router-plugin installer library
  with package and wheel validation.
- The complete v3 regression suite is maintained in this repository: core
  packager, layer-3 marketplace publication, MCP customer flow, setup, runtime
  lifecycle, closure, Copier, and wheel tests.
- `copier-template/` renders a payload-bearing publisher product that consumes
  the library as a normal dependency.
- Specs 002 and 003 are committed implementation contracts for the two-artifact
  layout and the next generated-payload migration.

## In flight

- No code migration is in flight. Spec 003 is the next approved implementation
  slice.

## Remaining

1. Implement spec 003's canonical assembly, portable validation, and embedded
   publication library APIs.
2. Replace the template's legacy import script and payload layout.
3. Establish the first released library version that safely enables generated
   publisher products.

## Risks and follow-ups

- Treat the v3 installer as a shared contract: this repository must own and
  validate compatibility changes before downstream consumers adopt them.
- Keep the direct operational path and Copier path on one canonical payload;
  do not introduce a template-specific marketplace representation.
- Preserve isolated-wheel tests and avoid path/editable dependencies in
  rendered product metadata.
