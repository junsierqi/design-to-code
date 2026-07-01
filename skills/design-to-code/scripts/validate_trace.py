#!/usr/bin/env python3
"""Validate design-to-code UI trace JSON before implementation or closeout."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


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
PASSING_STATUSES = {"pass", "passed", "ok", "complete", "completed", "implemented"}
DEFERRED_STATUSES = {"deferred", "blocked", "not-applicable", "not_applicable"}
ARTIFACT_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".json", ".md", ".html", ".zip", ".txt")
ARTIFACT_FIELDS = ("artifact", "artifacts", "screenshot", "screenshots", "path", "paths", "verification", "evidence")
SCHEMA_VERSION = "design-to-code.trace-validation.v1"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def trace_rows(trace: Any) -> list[dict[str, Any]]:
    if isinstance(trace, dict):
        for key in ("trace", "rows", "interactions"):
            rows = trace.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    if isinstance(trace, list):
        return [row for row in trace if isinstance(row, dict)]
    return []


def validation_checks(validation: Any) -> list[dict[str, Any]]:
    if isinstance(validation, dict) and isinstance(validation.get("checks"), list):
        return [check for check in validation["checks"] if isinstance(check, dict)]
    return []


def field_value(row: dict[str, Any], field: str) -> str:
    for alias in TRACE_FIELD_ALIASES.get(field, (field,)):
        value = row.get(alias)
        if value not in (None, ""):
            return str(value)
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
        for part in re.split(r"[\s,;]+", str(item).strip()):
            clean = part.strip().strip("`'\"()[]")
            if clean.lower().endswith(ARTIFACT_EXTENSIONS):
                candidates.append(clean)
    return candidates


def artifact_problems(items: list[dict[str, Any]], artifact_root: Path) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    resolved_root = artifact_root.resolve()
    for item in items:
        item_id = str(item.get("id") or item.get("name") or "artifact evidence")
        for field in ARTIFACT_FIELDS:
            for candidate in artifact_candidates(item.get(field)):
                if candidate in seen:
                    continue
                seen.add(candidate)
                path = Path(candidate)
                if path.is_absolute():
                    problems.append(f"artifact path must be relative to artifact root: {candidate}")
                    continue
                resolved = (resolved_root / path).resolve()
                try:
                    resolved.relative_to(resolved_root)
                except ValueError:
                    problems.append(f"artifact path escapes artifact root for {item_id}: {candidate}")
                    continue
                if not resolved.exists():
                    problems.append(f"artifact does not exist for {item_id}: {candidate}")
                elif not resolved.is_file():
                    problems.append(f"artifact is not a file for {item_id}: {candidate}")
                elif resolved.stat().st_size == 0:
                    problems.append(f"artifact is empty for {item_id}: {candidate}")
    return problems


def error_code(problem: str) -> str:
    if problem == "no UI trace rows supplied":
        return "TRACE_NO_ROWS"
    if "invalid id" in problem:
        return "TRACE_INVALID_ID"
    if problem.startswith("duplicate trace id"):
        return "TRACE_DUPLICATE_ID"
    if " missing " in problem:
        return "TRACE_MISSING_FIELD"
    if "deferred/blocked without a reason" in problem:
        return "TRACE_DEFERRED_REASON_MISSING"
    if problem.startswith("interaction row"):
        return "TRACE_INTERACTION_BEHAVIOR_MISSING"
    if problem == "validation has no checks":
        return "VALIDATION_NO_CHECKS"
    if "no validation check coverage" in problem:
        return "VALIDATION_COVERAGE_MISSING"
    if problem.startswith("artifact path must be relative"):
        return "ARTIFACT_ABSOLUTE_PATH"
    if "artifact path escapes" in problem:
        return "ARTIFACT_PATH_ESCAPE"
    if "artifact does not exist" in problem:
        return "ARTIFACT_MISSING"
    if "artifact is not a file" in problem:
        return "ARTIFACT_NOT_FILE"
    if "artifact is empty" in problem:
        return "ARTIFACT_EMPTY"
    return "TRACE_VALIDATION_ERROR"


def structured_errors(problems: list[str]) -> list[dict[str, str]]:
    return [{"code": error_code(problem), "message": problem} for problem in problems]


def validate_trace(trace: Any, validation: Any | None = None, artifact_root: Path | None = None) -> list[str]:
    problems: list[str] = []
    rows = trace_rows(trace)
    if not rows:
        problems.append("no UI trace rows supplied")
        return problems

    trace_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        row_id = str(row.get("id", "")).strip()
        if not TRACE_ID_PATTERN.match(row_id):
            problems.append(f"trace row {index} has invalid id: {row_id or 'empty'}")
        elif row_id in trace_ids:
            problems.append(f"duplicate trace id: {row_id}")
        else:
            trace_ids.add(row_id)
        for field in TRACE_REQUIRED_FIELDS:
            if not field_value(row, field).strip():
                problems.append(f"trace row {row_id or index} missing {field}")
        status = str(row.get("status", "")).strip().lower()
        deferred_reason = str(row.get("deferred_reason") or row.get("reason") or row.get("owner") or "").strip()
        if status in DEFERRED_STATUSES and not deferred_reason:
            problems.append(f"trace row {row_id or index} is deferred/blocked without a reason or owner")
        if str(row.get("type", "")).lower() in {"interaction", "i"} or row_id.startswith("I-"):
            behavior_status = str(row.get("behavior_status", "")).strip().lower()
            expected = field_value(row, "expected_ui_behavior").strip().lower()
            handler = str(row.get("handler", "")).strip()
            if behavior_status == "candidate-missing-handler" and status not in DEFERRED_STATUSES and "deferred" not in expected and not handler:
                problems.append(f"interaction row {row_id or index} has no detected behavior or deferred reason")

    if validation is not None:
        checks = validation_checks(validation)
        if not checks:
            problems.append("validation has no checks")
        covered: set[str] = set()
        for check in checks:
            covered.update(check_covers(check))
        for row_id in sorted(trace_ids - covered):
            problems.append(f"trace row has no validation check coverage: {row_id}")

    if artifact_root is not None:
        artifact_items = list(rows)
        if validation is not None:
            artifact_items.extend(validation_checks(validation))
        problems.extend(artifact_problems(artifact_items, artifact_root))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", help="Trace JSON path")
    parser.add_argument("--validation", help="Optional validation JSON path for coverage checks")
    parser.add_argument("--artifact-root", help="Optional root for artifact existence and non-empty checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    args = parser.parse_args()

    trace_path = Path(args.trace)
    if not trace_path.exists():
        raise SystemExit(f"trace file not found: {trace_path}")
    validation = load_json(Path(args.validation)) if args.validation else None
    artifact_root = Path(args.artifact_root).resolve() if args.artifact_root else None
    problems = validate_trace(load_json(trace_path), validation=validation, artifact_root=artifact_root)
    result = {
        "schema_version": SCHEMA_VERSION,
        "trace": str(trace_path),
        "ok": not problems,
        "problem_count": len(problems),
        "problems": problems,
        "errors": structured_errors(problems),
    }
    if args.json:
        print(json.dumps(result, indent=2))
    elif problems:
        print("design-to-code trace validation: FAIL")
        for problem in problems:
            print(f"- {problem}")
    else:
        print("design-to-code trace validation: PASS")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
