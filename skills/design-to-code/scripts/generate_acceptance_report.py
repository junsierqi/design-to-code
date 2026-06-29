#!/usr/bin/env python3
"""Generate a design-to-code acceptance report from trace and validation JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(lines)


def trace_rows(trace: Any) -> list[dict[str, Any]]:
    if isinstance(trace, dict):
        for key in ("trace", "rows", "interactions"):
            if isinstance(trace.get(key), list):
                return trace[key]
    if isinstance(trace, list):
        return trace
    return []


def validation_checks(validation: dict[str, Any]) -> list[dict[str, Any]]:
    checks = validation.get("checks", [])
    return checks if isinstance(checks, list) else []


def generate(title: str, trace: Any, validation: dict[str, Any]) -> str:
    rows = trace_rows(trace)
    checks = validation_checks(validation)
    visual_diffs = validation.get("visual_differences", []) if isinstance(validation, dict) else []
    limitations = validation.get("limitations") or validation.get("reason_browser_not_used") or "No limitations recorded."
    validation_type = validation.get("validation_type", "unverified")
    result = validation.get("result", "unknown")

    lines = [
        f"# {title}",
        "",
        "## Summary",
        "",
        f"- Validation type: {validation_type}",
        f"- Result: {result}",
        f"- Limitations: {limitations}",
        "",
        "## UI Trace",
        "",
    ]
    if rows:
        lines.append(table(
            ["ID", "Type", "Source Evidence", "Expected UI / Behavior", "Implementation", "Verification", "Status"],
            [
                [
                    row.get("id", ""),
                    row.get("type", row.get("tag", "")),
                    row.get("source_evidence", row.get("selector", "")),
                    row.get("expected_ui_behavior", row.get("expected_behavior", "")),
                    row.get("implementation", ""),
                    row.get("verification", ""),
                    row.get("status", ""),
                ]
                for row in rows
            ],
        ))
    else:
        lines.append("No trace rows supplied.")
    lines.extend(["", "## Validation Checks", ""])
    if checks:
        lines.append(table(
            ["ID", "Name", "Status", "Evidence"],
            [[c.get("id", ""), c.get("name", ""), c.get("status", ""), c.get("evidence", "")] for c in checks],
        ))
    else:
        lines.append("No validation checks supplied.")
    lines.extend(["", "## Visual Differences", ""])
    if visual_diffs:
        lines.append(table(
            ["Area", "Design", "Implementation", "Reason", "Accepted"],
            [
                [
                    d.get("area", ""),
                    d.get("design", ""),
                    d.get("implementation", ""),
                    d.get("reason", ""),
                    str(d.get("accepted", "")),
                ]
                for d in visual_diffs
            ],
        ))
    else:
        lines.append("No visual differences recorded.")
    lines.extend([
        "",
        "## Acceptance",
        "",
        "Use `Completed` only when trace coverage and validation evidence support the requested UI outcome. Use `Progress` when browser/runtime behavior is deferred.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True, help="Trace JSON path")
    parser.add_argument("--validation", required=True, help="Validation JSON path")
    parser.add_argument("--title", default="Design-to-code Acceptance Report")
    parser.add_argument("--output", help="Optional report output path")
    args = parser.parse_args()

    report = generate(args.title, load_json(Path(args.trace)), load_json(Path(args.validation)))
    if args.output:
        Path(args.output).write_text(report + "\n", encoding="utf-8")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
