# Router plugin packaging two-version bootstrap contract

Date: 2026-07-26

This artifact set freezes the first reusable implementation slice described in
`work-items/plans/router-plugin-packaging-any-repo-plan.md`.

The frozen slice supports exactly two bootstrap entry versions that converge to
one normalized package request before generation:

1. `repo_bootstrap`
   - point at a target repo
   - discover the canonical skill root
   - bootstrap the whole visible skill set into one router-pattern plugin
   - discover obvious branding assets and metadata when possible
2. `skill_list`
   - point at a target repo plus an explicit list of skill paths
   - package exactly that list into one router-pattern plugin
   - accept explicit naming and branding overrides when discovery is
     insufficient

For a ponytail-shaped repo, equivalent `repo_bootstrap` and `skill_list`
requests must produce the same normalized package request and the same plugin
output.

If implementation needs fields, outputs, or behaviors outside this document,
the contract is not frozen and coding should stop until the contract is revised
here first.

## Frozen first-slice implementation target

The first implementation slice uses one new portable Python entrypoint:

- `installers/router_plugin_packager.py`

The first-slice tests and fixtures live at:

- `tests/test_router_plugin_packager.py`
- `tests/fixtures/router_plugin_packager/`

No second entrypoint, helper package, or alternate CLI wrapper belongs in the
first slice.

Catalog-driven cohort and router catalogs are not part of this frozen artifact
set. That is a follow-on mode after the two bootstrap entry versions are proven.

## Included artifacts

- [positive-repo-bootstrap/invocation.json](positive-repo-bootstrap/invocation.json)
- [positive-repo-bootstrap/expected-normalized-request.json](positive-repo-bootstrap/expected-normalized-request.json)
- [positive-skill-list-equivalent/invocation.json](positive-skill-list-equivalent/invocation.json)
- [positive-skill-list-equivalent/expected-normalized-request.json](positive-skill-list-equivalent/expected-normalized-request.json)
- [positive-clinerules-skill-list/invocation.json](positive-clinerules-skill-list/invocation.json)
- [positive-clinerules-skill-list/expected-normalized-request.json](positive-clinerules-skill-list/expected-normalized-request.json)
- [negative-duplicate-visible-skill/invocation.json](negative-duplicate-visible-skill/invocation.json)
- [negative-duplicate-visible-skill/expected-error.json](negative-duplicate-visible-skill/expected-error.json)
- [negative-ambiguous-branding-asset/invocation.json](negative-ambiguous-branding-asset/invocation.json)
- [negative-ambiguous-branding-asset/expected-error.json](negative-ambiguous-branding-asset/expected-error.json)

## Canonical v1 invocation shape

The implementation accepts exactly one packaging request at a time.

Required fields:

- `format_version`: integer, must be `1`
- `input_mode`: string, must be `repo_bootstrap` or `skill_list`
- `repository_root`: repository-relative or absolute root used for bootstrap
  discovery, asset resolution, and namespaced output identity
- `output_root`: repository-local destination root

Optional fields:

- `plugin_kind`: string, defaults to `skills_only`; may be `mcp_based` only
  when the invocation explicitly packages an MCP-based plugin surface

Required fields for `skill_list` mode:

- `skill_paths`: ordered array of repository-relative source skill paths

Optional fields:

- `source_root`: repository-relative path to canonical source skills when the
  caller wants to pin discovery explicitly
- `display_name_override`: string
- `plugin_slug_override`: string
- `publisher_slug_override`: string
- `surface_id_override`: string
- `branding_asset_overrides`: object with any of:
  - `logo`
  - `dark_logo`
  - `composer_icon`

Invocation behavior must not depend on the caller's current working directory.
The explicit `repository_root` is the authority for repo-local path
resolution and repo-local decision-state writes.

For `repo_bootstrap`, automatic source-root discovery must ignore dot-prefixed
path segments such as `.openclaw/skills`. Hidden or tool-private skill trees do
not compete with the canonical visible source root unless the caller pins them
explicitly with `source_root`.

## Canonical v1 normalized package-request shape

Bootstrap must converge both entry versions into exactly one normalized package
request before generation starts.

Required fields:

- `format_version`: integer, must be `1`
- `source_root`: canonical source root
- `repository_root`
- `output_root`
- `surface_id`: stable packaging-unit identifier
- `skill_ids`: ordered array of visible source `skill_id` values
- `plugin_metadata`: object
- `decision_record`: object

Required `plugin_metadata` fields:

- `publisher_slug`: repo-scoped namespace for plugin identity
- `plugin_slug`
- `display_name`
- `packaging_mode`: must be `router-surface`

Conditionally required `plugin_metadata` fields:

- `role`: required only when the repository needs install-role distinction
- `branding_assets`: required when any logo, dark-logo, composer icon, or
  equivalent UI assets are declared or discovered

`branding_assets` fields, when present:

- `logo`
- `dark_logo`
- `composer_icon`

Required `decision_record` fields:

- `input_mode`
- `surface_id_source`: `discovered`, `derived`, or `override`
- `skill_ids_source`: `discovered` or `explicit`
- `plugin_metadata_sources`: object naming the provenance of:
  - `publisher_slug`
  - `plugin_slug`
  - `display_name`
  - `branding_assets`
- `rejected_candidates`: ordered array of rejected discovery candidates with
  reasons

## Frozen ownership and routing contract

The frozen first slice uses the ponytail-shaped router pattern:

- every listed `skill_id` becomes exactly one visible router
- every listed `skill_id` also becomes the same-named hidden module package
- visible router order is preserved into generated router ordering
- hidden modules render only as `references/modules/index.json` plus
  non-discoverable `instructions.md` packages, never nested `SKILL.md`

Many-to-one router ownership inference is out of scope in this slice.

Generated router `SKILL.md` frontmatter must still perform deterministic
semantic synthesis from the collected member-skill frontmatter descriptions:

- single-member routers should prefer the member skill's own description and
  trigger language over a generic router label such as `Route <slug> workflows`
- the synthesis must be deterministic, repo-local, and rule-based; no model
  inference is required for v1

## Branding and asset discovery rules

Branding asset paths resolve relative to `repository_root`.
Branding asset paths must remain inside `repository_root`.
Branding assets are never resolved relative to `source_root`.

For v1, "obvious asset" discovery must be deterministic and slot-specific:

- discover only under repository-owned metadata or asset paths, not under
  installed caches or generated output
- ignore dot-prefixed directories and generated-state trees while searching for
  asset candidates
- prefer exact slot-name matches such as `logo`, `dark-logo`, `dark_logo`,
  `icon`, or `composer-icon` before broader image-name fallbacks
- for plugin-facing icon slots, prefer PNG over SVG when both are equally
  strong candidates for the same slot; only fall back to SVG when no PNG
  candidate survives at that same strength
- if multiple equally strong candidates remain for one slot, stop and require
  an explicit override instead of picking arbitrarily

Explicit branding overrides win over discovered branding values, but the
decision record must name both the override and the displaced discovered
candidate when one existed.

When a repo-shared bootstrap-state record exists, a persisted winner may be
reused only while that recorded file still exists and still satisfies the
frozen slot rules. If the recorded file disappears, bootstrap must re-resolve
the slot and update the shared state explicitly.

## Canonical v1 output set

The first reusable coding slice renders exactly:

- normalized package request
- one repo-shared bootstrap-state file at
  `<repository_root>/.codex-plugin/router-plugin-packager/bootstrap-state.json`
- router `SKILL.md`
- internal module instruction files
- copied support files under allowed subtrees
- one plugin manifest
- required branding assets referenced by normalized plugin metadata
- one source map or equivalent receipt
- one repo-local decision-state file at
  `<repository_root>/.codex-plugin/router-plugin-packager/<surface_id>.json`

It does not render marketplace artifacts in v1.

Output plugin identity is frozen to:

- `<publisher_slug>/<plugin_slug>/<surface_id>`

## Canonical v1 failure surface

On contract violation, the tool must fail closed with:

- non-zero exit status
- one structured error record in JSON mode or one exact text error in text mode

The structured error shape is:

- `error_code`
- `message`
- `details`

`details` must name enough concrete fields to fix the contract problem without
debugging the implementation.

## Canonical v1 preview surface

Plan mode must report:

- `input_mode`
- normalized `surface_id`
- normalized ordered `skill_ids`
- `source_root`
- `repository_root`
- `output_root`
- `bootstrap_state_path`
- ordered generated output paths
- `decision_state_path`
- metadata and branding decisions that were inferred versus supplied
- ordered preserved or skipped paths
- ordered stale-generated-path findings, if any
- fatal validation errors, if any

Apply mode must produce the same intended scope when given the same normalized
inputs.

Repeated-run semantics for an existing `output_root`:

- writes are allowed only inside `output_root`
- existing non-generated paths are preserved and reported
- stale generated paths from a previous receipt for a different `surface_id`
  are a hard error
- stale generated paths from an older receipt for the same `surface_id` may be
  replaced only when receipt lineage matches and the apply report names the
  removed or replaced paths explicitly
- repo-local decision state is always rewritten at the same deterministic path
  under `repository_root` for the same normalized `surface_id`, regardless of
  the caller's current working directory
- repo-shared bootstrap state is always rewritten at the same deterministic
  path under `repository_root` and may be reused by later runs when its
  recorded `source_root`, `publisher_slug`, and branding-asset winners remain
  valid
- repeated `skill_list` runs for different groups in the same repository must
  coexist by using distinct normalized `surface_id` values

## Validation order

Implement validation in this order:

1. parse invocation
2. validate `input_mode`
3. resolve and validate `source_root`
4. discover or derive `source_root` when absent:
   - discover one canonical non-hidden visible-skill root for
     `repo_bootstrap`, or
   - derive one common source root from the explicit skill paths for
     `skill_list`
5. normalize the visible skill set:
   - discover whole visible set for `repo_bootstrap`, or
   - validate the explicit ordered skill list for `skill_list`
6. normalize plugin identity fields and branding metadata
7. validate deterministic asset discovery or explicit overrides
8. build the normalized package request
9. validate duplicate normalized `surface_id`, `skill_id`, and `router_slug`
   failures
10. validate support-file ownership and allowed support-material boundaries
11. render preview or apply from the normalized request

## Frozen fixture intent

- `positive-repo-bootstrap` proves that a repo-bootstrap request can discover a
  whole visible skill surface and normalize it successfully
- `positive-skill-list-equivalent` proves that the equivalent explicit skill
  list normalizes to the same result as the repo-bootstrap example
- `positive-clinerules-skill-list` proves that one chosen skill group can be
  packaged independently for repeated multi-group runs in the same repo
- `negative-duplicate-visible-skill` proves duplicate explicit visible entries
  fail closed
- `negative-ambiguous-branding-asset` proves ambiguous obvious-asset discovery
  fails closed without an explicit override

The live upstream `ponytail` validation added two concrete clarifications to
this frozen contract:

- `.openclaw/skills` is not a candidate canonical source root for automatic
  `repo_bootstrap` discovery because dot-prefixed roots are hidden
- when `logo-dark.png` and `logo-dark.svg` are otherwise equally strong plugin
  icon candidates, PNG wins deterministically rather than forcing an ambiguity
