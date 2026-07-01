#!/usr/bin/env python3
"""Generate acceptance matrix rows from design-to-code UI trace JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


HEADERS = [
    "ID",
    "User Goal Fit",
    "Acceptance Examples",
    "Counterexamples",
    "Non-Goal Boundaries",
    "Expected Path",
    "Negative/Invalid Inputs",
    "Boundary Cases",
    "State/Persistence",
    "Rollback/Cancellation",
    "Error Reporting",
    "Observability",
    "Real Product Path",
    "Validation Type",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def trace_rows(trace: Any) -> list[dict[str, Any]]:
    if isinstance(trace, dict):
        for key in ("trace", "rows", "interactions"):
            if isinstance(trace.get(key), list):
                return [row for row in trace[key] if isinstance(row, dict)]
    return [row for row in trace if isinstance(row, dict)] if isinstance(trace, list) else []


def value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        item = row.get(key)
        if item not in (None, ""):
            return str(item)
    return ""


def row_type(row: dict[str, Any]) -> str:
    rid = value(row, "id")
    kind = value(row, "type", "tag").lower()
    if rid.startswith("I-") or "interaction" in kind:
        return "interaction"
    if rid.startswith("S-") or "state" in kind:
        return "state"
    if rid.startswith("R-") or "responsive" in kind:
        return "responsive"
    if rid.startswith("A-") or "accessibility" in kind:
        return "accessibility"
    return "component"


def matrix_row(row: dict[str, Any]) -> dict[str, str]:
    rid = value(row, "id") or "TRACE"
    expected = value(row, "expected_ui_behavior", "expected_behavior") or "Expected UI behavior is visible"
    source = value(row, "source_evidence", "selector") or "source evidence"
    kind = row_type(row)
    validation_type = value(row, "validation_type") or ("real-product-path" if kind in {"interaction", "state", "responsive"} else "source-only")
    return {
        "ID": rid,
        "User Goal Fit": f"Trace row {rid} ensures {expected}.",
        "Acceptance Examples": f"Pass when {source} produces: {expected}.",
        "Counterexamples": f"Do not accept if {rid} is omitted, hidden, dead, or only present without the expected behavior.",
        "Non-Goal Boundaries": "Does not require unrelated visual polish, backend integration, or behavior outside this trace row.",
        "Expected Path": value(row, "verification") or f"Verify {rid} through the strongest available product or source path.",
        "Negative/Invalid Inputs": "Use missing data, disabled controls, invalid input, or no-match state when applicable.",
        "Boundary Cases": "Check narrow viewport, long text, empty/error state, or repeated instances when applicable.",
        "State/Persistence": "Record whether UI state is local, mocked, persisted, or not applicable.",
        "Rollback/Cancellation": "Verify close, cancel, retry, reset, or safe no-op behavior when applicable.",
        "Error Reporting": "Errors should be visible and actionable when this trace row can fail.",
        "Observability": "Evidence should name command, selector, screenshot, report, or artifact path.",
        "Real Product Path": "Use real-product-path when a running app route is available; otherwise state the lower validation type honestly.",
        "Validation Type": validation_type,
    }


def escape_cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def markdown(rows: list[dict[str, str]]) -> str:
    lines = ["| " + " | ".join(HEADERS) + " |", "| " + " | ".join("---" for _ in HEADERS) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(escape_cell(row.get(header, "")) for header in HEADERS) + " |")
    return "\n".join(lines) + "\n"


def generate(trace: Any) -> list[dict[str, str]]:
    return [matrix_row(row) for row in trace_rows(trace)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", help="Trace JSON path")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", help="Optional output path")
    args = parser.parse_args()
    path = Path(args.trace)
    if not path.exists():
        raise SystemExit(f"trace file not found: {path}")
    rows = generate(load_json(path))
    output = json.dumps({"rows": rows}, indent=2) + "\n" if args.format == "json" else markdown(rows)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
