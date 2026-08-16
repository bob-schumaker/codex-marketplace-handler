from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_constants import DECISION_STATE_DIR
from marketplace_installer.router_plugin_packager_errors import PackagerError
from marketplace_installer.router_plugin_packager_parsing import (
    has_hidden_path_segment,
    load_json,
)
from marketplace_installer.router_plugin_packager_receipts import (
    validate_existing_destination,
)


__all__ = [
    "discover_source_root",
    "discover_visible_skill_paths",
    "load_default_bootstrap_state",
]


def discover_visible_skill_paths(source_root: Path) -> list[Path]:
    if not source_root.is_dir():
        raise PackagerError(
            "missing_source_root",
            "source_root must resolve to a directory",
            {"source_root": str(source_root)},
        )
    discovered = [
        child
        for child in sorted(source_root.iterdir(), key=lambda item: item.name)
        if child.is_dir()
        and not child.name.startswith(".")
        and (child / "SKILL.md").is_file()
    ]
    if not discovered:
        raise PackagerError(
            "no_visible_skills",
            "repo_bootstrap could not discover any visible skills under source_root",
            {"source_root": str(source_root)},
        )
    return discovered


def discover_source_root(repository_root: Path) -> tuple[Path, str]:
    candidate_roots = {
        path.parent.parent.resolve()
        for path in repository_root.rglob("SKILL.md")
        if ".git" not in path.parts
        and ".codex-plugin" not in path.parts
        and "generated" not in path.parts
        and not has_hidden_path_segment(path.relative_to(repository_root))
    }
    if candidate_roots:
        if len(candidate_roots) == 1:
            common = next(iter(candidate_roots))
            return common, str(common.relative_to(repository_root.resolve()))
        raise PackagerError(
            "ambiguous_source_root",
            "repo_bootstrap could not determine one canonical source_root",
            {
                "candidates": sorted(
                    str(path.relative_to(repository_root)) for path in candidate_roots
                )
            },
        )
    raise PackagerError(
        "missing_source_root",
        "repo_bootstrap could not discover a canonical source_root",
        {"repository_root": str(repository_root)},
    )


def derive_source_root_from_skill_paths(
    repository_root: Path, skill_paths: list[str]
) -> tuple[Path, str]:
    skill_dirs = [(repository_root / raw_path).resolve() for raw_path in skill_paths]
    common = Path(
        os.path.commonpath([str(path.parent) for path in skill_dirs])
    ).resolve()
    return common, str(common.relative_to(repository_root.resolve()))


def normalize_skill_paths(
    invocation: Any,
    source_root: Path,
    *,
    discover_visible_skill_paths_fn: Any,
    resolve_local_path: Any,
    validate_relative_path: Any,
    normalize_slug: Any,
) -> tuple[list[str], list[str]]:
    if invocation.input_mode == "repo_bootstrap":
        skill_roots = discover_visible_skill_paths_fn(source_root)
        skill_paths = [
            str(path.relative_to(invocation.repository_root)) for path in skill_roots
        ]
    else:
        skill_paths = list(invocation.skill_paths)
    normalized_ids: list[str] = []
    normalized_paths: list[str] = []
    seen: dict[str, str] = {}
    for raw_path in skill_paths:
        skill_root = resolve_local_path(invocation.repository_root, raw_path)
        validate_relative_path(invocation.repository_root, skill_root, "skill_paths")
        try:
            skill_root.relative_to(source_root)
        except ValueError as exc:
            raise PackagerError(
                "skill_path_outside_source_root",
                "skill path must resolve under source_root",
                {"skill_path": raw_path, "source_root": str(source_root)},
            ) from exc
        skill_file = skill_root / "SKILL.md"
        if not skill_file.is_file():
            raise PackagerError(
                "missing_skill_source",
                "selected skill must contain SKILL.md under source_root",
                {"skill_path": raw_path, "skill_file": str(skill_file)},
            )
        skill_id = skill_root.name
        normalized = normalize_slug(skill_id)
        if normalized in seen:
            raise PackagerError(
                "duplicate_visible_skill",
                "normalized visible skill list contains a duplicate entry",
                {"skill_id": skill_id, "skill_paths": [seen[normalized], raw_path]},
            )
        seen[normalized] = raw_path
        normalized_ids.append(skill_id)
        normalized_paths.append(raw_path)
    return normalized_ids, normalized_paths


def collect_skill_sources(  # noqa: C901
    request: Any,
    *,
    resolve_local_path: Any,
    normalize_slug: Any,
    parse_markdown_frontmatter: Any,
    allowed_support_subtrees: tuple[str, ...],
    excluded_support_segments: set[str],
) -> dict[str, dict[str, Any]]:
    skills: dict[str, dict[str, Any]] = {}
    explicit_skill_roots: dict[str, Path] = {}
    for raw_path in request.skill_paths:
        resolved = resolve_local_path(request.repository_root, raw_path)
        skill_id = normalize_slug(resolved.name)
        if not skill_id:
            continue
        existing = explicit_skill_roots.get(skill_id)
        if existing is not None and existing != resolved:
            raise PackagerError(
                "duplicate_skill_id",
                "selected skill paths normalize to duplicate skill IDs",
                {
                    "skill_id": skill_id,
                    "first_path": str(existing),
                    "second_path": str(resolved),
                },
            )
        explicit_skill_roots[skill_id] = resolved
    for skill_id in request.skill_ids:
        skill_root = explicit_skill_roots.get(skill_id, request.source_root / skill_id)
        skill_file = skill_root / "SKILL.md"
        frontmatter = parse_markdown_frontmatter(skill_file)
        support_files: list[tuple[Path, Path]] = []
        for child in sorted(skill_root.iterdir(), key=lambda item: item.name):
            if child.name == "SKILL.md":
                continue
            if child.name not in allowed_support_subtrees:
                raise PackagerError(
                    "invalid_support_file_ownership",
                    "skill contains a disallowed support subtree",
                    {
                        "skill_id": skill_id,
                        "path": str(child.relative_to(request.source_root)),
                    },
                )
            if child.is_symlink():
                raise PackagerError(
                    "invalid_support_file_ownership",
                    "support subtree may not be a symlink",
                    {
                        "skill_id": skill_id,
                        "path": str(child.relative_to(request.source_root)),
                    },
                )
            for path in sorted(child.rglob("*")):
                if path.is_symlink():
                    raise PackagerError(
                        "invalid_support_file_ownership",
                        "support file may not be a symlink",
                        {
                            "skill_id": skill_id,
                            "path": str(path.relative_to(request.source_root)),
                        },
                    )
                if any(segment in excluded_support_segments for segment in path.parts):
                    continue
                if path.is_file():
                    support_files.append((path, path.relative_to(skill_root)))
        skills[skill_id] = {
            "skill_root": skill_root,
            "skill_file": skill_file,
            "support_files": support_files,
            "name": str(frontmatter.get("name", skill_id)),
            "description": str(
                frontmatter.get(
                    "description",
                    f"Use the {skill_id} module for routed {skill_id} work.",
                )
            )
            .replace("\n", " ")
            .strip(),
        }
    return skills


def bootstrap_state_path(
    repository_root: Path, *, decision_state_dir: str, bootstrap_state_name: str
) -> Path:
    return repository_root / decision_state_dir / bootstrap_state_name


def load_bootstrap_state(
    repository_root: Path,
    *,
    bootstrap_state_path_fn: Any,
    validate_existing_destination: Any,
    load_json: Any,
) -> dict[str, Any] | None:
    path = bootstrap_state_path_fn(repository_root)
    if not path.exists():
        return None
    validate_existing_destination(path)
    payload = load_json(path)
    if payload.get("format_version") != 1:
        return None
    return payload


def load_default_bootstrap_state(repository_root: Path) -> dict[str, Any] | None:
    """Load the standard router-packager bootstrap state when present."""
    return load_bootstrap_state(
        repository_root,
        bootstrap_state_path_fn=lambda root: bootstrap_state_path(
            root,
            decision_state_dir=DECISION_STATE_DIR,
            bootstrap_state_name="bootstrap-state.json",
        ),
        validate_existing_destination=validate_existing_destination,
        load_json=load_json,
    )
