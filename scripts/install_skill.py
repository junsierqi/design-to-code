#!/usr/bin/env python3
"""Install the design-to-code skill into a Codex skills directory."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
from pathlib import Path


def default_target() -> Path:
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return home / "skills" / "design-to-code"


def idea_to_code_path(target: Path) -> Path:
    return target.parent / "idea-to-code"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_manifest(root: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            manifest[path.relative_to(root).as_posix()] = file_hash(path)
    return manifest


def verify_parity(repo_root: Path, target: Path) -> tuple[bool, list[str]]:
    source = repo_root / "skills" / "design-to-code"
    if not source.exists():
        raise SystemExit(f"skill source not found: {source}")
    if not target.exists():
        return False, [f"target not found: {target}"]
    source_manifest = file_manifest(source)
    target_manifest = file_manifest(target)
    problems: list[str] = []
    for rel in sorted(source_manifest.keys() - target_manifest.keys()):
        problems.append(f"missing installed file: {rel}")
    for rel in sorted(target_manifest.keys() - source_manifest.keys()):
        problems.append(f"extra installed file: {rel}")
    for rel in sorted(source_manifest.keys() & target_manifest.keys()):
        if source_manifest[rel] != target_manifest[rel]:
            problems.append(f"hash mismatch: {rel}")
    return not problems, problems


def install(repo_root: Path, target: Path, dry_run: bool = False, force: bool = False) -> list[str]:
    source = repo_root / "skills" / "design-to-code"
    if not source.exists():
        raise SystemExit(f"skill source not found: {source}")
    idea_path = idea_to_code_path(target)
    actions = []
    if idea_path.exists():
        actions.append(f"dependency ok: idea-to-code found at {idea_path}")
    else:
        actions.append(
            "dependency note: idea-to-code not found next to target; "
            "design-to-code can fall back, but full lifecycle tracking requires installing idea-to-code"
        )
    actions.append(f"copy {source} -> {target}")
    if target.exists() and not force:
        actions.append(f"target exists: {target}")
        actions.append("use --force to overwrite the existing installed skill")
        if not dry_run:
            raise SystemExit(f"target exists; use --force to overwrite: {target}")
    if dry_run:
        return actions
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return actions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=str(default_target()), help="Install target directory")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without writing files")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing target directory")
    parser.add_argument("--verify", action="store_true", help="Verify source and installed skill file hash parity")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    target = Path(args.target).resolve()
    if args.verify:
        ok, problems = verify_parity(repo_root, target)
        if ok:
            print(f"parity ok: {repo_root / 'skills' / 'design-to-code'} == {target}")
            return 0
        print("parity FAIL")
        for problem in problems:
            print(f"- {problem}")
        return 2

    actions = install(repo_root, target, args.dry_run, args.force)
    for action in actions:
        prefix = "DRY RUN " if args.dry_run else ""
        print(prefix + action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
