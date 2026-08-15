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
`assembly_root`, marketplace name, and plugin name. The build script consumes
only `assembly_root`; recursive digests are verification results, not part of
the assembly API contract.
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
preview/commit protocol internally. Its exact successful result is:

```python
{
    "status": "preview" | "installed",
    "marketplace": str,
    "dry_run": bool,
    "added": list[str],
    "updated": list[str],
    "unchanged": list[str],
    "conflicts": list[str],
}
```

`dry_run=True` always returns `status="preview"` without mutation.
`force=False` raises `MarketplacePublishError` when the nonempty `conflicts`
list would prevent a commit; a dry run reports that list instead. `force=True`
permits only the replacement rows in the conflict table below. The operation
validates embedded receipt and publication metadata but does not re-read an
absent consumer source checkout.

The three v3 marketplace operations raise `MarketplacePublishError` for their
expected failures and return documented mappings. The Copier workflow consumes
no field beyond those named here.
For a caller-provided path that exists but violates a stated filesystem
precondition, each operation raises `MarketplacePublishError`; ordinary Python
argument-type errors are outside this compatibility promise.

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

The current workflow uses `marketplace-installer` directly. A caller invokes
the `router-plugin-packager` command or `run("apply", ...)` to produce a
validated plugin tree, then uses the existing `publish_generated_plugin`
preview/commit operation to merge that plugin into a selected operational
marketplace. The target may be a temporary test directory, a project staging
directory, or the local marketplace root selected by an existing operational
workflow.

This remains the canonical path for the current router-plugin packager and its
MCP, setup, first-user, runtime-lifecycle, and launcher flows. The library must
continue to validate the v3 receipt, publication metadata, source inventory,
and toolchain-manifest authority before it changes a marketplace root. No
Copier project, embedded payload, or package build is required for this path.

The library does not install a marketplace into Codex itself. A caller that
wants Codex installation performs that separate CLI or operational step after
the direct publication completes.

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
tree for the Copier build workflow. Its caller supplies a nonexistent or empty,
dedicated `assembly_root`; a nonempty root is rejected.
`publish_generated_plugin` retains its current merge-into-operational-target
behavior and is not the canonical-artifact API. The Copier workflow alone
consumes the assembly result:

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

The Copier workflow invokes `stage_marketplace_payload` on that root. It may
add only the existing regular `resources/__init__.py` package marker; that
wrapper file is excluded from canonical-payload comparison. It must not rewrite
the manifest, plugin files, receipts, metadata, digests, plugin directory
names, or create a template-specific payload layout. Deployment of a canonical
root into an arbitrary existing marketplace is not part of this specification.

The canonical root contains only `.agents/`, `plugins/`, and the fixed root
file `.marketplace-assembly-receipt.json`; it contains no transaction journal,
lock, backup, staging, or tokenized receipt directory. The receipt format is
`marketplace-assembly-receipt-v1`. It has exactly the following JSON-object
fields; unknown or missing fields are invalid.

For this receipt, canonical JSON is UTF-8
`json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"`. Every
digest is `sha256:` followed by lowercase hexadecimal SHA-256.

| Field | Value |
| --- | --- |
| `format` | Exact string `marketplace-assembly-receipt-v1`. |
| `marketplace_name`, `plugin_name` | Nonempty strings; `plugin_name` is a single safe path component. |
| `plugin_tree_digest` | Digest of canonical JSON `{"entries":[...]}`. Entries are sorted and each is `{path, mode, content_hash}` for every regular file under `plugins/<plugin_name>`; `path` is POSIX-relative, `mode` is `st_mode & 0o7777`, and `content_hash` is lowercase SHA-256. Symlinks and modes with `mode & 0o7000` are invalid. |
| `marketplace_manifest_digest` | Digest of `.agents/plugins/marketplace.json`. |

The receipt has no digest of itself or of the complete canonical root. It must
not contain absolute paths, home/workspace identifiers, credentials, timestamps,
transaction IDs, or other nondeterministic data.

Assembly first calls the existing strict, source-aware v3 validation, including
source-inventory freshness and live MCP-authority checks, then creates the
receipt from that validated input. Staging and installed publication use a
separate portable validation mode: it verifies the allowed root shape, regular
files and no symlinks, the one-plugin marketplace manifest and its local
`./plugins/<plugin_name>` source, plugin identity and publication metadata,
router-receipt generated-file entries, and every receipt digest listed above.
The fixed plugin-tree digest includes the router receipt, its source-inventory
and MCP-authority evidence, and publication metadata; those fields are not
duplicated in the assembly receipt. Portable validation does not traverse parent
directories, re-read source inventory, or re-resolve live MCP
configuration/registry authority. Library validation rejects a nonportable or
tampered receipt before staging or installed publication.

Canonical-payload validation and operational-target validation are separate
modes. Canonical-payload validation applies only to the assembly root or
embedded resources and enforces the exact root shape above. Before evaluating
an installed target, the library recovers an interrupted transaction, then
operational-target validation permits the valid marketplace tree plus only the
library-owned `.codex-marketplace-publish-transaction/`,
`.codex-marketplace-publish-receipts/`, and lock entries required by its
current protocol. It rejects symlinks, special files, malformed paths, and any
other unexpected root entry. Those operational artifacts are not payload files
or ownership state, are excluded from conflict calculation, and are preserved
or cleaned only by the library protocol. Every unrelated plugin tree and
allowed root entry is preserved byte-for-byte.

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

The script must set `publisher_root = Path(__file__).resolve().parents[1]`.
It resolves `--repository-root` and `--invocation` relative to the process
current working directory. The invocation must be a regular, nonsymlink file
within the resolved repository root; its declared repository root is resolved
by the packager relative to the invocation's parent and must equal the supplied
repository root. Its resolved output root must also remain inside that root.
The script derives `.build/marketplace-assembly` and
`src/<package_name>/resources/` only from `publisher_root`.

The script must:

1. validate the resolved repository root and invocation path;
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

The script passes the resolved inputs through to the packager without rewriting
invocation contents. Packager path-validation errors are reported before any
package-resource staging. Tests run the script from a foreign working directory
with relative arguments, an invocation outside the repository, and a mismatched
declared repository root.

The `.build/marketplace-assembly` root is ignored by package discovery. The
build script preserves it on failure for diagnosis and removes only its owned
contents after a successful staging call. `stage_marketplace_payload` creates
its own unique same-parent sibling of `resources/`; that sibling, any backup,
lock, or journal is never included in the wheel.

If `.build/marketplace-assembly` remains from a failed run, the next build
fails before applying the packager and names that directory in its error. It
never silently deletes or reuses diagnostic output. The operator must inspect
and remove that owned directory before retrying; a later successful build may
remove only the assembly root it created.

The resource replacement is intentionally a build-time operation. The
rendered product's installed console command only publishes its already
embedded resource payload; it does not regenerate router plugins at runtime.

## Payload contract

The generated product embeds the v3 local-marketplace layout verbatim:

```text
src/<package_name>/resources/
  .agents/plugins/marketplace.json
  .marketplace-assembly-receipt.json
  plugins/<plugin-slug>/
    .codex-plugin/plugin.json
    .codex-plugin/publication-metadata.json
    .router-plugin-packager-source-map.json
    ...
```

The template must retire the legacy root-level `resources/marketplace.json`
assumption. Its embedded-publisher adapter calls
`publish_embedded_generated_marketplace` directly, returns that mapping, and
re-exports `MarketplacePublishError` as its expected publisher error. It must
not retain `PublishResult`, `PublisherError`, or other legacy installer model
types. The rendered CLI converts a successful mapping to exactly this existing
JSON envelope:

```json
{
  "status": "installed",
  "marketplace": "example",
  "dry_run": false,
  "plugins": {
    "added": ["example-plugin"],
    "updated": [],
    "unchanged": [],
    "conflicts": []
  },
  "errors": []
}
```

For a `MarketplacePublishError`, the CLI retains the existing error envelope:
`status="error"`, `marketplace=null`, `dry_run=false`, empty nested plugin
lists, and `errors=[str(error)]`. It writes JSON to stdout with `--json`; for
human output it writes success to stdout and errors to stderr, and returns 0 or
1 respectively. `--verbose` remains a stderr-only progress message.

Installed publication uses no persistent ownership state. It evaluates the
target under the derived marketplace path according to this conflict table;
all successful rows preserve unrelated plugin directories and manifest entries.
For conflict classification, plugin equality is equality of the receipt-defined
`plugin_tree_digest`, including ordinary file modes. Manifest-entry equality is
canonical JSON equality for the one entry whose `name` is `plugin_name`.
Root-level manifest formatting, entry order, unrelated plugins, and permitted
operational artifacts do not affect equality.

| Existing target state | Dry run | `force=False` | `force=True` |
| --- | --- | --- | --- |
| Target absent | `added=[plugin_name]` | Create target; `status="installed"`, `added=[plugin_name]`. | Same as default. |
| Valid same-name marketplace; plugin absent | `added=[plugin_name]` | Add the plugin and manifest entry. | Same as default. |
| Valid same-name marketplace; plugin tree and manifest entry equal by the defined comparison | `unchanged=[plugin_name]` | Leave target unchanged. | Same as default. |
| Valid same-name marketplace; same plugin name but a defined comparison differs | `conflicts=[plugin_name]` | Raise `MarketplacePublishError`; leave target unchanged. | Replace only that plugin and entry; `updated=[plugin_name]`. |
| Missing/invalid marketplace manifest, different marketplace name, unsafe tree, or plugin source mapping not `./plugins/<plugin_name>` | `conflicts=["marketplace"]` | Raise `MarketplacePublishError`; leave target unchanged. | Raise `MarketplacePublishError`; leave target unchanged. |

Dry-run rows never mutate and always use `status="preview"`. The four lists in
the result are always present, sorted, and mutually exclusive. A target with a
same-name plugin that differs in bytes is a conflict regardless of whether it
was installed by a prior publisher version; `force=True` is the explicit
permission to replace it.

The fixed assembly receipt is the only payload provenance. The template must
not add product-specific provenance metadata, avoiding a second payload form.

## Dependency and development contract

Define `MIN_GENERATED_PAYLOAD_LIBRARY_VERSION` as the first released
`marketplace-installer` version implementing every public seam in this
specification. Before the template slice, the implementation selects its
concrete value by updating the root `[project].version`; the rendered
`pyproject.toml.jinja` declares that exact value as its lower bound. A root
test parses the root TOML, rendered TOML, and both built-wheel METADATA files
to assert that the library version, template lower bound, and product
`Requires-Dist` agree. The rendered `pyproject.toml`
declares
`marketplace-installer>=MIN_GENERATED_PAYLOAD_LIBRARY_VERSION` with an upper
bound at the next breaking compatibility boundary; it must not admit a prior
library version, render path/editable dependencies, or render credentials.
Copier adoption is blocked until that release exists.

The root project, Copier template, and rendered product require Python
`>=3.12,<4.0`, matching `marketplace-installer`. Root and rendered Ruff
`target-version` values are `py312`. Tests and metadata assertions must reject
a lower Python floor or Ruff target.

Before a PyPI release exists, the repository integration test creates a
temporary wheelhouse. It downloads the exact runtime-dependency wheels named
by the built library wheel's `Requires-Dist` into that wheelhouse, records each
SHA-256, then uses a fresh virtual environment to install the library wheel
with `pip install --no-index --find-links <wheelhouse>` and the rendered product
wheel with `--no-deps`. The install commands have no index access and must not
use an ambient pip cache. The test runs `pip check`, asserts the installed
library's exact version and artifact digest, and inspects the product wheel for
the required hidden canonical files and the absence of build/stage artifacts.
The dependency-download preparation is test-fixture setup only; it is not
rendered product metadata or an end-user setup instruction.

## Implementation map and test-first order

This is an ordered implementation contract, not a request to redesign the v3
packager. Each implementation slice starts by adding the named failing test,
then changes only the mapped files until that test passes.

| Order | Tests first | Implementation files | Required outcome |
| --- | --- | --- | --- |
| 1 | Add `tests/test_generated_plugin_payload.py` for empty-root assembly, exact receipt schema, every receipt/manifest/plugin tamper case, source-to-stage parity, symlink rejection, and rollback. Extend `tests/test_router_plugin_packager.py` only where a fixture must prove the existing apply output. | `src/marketplace_installer/marketplace_publish.py` | Add source-aware assembly plus portable static validation and `stage_marketplace_payload`; retain `publish_generated_plugin` as the existing merge-to-target API. |
| 2 | Add direct installed-publication tests for every conflict-table row, error non-mutation, and source-checkout absence. | `src/marketplace_installer/marketplace_publish.py`, `pyproject.toml`, and the public module exports actually used by the rendered adapter | Add `publish_embedded_generated_marketplace`, its exact mapping, and stateless conflict behavior. Bump the root package version and set root Ruff to `py312` before template metadata changes. |
| 3 | Remove the rendered importer tests; add `copier-template/tests/test_build_marketplace.py.jinja`; update `test_cli.py.jinja` and `test_packaging.py.jinja` for mapping-to-envelope conversion and v3 payloads. | Add `copier-template/scripts/build_marketplace.py.jinja`; remove `copier-template/scripts/import_marketplace.py.jinja` and `copier-template/src/{{ package_name }}/importer.py.jinja`; update `publisher.py.jinja`, `cli.py.jinja`, and `pyproject.toml.jinja`. | A rendered product builds and stages one v3 payload from explicit repository inputs; its installed CLI publishes that payload through the defined adapter. |
| 4 | Update `tests/test_copier_template.py`, `tests/test_copier_template_migration.py`, and `tests/test_two_wheel_integration.py` for the temporary wheelhouse. | `copier-template/README.md.jinja`, `copier-template/.gitignore` if needed for `.build/`, `tests/fixtures/copier-template/migration-manifest.json`, and the template tests listed above. | Rendering, migration evidence, wheel contents, Python 3.12 metadata, dependency lower bound, offline installation, and source-independent publication all agree. |

`copier-template/scripts/import_marketplace.py.jinja` and
`copier-template/src/{{ package_name }}/importer.py.jinja` are removed only in
order 3, after their rendered build-test replacement passes. The legacy
root-level `resources/marketplace.json` assertions are removed in the same
slice; no compatibility adapter retains that payload format. Existing direct
packager and `publish_generated_plugin` tests remain the regression oracle for
the first consumer throughout the migration.

## Acceptance tests

Tests must prove all of the following:

- a rendered project builds an embedded payload from a fixture consumer
  repository and invocation without a `HOME/.codex` directory;
- the embedded output has the exact v3 local-marketplace layout and validated
  router receipt, plugin metadata, marketplace manifest, and portable fixed
  assembly receipt;
- portable validation rejects each tampered receipt field, unknown receipt
  field, path escape, manifest, plugin file, router receipt, publication
  metadata, and router-receipt generated-file digest without reading a source
  checkout or changing a target;
- no embedded payload file contains an absolute source, target, home, or
  workspace path;
- invalid invocation, missing source root, invalid generated tree, and failed
  publish leave the existing `resources/` tree unchanged;
- a second successful build replaces the prior payload atomically and leaves
  exactly one valid, portable fixed receipt;
- the canonical assembly root and the rendered product `resources/`
  tree have identical recursive canonical paths and SHA-256 digests, excluding
  only `resources/__init__.py`;
- injected failures after staging and during replacement preserve the existing
  resource tree, repair only owned stage/backup paths, and reject symlinks;
- installed publication covers every row of the conflict table, including
  dry-run reporting, default rejection without mutation, identical reinstall,
  forced same-plugin replacement, manifest key-order equality, executable-mode
  differences, and preservation of unrelated plugins;
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
- root and rendered `pyproject.toml` metadata and Ruff target versions require
  Python 3.12 and the exact generated-payload library lower bound; and
- the two-wheel test provisions and hashes its temporary dependency wheelhouse,
  performs both installs without index access, and inspects the built product
  wheel for the full canonical payload and absence of build artifacts.

## Migration sequence

Follow the four ordered slices in
[Implementation map and test-first order](#implementation-map-and-test-first-order).
Do not begin the template slice until the library seam, portable receipt, and
concrete minimum library version have passing direct tests. Run Copier
rendering, library wheel, generated-product wheel, and full regression suites
before releasing the library version or adopting the template in a consumer
repository.
