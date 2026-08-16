#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["packaging==26.3", "PyYAML==6.0.3"]
# ///
"""No-prior-knowledge bootstrap for one skills-only router plugin."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from marketplace_installer.router_plugin_packager_parsing import validate_relative_path
from marketplace_installer.router_plugin_packager_branding import (
    discover_default_branding_assets,
)
from marketplace_installer.router_plugin_packager_constants import (
    DECISION_STATE_DIR,
    PUBLICATION_METADATA_NAME,
    RECEIPT_NAME,
)
from marketplace_installer.router_plugin_packager_source import (
    discover_source_root,
    discover_visible_skill_paths,
)
from marketplace_installer.router_plugin_packager_text import normalize_slug

try:
    from marketplace_installer.router_plugin_packager_script_loading import (
        load_sibling_module,
    )
except ModuleNotFoundError:
    from router_plugin_packager_script_loading import load_sibling_module


packager = load_sibling_module("router_plugin_packager.py")


REQUEST_SCHEMA = "router-plugin-request/v1"
RECEIPT_SCHEMA = "router-plugin-receipt/v1"
REQUESTS_DIR = DECISION_STATE_DIR / "requests"
RECEIPTS_DIR = DECISION_STATE_DIR / "receipts"
SEMVER_TAG = re.compile(r"^refs/tags/(v?)([0-9]+)\.([0-9]+)\.([0-9]+)$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class FirstUserFlowError(Exception):
    """Raised when first-user router bootstrap cannot proceed safely."""

    def __init__(self, error_code: str, message: str, details: dict[str, Any]) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details

    def payload(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _relative(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _valid_branding_asset(path: Path) -> bool:
    """Accept only actual PNG or SVG assets for publishable branding slots."""

    try:
        content = path.read_bytes()
    except OSError:
        return False
    if path.suffix.lower() == ".png":
        return content.startswith(PNG_SIGNATURE)
    if path.suffix.lower() == ".svg":
        return b"<svg" in content[:1024].lower()
    return False


def _load_manifest(repo_root: Path, relative_path: str) -> tuple[dict[str, Any], Path]:
    path = (repo_root / relative_path).resolve()
    try:
        validate_relative_path(repo_root, path, "canonical_manifest")
    except packager.PackagerError as exc:
        raise FirstUserFlowError(exc.error_code, exc.message, exc.details) from exc
    if not path.is_file():
        raise FirstUserFlowError(
            "missing_canonical_manifest",
            "canonical_manifest must name an existing regular file",
            {"canonical_manifest": relative_path},
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FirstUserFlowError(
            "invalid_canonical_manifest",
            "canonical_manifest must contain valid JSON",
            {"canonical_manifest": relative_path, "error": str(exc)},
        ) from exc
    if not isinstance(payload, dict):
        raise FirstUserFlowError(
            "invalid_canonical_manifest",
            "canonical_manifest must contain an object",
            {"canonical_manifest": relative_path},
        )
    return payload, path


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FirstUserFlowError(
            "missing_manifest_evidence",
            "canonical_manifest is missing a required string",
            {"field": field},
        )
    return value.strip()


def _publication(payload: dict[str, Any]) -> dict[str, str]:
    publication = payload.get("publication")
    if not isinstance(publication, dict):
        raise FirstUserFlowError(
            "missing_manifest_evidence",
            "canonical_manifest is missing publication.category",
            {"field": "publication.category"},
        )
    category = publication.get("category")
    if not isinstance(category, str) or not category.strip():
        raise FirstUserFlowError(
            "missing_manifest_evidence",
            "canonical_manifest is missing publication.category",
            {"field": "publication.category"},
        )
    return {"category": category.strip()}


def _latest_release(  # noqa: C901
    repo_root: Path, source_remote: str | None
) -> dict[str, str]:
    remote = source_remote
    if remote is None:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise FirstUserFlowError(
                "missing_upgrade_remote",
                "upgrade requires source_remote or an origin remote",
                {},
            )
        remote = "origin"
    dirty = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    if dirty.stdout:
        raise FirstUserFlowError(
            "dirty_worktree", "upgrade refuses a dirty worktree", {"remote": remote}
        )
    head = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if head.returncode or not head.stdout.strip():
        raise FirstUserFlowError(
            "missing_git_head",
            "upgrade requires a resolvable current HEAD",
            {"remote": remote},
        )
    tags = subprocess.run(
        ["git", "-C", str(repo_root), "ls-remote", "--tags", remote],
        capture_output=True,
        text=True,
    )
    if tags.returncode:
        raise FirstUserFlowError(
            "upgrade_remote_unavailable",
            "could not read release tags from source_remote",
            {"remote": remote},
        )
    tag_targets: dict[str, str] = {}
    for line in tags.stdout.splitlines():
        target, _, ref = line.partition("\t")
        tag_ref = ref.removesuffix("^{}")
        match = SEMVER_TAG.fullmatch(tag_ref)
        if not match:
            continue
        if ref.endswith("^{}") or tag_ref not in tag_targets:
            tag_targets[tag_ref] = target
    releases: dict[tuple[int, int, int], tuple[str, str]] = {}
    for ref, target in sorted(tag_targets.items()):
        match = SEMVER_TAG.fullmatch(ref)
        assert match is not None
        version = tuple(int(match.group(index)) for index in range(2, 5))
        prior = releases.get(version)
        if prior is not None:
            raise FirstUserFlowError(
                "ambiguous_release_version",
                "multiple exact SemVer tags normalize to the same version",
                {"remote": remote, "version": ".".join(map(str, version))},
            )
        releases[version] = (ref, target)
    if not releases:
        raise FirstUserFlowError(
            "no_eligible_release",
            "source_remote has no exact SemVer release tag",
            {"remote": remote},
        )
    version = max(releases)
    tag, target = releases[version]
    return {
        "remote": remote,
        "tag": tag.removeprefix("refs/tags/"),
        "target": target,
        "version": ".".join(map(str, version)),
        "current_head": head.stdout.strip(),
        "head_differs_from_release": head.stdout.strip() != target,
    }


def _release_is_current(repo_root: Path, selection: dict[str, Any]) -> bool:
    remote = selection.get("remote")
    tag = selection.get("tag")
    target = selection.get("target")
    if not all(isinstance(value, str) and value for value in (remote, tag, target)):
        return False
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-remote",
            "--tags",
            remote,
            f"refs/tags/{tag}",
            f"refs/tags/{tag}^{{}}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return False
    observed = None
    for line in result.stdout.splitlines():
        candidate, _, ref = line.partition("\t")
        if ref == f"refs/tags/{tag}^{{}}":
            observed = candidate
            break
        if ref == f"refs/tags/{tag}":
            observed = candidate
    return observed == target


def classify(repo_root: Path) -> dict[str, Any]:
    """Return the sole router candidate without creating any repository state."""

    repo_root = repo_root.resolve()
    try:
        source_root, source_root_text = discover_source_root(repo_root)
        skills = discover_visible_skill_paths(source_root)
    except packager.PackagerError as exc:
        return {
            "command": "classify",
            "state": "diagnostic",
            "diagnostic": exc.payload(),
        }
    return {
        "command": "classify",
        "state": "confirmation_required",
        "candidate": {
            "plugin_kind": "skills_only",
            "source_root": source_root_text,
            "skill_ids": [path.name for path in skills],
        },
    }


def _branding(repo_root: Path) -> dict[str, str]:
    discovered, rejected = discover_default_branding_assets(repo_root)
    if rejected:
        raise FirstUserFlowError(
            "ambiguous_branding_asset",
            "bootstrap requires one deterministic branding asset per slot",
            {"candidates": rejected},
        )
    if "composer_icon" not in discovered and "logo" in discovered:
        discovered["composer_icon"] = discovered["logo"]
    required_slots = {"logo", "dark_logo", "composer_icon"}
    missing = sorted(required_slots - set(discovered))
    if missing:
        raise FirstUserFlowError(
            "missing_branding_asset",
            "bootstrap requires logo, dark_logo, and composer_icon assets",
            {"missing_slots": missing},
        )
    invalid = sorted(
        {
            path
            for path in discovered.values()
            if not _valid_branding_asset(repo_root / path)
        }
    )
    if invalid:
        raise FirstUserFlowError(
            "invalid_branding_asset",
            "bootstrap requires valid PNG or SVG branding assets",
            {"invalid_paths": invalid},
        )
    return discovered


def _write_immutable_json(path: Path, payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise FirstUserFlowError(
                "immutable_request_conflict",
                "an immutable request path already contains different content",
                {"path": str(path)},
            )
        return
    path.write_text(rendered, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _load_receipt(repo_root: Path, surface_id: str) -> tuple[dict[str, Any], Path]:
    path = repo_root / DECISION_STATE_DIR / f"{surface_id}.json"
    if not path.is_file():
        raise FirstUserFlowError(
            "missing_bootstrap_receipt",
            "no first-user bootstrap receipt exists for surface_id",
            {"surface_id": surface_id},
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != RECEIPT_SCHEMA:
        raise FirstUserFlowError(
            "incompatible_bootstrap_receipt",
            "surface_id is owned by a legacy or incompatible receipt",
            {"surface_id": surface_id, "receipt_path": _relative(repo_root, path)},
        )
    return payload, path


def _changed_inputs(
    repo_root: Path, request: dict[str, Any], receipt: dict[str, Any]
) -> list[str]:
    expected = receipt["input_digests"]
    changed: list[str] = []
    canonical_manifest = str(request["canonical_manifest"])
    manifest_path = repo_root / canonical_manifest
    if (
        not manifest_path.is_file()
        or _sha256_file(manifest_path) != expected["canonical_manifest"]
    ):
        changed.append(canonical_manifest)
    for skill_path in request["skill_paths"]:
        skill_file = repo_root / skill_path / "SKILL.md"
        expected_hash = expected["skills"].get(Path(skill_path).name)
        if not skill_file.is_file() or _sha256_file(skill_file) != expected_hash:
            changed.append(f"{skill_path}/SKILL.md")
    for slot, asset_path in sorted(request["branding_asset_overrides"].items()):
        path = repo_root / asset_path
        expected_hash = expected["branding_assets"].get(slot)
        if not path.is_file() or _sha256_file(path) != expected_hash:
            changed.append(asset_path)
    release_selection = receipt.get("release_selection")
    if isinstance(release_selection, dict) and not _release_is_current(
        repo_root, release_selection
    ):
        changed.append(f"source_remote:{release_selection.get('tag', 'unknown')}")
    return sorted(set(changed))


def _output_digests(output_root: Path) -> dict[str, str]:
    return {
        _relative(output_root, path): _sha256_file(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file()
    }


def _branding_readiness(output_root: Path) -> dict[str, Any]:
    """Validate publication metadata and the three generated branding assets."""

    manifest_path = output_root / ".codex-plugin" / "plugin.json"
    metadata_path = output_root / PUBLICATION_METADATA_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "publication_ready": False,
            "missing_or_invalid": [
                str(path.relative_to(output_root))
                for path in (manifest_path, metadata_path)
                if not path.is_file()
            ],
        }
    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        interface = {}
    required = {"composerIcon", "logo", "logoDark"}
    assets = {
        field: interface.get(field)
        for field in required
        if isinstance(interface.get(field), str)
    }
    missing = sorted(required - set(assets))
    missing.extend(
        value
        for value in assets.values()
        if not _valid_branding_asset(output_root / value)
    )
    if (
        metadata.get("format") != "router-plugin-publication-metadata-v1"
        or metadata.get("category") != "Productivity"
        or not isinstance(metadata.get("plugin_slug"), str)
    ):
        missing.append(PUBLICATION_METADATA_NAME)
    return {
        "publication_ready": not missing,
        "missing_or_invalid": sorted(set(missing)),
        "assets": assets,
        "publication_metadata": _relative(output_root, metadata_path),
    }


def _changed_outputs(repo_root: Path, receipt: dict[str, Any]) -> list[str]:
    output_root = repo_root / str(receipt["output_root"])
    expected = receipt.get("output_digests")
    if not isinstance(expected, dict):
        return [str(receipt["output_root"])]
    actual = _output_digests(output_root) if output_root.is_dir() else {}
    return sorted(
        path
        for path in set(actual) | set(expected)
        if actual.get(path) != expected.get(path)
    )


def bootstrap(
    repo_root: Path,
    *,
    confirmed: bool,
    canonical_manifest: str,
    upgrade: bool = False,
    source_remote: str | None = None,
) -> dict[str, Any]:
    """Persist a reviewable request and receipt after explicit confirmation."""

    repo_root = repo_root.resolve()
    classification = classify(repo_root)
    if classification["state"] != "confirmation_required":
        raise FirstUserFlowError(
            "router_classification_failed",
            "bootstrap requires one deterministic router candidate",
            {"classification": classification},
        )
    if not confirmed:
        return {
            "command": "bootstrap",
            "state": "confirmation_required",
            "candidate": classification["candidate"],
        }

    candidate = classification["candidate"]
    manifest, manifest_path = _load_manifest(repo_root, canonical_manifest)
    plugin_slug = normalize_slug(_required_string(manifest, "name"))
    if not plugin_slug:
        raise FirstUserFlowError(
            "invalid_manifest_evidence",
            "canonical_manifest name must normalize to a plugin slug",
            {"field": "name"},
        )
    manifest_version = _required_string(manifest, "version")
    release = _latest_release(repo_root, source_remote) if upgrade else None
    version = release["version"] if release else manifest_version
    publication = _publication(manifest)
    branding = _branding(repo_root)
    output_root = (DECISION_STATE_DIR / "generated" / plugin_slug).as_posix()
    request_output_root = (Path("..") / "generated" / plugin_slug).as_posix()
    request = {
        "schema": REQUEST_SCHEMA,
        "format_version": 1,
        "input_mode": "skill_list",
        "plugin_kind": "skills_only",
        "repository_root": ".",
        "source_root": candidate["source_root"],
        "skill_paths": [
            f"{candidate['source_root']}/{skill_id}"
            for skill_id in candidate["skill_ids"]
        ],
        "output_root": request_output_root,
        "surface_id_override": plugin_slug,
        "plugin_slug_override": plugin_slug,
        "display_name_override": _required_string(manifest, "name"),
        "version_override": version,
        "publication": publication,
        "canonical_manifest": _relative(repo_root, manifest_path),
        "source_manifest": _relative(repo_root, manifest_path),
        "branding_asset_overrides": branding,
    }
    request_sha256 = _sha256_bytes(_canonical_bytes(request))
    request_path = repo_root / REQUESTS_DIR / f"{plugin_slug}-{request_sha256}.json"
    receipt_path = repo_root / DECISION_STATE_DIR / f"{plugin_slug}.json"
    if receipt_path.exists():
        existing = json.loads(receipt_path.read_text(encoding="utf-8"))
        existing_output = existing.get("output_root")
        if existing_output != f"./{output_root}":
            raise FirstUserFlowError(
                "identity_or_output_collision",
                "an existing receipt claims the same surface with another output root",
                {
                    "surface_id": plugin_slug,
                    "existing_output_root": existing_output,
                    "output_root": f"./{output_root}",
                },
            )
        existing_digest = existing.get("request_sha256")
        if isinstance(existing_digest, str) and existing_digest != request_sha256:
            _write_immutable_json(
                repo_root / RECEIPTS_DIR / f"{plugin_slug}-{existing_digest}.json",
                existing,
            )
    _write_immutable_json(request_path, request)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "state": "bootstrapped",
        "surface_id": plugin_slug,
        "request_path": _relative(repo_root, request_path),
        "request_sha256": request_sha256,
        "output_root": f"./{output_root}",
        "input_digests": {
            "canonical_manifest": _sha256_file(manifest_path),
            "skills": {
                skill_id: _sha256_file(
                    repo_root / candidate["source_root"] / skill_id / "SKILL.md"
                )
                for skill_id in candidate["skill_ids"]
            },
            "branding_assets": {
                slot: _sha256_file(repo_root / path)
                for slot, path in sorted(branding.items())
            },
        },
        "identity_evidence": {
            "name": {"source": "canonical_manifest", "path": canonical_manifest},
            "version": {"source": "canonical_manifest", "value": version},
            "publication": {
                "source": "canonical_manifest",
                "category": publication["category"],
            },
        },
        "owned_paths": {
            "receipt": _relative(repo_root, receipt_path),
            "request": _relative(repo_root, request_path),
            "native_manifest": ".codex-plugin/plugin.json",
            "generated_manifest": f"./{output_root}/.codex-plugin/plugin.json",
        },
    }
    if release is not None:
        receipt["release_selection"] = release
        receipt["identity_evidence"]["version"] = {
            "source": "source_remote",
            "value": version,
            "manifest_value": manifest_version,
        }
    _write_json(receipt_path, receipt)
    return {
        "command": "bootstrap",
        "state": "bootstrapped",
        "request_path": _relative(repo_root, request_path),
        "receipt_path": _relative(repo_root, receipt_path),
        "request_sha256": request_sha256,
    }


def package(repo_root: Path, *, surface_id: str) -> dict[str, Any]:
    """Apply the immutable request named by a fresh first-user receipt."""

    repo_root = repo_root.resolve()
    receipt, receipt_path = _load_receipt(repo_root, surface_id)
    request_path = repo_root / str(receipt["request_path"])
    if not request_path.is_file():
        raise FirstUserFlowError(
            "missing_bootstrap_request",
            "bootstrap receipt names a missing immutable request",
            {"request_path": str(receipt["request_path"])},
        )
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if request.get("schema") != REQUEST_SCHEMA:
        raise FirstUserFlowError(
            "incompatible_bootstrap_request",
            "bootstrap receipt names an incompatible request",
            {"request_path": str(receipt["request_path"])},
        )
    if _sha256_bytes(_canonical_bytes(request)) != receipt.get("request_sha256"):
        raise FirstUserFlowError(
            "stale_bootstrap_receipt",
            "immutable request content no longer matches its receipt",
            {"changed_inputs": [str(receipt["request_path"])]},
        )
    changed = _changed_inputs(repo_root, request, receipt)
    if changed:
        raise FirstUserFlowError(
            "stale_bootstrap_receipt",
            "bootstrap inputs changed after receipt creation",
            {"changed_inputs": changed},
        )
    try:
        summary = packager.run("apply", request_path, repo_root)
    except packager.PackagerError as exc:
        raise FirstUserFlowError(exc.error_code, exc.message, exc.details) from exc
    output_root = Path(summary["output_root"])
    receipt["state"] = "packaged"
    receipt["output_digests"] = _output_digests(output_root)
    receipt["generated_receipt_path"] = str(
        (output_root / RECEIPT_NAME).relative_to(repo_root)
    )
    receipt["branding_readiness"] = _branding_readiness(output_root)
    _write_json(receipt_path, receipt)
    return {
        "command": "package",
        "state": "packaged",
        "surface_id": surface_id,
        "receipt_path": _relative(repo_root, receipt_path),
        "output_root": _relative(repo_root, output_root),
    }


def inspect(repo_root: Path, *, surface_id: str) -> dict[str, Any]:
    """Inspect one packaged artifact without a write or chat-derived path."""

    repo_root = repo_root.resolve()
    receipt, receipt_path = _load_receipt(repo_root, surface_id)
    if receipt.get("state") != "packaged":
        raise FirstUserFlowError(
            "package_not_ready",
            "bootstrap receipt has not completed package",
            {"surface_id": surface_id, "state": receipt.get("state")},
        )
    input_changes = _changed_inputs(
        repo_root,
        json.loads((repo_root / receipt["request_path"]).read_text(encoding="utf-8")),
        receipt,
    )
    output_changes = _changed_outputs(repo_root, receipt)
    if input_changes or output_changes:
        raise FirstUserFlowError(
            "stale_bootstrap_receipt",
            "package inputs or rendered output changed after receipt creation",
            {"changed_inputs": input_changes, "changed_outputs": output_changes},
        )
    output_root = repo_root / str(receipt["output_root"])
    readiness = _branding_readiness(output_root)
    return {
        "command": "inspect",
        "state": "ready" if readiness["publication_ready"] else "not_ready",
        "surface_id": surface_id,
        "receipt_path": _relative(repo_root, receipt_path),
        "output_root": _relative(repo_root, output_root),
        "branding_readiness": readiness,
    }


def publish_handoff(repo_root: Path, *, surface_id: str) -> dict[str, Any]:
    """Return the sole publisher handoff after receipt-led revalidation.

    This deliberately does not load marketplace configuration or mutate a
    marketplace.  The marketplace capability owns selection, preview, and
    publication apply.
    """

    inspected = inspect(repo_root, surface_id=surface_id)
    if inspected["state"] != "ready":
        raise FirstUserFlowError(
            "publication_not_ready",
            "generated plugin is missing valid publication or branding evidence",
            {"branding_readiness": inspected["branding_readiness"]},
        )
    return {
        "command": "publish-handoff",
        "state": "publisher_required",
        "surface_id": surface_id,
        "plugin_root": inspected["output_root"],
        "publisher": "codex-marketplace-publish",
        "required_next_steps": ["dry_run", "apply_with_plan_digest"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="First-user router plugin bootstrap and package flow"
    )
    parser.add_argument(
        "command",
        choices=("classify", "bootstrap", "package", "inspect", "publish-handoff"),
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--canonical-manifest")
    parser.add_argument("--surface-id")
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--upgrade", action="store_true")
    parser.add_argument("--source-remote")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "classify":
            result = classify(args.repo_root)
        elif args.command == "bootstrap":
            if not args.canonical_manifest:
                raise FirstUserFlowError(
                    "missing_canonical_manifest",
                    "bootstrap requires an explicit canonical_manifest",
                    {},
                )
            result = bootstrap(
                args.repo_root,
                confirmed=args.confirmed,
                canonical_manifest=args.canonical_manifest,
                upgrade=args.upgrade,
                source_remote=args.source_remote,
            )
        elif args.command == "package":
            if not args.surface_id:
                raise FirstUserFlowError(
                    "missing_surface_id", "package requires surface_id", {}
                )
            result = package(args.repo_root, surface_id=args.surface_id)
        elif args.command == "inspect":
            if not args.surface_id:
                raise FirstUserFlowError(
                    "missing_surface_id", "inspect requires surface_id", {}
                )
            result = inspect(args.repo_root, surface_id=args.surface_id)
        else:
            if not args.surface_id:
                raise FirstUserFlowError(
                    "missing_surface_id", "publish-handoff requires surface_id", {}
                )
            result = publish_handoff(args.repo_root, surface_id=args.surface_id)
    except FirstUserFlowError as exc:
        print(json.dumps(exc.payload(), sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
