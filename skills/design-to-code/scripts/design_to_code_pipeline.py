#!/usr/bin/env python3
"""Run a local design-to-code tooling pipeline for HTML design sources."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import analyze_design_source  # noqa: E402
import extract_html_interactions  # noqa: E402
import generate_acceptance_report  # noqa: E402
import generate_playwright_checks  # noqa: E402
import trace_to_acceptance_matrix  # noqa: E402
import ui_smoke_check  # noqa: E402
import validate_trace  # noqa: E402


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_trace(source: Path) -> dict[str, Any]:
    rows = []
    for row in extract_html_interactions.extract(source):
        rows.append({
            "id": row["id"],
            "type": "interaction",
            "source_evidence": row.get("selector", ""),
            "selector": row.get("selector", ""),
            "expected_ui_behavior": row.get("expected_behavior", ""),
            "implementation": str(source),
            "verification": "pipeline generated source-only validation",
            "status": "pass" if row.get("behavior_status") == "detected" else "deferred",
            "behavior_status": row.get("behavior_status", ""),
            "handler": row.get("handler", ""),
            "deferred_reason": "" if row.get("behavior_status") == "detected" else "Pipeline detected candidate control without behavior.",
        })
    return {"rows": rows}


def build_validation(trace: dict[str, Any], smoke: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for row in trace.get("rows", []):
        checks.append({
            "id": f"TC-{row['id']}",
            "covers": row["id"],
            "name": f"Pipeline source check {row['id']}",
            "status": "pass" if row.get("status") == "pass" else "deferred",
            "evidence": row.get("verification", "pipeline generated validation"),
        })
    checks.append({
        "id": "TC-SMOKE-1",
        "name": "UI smoke check",
        "status": "pass" if smoke.get("ok") else "fail",
        "evidence": f"{smoke.get('finding_count', 0)} smoke findings",
    })
    return {
        "validation_type": "fixture-only",
        "result": "pass" if all(check["status"] == "pass" for check in checks) else "progress",
        "checks": checks,
        "limitations": "Pipeline validates local fixture/source artifacts only; it does not run a browser.",
    }


def run_pipeline(source: Path, output: Path) -> dict[str, Any]:
    if not source.exists():
        raise FileNotFoundError(f"source not found: {source}")
    output.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, str]] = []

    manifest = analyze_design_source.analyze(source)
    write_json(output / "manifest.json", manifest)
    steps.append({"name": "manifest", "status": "pass", "artifact": "manifest.json"})

    trace = build_trace(source)
    write_json(output / "trace.json", trace)
    steps.append({"name": "trace", "status": "pass", "artifact": "trace.json"})

    smoke = ui_smoke_check.smoke_check(source)
    write_json(output / "smoke.json", smoke)
    steps.append({"name": "smoke", "status": "pass" if smoke["ok"] else "fail", "artifact": "smoke.json"})

    validation = build_validation(trace, smoke)
    write_json(output / "validation.json", validation)
    problems = validate_trace.validate_trace(trace, validation=validation)
    steps.append({"name": "validate_trace", "status": "pass" if not problems else "fail", "artifact": "validation.json"})

    spec = generate_playwright_checks.generate(trace, default_url="/")
    (output / "ui-trace.spec.js").write_text(spec, encoding="utf-8")
    steps.append({"name": "playwright_spec", "status": "pass", "artifact": "ui-trace.spec.js"})

    matrix = trace_to_acceptance_matrix.markdown(trace_to_acceptance_matrix.generate(trace))
    (output / "acceptance-matrix.md").write_text(matrix, encoding="utf-8")
    steps.append({"name": "acceptance_matrix", "status": "pass", "artifact": "acceptance-matrix.md"})

    report = generate_acceptance_report.generate("Design-to-code Pipeline Acceptance Report", trace, validation)
    (output / "acceptance-report.md").write_text(report + "\n", encoding="utf-8")
    steps.append({"name": "acceptance_report", "status": "pass", "artifact": "acceptance-report.md"})

    result = {
        "source": str(source),
        "output": str(output),
        "ok": all(step["status"] == "pass" for step in steps),
        "steps": steps,
        "trace_problem_count": len(problems),
        "trace_problems": problems,
    }
    write_json(output / "pipeline-result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="HTML design source path")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--json", action="store_true", help="Print machine-readable result")
    args = parser.parse_args()
    try:
        result = run_pipeline(Path(args.source), Path(args.output))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"design-to-code pipeline: {'PASS' if result['ok'] else 'FAIL'}")
        print(f"output: {result['output']}")
        for step in result["steps"]:
            print(f"- {step['name']}: {step['status']} ({step['artifact']})")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
