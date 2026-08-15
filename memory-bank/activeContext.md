# Active Context

## Current focus

Maintain the implemented `marketplace-installer` library and its
`marketplace-publisher` Copier product as one versioned contract.

## Current status

- Done: `marketplace-installer` version `0.1.1` contains the v3 router-plugin
  packager closure, canonical assembly, portable validation, package-resource
  staging, embedded publication, integrity manifests, and regression suites.
- Done: the Copier template replaces the legacy importer with
  `scripts/build_marketplace.py`; it builds a generated plugin from explicit
  repository inputs and stages the canonical payload in package resources.
- Done: rendered CLI, Copier migration, and offline two-wheel tests cover the
  v3 payload contract. The dedicated first-user-flow regression suite imports
  the library directly, so the library now owns that behavioral coverage.
- Done: specs 001–003 now state their historical/current authority boundaries.

## Next steps

1. Publish `marketplace-installer` `0.1.1` to the approved PyPI release path
   before downstream Copier products adopt the generated-payload dependency.
2. Authorize and perform downstream adoption separately; generated products
   must use the bounded `>=0.1.1,<0.2.0` dependency.
3. Preserve direct and Copier integration coverage when changing the shared
   installer contract.
