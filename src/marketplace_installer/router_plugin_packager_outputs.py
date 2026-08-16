from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError
from marketplace_installer.router_plugin_packager_text import (
    collect_semantic_summaries,
    collect_trigger_phrases,
    join_human_list,
    normalize_whitespace,
    strip_terminal_punctuation,
    truncate_sentence,
)


__all__ = ["router_skill_content", "semantic_router_frontmatter_description"]


@dataclass
class OutputAccumulator:
    outputs: dict[str, bytes] = field(default_factory=dict)
    output_modes: dict[str, int] = field(default_factory=dict)
    entries: list[dict[str, Any]] = field(default_factory=list)
    payload_manifest_entries: list[dict[str, Any]] = field(default_factory=list)

    def add_output(
        self, relative_path: Path, content: bytes, entry: dict[str, Any]
    ) -> None:
        key = relative_path.as_posix()
        file_mode = int(entry["file_mode"], 8)
        if key in self.outputs:
            if self.outputs[key] != content or self.output_modes[key] != file_mode:
                raise PackagerError(
                    "duplicate_destination_path",
                    "multiple rendered artifacts resolve to the same destination path or mode",
                    {"path": key},
                )
            return
        self.outputs[key] = content
        self.output_modes[key] = file_mode
        self.entries.append(entry)

    def record_payload_entry(
        self,
        *,
        relative_path: Path,
        content: bytes,
        source_reference: str,
        acquisition_mode: str,
        ownership_role: str,
        ownership_class: str | None,
        hash_bytes: Any,
        file_mode: int = 0o644,
        source_hash: str | None = None,
        provenance_reference: str | None = None,
        transform_kind: str | None = None,
    ) -> dict[str, Any]:
        entry = {
            "relative_output_path": relative_path.as_posix(),
            "source_reference": source_reference,
            "acquisition_mode": acquisition_mode,
            "file_type": "file",
            "file_mode": oct(file_mode),
            "symlink_policy": "forbidden",
            "content_hash": hash_bytes(content),
            "ownership_role": ownership_role,
            "ownership_class": ownership_class,
        }
        self.payload_manifest_entries.append(entry)
        return {
            "kind": transform_kind or "payload-artifact",
            "path": relative_path.as_posix(),
            "content_hash": entry["content_hash"],
            "source_reference": source_reference,
            "transform_kind": transform_kind or acquisition_mode,
            "source_hash": source_hash,
            "ownership_role": ownership_role,
            "ownership_class": ownership_class,
            "file_mode": oct(file_mode),
            "acquisition_mode": acquisition_mode,
            "provenance_reference": provenance_reference,
        }


@dataclass(frozen=True)
class BuildOutputsPackagerDeps:
    build_outputs_for_packager_fn: Any
    collect_skill_sources_fn: Any
    validate_skill_release_consistency_fn: Any
    build_record_payload_entry_for_packager_fn: Any
    populate_primary_outputs_for_packager_fn: Any
    prepare_packaging_artifacts_for_packager_fn: Any
    finalize_release_state_for_packager_fn: Any
    add_direct_skill_outputs_fn: Any
    add_router_outputs_fn: Any
    add_module_outputs_fn: Any
    add_native_interface_asset_outputs_fn: Any
    add_branding_outputs_fn: Any
    add_payload_asset_outputs_fn: Any
    compute_version_fn: Any
    plugin_id_fn: Any
    emit_packaging_artifacts_fn: Any
    plugin_manifest_fn: Any
    validate_mcp_descriptor_round_trip_fn: Any
    mcp_descriptor_payload_fn: Any
    staging_plan_payload_fn: Any
    add_proof_artifacts_fn: Any
    native_generated_tree_digest_from_outputs_fn: Any
    build_receipt_payload_fn: Any
    build_state_payloads_fn: Any
    emit_native_state_outputs_fn: Any
    build_normalized_request_summary_fn: Any
    build_output_state_fn: Any
    payload_asset_records_fn: Any
    mcp_launch_contract_provenance_fn: Any
    mcp_authority_identity_fn: Any
    native_receipt_contract_fn: Any
    publication_metadata_name: str
    mcp_descriptor_name: str
    staging_plan_name: str
    receipt_name: str
    decision_state_dir: str
    native_routed_decision_state_name: str
    native_routed_bootstrap_state_name: str
    normalize_slug: Any
    hash_bytes: Any
    hash_text: Any
    canonical_json_bytes: Any


def build_record_payload_entry_for_packager(
    accumulator: OutputAccumulator, *, hash_bytes: Any
) -> Any:
    def record_payload_entry(
        *,
        relative_path: Path,
        content: bytes,
        source_reference: str,
        acquisition_mode: str,
        ownership_role: str,
        ownership_class: str | None,
        file_mode: int = 0o644,
        source_hash: str | None = None,
        provenance_reference: str | None = None,
        transform_kind: str | None = None,
    ) -> dict[str, Any]:
        return accumulator.record_payload_entry(
            relative_path=relative_path,
            content=content,
            source_reference=source_reference,
            acquisition_mode=acquisition_mode,
            ownership_role=ownership_role,
            ownership_class=ownership_class,
            hash_bytes=hash_bytes,
            file_mode=file_mode,
            source_hash=source_hash,
            provenance_reference=provenance_reference,
            transform_kind=transform_kind,
        )

    return record_payload_entry


def semantic_router_frontmatter_description(
    router: Any,
    modules: list[dict[str, str]],
    *,
    normalize_whitespace: Any = normalize_whitespace,
    collect_semantic_summaries: Any = collect_semantic_summaries,
    collect_trigger_phrases: Any = collect_trigger_phrases,
    join_human_list: Any = join_human_list,
    strip_terminal_punctuation: Any = strip_terminal_punctuation,
    truncate_sentence: Any = truncate_sentence,
) -> str:
    module_descriptions = [
        normalize_whitespace(str(module["description"]))
        for module in modules
        if normalize_whitespace(str(module["description"]))
    ]
    if not module_descriptions:
        return normalize_whitespace(router.description)
    summaries = collect_semantic_summaries(module_descriptions)
    if not summaries:
        return normalize_whitespace(router.description)
    if len(summaries) == 1:
        summary = summaries[0]
    else:
        summary = (
            join_human_list(
                [strip_terminal_punctuation(item) for item in summaries[:3]]
            )
            + "."
        )
    triggers = collect_trigger_phrases(module_descriptions)
    if triggers:
        return truncate_sentence(f"{summary} Trigger: {join_human_list(triggers)}.")
    return truncate_sentence(summary)


def router_skill_content(
    router: Any,
    modules: list[dict[str, str]],
    frontmatter_description: str,
) -> str:
    module_lines = "\n".join(
        f"- `{module['slug']}` — {module['description']}" for module in modules
    )
    ordinary_specific_lines = ""
    if router.router_slug == "workflow-router":
        ordinary_specific_lines = (
            "If a later turn asks to classify or route work that is itself owned by "
            "`workflow-router`, treat that as a concrete request for the "
            "`workflow-router` module and open it in the same turn.\n"
            "Do not stop at meta-routing commentary once that later turn has "
            "supplied the concrete routing request.\n"
        )
    elif router.router_slug == "research-and-writing":
        ordinary_specific_lines = (
            "For embedded first/second prompts, treat the first embedded request as "
            "already supplied; do not ask the user to send, resend, or restate "
            "that first request.\n"
            "If the first embedded request classifies as `academic-paper-markdown`, "
            "open that module in the same turn even when the paper identifier, "
            "source text, or output path is still missing.\n"
            "Do not stop at paired classification of a later empirical-review "
            "request before opening the first matched module.\n"
        )
    elif router.router_slug == "obsidian-memory":
        ordinary_specific_lines = (
            "For embedded first/second prompts, treat the first embedded request as "
            "already supplied; do not ask the user to provide the request text "
            "again.\n"
            "When the earliest request fits `obsidian-memory`, open that module in "
            "the same turn even if the operation, topic, vault, or path scope is "
            "still missing.\n"
            "After this router is selected, never say that no `obsidian-memory` "
            "module or plugin is available; use the bundled module and let it ask "
            "for missing details.\n"
        )
    elif router.router_slug == "agent-development":
        ordinary_specific_lines = (
            "For embedded first/second prompts, treat the first embedded request as "
            "already supplied; do not ask the user to send the first request "
            "again.\n"
            "When the earliest request classifies as `agent-development`, open that "
            "module in the same turn even if the agent goal, target system, or "
            "desired artifact is still missing.\n"
            "Do not stop at paired classification of a later `agent-evaluation` "
            "request before opening the first matched module.\n"
        )
    return (
        "---\n"
        f"name: {router.router_slug}\n"
        f"description: {frontmatter_description}\n"
        "---\n\n"
        f"# {router.router_slug}\n\n"
        "Classify the request, then read only the matching module from "
        "`references/modules/index.json`.\n"
        "After this router is selected, do not answer from this router file alone: "
        "select exactly one listed module and open its exact `path` before answering.\n"
        "Resolve only the earliest request that still needs module selection; do not "
        "read a second listed module from the same turn while the earlier request "
        "remains unresolved.\n"
        "When a turn only frames context, alternatives, or deferred follow-up work, "
        "do not open a module yet.\n"
        "After the earliest unresolved request matches one listed module, open that "
        "module in the same turn; classification alone is incomplete.\n"
        "After opening that earliest matched module, stop for that turn; do not "
        "classify, summarize, or open a later module from the same user turn until "
        "the earlier request is resolved.\n"
        "If a later turn narrows a previously classified unresolved request to one "
        "listed module, open that module in that later turn instead of restating the "
        "route.\n"
        "When the prompt already embeds the request text to classify, including "
        "labeled first/second requests or a later-turn follow-up request, treat "
        "that embedded text as the concrete request; do not ask the user to resend, "
        "relabel, or restate it.\n"
        "If the earliest request narrows to one listed module but downstream task "
        "details are still missing, open that module anyway; the module may ask for "
        "the missing details.\n"
        "After the host has selected this router, do not claim that this router, "
        "its listed modules, or its plugin are unavailable in the current runtime.\n"
        f"{ordinary_specific_lines}"
        "If no module matches, ask for the missing intent rather than loading every module.\n\n"
        "## Available internal modules\n\n"
        f"{module_lines}\n"
    )


def add_router_outputs(
    request: Any,
    skills: dict[str, dict[str, Any]],
    add_output: Any,
    record_payload_entry: Any,
    *,
    semantic_router_frontmatter_description_fn: Any,
    router_skill_content_fn: Any,
) -> None:
    for router in request.routers:
        router_modules = [
            {
                "slug": skill_id,
                "description": skills[skill_id]["description"],
                "path": f"references/modules/{skill_id}/instructions.md",
            }
            for skill_id in router.member_skill_ids
        ]
        frontmatter_description = semantic_router_frontmatter_description_fn(
            router, router_modules
        )
        router_rel = Path("skills") / router.router_slug / "SKILL.md"
        content = router_skill_content_fn(
            router, router_modules, frontmatter_description
        ).encode("utf-8")
        add_output(
            router_rel,
            content,
            {
                **record_payload_entry(
                    relative_path=router_rel,
                    content=content,
                    source_reference=f"router:{router.router_slug}",
                    acquisition_mode="generated",
                    ownership_role="router-skill",
                    ownership_class=None,
                    transform_kind="router-skill",
                ),
                "router_slug": router.router_slug,
                "frontmatter_description": frontmatter_description,
            },
        )
        index_rel = (
            Path("skills")
            / router.router_slug
            / "references"
            / "modules"
            / "index.json"
        )
        index_content = (
            json.dumps(
                {"router": router.router_slug, "modules": router_modules},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        add_output(
            index_rel,
            index_content,
            {
                **record_payload_entry(
                    relative_path=index_rel,
                    content=index_content,
                    source_reference=f"router-index:{router.router_slug}",
                    acquisition_mode="generated",
                    ownership_role="module-index",
                    ownership_class=None,
                    transform_kind="module-index",
                ),
                "router_slug": router.router_slug,
            },
        )


def add_direct_skill_outputs(
    request: Any,
    skills: dict[str, dict[str, Any]],
    add_output: Any,
    record_payload_entry: Any,
    *,
    hash_bytes: Any,
) -> None:
    for skill_id, info in sorted(skills.items()):
        skill_root = Path("skills") / skill_id
        skill_file = Path(info["skill_file"])
        skill_bytes = skill_file.read_bytes()
        skill_rel = skill_root / "SKILL.md"
        add_output(
            skill_rel,
            skill_bytes,
            {
                **record_payload_entry(
                    relative_path=skill_rel,
                    content=skill_bytes,
                    source_reference=str(
                        skill_file.relative_to(request.repository_root)
                    ),
                    acquisition_mode="copied",
                    ownership_role="visible-skill",
                    ownership_class=None,
                    file_mode=skill_file.stat().st_mode & 0o777,
                    source_hash=hash_bytes(skill_bytes),
                    transform_kind="visible-skill",
                ),
                "skill_id": skill_id,
            },
        )
        for support_path, relative_to_skill in info["support_files"]:
            out_rel = skill_root / relative_to_skill
            support_bytes = support_path.read_bytes()
            add_output(
                out_rel,
                support_bytes,
                {
                    **record_payload_entry(
                        relative_path=out_rel,
                        content=support_bytes,
                        source_reference=str(
                            support_path.relative_to(request.repository_root)
                        ),
                        acquisition_mode="copied",
                        ownership_role="skill-support",
                        ownership_class=None,
                        file_mode=support_path.stat().st_mode & 0o777,
                        source_hash=hash_bytes(support_bytes),
                        transform_kind="skill-support",
                    ),
                    "skill_id": skill_id,
                },
            )


def add_module_outputs(
    request: Any,
    skills: dict[str, dict[str, Any]],
    add_output: Any,
    record_payload_entry: Any,
    *,
    hash_bytes: Any,
) -> None:
    for skill_id, info in sorted(skills.items()):
        router_slug = next(
            router.router_slug
            for router in request.routers
            if skill_id in router.member_skill_ids
        )
        module_base = Path("skills") / router_slug / "references" / "modules" / skill_id
        instructions_rel = module_base / "instructions.md"
        skill_file = Path(info["skill_file"])
        skill_bytes = skill_file.read_bytes()
        add_output(
            instructions_rel,
            skill_bytes,
            {
                **record_payload_entry(
                    relative_path=instructions_rel,
                    content=skill_bytes,
                    source_reference=str(
                        skill_file.relative_to(request.repository_root)
                    ),
                    acquisition_mode="copied",
                    ownership_role="module-instructions",
                    ownership_class=None,
                    file_mode=skill_file.stat().st_mode & 0o777,
                    source_hash=hash_bytes(skill_bytes),
                    transform_kind="module-instructions",
                ),
                "skill_id": skill_id,
                "router_slug": router_slug,
            },
        )
        for support_path, relative_to_skill in info["support_files"]:
            out_rel = module_base / relative_to_skill
            support_bytes = support_path.read_bytes()
            add_output(
                out_rel,
                support_bytes,
                {
                    **record_payload_entry(
                        relative_path=out_rel,
                        content=support_bytes,
                        source_reference=str(
                            support_path.relative_to(request.repository_root)
                        ),
                        acquisition_mode="copied",
                        ownership_role="module-support",
                        ownership_class=None,
                        file_mode=support_path.stat().st_mode & 0o777,
                        source_hash=hash_bytes(support_bytes),
                        transform_kind="module-support",
                    ),
                    "skill_id": skill_id,
                    "router_slug": router_slug,
                },
            )


def add_branding_outputs(
    request: Any,
    add_output: Any,
    record_payload_entry: Any,
) -> dict[str, str]:
    branding_output_paths: dict[str, str] = {}
    for key, relative_path in sorted(request.plugin_metadata.branding_assets.items()):
        source_path = (request.repository_root / relative_path).resolve()
        content = source_path.read_bytes()
        out_rel = Path(relative_path)
        branding_output_paths[key] = out_rel.as_posix()
        add_output(
            out_rel,
            content,
            {
                **record_payload_entry(
                    relative_path=out_rel,
                    content=content,
                    source_reference=str(
                        source_path.relative_to(request.repository_root)
                    ),
                    acquisition_mode="copied",
                    ownership_role="branding-asset",
                    ownership_class=None,
                    file_mode=source_path.stat().st_mode & 0o777,
                    source_hash=None,
                    transform_kind="branding-asset",
                ),
                "branding_key": key,
            },
        )
    return branding_output_paths


def iter_native_interface_asset_paths(request: Any) -> list[str]:
    if request.input_mode != "native_routed":
        return []
    values: list[str] = []
    for key in ("composerIcon", "logo", "logoDark"):
        value = request.plugin_metadata.interface.get(key)
        if isinstance(value, str):
            values.append(value)
    screenshots = request.plugin_metadata.interface.get("screenshots")
    if isinstance(screenshots, list):
        values.extend(item for item in screenshots if isinstance(item, str))
    return values


def validate_pregenerated_provenance(
    request: Any,
    asset: Any,
    source_path: Path,
    *,
    resolve_local_path: Any,
    validate_relative_path: Any,
    load_json: Any,
    hash_tree: Any,
    hash_bytes: Any,
) -> dict[str, Any]:
    assert asset.provenance_path is not None
    provenance_path = resolve_local_path(
        request.repository_root, str(asset.provenance_path)
    )
    validate_relative_path(
        request.repository_root,
        provenance_path,
        f"payload_assets.{asset.asset_id}.provenance_path",
    )
    payload = load_json(provenance_path)
    required = (
        "artifact_path",
        "source_digest",
        "generator_identity",
        "generator_version",
        "generator_parameters",
        "freshness_basis",
        "compatibility",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        raise PackagerError(
            "pregenerated_missing_proof",
            "pre_generated provenance is missing required fields",
            {
                "asset_id": asset.asset_id,
                "provenance_path": str(provenance_path),
                "missing_fields": missing,
            },
        )
    expected_artifact = str(source_path.relative_to(request.repository_root))
    if str(payload["artifact_path"]) != expected_artifact:
        raise PackagerError(
            "pregenerated_incompatible",
            "pre_generated provenance artifact_path does not match the declared source",
            {
                "asset_id": asset.asset_id,
                "artifact_path": payload["artifact_path"],
                "expected_artifact_path": expected_artifact,
            },
        )
    current_digest = (
        hash_tree(source_path)
        if source_path.is_dir()
        else hash_bytes(source_path.read_bytes())
    )
    if str(payload["source_digest"]) != current_digest:
        raise PackagerError(
            "pregenerated_stale_proof",
            "pre_generated provenance source_digest does not match current source content",
            {"asset_id": asset.asset_id, "source": expected_artifact},
        )
    compatibility = payload.get("compatibility")
    if not isinstance(compatibility, dict):
        raise PackagerError(
            "pregenerated_incompatible",
            "pre_generated provenance compatibility must be a mapping",
            {"asset_id": asset.asset_id},
        )
    expected_root = request.source_root_text
    if compatibility.get("source_root") != expected_root:
        raise PackagerError(
            "pregenerated_incompatible",
            "pre_generated provenance source_root is incompatible with the selected source_root",
            {
                "asset_id": asset.asset_id,
                "source_root": compatibility.get("source_root"),
                "expected_source_root": expected_root,
            },
        )
    return payload


def iter_glob_payload_files(source_path: Path, asset: Any) -> list[tuple[Path, Path]]:
    assert asset.source_glob is not None
    files: list[tuple[Path, Path]] = []
    for path in sorted(source_path.glob(asset.source_glob)):
        if path.is_symlink():
            raise PackagerError(
                "invalid_payload_asset",
                "payload asset source_glob may not resolve to a symlink",
                {"asset_id": asset.asset_id, "path": str(path)},
            )
        if not path.is_file():
            continue
        relative = path.relative_to(source_path)
        if any(
            fnmatch.fnmatch(relative.as_posix(), pattern) for pattern in asset.exclude
        ):
            continue
        files.append((path, relative))
    if files:
        return files
    raise PackagerError(
        "empty_payload_asset_glob",
        "payload asset source_glob did not select any files",
        {
            "asset_id": asset.asset_id,
            "source": asset.source,
            "source_glob": asset.source_glob,
        },
    )


def iter_payload_files(
    request: Any,
    asset: Any,
    *,
    resolve_local_path: Any,
    iter_glob_payload_files_fn: Any,
) -> list[tuple[Path, Path]]:
    source_path = resolve_local_path(request.repository_root, asset.source)
    if asset.source_glob is not None:
        return iter_glob_payload_files_fn(source_path, asset)
    if source_path.is_file():
        return [(source_path, Path(source_path.name))]
    if not source_path.is_dir():
        raise PackagerError(
            "missing_payload_asset_source",
            "payload asset source must resolve to a file or directory",
            {"asset_id": asset.asset_id, "source": asset.source},
        )
    files: list[tuple[Path, Path]] = []
    for path in sorted(source_path.rglob("*")):
        if path.is_symlink():
            raise PackagerError(
                "invalid_payload_asset",
                "payload asset source tree may not contain symlinks",
                {
                    "asset_id": asset.asset_id,
                    "path": str(path.relative_to(source_path)),
                },
            )
        if not path.is_file():
            continue
        relative = path.relative_to(source_path)
        if any(
            fnmatch.fnmatch(relative.as_posix(), pattern) for pattern in asset.exclude
        ):
            continue
        files.append((path, relative))
    return files


def add_native_interface_asset_outputs(
    request: Any,
    add_output: Any,
    record_payload_entry: Any,
    *,
    iter_native_interface_asset_paths_fn: Any,
    validate_relative_path: Any,
    hash_bytes: Any,
) -> None:
    for raw_path in iter_native_interface_asset_paths_fn(request):
        relative = Path(raw_path)
        if not raw_path.startswith("./"):
            raise PackagerError(
                "invalid_source_plugin_manifest",
                "native interface asset paths must start with ./",
                {"path": raw_path},
            )
        source_path = (request.source_root / relative).resolve()
        validate_relative_path(request.source_root, source_path, "interface asset path")
        if source_path.is_symlink() or not source_path.is_file():
            raise PackagerError(
                "invalid_source_plugin_manifest",
                "native interface asset paths must resolve to regular files",
                {"path": raw_path},
            )
        content = source_path.read_bytes()
        add_output(
            relative,
            content,
            {
                **record_payload_entry(
                    relative_path=relative,
                    content=content,
                    source_reference=str(
                        source_path.relative_to(request.repository_root)
                    ),
                    acquisition_mode="copied",
                    ownership_role="branding-asset",
                    ownership_class=None,
                    file_mode=source_path.stat().st_mode & 0o777,
                    source_hash=hash_bytes(content),
                    transform_kind="branding-asset",
                ),
                "branding_key": raw_path,
            },
        )


def add_payload_asset_outputs(
    request: Any,
    add_output: Any,
    record_payload_entry: Any,
    *,
    resolve_local_path: Any,
    validate_pregenerated_provenance_fn: Any,
    render_template_text: Any,
    hash_bytes: Any,
    iter_payload_files_fn: Any,
) -> None:
    for asset in request.payload_assets:
        source_path = resolve_local_path(request.repository_root, asset.source)
        provenance_payload = None
        if asset.acquisition_mode == "pre_generated":
            provenance_payload = validate_pregenerated_provenance_fn(
                request, asset, source_path
            )
        if asset.acquisition_mode == "templated":
            template_bytes = source_path.read_bytes()
            rendered_text = render_template_text(
                template_bytes.decode("utf-8"), asset.template_parameters
            )
            content = rendered_text.encode("utf-8")
            out_rel = Path(asset.destination)
            add_output(
                out_rel,
                content,
                record_payload_entry(
                    relative_path=out_rel,
                    content=content,
                    source_reference=str(
                        source_path.relative_to(request.repository_root)
                    ),
                    acquisition_mode=asset.acquisition_mode,
                    ownership_role=asset.ownership_role,
                    ownership_class=asset.ownership_class,
                    source_hash=hash_bytes(template_bytes),
                    provenance_reference=None,
                    transform_kind="payload-asset",
                ),
            )
            continue
        provenance_reference = None
        if provenance_payload is not None and asset.provenance_path is not None:
            provenance_reference = str(
                resolve_local_path(
                    request.repository_root, str(asset.provenance_path)
                ).relative_to(request.repository_root)
            )
        for path, relative in iter_payload_files_fn(request, asset):
            out_rel = Path(asset.destination)
            if source_path.is_dir():
                out_rel = out_rel / relative
            content = path.read_bytes()
            add_output(
                out_rel,
                content,
                record_payload_entry(
                    relative_path=out_rel,
                    content=content,
                    source_reference=str(path.relative_to(request.repository_root)),
                    acquisition_mode=asset.acquisition_mode,
                    ownership_role=asset.ownership_role,
                    ownership_class=asset.ownership_class,
                    file_mode=path.stat().st_mode & 0o777,
                    source_hash=hash_bytes(content),
                    provenance_reference=provenance_reference,
                    transform_kind="payload-asset",
                ),
            )


def populate_primary_outputs_for_packager(
    request: Any,
    skills: dict[str, dict[str, Any]],
    add_output: Any,
    record_payload_entry: Any,
    *,
    add_direct_skill_outputs_fn: Any,
    add_router_outputs_fn: Any,
    add_module_outputs_fn: Any,
    add_native_interface_asset_outputs_fn: Any,
    add_branding_outputs_fn: Any,
    add_payload_asset_outputs_fn: Any,
) -> dict[str, str]:
    if request.mcp_packaging is not None:
        add_direct_skill_outputs_fn(request, skills, add_output, record_payload_entry)
    else:
        add_router_outputs_fn(request, skills, add_output, record_payload_entry)
        add_module_outputs_fn(request, skills, add_output, record_payload_entry)
        add_native_interface_asset_outputs_fn(request, add_output, record_payload_entry)
    branding_output_paths = add_branding_outputs_fn(
        request, add_output, record_payload_entry
    )
    add_payload_asset_outputs_fn(request, add_output, record_payload_entry)
    return branding_output_paths


def build_outputs_for_packager(
    request: Any,
    *,
    collect_skill_sources_fn: Any,
    validate_skill_release_consistency_fn: Any,
    build_record_payload_entry_for_packager_fn: Any,
    populate_primary_outputs_for_packager_fn: Any,
    prepare_packaging_artifacts_for_packager_fn: Any,
    finalize_release_state_for_packager_fn: Any,
    add_direct_skill_outputs_fn: Any,
    add_router_outputs_fn: Any,
    add_module_outputs_fn: Any,
    add_native_interface_asset_outputs_fn: Any,
    add_branding_outputs_fn: Any,
    add_payload_asset_outputs_fn: Any,
    compute_version_fn: Any,
    plugin_id_fn: Any,
    emit_packaging_artifacts_fn: Any,
    plugin_manifest_fn: Any,
    validate_mcp_descriptor_round_trip_fn: Any,
    mcp_descriptor_payload_fn: Any,
    staging_plan_payload_fn: Any,
    add_proof_artifacts_fn: Any,
    native_generated_tree_digest_from_outputs_fn: Any,
    build_receipt_payload_fn: Any,
    build_state_payloads_fn: Any,
    emit_native_state_outputs_fn: Any,
    build_normalized_request_summary_fn: Any,
    build_output_state_fn: Any,
    payload_asset_records_fn: Any,
    mcp_launch_contract_provenance_fn: Any,
    mcp_authority_identity_fn: Any,
    native_receipt_contract_fn: Any,
    publication_metadata_name: str,
    mcp_descriptor_name: str,
    staging_plan_name: str,
    receipt_name: str,
    decision_state_dir: str,
    native_routed_decision_state_name: str,
    native_routed_bootstrap_state_name: str,
    normalize_slug: Any,
    hash_bytes: Any,
    hash_text: Any,
    canonical_json_bytes: Any,
) -> tuple[dict[str, bytes], dict[str, int], dict[str, Any], str]:
    accumulator = OutputAccumulator()
    skills = collect_skill_sources_fn(request)
    validate_skill_release_consistency_fn(request, skills)
    record_payload_entry = build_record_payload_entry_for_packager_fn(
        accumulator, hash_bytes=hash_bytes
    )
    branding_output_paths = populate_primary_outputs_for_packager_fn(
        request,
        skills,
        accumulator.add_output,
        record_payload_entry,
        add_direct_skill_outputs_fn=add_direct_skill_outputs_fn,
        add_router_outputs_fn=add_router_outputs_fn,
        add_module_outputs_fn=add_module_outputs_fn,
        add_native_interface_asset_outputs_fn=add_native_interface_asset_outputs_fn,
        add_branding_outputs_fn=add_branding_outputs_fn,
        add_payload_asset_outputs_fn=add_payload_asset_outputs_fn,
    )
    (
        plugin_id,
        version,
        mcp_descriptor_bytes_sha256,
        mcp_descriptor_canonical_sha256,
    ) = prepare_packaging_artifacts_for_packager_fn(
        request,
        outputs=accumulator.outputs,
        branding_output_paths=branding_output_paths,
        add_output=accumulator.add_output,
        record_payload_entry=record_payload_entry,
        publication_metadata_name=publication_metadata_name,
        mcp_descriptor_name=mcp_descriptor_name,
        staging_plan_name=staging_plan_name,
        compute_version_fn=compute_version_fn,
        plugin_id_fn=plugin_id_fn,
        normalize_slug=normalize_slug,
        hash_bytes=hash_bytes,
        hash_text=hash_text,
        emit_packaging_artifacts_fn=emit_packaging_artifacts_fn,
        plugin_manifest_fn=plugin_manifest_fn,
        validate_mcp_descriptor_round_trip_fn=validate_mcp_descriptor_round_trip_fn,
        mcp_descriptor_payload_fn=mcp_descriptor_payload_fn,
        staging_plan_payload_fn=staging_plan_payload_fn,
        canonical_json_bytes=canonical_json_bytes,
    )
    state = finalize_release_state_for_packager_fn(
        request,
        accumulator=accumulator,
        record_payload_entry_fn=record_payload_entry,
        plugin_id=plugin_id,
        version=version,
        receipt_name=receipt_name,
        mcp_descriptor_bytes_sha256=mcp_descriptor_bytes_sha256,
        mcp_descriptor_canonical_sha256=mcp_descriptor_canonical_sha256,
        decision_state_dir=decision_state_dir,
        native_routed_decision_state_name=native_routed_decision_state_name,
        native_routed_bootstrap_state_name=native_routed_bootstrap_state_name,
        add_proof_artifacts_fn=add_proof_artifacts_fn,
        native_generated_tree_digest_from_outputs_fn=native_generated_tree_digest_from_outputs_fn,
        build_receipt_payload_fn=build_receipt_payload_fn,
        build_state_payloads_fn=build_state_payloads_fn,
        emit_native_state_outputs_fn=emit_native_state_outputs_fn,
        build_normalized_request_summary_fn=build_normalized_request_summary_fn,
        build_output_state_fn=build_output_state_fn,
        payload_asset_records_fn=payload_asset_records_fn,
        mcp_launch_contract_provenance_fn=mcp_launch_contract_provenance_fn,
        mcp_authority_identity_fn=mcp_authority_identity_fn,
        native_receipt_contract_fn=native_receipt_contract_fn,
        normalize_slug=normalize_slug,
    )
    return (accumulator.outputs, accumulator.output_modes, state, version)


def build_outputs_with_packager_deps(
    request: Any,
    *,
    deps: BuildOutputsPackagerDeps,
) -> tuple[dict[str, bytes], dict[str, int], dict[str, Any], str]:
    return deps.build_outputs_for_packager_fn(
        request,
        collect_skill_sources_fn=deps.collect_skill_sources_fn,
        validate_skill_release_consistency_fn=deps.validate_skill_release_consistency_fn,
        build_record_payload_entry_for_packager_fn=deps.build_record_payload_entry_for_packager_fn,
        populate_primary_outputs_for_packager_fn=deps.populate_primary_outputs_for_packager_fn,
        prepare_packaging_artifacts_for_packager_fn=deps.prepare_packaging_artifacts_for_packager_fn,
        finalize_release_state_for_packager_fn=deps.finalize_release_state_for_packager_fn,
        add_direct_skill_outputs_fn=deps.add_direct_skill_outputs_fn,
        add_router_outputs_fn=deps.add_router_outputs_fn,
        add_module_outputs_fn=deps.add_module_outputs_fn,
        add_native_interface_asset_outputs_fn=deps.add_native_interface_asset_outputs_fn,
        add_branding_outputs_fn=deps.add_branding_outputs_fn,
        add_payload_asset_outputs_fn=deps.add_payload_asset_outputs_fn,
        compute_version_fn=deps.compute_version_fn,
        plugin_id_fn=deps.plugin_id_fn,
        emit_packaging_artifacts_fn=deps.emit_packaging_artifacts_fn,
        plugin_manifest_fn=deps.plugin_manifest_fn,
        validate_mcp_descriptor_round_trip_fn=deps.validate_mcp_descriptor_round_trip_fn,
        mcp_descriptor_payload_fn=deps.mcp_descriptor_payload_fn,
        staging_plan_payload_fn=deps.staging_plan_payload_fn,
        add_proof_artifacts_fn=deps.add_proof_artifacts_fn,
        native_generated_tree_digest_from_outputs_fn=deps.native_generated_tree_digest_from_outputs_fn,
        build_receipt_payload_fn=deps.build_receipt_payload_fn,
        build_state_payloads_fn=deps.build_state_payloads_fn,
        emit_native_state_outputs_fn=deps.emit_native_state_outputs_fn,
        build_normalized_request_summary_fn=deps.build_normalized_request_summary_fn,
        build_output_state_fn=deps.build_output_state_fn,
        payload_asset_records_fn=deps.payload_asset_records_fn,
        mcp_launch_contract_provenance_fn=deps.mcp_launch_contract_provenance_fn,
        mcp_authority_identity_fn=deps.mcp_authority_identity_fn,
        native_receipt_contract_fn=deps.native_receipt_contract_fn,
        publication_metadata_name=deps.publication_metadata_name,
        mcp_descriptor_name=deps.mcp_descriptor_name,
        staging_plan_name=deps.staging_plan_name,
        receipt_name=deps.receipt_name,
        decision_state_dir=deps.decision_state_dir,
        native_routed_decision_state_name=deps.native_routed_decision_state_name,
        native_routed_bootstrap_state_name=deps.native_routed_bootstrap_state_name,
        normalize_slug=deps.normalize_slug,
        hash_bytes=deps.hash_bytes,
        hash_text=deps.hash_text,
        canonical_json_bytes=deps.canonical_json_bytes,
    )
