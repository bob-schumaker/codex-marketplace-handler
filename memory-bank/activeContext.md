# Active Context

## Current focus

Prepare the Copier template to build and embed a canonical v3 generated
marketplace payload, as specified by `specs/003-generated-plugin-copier-publisher.md`.

## Current status

- Done: `marketplace-installer` contains the v3 router-plugin packager closure,
  generated-plugin marketplace publisher, integrity manifests, runtime
  dependencies, console commands, and migrated regression suites.
- Done: the root library wheel and existing Copier product wheel have isolated
  integration coverage.
- Done: specs 002 and 003 define library/template separation and the approved
  canonical generated-payload direction.
- Current template behavior remains legacy: its repository-only importer copies
  an existing local marketplace into `resources/marketplace.json`.

## Next steps

1. Implement the public v3 canonical-assembly, embedded-publication, staging,
   and portable-validation seams required by spec 003; version the library and
   record the generated-payload minimum dependency.
2. Add library-first assembly/staging parity and failure tests.
3. Migrate the Copier template, fixtures, rendered tests, and wheel test from
   legacy importer payloads to generated canonical payloads.
4. Re-run the complete suite and build/wheel isolation checks before adopting
   the template in another project.
