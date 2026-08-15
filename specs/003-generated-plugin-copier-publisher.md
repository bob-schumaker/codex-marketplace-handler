# Generated Plugin Copier Publisher

## Goal

Replace the Copier product's legacy "import an existing local marketplace"
workflow with an offline build workflow that generates a router plugin from a
consumer project's own source and assembles that generated plugin into the
product's embedded marketplace payload.

For a project such as `werner-mcp-tools`, the rendered `marketplace-publisher`
project must create a releasable marketplace package without first publishing a
plugin to a Codex marketplace or copying one from `~/.codex`.

This specification extends
`002-marketplace-installer-library-and-baseline.md`. Where the two conflict,
this specification controls generated-plugin packaging and the Copier product
resource layout.

The library has two consumers, not two implementations. This work adds the
second consumer and must preserve the first.

## Scope

In scope:

- promote the v3 router-plugin packager and generated-plugin publisher to
  documented public `marketplace-installer` seams;
- replace the rendered product's `scripts/import_marketplace.py` workflow with
  a repository-only build script;
- make the rendered product embed the generated local-marketplace payload;
- define isolated tests that build a payload without a real Codex home,
  installed marketplace, package-index publication, or marketplace release;
- update the Copier template's documentation, adapters, tests, and provenance
  to the generated-payload model.

The existing direct router-plugin packaging and local-marketplace assembly
workflow remains in scope as a supported library consumer. Its behavior is not
replaced by the Copier workflow.

Out of scope:

- publishing `marketplace-installer` to PyPI or configuring release automation;
- publishing or installing a generated marketplace into a user's Codex home;
- changing a consumer project's plugin source, router catalog, release
  metadata, or MCP descriptor;
- maintaining the legacy `resources/marketplace.json` payload contract after
  the template migration;
- changing the existing v3 plugin or marketplace schemas.

Version `0.1.x` supports exactly one generated plugin per rendered publisher
package. A multi-plugin publisher is separate work; repeated single-plugin
assembly calls must not become an implicit multi-plugin API.

## Ownership and boundary

`marketplace-installer` owns generic mechanics. Its v3 public modules are:

```python
from marketplace_installer.router_plugin_packager import PackagerError, run
from marketplace_installer.marketplace_publish import (
    MarketplacePublishError,
    assemble_generated_plugin,
    publish_embedded_generated_marketplace,
    publish_generated_plugin,
    stage_marketplace_payload,
)
```

The required operations are:

```python
run("apply", invocation_path: Path, repo_root: Path) -> dict[str, Any]

assemble_generated_plugin(
    *,
    plugin_root: Path,
    assembly_root: Path,
    marketplace_name: str,
) -> dict[str, Any]

publish_generated_plugin(
    *,
    plugin_root: Path,
    target_root: Path,
    marketplace_name: str,
    backup_dir: Path | None = None,
    dry_run: bool = False,
    plan_digest: str | None = None,
) -> dict[str, Any]

publish_embedded_generated_marketplace(
    resource_package: str,
    *,
    home: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]

stage_marketplace_payload(
    canonical_root: Path,
    destination_resources: Path,
) -> dict[str, Any]
```

These modules, their stated signatures, result fields, and typed expected
errors are public compatibility surfaces. The rendered product may not import
private helpers from them.

`run("apply", ...)` returns an absolute `output_root` path to the validated
generated plugin tree. `assemble_generated_plugin` returns an absolute
`assembly_root`, marketplace name, plugin name, and canonical-tree digest.
`publish_generated_plugin(..., dry_run=True)` returns a preview containing
absolute `target_root` and `plan_digest`; its commit call uses the same inputs
plus that exact digest. A successful commit additionally returns
`publish_receipt_path`. These are the only v3 dictionary fields the Copier
build script may consume. `plan` mode returns a `plan_digest` but no
`output_root`.

`publish_embedded_generated_marketplace` materializes an installed resource
package, validates the canonical v3 tree, derives its marketplace name from
`.agents/plugins/marketplace.json`, and publishes it beneath
`<home>/.codex/local-marketplaces/<marketplace-name>`. It owns the required
preview/commit protocol internally. `dry_run=True` returns a preview without
mutation; `force=False` rejects a conflicting existing plugin and `force=True`
permits replacement. Its result has stable `status`, `marketplace`, `dry_run`,
`added`, `updated`, `unchanged`, and `conflicts` fields, preserving the
existing product CLI JSON mapping. It validates embedded receipt and
publication metadata but does not re-read an absent consumer source checkout.

The three v3 marketplace operations raise `MarketplacePublishError` for their
expected failures and return documented mappings. The Copier workflow consumes
no field beyond those named here.

`stage_marketplace_payload` is the only public repository-build operation that
copies a canonical root into package resources. It rejects symlinks in either
input, preserves an existing regular `resources/__init__.py` marker, uses a
same-parent staging directory and rollback-safe replacement, and returns the
absolute destination plus recursive payload digest. Its expected failure is
`MarketplacePublishError`.

The Copier product owns consumer-specific inputs only:

- the selected source repository root;
- a v3 packager invocation JSON file supplied by that project;
- the embedded marketplace display/name selection; and
- the destination package resource directory.

It must not copy the router packager, generated-plugin publisher, or their
support modules into the rendered project.

## Supported workflows

### Direct packaging and local assembly

The current workflow uses `marketplace-installer` directly. A caller may invoke
the `router-plugin-packager` command or `run("apply", ...)` to produce a
validated plugin tree. It may then call `assemble_generated_plugin` to create a
portable canonical artifact in an empty dedicated root, or use the existing
`publish_generated_plugin` preview/commit operation to merge that plugin into
a selected operational marketplace. The latter root may be a temporary test
directory, a project staging directory, or the local marketplace root selected
by an existing operational workflow.

This remains the canonical path for the current router-plugin packager and its
MCP, setup, first-user, runtime-lifecycle, and launcher flows. The library must
continue to validate the v3 receipt, publication metadata, source inventory,
and toolchain-manifest authority before it changes a marketplace root. No
Copier project, embedded payload, or package build is required for this path.

The library does not install a marketplace into Codex itself. A caller that
wants Codex installation performs that separate CLI or operational step after
the library has assembled the local marketplace.

### Copier-generated publisher package

The proposed workflow reuses the packager and canonical assembly operations at
package build time, then stages their result into the rendered product's
`resources/` directory. It does not change packager output, marketplace
validation, transactional publication semantics, or the current direct
commands.

The rendered installed-product CLI calls
`publish_embedded_generated_marketplace`, not `publish_generated_plugin`. The
latter requires a source-produced generated plugin tree; the former is the
source-checkout-independent operation for an already embedded canonical tree.

## Canonical assembled marketplace output

`assemble_generated_plugin` produces the one canonical assembled marketplace
tree. Its caller supplies a nonexistent or empty, dedicated `assembly_root`; a
nonempty root is rejected. `publish_generated_plugin` retains its current
merge-into-operational-target behavior and is not the canonical-artifact API.
Both workflows consume the assembly result:

```text
router-plugin source + invocation
  → router-plugin packager
  → generated plugin tree
  → assemble_generated_plugin
  → canonical local marketplace root
      ├── .agents/plugins/marketplace.json
      ├── plugins/<plugin-slug>/...
      └── .marketplace-assembly-receipt.json
```

The direct workflow may validate or later deploy that root with a separate
merge operation. The Copier workflow invokes `stage_marketplace_payload` on
that same root. It may add only the existing regular `resources/__init__.py`
package marker; that wrapper file is excluded from canonical-payload comparison.
It must not rewrite the manifest, plugin files, receipts, metadata, digests,
plugin directory names, or create a template-specific payload layout.

The canonical root contains only `.agents/`, `plugins/`, and the fixed root
file `.marketplace-assembly-receipt.json`; it contains no transaction journal,
lock, backup, staging, or tokenized receipt directory. The receipt format is
`marketplace-assembly-receipt-v1`. Its only allowed fields are its format,
marketplace and plugin names, relative artifact paths, plan digest, source and
generated-tree digests, marketplace-manifest digest, router-receipt digest,
publication-metadata digest, source-inventory digests, digest-only MCP
authority, and canonical-tree digest. It must not contain absolute paths,
home/workspace identifiers, credentials, timestamps, transaction IDs, or other
nondeterministic data. Library validation rejects a nonportable receipt before
staging or installed publication.

This establishes a single compatibility target: compare every regular file
beneath the canonical root, including the fixed receipt, with the rendered
product's `resources/` tree by relative path and SHA-256. Exclude only the
regular `resources/__init__.py` wrapper marker. Do not normalize receipt
contents, timestamps, paths, or any other payload file. This is a source-tree
to staged-copy comparison; it does not require two independent assemblies to
be byte-identical.

## Rendered project workflow

The template renders a repository-only script named
`scripts/build_marketplace.py`. It accepts explicit paths, rather than
implicitly reading a user home:

```text
poetry run python scripts/build_marketplace.py \
  --repository-root ../werner-mcp-tools \
  --invocation ../werner-mcp-tools/router-plugin-config.json \
  --marketplace-name werner-mcp-tools
```

The script must:

1. resolve and validate the supplied repository root and invocation path;
2. run `marketplace_installer.router_plugin_packager.run("apply", ...)`;
3. obtain the generated plugin root from the apply result;
4. create an owned, initially empty `.build/marketplace-assembly` root outside
   `resources/`;
5. call `assemble_generated_plugin` with that root and the requested
   marketplace name; and
6. call `stage_marketplace_payload` to replace
   `src/<package_name>/resources/` only after both library operations succeed.

The script must never read or write `~/.codex`, use a configured marketplace,
or invoke a Codex CLI command. It must reject a generated plugin tree that
does not carry the v3 receipt and publication metadata validated by the
library.

The invocation's declared `repository_root` and `output_root` must remain
inside the supplied `--repository-root`; the script passes inputs through to
the packager without rewriting invocation contents. Packager path-validation
errors are reported before any package-resource staging.

The `.build/marketplace-assembly` root is ignored by package discovery. The
build script preserves it on failure for diagnosis and removes only its owned
contents after a successful staging call. `stage_marketplace_payload` creates
its own unique same-parent sibling of `resources/`; that sibling, any backup,
lock, or journal is never included in the wheel.

The resource replacement is intentionally a build-time operation. The
rendered product's installed console command only publishes its already
embedded resource payload; it does not regenerate router plugins at runtime.

## Payload contract

The generated product embeds the v3 local-marketplace layout verbatim:

```text
src/<package_name>/resources/
  .agents/plugins/marketplace.json
  plugins/<plugin-slug>/
    .codex-plugin/plugin.json
    .codex-plugin/publication-metadata.json
    .router-plugin-packager-source-map.json
    ...
```

The template must retire the legacy root-level `resources/marketplace.json`
assumption. Its embedded-publisher adapter must call
`publish_embedded_generated_marketplace`, retaining dry-run, force, conflict,
JSON, exit-status, and stdout/stderr behavior where those product CLI contracts
remain applicable.

The fixed assembly receipt is the only payload provenance. The template must
not add product-specific provenance metadata, avoiding a second payload form.

## Dependency and development contract

Define `MIN_GENERATED_PAYLOAD_LIBRARY_VERSION` as the first released
`marketplace-installer` version implementing every public seam in this
specification. The implementation selects and records its concrete value when
it versions those APIs. The rendered `pyproject.toml` declares
`marketplace-installer>=MIN_GENERATED_PAYLOAD_LIBRARY_VERSION` with an upper
bound at the next breaking compatibility boundary; it must not admit a prior
library version, render path/editable dependencies, or render credentials.
Copier adoption is blocked until that release exists.

The Copier template and the rendered product require Python `>=3.12,<4.0`,
matching `marketplace-installer`. Template tests and metadata assertions must
reject a lower Python floor.

Before a PyPI release exists, repository integration tests may create an
isolated environment, build the exact library wheel, install it with its
declared dependencies, and install the rendered product wheel with
`--no-deps` with index access disabled. It must run `pip check` and assert the
installed library's exact version and artifact digest. This is a test harness
only; it is not rendered product metadata or an end-user setup instruction.

## Acceptance tests

Tests must prove all of the following:

- a rendered project builds an embedded payload from a fixture consumer
  repository and invocation without a `HOME/.codex` directory;
- the embedded output has the exact v3 local-marketplace layout and validated
  router receipt, plugin metadata, marketplace manifest, and portable fixed
  assembly receipt;
- no embedded payload file contains an absolute source, target, home, or
  workspace path;
- invalid invocation, missing source root, invalid generated tree, and failed
  publish leave the existing `resources/` tree unchanged;
- a second successful build replaces the prior payload atomically and records
  updated provenance;
- the canonical direct-assembly root and the rendered product `resources/`
  tree have identical recursive canonical paths and SHA-256 digests, excluding
  only `resources/__init__.py`;
- injected failures after staging and during replacement preserve the existing
  resource tree, repair only owned stage/backup paths, and reject symlinks;
- the rendered wheel includes the generated payload but no assembly root,
  stage, backup, lock, journal, or repository-only build script;
- an installed rendered wheel publishes its v3 payload from a clean temporary
  environment with no source checkout on `PYTHONPATH`; and
- Copier render, package build, and wheel tests use only the public v3 library
  modules named above;
- the existing direct packager, MCP, setup, first-user, runtime-lifecycle,
  launcher, and generated-plugin publication suites still pass without a
  Copier render; and
- a library-first fixture test applies a packager invocation, assembles into an
  empty root, stages that root, and proves canonical path/digest parity before
  any rendered-wheel test; and
- rendered `pyproject.toml` metadata and Ruff target version both require
  Python 3.12 and the exact generated-payload library lower bound.

## Migration sequence

1. Add and test `assemble_generated_plugin`, the embedded-payload publication
   operation, portable fixed receipts, canonical-root staging, and their
   typed result/error contracts. Bump and record the first library version that
   contains those APIs.
2. Add fixture consumer input and a failing rendered-product build test.
3. Implement `scripts/build_marketplace.py` and the atomic resource staging
   path.
4. Change the template publisher adapter and CLI to consume the v3 payload.
5. Update `tests/fixtures/copier-template/migration-manifest.json`, the Copier
   render tests, the two-wheel fixture, and template documentation. Remove
   `scripts/import_marketplace.py`, the template importer adapter, and old
   `resources/marketplace.json` tests only after their generated-payload
   replacements pass. In the same slice, update rendered Python metadata and
   Ruff target from 3.11 to 3.12.
6. Run Copier rendering, library wheel, generated-product wheel, and full
   regression suites before releasing a library version or adopting the
   template in a consumer repository.
