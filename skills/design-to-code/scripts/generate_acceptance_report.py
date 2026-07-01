#!/usr/bin/env python3
"""Generate a design-to-code acceptance report from trace and validation JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
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


def validation_attempts(validation: dict[str, Any]) -> list[dict[str, Any]]:
    attempts = validation.get("attempts", [])
    return attempts if isinstance(attempts, list) else []


TRACE_ID_PATTERN = re.compile(r"^(?:C|I|S|R|A)-\d+$")
TRACE_REQUIRED_FIELDS = (
    "id",
    "type",
    "source_evidence",
    "expected_ui_behavior",
    "implementation",
    "verification",
    "status",
)
TRACE_FIELD_ALIASES = {
    "source_evidence": ("source_evidence", "selector"),
    "expected_ui_behavior": ("expected_ui_behavior", "expected_behavior"),
}
ARTIFACT_FIELDS = ("artifact", "artifacts", "screenshot", "screenshots", "path", "paths", "verification", "evidence")
ARTIFACT_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".json", ".md", ".html", ".zip", ".txt")


def field_value(row: dict[str, Any], field: str) -> Any:
    aliases = TRACE_FIELD_ALIASES.get(field, (field,))
    for alias in aliases:
        value = row.get(alias)
        if value not in (None, ""):
            return value
    return ""


def check_covers(check: dict[str, Any]) -> set[str]:
    values: list[Any] = [check.get("id"), check.get("covers")]
    if isinstance(check.get("covers"), list):
        values.extend(check["covers"])
    covered: set[str] = set()
    for value in values:
        if value is None:
            continue
        for item in str(value).replace(";", ",").split(","):
            clean = item.strip()
            if TRACE_ID_PATTERN.match(clean):
                covered.add(clean)
    return covered


def artifact_candidates(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    candidates: list[str] = []
    for item in values:
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        parts = re.split(r"[\s,;]+", text)
        for part in parts:
            clean = part.strip().strip("`'\"()[]")
            if clean and clean.lower().endswith(ARTIFACT_EXTENSIONS):
                candidates.append(clean)
    return candidates


def artifact_problems(items: list[dict[str, Any]], artifact_root: Path) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id") or item.get("name") or item.get("area") or "artifact evidence"
        for field in ARTIFACT_FIELDS:
            for candidate in artifact_candidates(item.get(field)):
                if candidate in seen:
                    continue
                seen.add(candidate)
                path = Path(candidate)
                if path.is_absolute():
                    problems.append(f"strict: artifact path must be relative to artifact root: {candidate}")
                    continue
                resolved = (artifact_root / path).resolve()
                try:
                    resolved.relative_to(artifact_root)
                except ValueError:
                    problems.append(f"strict: artifact path escapes artifact root: {candidate}")
                    continue
                if not resolved.exists():
                    problems.append(f"strict: artifact does not exist for {item_id}: {candidate}")
                elif not resolved.is_file():
                    problems.append(f"strict: artifact is not a file for {item_id}: {candidate}")
                elif resolved.stat().st_size == 0:
                    problems.append(f"strict: artifact is empty for {item_id}: {candidate}")
    return problems


def strict_problems(trace: Any, validation: dict[str, Any], artifact_root: Path | None = None) -> list[str]:
    problems: list[str] = []
    rows = trace_rows(trace)
    checks = validation_checks(validation)
    result = str(validation.get("result", "unknown")).strip().lower()
    passing_results = {"pass", "passed", "ok", "success", "pass-with-limitations"}
    nonpassing_check_statuses = {"fail", "failed", "blocked", "deferred", "skipped", "progress", "unknown"}

    if not rows:
        problems.append("strict: no UI trace rows supplied")
    if not checks:
        problems.append("strict: no validation checks supplied")
    if result not in passing_results:
        problems.append(f"strict: validation result is not passing: {result or 'empty'}")
    trace_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            problems.append(f"strict: trace row {index} is not an object")
            continue
        row_id = str(row.get("id", "")).strip()
        if not TRACE_ID_PATTERN.match(row_id):
            problems.append(f"strict: trace row {index} has invalid id: {row_id or 'empty'}")
        else:
            trace_ids.add(row_id)
        for field in TRACE_REQUIRED_FIELDS:
            if not str(field_value(row, field)).strip():
                problems.append(f"strict: trace row {row_id or index} missing {field}")
    covered_ids: set[str] = set()
    for check in checks:
        status = str(check.get("status", "")).strip().lower() or "unknown"
        covered_ids.update(check_covers(check))
        if status in nonpassing_check_statuses:
            check_id = check.get("id") or check.get("name") or "unnamed check"
            problems.append(f"strict: validation check is not passing: {check_id} status={status}")
    missing_coverage = sorted(trace_ids - covered_ids)
    for row_id in missing_coverage:
        problems.append(f"strict: trace row has no validation check coverage: {row_id}")
    if artifact_root is not None:
        artifact_items: list[dict[str, Any]] = []
        artifact_items.extend(row for row in rows if isinstance(row, dict))
        artifact_items.extend(check for check in checks if isinstance(check, dict))
        artifact_items.extend(attempt for attempt in validation_attempts(validation) if isinstance(attempt, dict))
        visual_diffs = validation.get("visual_differences", []) if isinstance(validation, dict) else []
        if isinstance(visual_diffs, list):
            artifact_items.extend(diff for diff in visual_diffs if isinstance(diff, dict))
        problems.extend(artifact_problems(artifact_items, artifact_root.resolve()))
    return problems


def generate(title: str, trace: Any, validation: dict[str, Any]) -> str:
    rows = trace_rows(trace)
    checks = validation_checks(validation)
    attempts = validation_attempts(validation)
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
    if attempts:
        lines.extend(["", "## Browser Attempts", ""])
        lines.append(table(
            ["Name", "Status", "Validation Type", "Limitation"],
            [
                [
                    attempt.get("name", ""),
                    attempt.get("status", ""),
                    attempt.get("validation_type", ""),
                    attempt.get("limitation", ""),
                ]
                for attempt in attempts
            ],
        ))
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
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when trace or validation evidence is incomplete or failing")
    parser.add_argument("--artifact-root", help="Optional root for strict artifact existence and non-empty checks")
    args = parser.parse_args()

    trace = load_json(Path(args.trace))
    validation = load_json(Path(args.validation))
    report = generate(args.title, trace, validation)
    if args.output:
        Path(args.output).write_text(report + "\n", encoding="utf-8")
    else:
        print(report)
    if args.strict:
        problems = strict_problems(trace, validation, Path(args.artifact_root).resolve() if args.artifact_root else None)
        if problems:
            for problem in problems:
                print(problem, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
