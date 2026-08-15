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

## Canonical generated payload

Spec 003 defines a single-plugin canonical assembly root with `.agents/`,
`plugins/`, and a portable fixed assembly receipt. `assemble_generated_plugin`
creates that artifact after strict source-aware v3 validation; the direct
workflow continues to publish a generated plugin with
`publish_generated_plugin`. The Copier workflow calls
`stage_marketplace_payload` to copy the same regular files into resources,
adding only `resources/__init__.py`. Receipt portability and byte-for-byte
path/digest parity are library responsibilities, not template rewrites.

Portable validation of the embedded canonical root is distinct from validation
of its mutable operational destination. The latter permits only the library's
transaction, receipt, and lock artifacts in addition to a regular marketplace
tree; those artifacts never become package payload or conflict state.

## Template boundary and installed publication

The template's repository-only `scripts/build_marketplace.py` resolves explicit
consumer-repository and invocation paths, runs the public packager, assembles a
canonical payload under its ignored `.build/` directory, and stages it into
resources. The installed CLI calls
`publish_embedded_generated_marketplace`; it never regenerates the plugin or
reads a configured marketplace. The product adapter may use only public
library APIs and maps the library result to the stable CLI JSON envelope.
