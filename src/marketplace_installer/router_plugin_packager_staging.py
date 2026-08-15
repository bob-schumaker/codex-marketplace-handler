from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


def staging_plan_payload(request: Any, version: str) -> dict[str, Any] | None:
    if request.mcp_packaging is None:
        return None
    contract = request.mcp_packaging.staging_contract
    return {
        "format_version": contract.format_version,
        "marketplace_name": contract.marketplace_name,
        "plugin_relpath": contract.plugin_relpath,
        "version": version,
        "version_suffix_source": contract.version_suffix_source,
        "allowed_mutations": [
            {
                "path": rule.path,
                "field_path": rule.field_path,
                "transform": rule.transform,
            }
            for rule in contract.allowed_mutations
        ],
        "required_byte_preserved_paths": list(contract.required_byte_preserved_paths),
    }


def set_nested_field(payload: dict[str, Any], field_path: str, value: Any) -> None:
    parts = field_path.split(".")
    current: Any = payload
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise PackagerError(
                "invalid_staging_plan",
                "staging mutation field_path does not exist",
                {"field_path": field_path},
            )
        current = current[part]
    if not isinstance(current, dict) or parts[-1] not in current:
        raise PackagerError(
            "invalid_staging_plan",
            "staging mutation field_path does not exist",
            {"field_path": field_path},
        )
    current[parts[-1]] = value


def write_output_tree(
    root: Path,
    outputs: dict[str, bytes],
    output_modes: dict[str, int],
    stale_paths: list[str],
    output_root: Path,
    *,
    remove_stale_paths_fn: Any,
    validate_existing_destination_fn: Any,
) -> None:
    staged_stale_paths = [
        str(root / Path(path).relative_to(output_root)) for path in stale_paths
    ]
    remove_stale_paths_fn(staged_stale_paths)
    for rel, content in sorted(outputs.items()):
        destination = root / rel
        validate_existing_destination_fn(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        destination.chmod(output_modes[rel])


def promote_staged_output(
    request: Any,
    stage: Path,
    *,
    promotion_receipt_path_fn: Any,
    write_json_fn: Any,
    os_module: Any,
    shutil_module: Any,
) -> None:
    """Atomically replace the generated tree and restore a backup on failure."""

    output_root = request.output_root
    backup = output_root.parent / f".{output_root.name}.backup-{uuid.uuid4().hex}"
    receipt_path = promotion_receipt_path_fn(output_root)
    receipt = {
        "format_version": 1,
        "target": str(output_root),
        "stage": str(stage),
        "backup": str(backup),
        "state": "staged",
    }
    write_json_fn(receipt_path, receipt)
    backed_up = False
    try:
        if output_root.exists():
            os_module.replace(output_root, backup)
            backed_up = True
            receipt["state"] = "backed_up"
            write_json_fn(receipt_path, receipt)
        os_module.replace(stage, output_root)
        receipt["state"] = "promoted"
        write_json_fn(receipt_path, receipt)
        if backed_up:
            shutil_module.rmtree(backup)
        receipt_path.unlink()
    except OSError as error:
        if backed_up and backup.exists() and not output_root.exists():
            os_module.replace(backup, output_root)
        if stage.exists():
            shutil_module.rmtree(stage)
        if receipt_path.exists():
            receipt_path.unlink()
        raise PackagerError(
            "output_promotion_failed",
            "failed to atomically promote generated output",
            {"output_root": str(output_root), "error": str(error)},
        ) from error


def validate_staged_plugin_artifact(
    plugin_root: Path,
    *,
    load_json_fn: Any,
    ensure_string_fn: Any,
    normalize_mcp_environment_fn: Any,
    mcp_descriptor_name: str,
) -> tuple[str, str]:
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    descriptor_path = plugin_root / mcp_descriptor_name
    manifest = load_json_fn(manifest_path)
    name = ensure_string_fn(manifest.get("name"), field="plugin_manifest.name")
    version = ensure_string_fn(manifest.get("version"), field="plugin_manifest.version")
    if (
        manifest.get("skills") != "./skills/"
        or manifest.get("mcpServers") != "./.mcp.json"
    ):
        raise PackagerError(
            "invalid_staged_plugin_artifact",
            "staged plugin manifest does not declare the required Codex paths",
            {"path": str(manifest_path)},
        )
    descriptor = load_json_fn(descriptor_path)
    if set(descriptor) != {"mcpServers"}:
        raise PackagerError(
            "invalid_staged_plugin_artifact",
            "staged plugin descriptor may contain only mcpServers",
            {"path": str(descriptor_path)},
        )
    servers = descriptor.get("mcpServers")
    if not isinstance(servers, dict) or len(servers) != 1:
        raise PackagerError(
            "invalid_staged_plugin_artifact",
            "staged plugin descriptor must define exactly one MCP server",
            {"path": str(descriptor_path)},
        )
    server = next(iter(servers.values()))
    if not isinstance(server, dict) or server.get("command") != "uvx":
        raise PackagerError(
            "invalid_staged_plugin_artifact",
            "staged plugin descriptor must retain the package-backed uvx command",
            {"path": str(descriptor_path)},
        )
    if set(server) - {"command", "args", "env"}:
        raise PackagerError(
            "invalid_staged_plugin_artifact",
            "staged plugin descriptor contains unsupported server properties",
            {"path": str(descriptor_path)},
        )
    if "env" in server:
        normalize_mcp_environment_fn(server["env"], field="mcpServers.env")
    return name, version


def apply_staging_plan_for_validation(
    source_root: Path,
    staging_plan: dict[str, Any],
    staged_root: Path,
    cachebuster: str,
    *,
    validate_staged_plugin_artifact_fn: Any,
    load_json_fn: Any,
    set_nested_field_fn: Any,
    write_json_fn: Any,
) -> dict[str, Any]:
    if staged_root.exists():
        raise PackagerError(
            "invalid_staging_root",
            "staged_root must not already exist",
            {"staged_root": str(staged_root)},
        )
    source_root = source_root.resolve()
    staged_root = staged_root.resolve()
    if cachebuster.strip() == "":
        raise PackagerError(
            "invalid_staging_plan",
            "cachebuster must be a non-empty string",
            {"cachebuster": cachebuster},
        )
    validate_staged_plugin_artifact_fn(source_root)
    shutil.copytree(source_root, staged_root)
    mutated_paths: list[str] = []
    for mutation in staging_plan.get("allowed_mutations", []):
        path = staged_root / mutation["path"]
        payload = load_json_fn(path)
        current = payload
        for part in mutation["field_path"].split("."):
            current = current[part]
        if mutation["transform"] != "append-version-suffix":
            raise PackagerError(
                "invalid_staging_plan",
                "unsupported staging mutation transform",
                {"transform": mutation["transform"]},
            )
        set_nested_field_fn(
            payload,
            mutation["field_path"],
            f"{current}+codex.{cachebuster}",
        )
        write_json_fn(path, payload)
        mutated_paths.append(mutation["path"])
    preserved_failures: list[str] = []
    for relative_path in staging_plan.get("required_byte_preserved_paths", []):
        original = source_root / relative_path
        staged = staged_root / relative_path
        if not original.is_file() or not staged.is_file():
            raise PackagerError(
                "staging_parity_failure",
                "required byte-preserved path is missing during staging validation",
                {"path": relative_path},
            )
        if original.read_bytes() != staged.read_bytes():
            preserved_failures.append(relative_path)
    if preserved_failures:
        raise PackagerError(
            "staging_parity_failure",
            "staged validation mutated a required byte-preserved path",
            {"paths": preserved_failures},
        )
    return {
        "staged_root": str(staged_root),
        "mutated_paths": sorted(mutated_paths),
        "required_byte_preserved_paths": list(
            staging_plan.get("required_byte_preserved_paths", [])
        ),
    }


def validate_staged_marketplace_install(
    source_root: Path,
    staging_plan: dict[str, Any],
    sandbox_root: Path,
    cachebuster: str,
    *,
    validate_staged_plugin_artifact_fn: Any,
    apply_staging_plan_for_validation_fn: Any,
    ensure_string_fn: Any,
    write_json_fn: Any,
    hash_tree_fn: Any,
) -> dict[str, Any]:
    """Validate staged MCP output through disposable marketplace/cache trees."""

    if sandbox_root.exists():
        raise PackagerError(
            "invalid_staging_sandbox",
            "staging validation sandbox must not already exist",
            {"sandbox_root": str(sandbox_root)},
        )
    validate_staged_plugin_artifact_fn(source_root.resolve())
    sandbox_root.mkdir(parents=True)
    staged_root = sandbox_root / "staged-plugin"
    staging_result = apply_staging_plan_for_validation_fn(
        source_root, staging_plan, staged_root, cachebuster
    )
    plugin_name, version = validate_staged_plugin_artifact_fn(staged_root)
    plugin_relpath = ensure_string_fn(
        staging_plan.get("plugin_relpath"), field="staging_plan.plugin_relpath"
    )
    expected_relpath = Path("plugins") / plugin_name
    if Path(plugin_relpath) != expected_relpath:
        raise PackagerError(
            "invalid_staging_plan",
            "staging plugin_relpath must name the staged plugin under plugins/",
            {"plugin_relpath": plugin_relpath, "plugin_name": plugin_name},
        )
    marketplace_name = ensure_string_fn(
        staging_plan.get("marketplace_name"), field="staging_plan.marketplace_name"
    )
    marketplace_root = sandbox_root / "marketplace"
    marketplace_plugin_root = marketplace_root / expected_relpath
    marketplace_plugin_root.parent.mkdir(parents=True)
    shutil.copytree(staged_root, marketplace_plugin_root)
    write_json_fn(
        marketplace_root / ".agents" / "plugins" / "marketplace.json",
        {
            "name": marketplace_name,
            "interface": {"displayName": marketplace_name},
            "plugins": [
                {
                    "name": plugin_name,
                    "source": {"source": "local", "path": f"./{plugin_relpath}"},
                    "policy": {
                        "installation": "AVAILABLE",
                        "authentication": "ON_INSTALL",
                    },
                    "category": "Productivity",
                }
            ],
        },
    )
    cache_plugin_root = (
        sandbox_root / "cache" / marketplace_name / plugin_name / version
    )
    cache_plugin_root.parent.mkdir(parents=True)
    shutil.copytree(marketplace_plugin_root, cache_plugin_root)
    validate_staged_plugin_artifact_fn(cache_plugin_root)
    if hash_tree_fn(staged_root) != hash_tree_fn(cache_plugin_root):
        raise PackagerError(
            "staging_install_parity_failure",
            "disposable marketplace cache does not preserve the staged plugin tree",
            {"plugin_name": plugin_name, "version": version},
        )
    return {
        **staging_result,
        "marketplace_root": str(marketplace_root),
        "cache_plugin_root": str(cache_plugin_root),
        "plugin_name": plugin_name,
        "version": version,
    }


def apply_generated_output(
    request: Any,
    outputs: dict[str, bytes],
    output_modes: dict[str, int],
    state: dict[str, Any],
    stale_generated_paths: list[str],
    *,
    validate_output_ownership_fn: Any,
    write_output_tree_fn: Any,
    promote_staged_output_fn: Any,
    validate_existing_destination_fn: Any,
    write_json_fn: Any,
    shutil_module: Any,
    uuid_module: Any,
) -> None:
    validate_output_ownership_fn(request)
    stage = (
        request.output_root.parent
        / f".{request.output_root.name}.stage-{uuid_module.uuid4().hex}"
    )
    if request.output_root.exists():
        shutil_module.copytree(request.output_root, stage)
    else:
        stage.mkdir(parents=True)
    write_output_tree_fn(
        stage,
        outputs,
        output_modes,
        stale_generated_paths,
        request.output_root,
    )
    promote_staged_output_fn(request, stage)
    validate_existing_destination_fn(state["bootstrap_state_path"])
    write_json_fn(state["bootstrap_state_path"], state["bootstrap_state_payload"])
    validate_existing_destination_fn(state["decision_state_path"])
    write_json_fn(state["decision_state_path"], state["decision_state_payload"])


def write_output_tree_for_packager(
    root: Path,
    outputs: dict[str, bytes],
    output_modes: dict[str, int],
    stale_paths: list[str],
    output_root: Path,
    *,
    remove_stale_paths_fn: Any,
    validate_existing_destination_fn: Any,
) -> None:
    write_output_tree(
        root,
        outputs,
        output_modes,
        stale_paths,
        output_root,
        remove_stale_paths_fn=remove_stale_paths_fn,
        validate_existing_destination_fn=validate_existing_destination_fn,
    )


def promote_staged_output_for_packager(
    request: Any,
    stage: Path,
    *,
    suffix: str,
    write_json_fn: Any,
    os_module: Any,
    shutil_module: Any,
    promotion_receipt_path_fn: Any,
) -> None:
    promote_staged_output(
        request,
        stage,
        promotion_receipt_path_fn=lambda output_root: promotion_receipt_path_fn(
            output_root, suffix=suffix
        ),
        write_json_fn=write_json_fn,
        os_module=os_module,
        shutil_module=shutil_module,
    )


def apply_generated_output_for_packager(
    request: Any,
    outputs: dict[str, bytes],
    output_modes: dict[str, int],
    state: dict[str, Any],
    stale_generated_paths: list[str],
    *,
    receipt_name: str,
    load_json_fn: Any,
    native_receipt_format: str,
    native_receipt_contract_fn: Any,
    native_generated_tree_digest_from_disk_fn: Any,
    suffix: str,
    validate_existing_destination_fn: Any,
    write_json_fn: Any,
    os_module: Any,
    shutil_module: Any,
    uuid_module: Any,
    validate_output_ownership_for_packager_fn: Any,
    write_output_tree_for_packager_fn: Any,
    remove_stale_paths_for_packager_fn: Any,
    promote_staged_output_for_packager_fn: Any,
    promotion_receipt_path_fn: Any,
) -> None:
    apply_generated_output(
        request,
        outputs,
        output_modes,
        state,
        stale_generated_paths,
        validate_output_ownership_fn=lambda req: validate_output_ownership_for_packager_fn(
            req,
            receipt_name=receipt_name,
            load_json_fn=load_json_fn,
            native_receipt_format=native_receipt_format,
            native_receipt_contract_fn=native_receipt_contract_fn,
            native_generated_tree_digest_from_disk_fn=native_generated_tree_digest_from_disk_fn,
        ),
        write_output_tree_fn=lambda root,
        out,
        modes,
        stale,
        out_root: write_output_tree_for_packager_fn(
            root,
            out,
            modes,
            stale,
            out_root,
            remove_stale_paths_fn=lambda paths: remove_stale_paths_for_packager_fn(
                paths,
                validate_existing_destination_fn=validate_existing_destination_fn,
            ),
            validate_existing_destination_fn=validate_existing_destination_fn,
        ),
        promote_staged_output_fn=lambda req,
        stage: promote_staged_output_for_packager_fn(
            req,
            stage,
            suffix=suffix,
            write_json_fn=write_json_fn,
            os_module=os_module,
            shutil_module=shutil_module,
            promotion_receipt_path_fn=promotion_receipt_path_fn,
        ),
        validate_existing_destination_fn=validate_existing_destination_fn,
        write_json_fn=write_json_fn,
        shutil_module=shutil_module,
        uuid_module=uuid_module,
    )
