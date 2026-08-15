from __future__ import annotations

import json
from pathlib import Path

import pytest


from marketplace_installer import plugin_runtime_lifecycle as lifecycle


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_file(path: Path) -> str:
    return lifecycle._hash_bytes(path.read_bytes())


def _headsup_plugin(
    tmp_path: Path,
    *,
    version: str = "1.0.0",
    runtime_compatibility_version: str = "headsup-2026.07",
    migration_contract_version: str | None = None,
    verify_only_finder: bool = False,
    invalid_target_relpath: str | None = None,
) -> Path:
    root = tmp_path / f"headsup-plugin-{version.replace('.', '-')}"
    skill = root / "skills" / "headsup-setup" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        "---\nname: headsup-setup\ndescription: Manage the durable Headsup runtime.\n---\n\n# Headsup setup\n",
        encoding="utf-8",
    )
    runtime_file = root / "payload" / "runtime" / "headsup.py"
    runtime_file.parent.mkdir(parents=True, exist_ok=True)
    runtime_file.write_text(
        f"VERSION = '{version}'\nprint('headsup runtime {version}')\n",
        encoding="utf-8",
    )
    prefs = root / "payload" / "state" / "preferences.json"
    prefs.parent.mkdir(parents=True, exist_ok=True)
    prefs.write_text('{"theme": "light", "version": 1}\n', encoding="utf-8")
    integrations = {
        "codex-hooks": "hooks",
        "launchagent": "agent",
        "iterm-bridge": "bridge",
        "finder-quick-action": "finder",
    }
    for integration_id, token in integrations.items():
        path = root / "payload" / "integrations" / f"{integration_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"id": integration_id, "token": f"{token}-{version}"}) + "\n",
            encoding="utf-8",
        )
    plugin_manifest = {
        "schema_version": 1,
        "id": "bob-schumaker-codex-support/headsup/headsup",
        "name": "headsup",
        "version": version,
        "packaging_mode": "router-surface",
        "publisher_slug": "bob-schumaker-codex-support",
        "plugin_slug": "headsup",
        "surface_id": "headsup",
        "branding_assets": {},
        "interface": {"displayName": "Headsup"},
    }
    _write_json(root / ".codex-plugin" / "plugin.json", plugin_manifest)
    integration_points = []
    for integration_id in integrations:
        target_relpath = (
            invalid_target_relpath
            if integration_id == "finder-quick-action" and invalid_target_relpath
            else f"owned-integrations/{integration_id}.json"
        )
        integration_points.append(
            {
                "id": integration_id,
                "ownership_class": "owned-integration-artifact",
                "target_relpath": target_relpath,
                "source_relpath": f"payload/integrations/{integration_id}.json",
                "reconciliation_mode": (
                    "verify-only"
                    if verify_only_finder and integration_id == "finder-quick-action"
                    else "replace-if-owned"
                ),
                "restart_required": integration_id == "launchagent",
                "repair_policy": "restore-active",
                "rollback_policy": "restore-candidate",
            }
        )
    release_metadata = {
        "format_version": 1,
        "packager_format_version": 1,
        "payload_fingerprint": "PENDING",
        "runtime_compatibility_version": runtime_compatibility_version,
        "migration_contract_version": migration_contract_version,
        "rollback_compatibility_hints": {
            "compatible": migration_contract_version is None
        },
        "control_surface": {
            "skill_id": "headsup-setup",
            "operations": ["verify", "install", "update", "repair", "rollback"],
        },
        "owned_integration_root": "owned-integrations",
        "integration_points": integration_points,
        "verification_targets": [
            {
                "id": "runtime-entrypoint",
                "kind": "active_file_exists",
                "relative_path": "payload/runtime/headsup.py",
            },
            {
                "id": "user-state",
                "kind": "user_state_exists",
                "relative_path": "payload/state/preferences.json",
            },
            {
                "id": "launchagent",
                "kind": "integration_exists",
                "integration_id": "launchagent",
            },
        ],
    }
    _write_json(root / ".codex-plugin" / "release-metadata.json", release_metadata)
    manifest_entries = []
    ownership_classes = {
        "payload/runtime/headsup.py": "replaceable-upgrade-artifact",
        "payload/state/preferences.json": "preserved-user-state-artifact",
        "payload/integrations/codex-hooks.json": "owned-integration-artifact",
        "payload/integrations/launchagent.json": "owned-integration-artifact",
        "payload/integrations/iterm-bridge.json": "owned-integration-artifact",
        "payload/integrations/finder-quick-action.json": "owned-integration-artifact",
    }
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in {
            ".codex-plugin/release-metadata.json",
            ".codex-plugin/payload-manifest.json",
        }:
            continue
        manifest_entries.append(
            {
                "relative_output_path": relative,
                "source_reference": f"fixture:{relative}",
                "acquisition_mode": "generated",
                "file_type": "file",
                "file_mode": "0o644",
                "symlink_policy": "forbidden",
                "content_hash": _hash_file(path),
                "ownership_role": "fixture",
                "ownership_class": ownership_classes.get(relative),
            }
        )
    fingerprint_seed = json.dumps(
        [
            {
                "path": entry["relative_output_path"],
                "hash": entry["content_hash"],
                "mode": entry["acquisition_mode"],
            }
            for entry in manifest_entries
        ],
        sort_keys=True,
    )
    payload_fingerprint = lifecycle._hash_bytes(fingerprint_seed.encode("utf-8"))
    release_metadata["payload_fingerprint"] = payload_fingerprint
    _write_json(root / ".codex-plugin" / "release-metadata.json", release_metadata)
    _write_json(
        root / ".codex-plugin" / "payload-manifest.json",
        {
            "format_version": 1,
            "payload_fingerprint": payload_fingerprint,
            "packager_format_version": 1,
            "entries": manifest_entries,
        },
    )
    return root


def _generic_runtime_plugin(
    tmp_path: Path,
    *,
    plugin_slug: str = "sample-runtime",
    version: str = "1.0.0",
    lifecycle_skill_id: str = "runtime-setup",
    runtime_filename: str = "runtime.py",
    integration_root: str = "managed-integrations",
) -> Path:
    root = tmp_path / f"{plugin_slug}-{version.replace('.', '-')}"
    skill = root / "skills" / lifecycle_skill_id / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        f"---\nname: {lifecycle_skill_id}\ndescription: Manage the durable {plugin_slug} runtime.\n---\n\n# Runtime setup\n",
        encoding="utf-8",
    )
    runtime_file = root / "payload" / "runtime" / runtime_filename
    runtime_file.parent.mkdir(parents=True, exist_ok=True)
    runtime_file.write_text(
        f"VERSION = '{version}'\nprint('{plugin_slug} runtime {version}')\n",
        encoding="utf-8",
    )
    prefs = root / "payload" / "state" / "preferences.json"
    prefs.parent.mkdir(parents=True, exist_ok=True)
    prefs.write_text('{"theme": "light", "version": 1}\n', encoding="utf-8")
    integrations = {
        "service-hook": "hooks",
        "notifier": "notify",
    }
    for integration_id, token in integrations.items():
        path = root / "payload" / "integrations" / f"{integration_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"id": integration_id, "token": f"{token}-{version}"}) + "\n",
            encoding="utf-8",
        )
    _write_json(
        root / ".codex-plugin" / "plugin.json",
        {
            "schema_version": 1,
            "id": f"example/{plugin_slug}/{plugin_slug}",
            "name": plugin_slug,
            "version": version,
            "packaging_mode": "router-surface",
            "publisher_slug": "example",
            "plugin_slug": plugin_slug,
            "surface_id": plugin_slug,
            "branding_assets": {},
            "interface": {"displayName": plugin_slug.title()},
        },
    )
    integration_points = [
        {
            "id": integration_id,
            "ownership_class": "owned-integration-artifact",
            "target_relpath": f"{integration_root}/{integration_id}.json",
            "source_relpath": f"payload/integrations/{integration_id}.json",
            "reconciliation_mode": "replace-if-owned",
            "restart_required": False,
            "repair_policy": "restore-active",
            "rollback_policy": "restore-candidate",
        }
        for integration_id in integrations
    ]
    release_metadata = {
        "format_version": 1,
        "packager_format_version": 1,
        "payload_fingerprint": "PENDING",
        "runtime_compatibility_version": "runtime-2026.07",
        "migration_contract_version": None,
        "rollback_compatibility_hints": {"compatible": True},
        "control_surface": {
            "skill_id": lifecycle_skill_id,
            "operations": ["verify", "install", "update", "repair", "rollback"],
        },
        "owned_integration_root": integration_root,
        "integration_points": integration_points,
        "verification_targets": [
            {
                "id": "runtime-entrypoint",
                "kind": "active_file_exists",
                "relative_path": f"payload/runtime/{runtime_filename}",
            },
            {
                "id": "service-hook",
                "kind": "integration_exists",
                "integration_id": "service-hook",
            },
        ],
    }
    _write_json(root / ".codex-plugin" / "release-metadata.json", release_metadata)
    manifest_entries = []
    ownership_classes = {
        f"payload/runtime/{runtime_filename}": "replaceable-upgrade-artifact",
        "payload/state/preferences.json": "preserved-user-state-artifact",
        "payload/integrations/service-hook.json": "owned-integration-artifact",
        "payload/integrations/notifier.json": "owned-integration-artifact",
    }
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in {
            ".codex-plugin/release-metadata.json",
            ".codex-plugin/payload-manifest.json",
        }:
            continue
        manifest_entries.append(
            {
                "relative_output_path": relative,
                "source_reference": f"fixture:{relative}",
                "acquisition_mode": "generated",
                "file_type": "file",
                "file_mode": "0o644",
                "symlink_policy": "forbidden",
                "content_hash": _hash_file(path),
                "ownership_role": "fixture",
                "ownership_class": ownership_classes.get(relative),
            }
        )
    fingerprint_seed = json.dumps(
        [
            {
                "path": entry["relative_output_path"],
                "hash": entry["content_hash"],
                "mode": entry["acquisition_mode"],
            }
            for entry in manifest_entries
        ],
        sort_keys=True,
    )
    payload_fingerprint = lifecycle._hash_bytes(fingerprint_seed.encode("utf-8"))
    release_metadata["payload_fingerprint"] = payload_fingerprint
    _write_json(root / ".codex-plugin" / "release-metadata.json", release_metadata)
    _write_json(
        root / ".codex-plugin" / "payload-manifest.json",
        {
            "format_version": 1,
            "payload_fingerprint": payload_fingerprint,
            "packager_format_version": 1,
            "entries": manifest_entries,
        },
    )
    return root


def _install(plugin_root: Path, install_root: Path) -> dict:
    return lifecycle.run("install", plugin_root, install_root)


def _update(plugin_root: Path, install_root: Path) -> dict:
    return lifecycle.run("update", plugin_root, install_root)


def _verify(plugin_root: Path, install_root: Path) -> dict:
    return lifecycle.run("verify", plugin_root, install_root)


def _repair(plugin_root: Path, install_root: Path) -> dict:
    return lifecycle.run("repair", plugin_root, install_root)


def _rollback(plugin_root: Path, install_root: Path) -> dict:
    return lifecycle.run("rollback", plugin_root, install_root)


def _assert_diagnostic_schema(result: dict, operation: str) -> None:
    assert result["diagnostic_schema_version"] == "1"
    assert result["operation"] == operation
    assert "result_code" in result
    assert "stage_id" in result
    assert "install_root" in result
    assert "verification_summary" in result
    assert "integration_summary" in result


def test_install_creates_durable_install_state_and_release(tmp_path: Path) -> None:
    plugin_root = _headsup_plugin(tmp_path, version="1.0.0")
    install_root = (tmp_path / "headsup-runtime").resolve()

    result = _install(plugin_root, install_root)

    _assert_diagnostic_schema(result, "install")
    assert result["result_code"] == "success"
    assert result["mutation_summary"]["cleaned_workspace"] is True
    assert result["active_release_path"].endswith(
        "1.0.0__" + result["active_payload_fingerprint"][:12]
    )
    state = _load_json(install_root / ".runtime-lifecycle" / "install-state.json")
    assert state["schema_version"] == "1"
    assert state["plugin_id"] == "bob-schumaker-codex-support/headsup/headsup"
    assert state["runtime_compatibility_version"] == "headsup-2026.07"
    assert state["migration_state"] == "none"
    assert state["rollback_candidate_path"] is None
    assert (
        install_root / "user-state" / "payload" / "state" / "preferences.json"
    ).is_file()


def test_verify_reports_missing_install_state(tmp_path: Path) -> None:
    plugin_root = _headsup_plugin(tmp_path)
    install_root = (tmp_path / "headsup-runtime").resolve()

    result = _verify(plugin_root, install_root)

    _assert_diagnostic_schema(result, "verify")
    assert result["result_code"] == "missing_state"


def test_verify_reports_state_invalid_for_malformed_install_state(
    tmp_path: Path,
) -> None:
    plugin_root = _headsup_plugin(tmp_path)
    install_root = (tmp_path / "headsup-runtime").resolve()
    (install_root / ".runtime-lifecycle").mkdir(parents=True, exist_ok=True)
    (install_root / ".runtime-lifecycle" / "install-state.json").write_text(
        '{"schema_version": 1}\n', encoding="utf-8"
    )

    result = _verify(plugin_root, install_root)

    assert result["result_code"] in {
        "state_invalid",
        "invalid_contract",
        "malformed_layer1_artifact",
    }


def test_install_refuses_plugin_cache_install_root(tmp_path: Path) -> None:
    plugin_root = _headsup_plugin(tmp_path)
    install_root = (
        tmp_path / ".codex" / "plugins" / "cache" / "headsup-live"
    ).resolve()

    result = _install(plugin_root, install_root)

    assert result["result_code"] == "invalid_install_root"


def test_install_refuses_non_user_owned_install_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_root = _headsup_plugin(tmp_path)
    install_root = (tmp_path / "headsup-runtime").resolve()
    monkeypatch.setattr(
        lifecycle.os, "getuid", lambda: install_root.parent.stat().st_uid + 1
    )

    result = _install(plugin_root, install_root)

    assert result["result_code"] == "invalid_install_root"


def test_verify_detects_payload_fingerprint_mismatch_after_drift(
    tmp_path: Path,
) -> None:
    plugin_root = _headsup_plugin(tmp_path)
    install_root = (tmp_path / "headsup-runtime").resolve()
    _install(plugin_root, install_root)
    state = _load_json(install_root / ".runtime-lifecycle" / "install-state.json")
    active_release = Path(state["active_release_path"])
    (active_release / "payload" / "runtime" / "headsup.py").write_text(
        "print('drifted')\n", encoding="utf-8"
    )

    result = _verify(plugin_root, install_root)

    assert result["result_code"] == "payload_mismatch"


def test_update_blocks_on_release_metadata_incompatibility(tmp_path: Path) -> None:
    base = _headsup_plugin(
        tmp_path / "base",
        version="1.0.0",
        runtime_compatibility_version="headsup-2026.07",
    )
    candidate = _headsup_plugin(
        tmp_path / "candidate",
        version="2.0.0",
        runtime_compatibility_version="headsup-2027.01",
    )
    install_root = (tmp_path / "headsup-runtime").resolve()
    _install(base, install_root)

    result = _update(candidate, install_root)

    assert result["result_code"] == "compatibility_blocked"


def test_install_cleans_activation_workspace_after_failure(tmp_path: Path) -> None:
    plugin_root = _headsup_plugin(tmp_path)
    install_root = (tmp_path / "headsup-runtime").resolve()
    conflict = install_root / "owned-integrations" / "launchagent.json"
    conflict.parent.mkdir(parents=True, exist_ok=True)
    conflict.write_text('{"foreign": true}\n', encoding="utf-8")

    result = _install(plugin_root, install_root)

    assert result["result_code"] == "ownership_ambiguous"
    workspaces = install_root / ".runtime-lifecycle" / "workspaces"
    assert not any(workspaces.iterdir()) if workspaces.exists() else True


def test_update_preserves_user_state(tmp_path: Path) -> None:
    base = _headsup_plugin(tmp_path / "base", version="1.0.0")
    candidate = _headsup_plugin(tmp_path / "candidate", version="1.1.0")
    install_root = (tmp_path / "headsup-runtime").resolve()
    _install(base, install_root)
    prefs = install_root / "user-state" / "payload" / "state" / "preferences.json"
    prefs.write_text('{"theme": "dark", "version": 99}\n', encoding="utf-8")

    result = _update(candidate, install_root)

    assert result["result_code"] == "success"
    assert prefs.read_text(encoding="utf-8") == '{"theme": "dark", "version": 99}\n'


def test_install_rejects_undeclared_integration_target(tmp_path: Path) -> None:
    plugin_root = _headsup_plugin(
        tmp_path, invalid_target_relpath="../foreign/finder.json"
    )
    install_root = (tmp_path / "headsup-runtime").resolve()

    result = _install(plugin_root, install_root)

    assert result["result_code"] == "undeclared_integration_target"


def test_install_supports_declared_non_headsup_integration_root(tmp_path: Path) -> None:
    plugin_root = _generic_runtime_plugin(
        tmp_path, integration_root="managed-artifacts"
    )
    install_root = (tmp_path / "generic-runtime").resolve()

    result = _install(plugin_root, install_root)

    _assert_diagnostic_schema(result, "install")
    assert result["result_code"] == "success"
    assert (install_root / "managed-artifacts" / "service-hook.json").is_file()
    state = _load_json(install_root / ".runtime-lifecycle" / "install-state.json")
    assert state["plugin_id"] == "example/sample-runtime/sample-runtime"


def test_verify_reports_ownership_ambiguous_for_existing_unowned_integration(
    tmp_path: Path,
) -> None:
    plugin_root = _headsup_plugin(tmp_path)
    install_root = (tmp_path / "headsup-runtime").resolve()
    _install(plugin_root, install_root)
    launchagent = install_root / "owned-integrations" / "launchagent.json"
    marker = (
        launchagent.parent / f"{launchagent.name}{lifecycle.INTEGRATION_MARKER_SUFFIX}"
    )
    marker.unlink()
    state_path = install_root / ".runtime-lifecycle" / "install-state.json"
    state = _load_json(state_path)
    state["owned_integration_status"].pop("launchagent")
    _write_json(state_path, state)

    result = _verify(plugin_root, install_root)

    assert result["result_code"] == "ownership_ambiguous"


def test_verify_reports_missing_owned_integration_points(tmp_path: Path) -> None:
    plugin_root = _headsup_plugin(tmp_path)
    install_root = (tmp_path / "headsup-runtime").resolve()
    _install(plugin_root, install_root)
    (install_root / "owned-integrations" / "launchagent.json").unlink()

    result = _verify(plugin_root, install_root)

    assert result["result_code"] == "integration_missing"


def test_verify_only_integration_is_not_mutated_by_install(tmp_path: Path) -> None:
    plugin_root = _headsup_plugin(tmp_path, verify_only_finder=True)
    install_root = (tmp_path / "headsup-runtime").resolve()

    result = _install(plugin_root, install_root)

    assert result["result_code"] == "success"
    assert not (
        install_root / "owned-integrations" / "finder-quick-action.json"
    ).exists()
    verify = _verify(plugin_root, install_root)
    assert verify["result_code"] == "integration_missing"


def test_update_detects_no_op_for_same_payload(tmp_path: Path) -> None:
    plugin_root = _headsup_plugin(tmp_path)
    install_root = (tmp_path / "headsup-runtime").resolve()
    _install(plugin_root, install_root)

    result = _update(plugin_root, install_root)

    assert result["result_code"] == "no_op"


def test_rollback_refuses_without_candidate(tmp_path: Path) -> None:
    plugin_root = _headsup_plugin(tmp_path)
    install_root = (tmp_path / "headsup-runtime").resolve()
    _install(plugin_root, install_root)

    result = _rollback(plugin_root, install_root)

    assert result["result_code"] == "compatibility_blocked"


def test_rollback_rejects_candidate_fingerprint_mismatch(tmp_path: Path) -> None:
    base = _headsup_plugin(tmp_path / "base", version="1.0.0")
    candidate = _headsup_plugin(tmp_path / "candidate", version="1.1.0")
    install_root = (tmp_path / "headsup-runtime").resolve()
    _install(base, install_root)
    _update(candidate, install_root)
    state_path = install_root / ".runtime-lifecycle" / "install-state.json"
    state = _load_json(state_path)
    rollback_manifest = (
        Path(state["rollback_candidate_path"])
        / ".codex-plugin"
        / "payload-manifest.json"
    )
    manifest = _load_json(rollback_manifest)
    manifest["payload_fingerprint"] = "wrong"
    _write_json(rollback_manifest, manifest)

    result = _rollback(candidate, install_root)

    assert result["result_code"] == "compatibility_blocked"


def test_rollback_blocks_when_migration_state_blocks(tmp_path: Path) -> None:
    base = _headsup_plugin(tmp_path / "base", version="1.0.0")
    candidate = _headsup_plugin(tmp_path / "candidate", version="1.1.0")
    install_root = (tmp_path / "headsup-runtime").resolve()
    _install(base, install_root)
    _update(candidate, install_root)
    state_path = install_root / ".runtime-lifecycle" / "install-state.json"
    state = _load_json(state_path)
    state["migration_state"] = "rollback_blocked"
    state["migration_version"] = "v-next"
    _write_json(state_path, state)

    result = _rollback(candidate, install_root)

    assert result["result_code"] == "compatibility_blocked"


def test_rollback_reports_partial_failure(tmp_path: Path) -> None:
    base = _headsup_plugin(tmp_path / "base", version="1.0.0")
    candidate = _headsup_plugin(tmp_path / "candidate", version="1.1.0")
    install_root = (tmp_path / "headsup-runtime").resolve()
    _install(base, install_root)
    _update(candidate, install_root)
    launchagent = install_root / "owned-integrations" / "launchagent.json"
    marker = (
        launchagent.parent / f"{launchagent.name}{lifecycle.INTEGRATION_MARKER_SUFFIX}"
    )
    marker.unlink()
    state_path = install_root / ".runtime-lifecycle" / "install-state.json"
    state = _load_json(state_path)
    state["owned_integration_status"].pop("launchagent")
    _write_json(state_path, state)

    result = _rollback(candidate, install_root)

    assert result["result_code"] == "partial_rollback_failure"
    assert result["mutation_summary"]["integration_mutations"]


def test_update_blocks_migration_required_payloads(tmp_path: Path) -> None:
    base = _headsup_plugin(tmp_path / "base", version="1.0.0")
    candidate = _headsup_plugin(
        tmp_path / "candidate",
        version="2.0.0",
        migration_contract_version="migrate-v2",
    )
    install_root = (tmp_path / "headsup-runtime").resolve()
    _install(base, install_root)

    result = _update(candidate, install_root)

    assert result["result_code"] == "compatibility_blocked"


def test_repair_restores_payload_drift(tmp_path: Path) -> None:
    plugin_root = _headsup_plugin(tmp_path)
    install_root = (tmp_path / "headsup-runtime").resolve()
    _install(plugin_root, install_root)
    state = _load_json(install_root / ".runtime-lifecycle" / "install-state.json")
    active_release = Path(state["active_release_path"])
    (active_release / "payload" / "runtime" / "headsup.py").write_text(
        "print('broken')\n", encoding="utf-8"
    )

    result = _repair(plugin_root, install_root)

    assert result["result_code"] == "success"
    verify = _verify(plugin_root, install_root)
    assert verify["result_code"] == "success"


def test_happy_path_install_update_verify_repair_rollback_cycle(tmp_path: Path) -> None:
    base = _headsup_plugin(tmp_path / "base", version="1.0.0")
    candidate = _headsup_plugin(tmp_path / "candidate", version="1.1.0")
    install_root = (tmp_path / "headsup-runtime").resolve()

    installed = _install(base, install_root)
    assert installed["result_code"] == "success"
    assert _verify(base, install_root)["result_code"] == "success"
    updated = _update(candidate, install_root)
    assert updated["result_code"] == "success"
    assert _verify(candidate, install_root)["result_code"] == "success"
    rolled_back = _rollback(candidate, install_root)
    assert rolled_back["result_code"] == "success"
    assert _verify(base, install_root)["result_code"] == "success"
