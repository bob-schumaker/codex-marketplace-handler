from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


def execute_packager_command_for_packager(
    command: str,
    *,
    request: Any,
    receipt_name: str,
    suffix: str,
    native_receipt_format: str,
    load_json_fn: Any,
    write_json_fn: Any,
    validate_existing_destination_fn: Any,
    build_outputs_fn: Any,
    summarize_outputs_for_packager_fn: Any,
    recover_interrupted_promotion_for_packager_fn: Any,
    apply_generated_output_for_packager_fn: Any,
    native_receipt_contract_fn: Any,
    native_generated_tree_digest_from_disk_fn: Any,
    os_module: Any,
    shutil_module: Any,
    uuid_module: Any,
    validate_output_ownership_for_packager_fn: Any,
    write_output_tree_for_packager_fn: Any,
    remove_stale_paths_for_packager_fn: Any,
    promote_staged_output_for_packager_fn: Any,
    promotion_receipt_path_fn: Any,
    source_projection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    recover_interrupted_promotion_for_packager_fn(
        request.output_root,
        suffix=suffix,
        load_json_fn=load_json_fn,
        receipt_name=receipt_name,
    )
    outputs, output_modes, state, version = build_outputs_fn(request)
    summary = summarize_outputs_for_packager_fn(
        request=request,
        outputs=outputs,
        state=state,
        version=version,
        receipt_name=receipt_name,
        load_json_fn=load_json_fn,
        validate_existing_destination_fn=validate_existing_destination_fn,
    )
    if source_projection is not None:
        summary["source_projection"] = source_projection
    if command == "apply":
        apply_generated_output_for_packager_fn(
            request,
            outputs,
            output_modes,
            state,
            summary["stale_generated_paths"],
            receipt_name=receipt_name,
            load_json_fn=load_json_fn,
            native_receipt_format=native_receipt_format,
            native_receipt_contract_fn=native_receipt_contract_fn,
            native_generated_tree_digest_from_disk_fn=native_generated_tree_digest_from_disk_fn,
            suffix=suffix,
            validate_existing_destination_fn=validate_existing_destination_fn,
            write_json_fn=write_json_fn,
            os_module=os_module,
            shutil_module=shutil_module,
            uuid_module=uuid_module,
            validate_output_ownership_for_packager_fn=validate_output_ownership_for_packager_fn,
            write_output_tree_for_packager_fn=write_output_tree_for_packager_fn,
            remove_stale_paths_for_packager_fn=remove_stale_paths_for_packager_fn,
            promote_staged_output_for_packager_fn=promote_staged_output_for_packager_fn,
            promotion_receipt_path_fn=promotion_receipt_path_fn,
        )
    return summary


def run_packager_with_deps(
    command: str,
    invocation_path: Path,
    repo_root: Path,
    *,
    parse_invocation_fn: Any,
    normalize_request_fn: Any,
    execute_packager_command_for_packager_fn: Any,
    receipt_name: str,
    suffix: str,
    native_receipt_format: str,
    load_json_fn: Any,
    write_json_fn: Any,
    validate_existing_destination_fn: Any,
    build_outputs_fn: Any,
    summarize_outputs_for_packager_fn: Any,
    recover_interrupted_promotion_for_packager_fn: Any,
    apply_generated_output_for_packager_fn: Any,
    native_receipt_contract_fn: Any,
    native_generated_tree_digest_from_disk_fn: Any,
    os_module: Any,
    shutil_module: Any,
    uuid_module: Any,
    validate_output_ownership_for_packager_fn: Any,
    write_output_tree_for_packager_fn: Any,
    remove_stale_paths_for_packager_fn: Any,
    promote_staged_output_for_packager_fn: Any,
    promotion_receipt_path_fn: Any,
    verify_source_projection_fn: Any,
    load_json_bytes_fn: Any,
    hash_bytes_fn: Any,
) -> dict[str, Any]:
    resolved_repo_root = repo_root.resolve()
    invocation = parse_invocation_fn(invocation_path.resolve(), resolved_repo_root)
    source_projection = verify_source_projection_fn(
        invocation.source_projection_receipt,
        invocation.repository_root,
        load_json_bytes_fn=load_json_bytes_fn,
        hash_bytes_fn=hash_bytes_fn,
    )
    request = normalize_request_fn(invocation, resolved_repo_root)
    return execute_packager_command_for_packager_fn(
        command,
        request=request,
        receipt_name=receipt_name,
        suffix=suffix,
        native_receipt_format=native_receipt_format,
        load_json_fn=load_json_fn,
        write_json_fn=write_json_fn,
        validate_existing_destination_fn=validate_existing_destination_fn,
        build_outputs_fn=build_outputs_fn,
        summarize_outputs_for_packager_fn=summarize_outputs_for_packager_fn,
        recover_interrupted_promotion_for_packager_fn=recover_interrupted_promotion_for_packager_fn,
        apply_generated_output_for_packager_fn=apply_generated_output_for_packager_fn,
        native_receipt_contract_fn=native_receipt_contract_fn,
        native_generated_tree_digest_from_disk_fn=native_generated_tree_digest_from_disk_fn,
        os_module=os_module,
        shutil_module=shutil_module,
        uuid_module=uuid_module,
        validate_output_ownership_for_packager_fn=validate_output_ownership_for_packager_fn,
        write_output_tree_for_packager_fn=write_output_tree_for_packager_fn,
        remove_stale_paths_for_packager_fn=remove_stale_paths_for_packager_fn,
        promote_staged_output_for_packager_fn=promote_staged_output_for_packager_fn,
        promotion_receipt_path_fn=promotion_receipt_path_fn,
        source_projection=source_projection,
    )


def build_parser_for_packager(*, description: str, default_repo_root: Path) -> Any:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("command", choices=["plan", "apply"])
    parser.add_argument("--invocation", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=default_repo_root)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    return parser


def run_main_for_packager(
    argv: list[str] | None,
    *,
    build_parser_fn: Any,
    run_fn: Any,
    print_payload_fn: Any,
    print_error_payload_fn: Any,
    packager_error_type: type[Exception],
    description: str,
    default_repo_root: Path,
) -> int:
    parser = build_parser_fn(
        description=description, default_repo_root=default_repo_root
    )
    args = parser.parse_args(argv)
    try:
        payload = run_fn(args.command, args.invocation, args.repo_root)
    except packager_error_type as exc:
        print_error_payload_fn(exc.payload(), args.format)
        return 1
    print_payload_fn(payload, args.format)
    return 0
