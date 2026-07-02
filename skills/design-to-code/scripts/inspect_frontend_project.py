#!/usr/bin/env python3
"""Inspect a frontend project for design-to-code implementation cues."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "design-to-code.frontend-project-inspection.v1"


def load_package_json(root: Path) -> dict[str, Any]:
    package = root / "package.json"
    if not package.exists():
        return {}
    try:
        data = json.loads(package.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {"_error": "invalid package.json"}
    return data if isinstance(data, dict) else {}


def all_deps(package: dict[str, Any]) -> dict[str, str]:
    deps: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        values = package.get(key)
        if isinstance(values, dict):
            deps.update({str(name): str(version) for name, version in values.items()})
    return deps


def detect_package_manager(root: Path) -> str:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "package-lock.json").exists():
        return "npm"
    if (root / "bun.lockb").exists() or (root / "bun.lock").exists():
        return "bun"
    return "unknown"


def detect_framework(root: Path, deps: dict[str, str]) -> dict[str, Any]:
    signals: list[str] = []
    framework = "unknown"
    if "next" in deps or (root / "next.config.js").exists() or (root / "next.config.mjs").exists():
        framework = "Next.js"
        signals.append("next dependency or config")
    elif "nuxt" in deps or (root / "nuxt.config.ts").exists() or (root / "nuxt.config.js").exists():
        framework = "Nuxt"
        signals.append("nuxt dependency or config")
    elif "@angular/core" in deps or (root / "angular.json").exists():
        framework = "Angular"
        signals.append("angular dependency or angular.json")
    elif "svelte" in deps or "@sveltejs/kit" in deps or (root / "svelte.config.js").exists():
        framework = "Svelte"
        signals.append("svelte dependency or config")
    elif "vue" in deps:
        framework = "Vue"
        signals.append("vue dependency")
    elif "react" in deps:
        framework = "React"
        signals.append("react dependency")

    if (root / "vite.config.ts").exists() or (root / "vite.config.js").exists() or "vite" in deps:
        signals.append("vite")
    if (root / "src" / "app").exists():
        signals.append("src/app")
    if (root / "pages").exists() or (root / "src" / "pages").exists():
        signals.append("pages")
    if (root / "app").exists():
        signals.append("app")

    return {"name": framework, "signals": sorted(set(signals))}


def detect_style_system(root: Path, deps: dict[str, str]) -> dict[str, Any]:
    systems: list[str] = []
    if "tailwindcss" in deps or any((root / name).exists() for name in ("tailwind.config.js", "tailwind.config.ts", "tailwind.config.cjs")):
        systems.append("Tailwind CSS")
    if "@mui/material" in deps:
        systems.append("MUI")
    if "antd" in deps:
        systems.append("Ant Design")
    if "styled-components" in deps:
        systems.append("styled-components")
    if "@emotion/react" in deps:
        systems.append("Emotion")
    if any(root.glob("**/*.module.css")):
        systems.append("CSS Modules")
    if any(root.glob("**/*.scss")):
        systems.append("Sass")
    if any(root.glob("**/*.css")):
        systems.append("CSS")
    return {"systems": sorted(set(systems))}


def detect_routes(root: Path) -> list[str]:
    candidates = [
        root / "src" / "app",
        root / "app",
        root / "src" / "pages",
        root / "pages",
        root / "src" / "routes",
        root / "routes",
    ]
    routes: list[str] = []
    for base in candidates:
        if not base.exists() or not base.is_dir():
            continue
        for item in sorted(base.rglob("*")):
            if item.is_file() and item.suffix.lower() in {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}:
                routes.append(str(item.relative_to(root)))
                if len(routes) >= 50:
                    return routes
    return routes


def detect_tests(root: Path, deps: dict[str, str], scripts: dict[str, Any]) -> dict[str, Any]:
    tools: list[str] = []
    for name, label in (
        ("@playwright/test", "Playwright"),
        ("playwright", "Playwright"),
        ("cypress", "Cypress"),
        ("vitest", "Vitest"),
        ("jest", "Jest"),
        ("@testing-library/react", "Testing Library"),
    ):
        if name in deps:
            tools.append(label)
    if (root / "playwright.config.ts").exists() or (root / "playwright.config.js").exists():
        tools.append("Playwright")
    if (root / "cypress").exists():
        tools.append("Cypress")
    script_hints = {name: value for name, value in scripts.items() if any(token in name.lower() for token in ("test", "e2e", "lint", "build", "dev"))}
    return {"tools": sorted(set(tools)), "scripts": script_hints}


def command_for(manager: str, script: str) -> str:
    if manager == "yarn":
        return f"yarn {script}"
    if manager == "pnpm":
        return f"pnpm {script}"
    if manager == "bun":
        return f"bun run {script}"
    return f"npm run {script}"


def recommended_commands(manager: str, scripts: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for name in ("lint", "test", "build", "dev"):
        if name in scripts:
            commands.append(command_for(manager, name))
    return commands


def inspect(root: Path) -> dict[str, Any]:
    root = root.resolve()
    package = load_package_json(root)
    deps = all_deps(package)
    scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
    manager = detect_package_manager(root)
    framework = detect_framework(root, deps)
    tests = detect_tests(root, deps, scripts)
    findings: list[dict[str, str]] = []
    if not package:
        findings.append({"severity": "warning", "code": "missing-package-json", "message": "package.json not found or unreadable"})
    if framework["name"] == "unknown":
        findings.append({"severity": "info", "code": "unknown-framework", "message": "framework could not be inferred from common signals"})
    return {
        "schema_version": SCHEMA_VERSION,
        "root": str(root),
        "package_manager": manager,
        "framework": framework,
        "scripts": scripts,
        "style_system": detect_style_system(root, deps),
        "routes": detect_routes(root),
        "test_tooling": tests,
        "recommended_commands": recommended_commands(manager, scripts),
        "findings": findings,
    }


def to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Frontend Project Inspection",
        "",
        f"- Root: `{payload['root']}`",
        f"- Package Manager: {payload['package_manager']}",
        f"- Framework: {payload['framework']['name']}",
        f"- Style Systems: {', '.join(payload['style_system']['systems']) or 'none detected'}",
        f"- Test Tools: {', '.join(payload['test_tooling']['tools']) or 'none detected'}",
        "",
        "## Recommended Commands",
    ]
    commands = payload["recommended_commands"]
    lines.extend([f"- `{command}`" for command in commands] or ["- none detected"])
    lines.extend(["", "## Routes"])
    lines.extend([f"- `{route}`" for route in payload["routes"]] or ["- none detected"])
    if payload["findings"]:
        lines.extend(["", "## Findings"])
        lines.extend([f"- {finding['severity']}: {finding['message']}" for finding in payload["findings"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect frontend project conventions for design-to-code implementation.")
    parser.add_argument("root", nargs="?", default=".", help="Frontend project root")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Output format")
    args = parser.parse_args()

    payload = inspect(Path(args.root))
    if args.format == "markdown":
        print(to_markdown(payload), end="")
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
