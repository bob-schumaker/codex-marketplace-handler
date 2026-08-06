# TDD Tasks: Embedded Local Marketplace Publisher

This task list implements
`001-embedded-local-marketplace.md` according to its companion technical plan.
Complete each behavior task with a documented RED, GREEN, and REFACTOR cycle.

## 1. Package bootstrap

- [ ] Add the `src/marketplace_publisher` package, resource-package markers,
  `tests/`, and Poetry script/package-data configuration.
- [ ] Add test fixtures for a personal home directory, valid marketplace JSON,
  and valid plugin trees.
- [ ] Verify the scaffolding with `poetry run pytest` and `poetry build`.

## 2. Marketplace validation

- [ ] RED: add tests for malformed JSON, missing or invalid marketplace names,
  duplicate plugin names, non-local sources, unsafe source paths, and symlinked
  plugin roots.
- [ ] GREEN: implement typed validation and safe path resolution with an
  injected home directory.
- [ ] REFACTOR: centralize shared validation so importer and publisher cannot
  diverge; rerun `poetry run pytest tests/test_validation.py`.

## 3. Development importer

- [ ] RED: test import of all plugins, a requested subset, unknown plugin
  names, marketplace-name mismatch, missing plugin directories, and no-change
  behavior after a staging failure.
- [ ] GREEN: implement staged replacement from the local catalog to
  `resources/marketplace.json` and each selected local plugin directory to
  `resources/plugins/<plugin-name>/` in `importer.py`.
- [ ] REFACTOR: make the filtered marketplace document and plugin copy share
  one selected-entry model; rerun `poetry run pytest tests/test_importer.py`.
- [ ] Add and test the repository-only `scripts/import_marketplace.py` wrapper;
  confirm it is not registered as an installed console script.

## 4. Publisher: fresh and merged marketplaces

- [ ] RED: test an absent personal marketplace creates its JSON and plugin
  files, then writes state.
- [ ] RED: test same-name merge preserves unknown metadata and unrelated
  plugins, adds new entries, replaces changed package entries, and avoids
  duplicate names.
- [ ] GREEN: implement package-resource loading, merge planning, plugin copy,
  atomic marketplace JSON writes, and state persistence.
- [ ] REFACTOR: isolate result construction from filesystem mutation; rerun
  `poetry run pytest tests/test_publisher.py`.

## 5. Publisher: safety and recovery

- [ ] RED: test different-name marketplace rejection, unsafe destinations,
  changed tracked files, and unmanaged destinations.
- [ ] RED: test `--force` restores package-owned files while preserving extra
  destination files.
- [ ] RED: test copy and JSON-write failures preserve prior JSON and state.
- [ ] GREEN: implement state comparisons, conflict errors, staged source
  validation, and force behavior.
- [ ] REFACTOR: simplify hashing/copy seams without weakening symlink checks;
  rerun the focused publisher tests.

## 6. Runtime CLI

- [ ] RED: test human summaries, non-zero expected-error exits, single-object
  JSON results, verbose diagnostics on standard error, and `--dry-run` with no
  filesystem changes.
- [ ] GREEN: implement `argparse` runtime handling in `cli.py` and delegate
  `__main__.py` to it.
- [ ] REFACTOR: ensure importer and runtime CLIs share only formatting/error
  primitives that genuinely have the same contract; rerun
  `poetry run pytest tests/test_cli.py`.

## 7. Distribution verification

- [ ] RED: add a wheel-install integration test that removes the original
  marketplace source, installs the built wheel into an isolated environment,
  and proves the runtime publishes from embedded `importlib.resources` data.
- [ ] GREEN: correct Poetry package-data and script configuration until the
  installed-wheel test passes.
- [ ] REFACTOR: remove any source-checkout assumptions from fixtures and tests.

## 8. Final quality gate

- [ ] Run `pre-commit run --all-files`.
- [ ] Run the six quality commands listed in the specification.
- [ ] Record final validation output and every TDD exception in the handoff.
- [ ] Confirm no marketplace payload, plugin, credential, or private-path data
  was accidentally committed.

## 9. Publisher state coexistence

- [ ] RED: add a test that two distinct package payloads targeting the same
  marketplace publish different plugins in either order, retain both state
  records, and rerun without conflicts.
- [ ] RED: add tests that a plugin directory with no state record reports an
  unmanaged conflict, while a digest mismatch reports a modified
  package-owned-file conflict.
- [ ] RED: add a test that forced adoption updates only its plugin state record
  and preserves state records for other installer-owned plugins.
- [ ] GREEN: merge publisher state records by plugin name when writing state;
  replace only records for embedded plugins and preserve validated unrelated
  records.
- [ ] GREEN: introduce distinct unmanaged and modified ownership-conflict
  diagnostics without changing `--force`, dry-run, or atomic-write behavior.
- [ ] REFACTOR: centralize state-record merge and validation helpers, then run
  `poetry run pytest tests/test_publisher.py`.
