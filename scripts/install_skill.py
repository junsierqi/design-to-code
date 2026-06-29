#!/usr/bin/env python3
"""Install the design-to-code skill into a Codex skills directory."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


def default_target() -> Path:
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return home / "skills" / "design-to-code"


def idea_to_code_path(target: Path) -> Path:
    return target.parent / "idea-to-code"


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
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    actions = install(repo_root, Path(args.target).resolve(), args.dry_run, args.force)
    for action in actions:
        prefix = "DRY RUN " if args.dry_run else ""
        print(prefix + action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
