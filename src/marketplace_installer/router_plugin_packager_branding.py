from __future__ import annotations

from typing import Any

from marketplace_installer.router_plugin_packager_errors import PackagerError


def discover_branding_assets(
    repository_root: Any,
    *,
    branding_slot_candidates: dict[str, list[str]],
    has_hidden_path_segment: Any,
    normalize_slug: Any,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    discovered: dict[str, str] = {}
    rejected: dict[str, list[str]] = {}
    all_files = [
        path
        for path in repository_root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and ".codex-plugin" not in path.parts
        and "generated" not in path.parts
        and not has_hidden_path_segment(path.relative_to(repository_root))
    ]
    for slot, candidates in branding_slot_candidates.items():
        scored: list[tuple[int, int, str]] = []
        for path in all_files:
            stem = normalize_slug(path.stem)
            rel = path.relative_to(repository_root).as_posix()
            score = None
            for index, candidate in enumerate(candidates):
                if stem == normalize_slug(candidate):
                    score = index
                    break
            if score is None:
                continue
            suffix_score = 0 if path.suffix.lower() == ".png" else 1
            scored.append((score, suffix_score, rel))
        if not scored:
            continue
        scored.sort(key=lambda item: (item[0], item[1], item[2]))
        best_score = scored[0][0]
        best_suffix_score = scored[0][1]
        best = [
            path
            for score, suffix_score, path in scored
            if score == best_score and suffix_score == best_suffix_score
        ]
        if len(best) > 1:
            rejected[slot] = best
            continue
        discovered[slot] = best[0]
    return discovered, rejected


def resolve_branding_assets(
    invocation: Any,
    repository_root: Any,
    bootstrap_state: dict[str, Any] | None,
    *,
    discover_branding_assets_fn: Any,
    validate_relative_path: Any,
) -> tuple[dict[str, str], dict[str, Any]]:
    discovered, rejected = discover_branding_assets_fn(repository_root)
    overrides = dict(invocation.branding_asset_overrides)
    for key, raw_path in overrides.items():
        candidate = (repository_root / raw_path).resolve()
        validate_relative_path(
            repository_root, candidate, f"branding_asset_overrides.{key}"
        )
        if not candidate.is_file():
            raise PackagerError(
                "missing_branding_asset",
                "branding asset path does not resolve to a file",
                {"branding_key": key, "path": str(candidate)},
            )
    bootstrap_assets = (
        dict(bootstrap_state.get("branding_assets", {})) if bootstrap_state else {}
    )
    valid_bootstrap_assets: dict[str, str] = {}
    for key, raw_path in bootstrap_assets.items():
        candidate = (repository_root / raw_path).resolve()
        try:
            validate_relative_path(
                repository_root, candidate, f"bootstrap_state.branding_assets.{key}"
            )
        except PackagerError:
            continue
        if candidate.is_file():
            valid_bootstrap_assets[key] = raw_path
    for slot, paths in rejected.items():
        if slot in overrides or slot in valid_bootstrap_assets:
            continue
        raise PackagerError(
            "ambiguous_branding_asset",
            "multiple equally strong branding asset candidates remain for one slot",
            {
                "slot": slot,
                "candidates": paths,
                "resolution": f"provide branding_asset_overrides.{slot}",
            },
        )
    if overrides:
        resolved = {**valid_bootstrap_assets, **discovered, **overrides}
        source = "override"
    elif valid_bootstrap_assets:
        resolved = {**valid_bootstrap_assets, **discovered}
        source = (
            "discovered" if discovered != valid_bootstrap_assets else "bootstrap_state"
        )
    else:
        resolved = discovered
        source = "discovered" if resolved else "none"
    sources = {
        "branding_assets": source,
    }
    return resolved, {
        "rejected_candidates": [
            {"slot": slot, "candidates": paths, "reason": "ambiguous"}
            for slot, paths in sorted(rejected.items())
        ],
        "sources": sources,
    }
