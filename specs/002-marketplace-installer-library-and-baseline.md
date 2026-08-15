# Marketplace Installer Library and Copier Template

## Goal

Restructure this repository into two independently built artifacts while it
retains the `marketplace-publisher` repository name:

- `marketplace-installer` is the canonical, reusable Python distribution for
  packaging Codex router plugins and safely installing an embedded Codex local
  marketplace.
- `marketplace-publisher` is the payload-bearing product generated from this
  repository's Copier template. It embeds a marketplace payload and consumes
  `marketplace-installer` as a normal dependency.

This specification replaces the packaging and template-structure portions of
`001-embedded-local-marketplace.md`. The marketplace import, validation,
publication, merge, state, safety, and runtime CLI behavior defined there
remain required unless this specification explicitly changes them.

## Scope

All changes are confined to this repository.

In scope:

- create and package the `marketplace-installer` library;
- make `copier-template/` the sole Copier-rendered `marketplace-publisher` product;
- move the current template content into that Copier template;
- define the public seams between a payload product and the library;
- update repository tests, Copier metadata, documentation, and provenance
  checks for the two-artifact model.

Out of scope:

- changes to `ai-environment-roschuma`, its installers, payloads, cohorts,
  generated output, or release artifacts;
- hand-editing existing generated installer repositories;
- publishing to PyPI, configuring package-index publishing, or adding release
  automation;
- installing into a real Codex home;
- custom package sources, credentials, local/editable dependencies, or a
  rendered lockfile in the Copier template;
- changes to the Codex marketplace schema.

## Repository layout

The repository must have this logical layout:

```text
marketplace-publisher/
  copier.yml
  copier-template/
    src/{{ package_name }}/
    scripts/
    tests/
    pyproject.toml
    ...
  src/marketplace_installer/
  tests/
  specs/
  memory-bank/
```

`copier.yml` is at the repository root and declares `_subdirectory: copier-template`.
`copier-template/` is the only Copier rendering tree. The legacy
`copier-template/template/` tree must not remain as a second rendering path.
Root-level `specs/` and `memory-bank/` are repository control material and are
not part of rendered products.

## Artifact contracts

### `marketplace-installer`

The top-level Poetry project builds distribution `marketplace-installer` with
import package `marketplace_installer`. Its initial package version is `0.1.0`
and it follows semantic versioning. Publishing that version is separate release
work.

It owns all generic local-marketplace mechanics:

- marketplace parsing and validation;
- safe plugin-path resolution, symlink rejection, staging, copying, hashing,
  and atomic catalog writing;
- same-name catalog merge behavior and different-name conflict handling;
- publisher-state persistence and ownership/modification conflict behavior;
- publication result and expected error models; and
- importer validation and resource-payload replacement logic; and
- transactional publication and validation of generated router-plugin trees
  into local marketplaces.

It also owns the complete v3 router-plugin packager closure: the router
packager, first-user and MCP flows, setup flow, runtime lifecycle, launcher,
their support modules, and the integrity manifest that declares that closure.
Those operations are exposed through the package modules and the
`marketplace-installer`, `router-plugin-packager`,
`router-plugin-first-user-flow`, `mcp-plugin-packaging-customer-flow`,
`router-plugin-packager-setup`, `plugin-runtime-lifecycle`, and
`codex-packaging-toolchain` console commands. The package requires Python
3.12 or newer plus the manifest-pinned `packaging` and `PyYAML` runtime
dependencies.

The library distribution must contain no marketplace payload, product
`resources/` tree, payload-specific `__main__.py`, product console-script
entry point, or `marketplace_publisher` package. The v3 package console
commands above are library entry points, not product entry points.

The established `publish_marketplace(resource_root, home, ...)` behavior,
publisher-state format, and documented error behavior remain compatible.
Version `0.1.0` retains the existing shared state location
`<home>/.codex/local-marketplaces/<name>/.marketplace-publisher/state.json`
and its JSON format. There is no state-directory rename or migration in this
work; regression tests seed that legacy state and preserve its modified-file
conflict behavior through the extracted library.

### Public payload seams

The library must expose a narrow public publishing API through which a payload
product identifies its resources. An API equivalent to the following is
required:

```python
publish_embedded_marketplace(
    resource_package: str,
    *,
    home: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> PublishResult
```

It must support resources from both an unpacked package and an installed wheel.
The library must not assume a resource package named
`marketplace_publisher.resources`.

The importer must likewise expose a public seam equivalent to:

```python
import_marketplace(
    marketplace_root: Path,
    destination_resources: Path,
    *,
    selected_plugins: Sequence[str] | None = None,
    expected_name: str | None = None,
) -> Marketplace
```

The canonical direct operation is:

```python
publish_marketplace(
    resource_root: Path,
    home: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> PublishResult
```

The public result and expected error types, public imports, and function
signatures are compatibility surfaces. Payload projects must not import
library-private models or validation modules.

The canonical public import surface is the `marketplace_installer` package root:

| Category | Required exports |
| --- | --- |
| Operations | `publish_marketplace`, `publish_embedded_marketplace`, `import_marketplace` |
| Models/results | `Marketplace`, `PluginEntry`, `PublishResult` |
| Errors | `PublisherError`, `MarketplaceConflictError`, `ModificationConflictError`, `UnmanagedPluginConflictError`, `ImportError` |

Library-wheel consumer tests must import these symbols from the package root.
The Copier template may import only these public paths.
`PublisherError` and its three listed subclasses are the complete supported
publish-error surface; `ImportError` is the complete supported import-error
surface. `MarketplaceValidationError`, `PathSafetyError`, `MarketplacePaths`,
and parsing/path-validation helpers are library-private in version `0.1.0`.

### `marketplace-publisher` Copier template

The Copier template renders the payload-bearing `marketplace-publisher`
project. Its default distribution name is `marketplace-publisher`; its normal
Python package name is `marketplace_publisher`. Copier validation must reject a
rendered distribution or package-name collision with the library. Set
`project_slug` and `package_name` defaults to these values. Reject a slug whose
PEP 503 normalized form (lowercase with `[-_.]+` collapsed to `-`) equals the
library distribution name, and reject `marketplace_installer` as a package name.
Render tests cover defaults, a valid custom name, and rejected
`marketplace-installer`, `marketplace--installer`, and
`marketplace_installer` collisions.

The Copier template owns only product-specific concerns:

- embedded `marketplace.json` and plugin resources;
- the product console script and `__main__` entry point;
- resource-package selection for publication;
- runtime CLI parsing and presentation; and
- the repository-only `scripts/import_marketplace.py` wrapper and its resource
  directory lookup.

The Copier template preserves the existing `--dry-run`, `--force`, `--json`, and
`--verbose` flags; exit statuses; JSON success/error schema; and stdout/stderr
routing. It may call only public `marketplace_installer` APIs for importer and
publisher behavior. It must not carry copied shared installer implementation.

The Copier template retains a thin `publisher.py` adapter. It derives its resource
package as `f"{__package__}.resources"`, exposes the existing zero-argument
`publish_embedded_marketplace(home=None, *, dry_run=False, force=False)` shape,
and forwards to the public library API. The product CLI imports this adapter.
No validation, filesystem, merge, state, or error implementation may remain in
the adapter. A non-default rendered `package_name` test proves that it does not
hard-code `marketplace_publisher.resources`.

For version `0.1.0`, `publisher.py` and `importer.py` remain thin deprecated
compatibility adapters for the current product-module import paths. They
re-export their current public operations, models/results, and error types from
the canonical `marketplace_installer` surface; only the embedded-publisher
adapter and repository resource lookup may add product-specific behavior. An
import-only compatibility test covers these legacy paths.

The Copier template declares `marketplace-installer >=0.1.0,<0.2.0` through default
PyPI resolution. Its rendered `pyproject.toml` declares that exact requirement
in PEP 621 `[project].dependencies`; `[tool.poetry]` contains only
Poetry-specific package and include configuration. The Copier template
contains no custom source, credentials, local path, editable dependency, or
rendered lockfile.

## Copier identity and provenance

A rendered product's template identity consists only of:

- the resolved full VCS commit SHA for this template repository (with a
  requested tag or ref recorded only as supplemental context);
- Copier's `_subdirectory: copier-template`; and
- the declared `marketplace-installer` version range.

The product must record this provenance. Do not introduce a separate template
version. The repository's Copier version, template revision, answers, and a
known rendered fixture are frozen as test provenance before migration work
relies on them.

Use Copier's VCS rendering and generated `.copier-answers.yml` as the
provenance record. Reproducible fixture and release renders use a VCS source
pinned to a full commit SHA; their answers file must record the VCS source and
that SHA. Direct local Copier copies remain permitted for development but cannot
satisfy fixture or release verification. The declared library range is recorded
by the rendered `pyproject.toml`; do not add a second provenance file or custom
render wrapper.

Before any file move, create
`tests/fixtures/copier-copier-template/migration-manifest.json`. It is the sole
versioned authority for migration evidence. It is loaded with the standard
library `json` module and has only:

- `moves`: `source`, `target` or `disposition`, and `reason` for every runtime
  module, generated-project test, importer script, resource marker, Poetry
  entry, and Copier configuration file;
- `files`: a POSIX-relative path-to-raw-SHA-256 map for the frozen render; and
- `allowed_changes`: a path-to-reason map for the post-extraction comparison.

The comparison test rejects any unlisted difference. Except for the VCS fields
in `.copier-answers.yml`, it compares rendered-file bytes directly; do not
normalize timestamp, whitespace, generated-file, or glob categories.
`memory-bank/` and `specs/` remain root-only. The move map classifies
`models.py`, `paths.py`, and `validation.py` as removed private template modules;
their library tests move with the implementation.

## Migration sequence and comparison controls

1. Freeze the current root product and Copier template before moving files.
   The pre-move fixture exposes the current `copier-template/` contents as the
   root of a temporary VCS source and renders it with Copier at the recorded
   commit. The manifest records the raw digest inventory.
2. Relocate the template into `copier-template/`, move `copier.yml` to the
   repository root, set `_subdirectory: copier-template`, and render from the
   repository-root VCS source at its recorded commit. Compare against the
   frozen manifest and assert that no root control material is rendered. At
   this point only the VCS fields in `.copier-answers.yml` may differ.
3. Extract the library and public seams. A reviewed migration manifest then
   permits only its `allowed_changes`: enumerated shared-module/test removals,
   thin integration files, and the rendered
   `pyproject.toml` addition of `marketplace-installer >=0.1.0,<0.2.0` plus
   removal of extracted-package declarations. Rendered `poetry.lock` must be
   absent. Root-library lock metadata, if retained, is outside the rendered
   product comparison scope.
4. Update package metadata and tests, then run the clean two-wheel integration
   test and repository quality gates. Do not remove a phase oracle until its
   comparison passes.

## Behavior preservation

`marketplace-installer` must preserve the safety and publication guarantees of
specification 001, including validation before mutation, symlink and escaping
path rejection, never executing plugin code, marketplace-wide shared state,
`--force` conflict semantics, `--dry-run` no-write behavior, and atomic
marketplace catalog persistence.

The library is payload-agnostic. It must not know corpus cohorts, payload
selection, generated project names, or a product CLI identity. Conversely, the
Copier template must not duplicate generic installation logic.

## Verification requirements

Tests must establish all of the following:

- the frozen fixture, relocation comparison, and post-extraction comparison
  controls above pass;
- the rendered fixture retains importer, publisher, CLI, and wheel behavior;
- direct library tests cover validation, symlink safety, catalog merge,
  publisher-state conflicts, dry runs, and write-failure recovery;
- the public resource-location API works from unpacked resources and an
  installed wheel;
- a library-wheel consumer-contract test imports every documented public
  symbol from `marketplace_installer` and proves the Copier template imports
  no private module;
- the root wheel and sdist contain `marketplace_installer` but contain neither
  `marketplace_publisher` nor payload resources or product console scripts;
  they include the v3 toolchain manifests and its declared library console
  commands;
- the rendered Copier template contains no copied shared publisher implementation;
- before PyPI publication, a fresh temporary environment installs the exact
  built library and rendered product wheels with `--no-deps`; it has a temporary
  `HOME`, no `PYTHONPATH`, and a working directory outside checkout/build trees.
  The environment's Python and console script publish only under that home,
  `pip check` passes, both modules resolve from site-packages, and the product
  wheel contains exactly one no-extra/no-marker `marketplace-installer`
  `Requires-Dist` with `SpecifierSet(">=0.1.0,<0.2.0")` parsed using the direct
  test dependency `packaging`; and
- `.copier-answers.yml` records the resolved full commit SHA and VCS source;
  root `copier.yml` records `_subdirectory: copier-template`; and the rendered
  `pyproject.toml` records the library version range.

Every behavior-changing implementation follows the repository RED, GREEN,
REFACTOR policy. Before handoff, run the applicable repository formatting,
lint, Markdown, test, and build checks documented in `AGENTS.md`.

## Ongoing compatibility control

Continuous integration must run direct library tests and the rendered-fixture
two-wheel integration test. A generated product binds to its reviewed template
revision and `marketplace-installer` range. Library upgrades require a
compatibility review when changing the declared range. Releases already admitted
by that range follow the library's semantic-version compatibility policy.

Adoption by existing generated repositories and any corpus-repository gate are
separate authorized work. A future corporate package-source change is also
separate work and may replace the PyPI dependency source only through an
explicit follow-on decision.
