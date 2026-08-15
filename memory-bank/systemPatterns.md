# System Patterns

## Two artifacts, one contract

The root Poetry project builds `marketplace-installer`; `copier-template/`
renders a separate `marketplace-publisher` product that depends on that
library. The template contains product concerns only and must not carry copied
installer logic.

## V3 installer closure

`src/marketplace_installer/` owns the complete router-plugin packager, MCP and
setup flows, runtime lifecycle, generated-plugin marketplace publisher, and
toolchain manifests. Internal imports use `marketplace_installer`, not an
external source tree. The library owns the shared contract and its full
regression suite.

## Marketplace safety

Local marketplace trees use `.agents/plugins/marketplace.json` and relative
`./plugins/<plugin-name>` entries. Validate JSON, paths, receipt/metadata, and
regular file trees before mutation; reject symlinks and avoid executing plugin
code. Existing merge publication preserves unrelated content and protects
modified package-owned files unless forced.

## Canonical generated payload (planned)

Spec 003 defines a single-plugin canonical assembly root with `.agents/`,
`plugins/`, and a portable fixed assembly receipt. Canonical assembly is a
Copier-build artifact; the direct workflow continues to publish a generated
plugin with `publish_generated_plugin`. The Copier workflow stages the same
regular files into resources, adding only `resources/__init__.py`. Receipt
portability and byte-for-byte path/digest parity are library responsibilities,
not template rewrites.

Portable validation of the embedded canonical root is distinct from validation
of its mutable operational destination. The latter permits only the library's
transaction, receipt, and lock artifacts in addition to a regular marketplace
tree; those artifacts never become package payload or conflict state.

## Template boundary

The current template still uses repository-only marketplace import and the
legacy root-level `resources/marketplace.json` payload. Spec 003 replaces that
with a repository-only generated-payload build script. Until then, preserve the
current template contract and its frozen migration fixtures.
