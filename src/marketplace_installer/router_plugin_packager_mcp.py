from __future__ import annotations

from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


__all__ = [
    "mcp_launch_contract_invocation_payload",
    "validate_mcp_descriptor_round_trip",
]


def mcp_descriptor_payload(contract: Any) -> dict[str, Any]:
    package_selector = contract.package_name
    if contract.schema_version == 3 and contract.package_version:
        package_selector = f"{package_selector}=={contract.package_version}"
    args = [
        "--python",
        contract.python_version,
        "--default-index",
        contract.package_index,
        "--from",
        package_selector,
        contract.entrypoint,
        *contract.extra_args,
        "--stdio",
    ]
    descriptor: dict[str, Any] = {"command": contract.command, "args": args}
    if contract.environment:
        descriptor["env"] = dict(contract.environment)
    return {"mcpServers": {contract.server_id: descriptor}}


def mcp_launch_contract_provenance(contract: Any) -> dict[str, Any]:
    payload = {
        "schema_version": contract.schema_version,
        "input_schema_version": contract.input_schema_version,
        "resolved_schema_version": contract.schema_version,
        "server_id": contract.server_id,
        "transport": contract.transport,
        "command": contract.command,
        "python_version": contract.python_version,
        "package_index": contract.package_index,
        "package_name": contract.package_name,
        "entrypoint": contract.entrypoint,
        "extra_args": list(contract.extra_args),
        "forbidden_arg_fragments": list(contract.forbidden_arg_fragments),
        "environment": dict(contract.environment),
        "environment_authority": contract.environment_authority,
    }
    if contract.schema_version == 3:
        payload["package_version"] = contract.package_version
    return payload


def mcp_launch_contract_invocation_payload(contract: Any) -> dict[str, Any]:
    payload = {
        "schema_version": contract.schema_version,
        "server_id": contract.server_id,
        "transport": contract.transport,
        "command": contract.command,
        "python_version": contract.python_version,
        "package_index": contract.package_index,
        "package_name": contract.package_name,
        "entrypoint": contract.entrypoint,
        "extra_args": list(contract.extra_args),
        "forbidden_arg_fragments": list(contract.forbidden_arg_fragments),
        "environment": dict(contract.environment),
        "environment_authority": contract.environment_authority,
    }
    if contract.schema_version == 3:
        payload["package_version"] = contract.package_version
    return payload


def validate_mcp_descriptor_round_trip(
    contract: Any, *, mcp_descriptor_payload_fn: Any = mcp_descriptor_payload
) -> None:
    payload = mcp_descriptor_payload_fn(contract)
    mcp_servers = payload.get("mcpServers")
    descriptor = (
        mcp_servers.get(contract.server_id) if isinstance(mcp_servers, dict) else None
    )
    package_selector = contract.package_name
    if contract.schema_version == 3 and contract.package_version:
        package_selector = f"{package_selector}=={contract.package_version}"
    expected: dict[str, Any] = {
        "command": contract.command,
        "args": [
            "--python",
            contract.python_version,
            "--default-index",
            contract.package_index,
            "--from",
            package_selector,
            contract.entrypoint,
            *contract.extra_args,
            "--stdio",
        ],
    }
    if contract.environment:
        expected["env"] = dict(contract.environment)
    if (
        not isinstance(mcp_servers, dict)
        or sorted(mcp_servers) != [contract.server_id]
        or descriptor != expected
    ):
        raise PackagerError(
            "invalid_mcp_descriptor_round_trip",
            "generated .mcp.json does not round-trip from the launch contract",
            {"server_id": contract.server_id},
        )
