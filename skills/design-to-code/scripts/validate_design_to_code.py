#!/usr/bin/env python3
"""Validate the design-to-code skill repository contract."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = [
    "README.md",
    "skills/design-to-code/SKILL.md",
    "skills/design-to-code/agents/openai.yaml",
    "skills/design-to-code/references/design-source-analysis.md",
    "skills/design-to-code/references/ui-implementation.md",
    "skills/design-to-code/references/ui-verification.md",
    "skills/design-to-code/references/acceptance-report.md",
    "skills/design-to-code/references/playwright-patterns.md",
    "skills/design-to-code/scripts/extract_html_interactions.py",
    "skills/design-to-code/scripts/generate_acceptance_report.py",
    "skills/design-to-code/scripts/dogfood_playwright_fixture.py",
    "skills/design-to-code/scripts/validate_design_to_code.py",
    "skills/design-to-code/scripts/test_validate_design_to_code.py",
    "scripts/install_skill.py",
]

SKILL_REQUIRED_PHRASES = [
    "idea-to-code",
    "lifecycle foundation",
    "design-source analysis",
    "UI trace",
    "references/design-source-analysis.md",
    "references/ui-implementation.md",
    "references/ui-verification.md",
    "references/acceptance-report.md",
    "references/playwright-patterns.md",
    "--strict",
]

SKILL_FORBIDDEN_PHRASES = [
    "Fully autonomous. Zero user interaction",
    "Do NOT ask the user:",
    "Gate 8 Delivery Manifest",
    "design-to-code-team",
]

REFERENCE_REQUIREMENTS = {
    "skills/design-to-code/references/design-source-analysis.md": [
        "Source Types",
        "Figma And Design System Signals",
        "Multi-Screen Flow Map",
        "Design State Inventory",
        "Responsive Frame Interpretation",
        "Component / Interaction / State",
        "Interaction Extraction",
        "Trace Matrix",
        "HTML prototype",
    ],
    "skills/design-to-code/references/ui-implementation.md": [
        "Project Discovery",
        "Missing Backend",
        "Design Token Mapping",
        "Theme And Mode Support",
        "Assets, Icons, And Fonts",
        "Internationalization And Text Resilience",
        "Interaction Behavior",
        "Responsive Behavior",
        "Accessibility",
    ],
    "skills/design-to-code/references/ui-verification.md": [
        "Validation Priority",
        "Viewport Matrix",
        "Visual Diff And Screenshot Baselines",
        "Accessibility Smoke Checks",
        "Dead Button Scan",
        "Screenshot Evidence",
        "source-only",
        "Playwright",
    ],
    "skills/design-to-code/references/acceptance-report.md": [
        "UI trace matrix",
        "Visual Acceptance",
        "Design Decisions",
        "Accessibility And I18n Notes",
        "Artifact Checklist",
        "Backend Handoff",
        "Test Result Table",
        "idea-to-code",
    ],
    "skills/design-to-code/references/playwright-patterns.md": [
        "Browser Evidence Contract",
        "Installation Pattern",
        "System Browser Fallback",
        "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH",
        "Screenshot Pattern",
        "Interaction Pattern",
        "State Pattern",
        "Console Error Pattern",
        "Accessibility Pattern",
        "Viewport Matrix Pattern",
    ],
}

README_REQUIRED_PHRASES = [
    "idea-to-code",
    "validate_design_to_code.py",
    "extract_html_interactions.py",
    "generate_acceptance_report.py",
    "dogfood_playwright_fixture.py",
    "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH",
    "test_validate_design_to_code.py",
    "install_skill.py",
    "skills/design-to-code/",
    "--strict",
]

REPORT_REQUIRED_COLUMNS = [
    "ID",
    "Type",
    "Source Evidence",
    "Expected UI / Behavior",
    "Implementation",
    "Verification",
    "Status",
]

AGENT_REQUIRED_PHRASES = [
    "Design To Code",
    "idea-to-code",
    "visual",
]

CLI_SCRIPT_PATHS = [
    "skills/design-to-code/scripts/extract_html_interactions.py",
    "skills/design-to-code/scripts/generate_acceptance_report.py",
    "skills/design-to-code/scripts/dogfood_playwright_fixture.py",
    "scripts/install_skill.py",
]


def read_text(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def validate_reference_links(root: Path, skill: str) -> list[str]:
    problems: list[str] = []
    references = sorted(set(re.findall(r"references/[A-Za-z0-9_.-]+\.md", skill)))
    for reference in references:
        rel = f"skills/design-to-code/{reference}"
        if not (root / rel).exists():
            problems.append(f"strict: SKILL.md references missing file: {rel}")
    return problems


def validate_script_help(root: Path) -> list[str]:
    problems: list[str] = []
    for rel in CLI_SCRIPT_PATHS:
        path = root / rel
        result = subprocess.run(
            [sys.executable, str(path), "--help"],
            cwd=root,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            problems.append(f"strict: script --help failed for {rel}: {result.stderr.strip() or result.stdout.strip()}")
        elif "usage:" not in result.stdout.lower():
            problems.append(f"strict: script --help did not print usage for {rel}")
    return problems


def validate_acceptance_report_contract(root: Path) -> list[str]:
    problems: list[str] = []
    report_script = read_text(root, "skills/design-to-code/scripts/generate_acceptance_report.py")
    for column in REPORT_REQUIRED_COLUMNS:
        if column not in report_script:
            problems.append(f"acceptance report generator missing UI Trace column: {column}")
    return problems


def validate(root: Path, strict: bool = False) -> list[str]:
    problems: list[str] = []

    for rel in REQUIRED_FILES:
        path = root / rel
        if not path.exists():
            problems.append(f"missing required file: {rel}")
        elif path.is_file() and not path.read_text(encoding="utf-8").strip():
            problems.append(f"empty required file: {rel}")

    if problems:
        return problems

    skill = read_text(root, "skills/design-to-code/SKILL.md")
    for phrase in SKILL_REQUIRED_PHRASES:
        if phrase not in skill:
            problems.append(f"SKILL.md missing required phrase: {phrase}")
    for phrase in SKILL_FORBIDDEN_PHRASES:
        if phrase in skill:
            problems.append(f"SKILL.md still contains standalone legacy phrase: {phrase}")

    if skill.count("## ") > 12:
        problems.append("SKILL.md has too many top-level sections; keep details in references")

    for rel, phrases in REFERENCE_REQUIREMENTS.items():
        text = read_text(root, rel)
        for phrase in phrases:
            if phrase not in text:
                problems.append(f"{rel} missing required phrase: {phrase}")

    readme = read_text(root, "README.md")
    for phrase in README_REQUIRED_PHRASES:
        if phrase not in readme:
            problems.append(f"README.md missing required phrase: {phrase}")

    agent = read_text(root, "skills/design-to-code/agents/openai.yaml")
    for phrase in AGENT_REQUIRED_PHRASES:
        if phrase not in agent:
            problems.append(f"agents/openai.yaml missing required phrase: {phrase}")

    problems.extend(validate_acceptance_report_contract(root))

    if strict:
        problems.extend(validate_reference_links(root, skill))
        problems.extend(validate_script_help(root))

    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root to validate")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    parser.add_argument("--strict", action="store_true", help="Run reference-link and CLI smoke checks")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    problems = validate(root, strict=args.strict)
    result = {
        "root": str(root),
        "strict": args.strict,
        "ok": not problems,
        "problem_count": len(problems),
        "problems": problems,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    elif problems:
        print("design-to-code validation: FAIL")
        for problem in problems:
            print(f"- {problem}")
    else:
        print("design-to-code validation: PASS")

    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
