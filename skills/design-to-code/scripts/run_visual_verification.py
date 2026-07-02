#!/usr/bin/env python3
"""Run or plan design-to-code visual verification checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "design-to-code.visual-verification.v1"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def validate_config(config: Any) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(config, dict):
        return [{"code": "invalid-config", "field": "$", "message": "visual verification config must be an object"}]
    routes = list_of_dicts(config.get("routes"))
    viewports = list_of_dicts(config.get("viewports"))
    if not routes:
        errors.append({"code": "missing-routes", "field": "routes", "message": "at least one route is required"})
    if not viewports:
        errors.append({"code": "missing-viewports", "field": "viewports", "message": "at least one viewport is required"})
    for index, route in enumerate(routes):
        if not str(route.get("name") or "").strip():
            errors.append({"code": "missing-route-name", "field": f"routes[{index}].name", "message": "route name is required"})
        if not str(route.get("url") or route.get("path") or "").strip():
            errors.append({"code": "missing-route-target", "field": f"routes[{index}]", "message": "route needs url or path"})
    for index, viewport in enumerate(viewports):
        if not str(viewport.get("name") or "").strip():
            errors.append({"code": "missing-viewport-name", "field": f"viewports[{index}].name", "message": "viewport name is required"})
        for field in ("width", "height"):
            value = viewport.get(field)
            if not isinstance(value, int) or value <= 0:
                errors.append({"code": "invalid-viewport-size", "field": f"viewports[{index}].{field}", "message": f"{field} must be a positive integer"})
    return errors


def planned_checks(config: dict[str, Any], artifact_root: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for route in list_of_dicts(config.get("routes")):
        route_name = str(route.get("name") or "route")
        target = str(route.get("url") or route.get("path") or "")
        for viewport in list_of_dicts(config.get("viewports")):
            viewport_name = str(viewport.get("name") or "viewport")
            screenshot = route.get("screenshot")
            if not screenshot:
                screenshot = f"{route_name}-{viewport_name}.png".lower().replace(" ", "-")
            screenshot_path = Path(str(screenshot))
            screenshot_exists = (artifact_root / screenshot_path).exists() if not screenshot_path.is_absolute() else screenshot_path.exists()
            checks.append(
                {
                    "id": f"{route_name}:{viewport_name}",
                    "route": route_name,
                    "target": target,
                    "viewport": {
                        "name": viewport_name,
                        "width": viewport.get("width"),
                        "height": viewport.get("height"),
                    },
                    "screenshot": str(screenshot_path),
                    "screenshot_exists": screenshot_exists,
                    "status": "planned",
                }
            )
    return checks


def run_browser_command(command: str, config: Path, output: Path, timeout: int) -> dict[str, Any]:
    if not command.strip():
        return {
            "status": "blocked",
            "reason": "browser command not provided",
            "returncode": None,
            "stdout": "",
            "stderr": "",
        }
    expanded = command.replace("{config}", str(config)).replace("{output}", str(output))
    try:
        result = subprocess.run(expanded, shell=True, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "fail",
            "reason": "browser command timed out",
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    return {
        "status": "pass" if result.returncode == 0 else "fail",
        "reason": "browser command completed" if result.returncode == 0 else "browser command failed",
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": expanded,
    }


def build_result(config_path: Path, config: Any, artifact_root: Path, browser: dict[str, Any] | None) -> dict[str, Any]:
    errors = validate_config(config)
    config_object = config if isinstance(config, dict) else {}
    checks = [] if errors else planned_checks(config_object, artifact_root)
    status = "fail" if errors else "planned"
    if browser is not None:
        status = browser["status"] if not errors else "fail"
    return {
        "schema_version": SCHEMA_VERSION,
        "config": str(config_path),
        "artifact_root": str(artifact_root),
        "status": status,
        "ok": status in {"planned", "pass"},
        "errors": errors,
        "checks": checks,
        "browser_run": browser,
        "summary": {
            "route_count": len(list_of_dicts(config_object.get("routes"))),
            "viewport_count": len(list_of_dicts(config_object.get("viewports"))),
            "check_count": len(checks),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or run visual verification for design-to-code UI work.")
    parser.add_argument("config", help="Visual verification JSON config")
    parser.add_argument("--artifact-root", default=".", help="Directory for screenshot artifacts")
    parser.add_argument("--run-browser", action="store_true", help="Run the configured browser command")
    parser.add_argument("--browser-command", default="", help="Command to run for browser verification; {config} and {output} placeholders are supported")
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("--timeout", type=int, default=60, help="Browser command timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    args = parser.parse_args()

    config_path = Path(args.config)
    artifact_root = Path(args.artifact_root)
    try:
        config = load_json(config_path)
    except FileNotFoundError:
        config = {}
        result = build_result(config_path, config, artifact_root, None)
        result["errors"].append({"code": "config-not-found", "field": "config", "message": f"config not found: {config_path}"})
        result["status"] = "fail"
        result["ok"] = False
    except json.JSONDecodeError as exc:
        result = build_result(config_path, {}, artifact_root, None)
        result["errors"].append({"code": "invalid-json", "field": "config", "message": f"invalid JSON: {exc.msg}"})
        result["status"] = "fail"
        result["ok"] = False
    else:
        browser = run_browser_command(args.browser_command, config_path, Path(args.output or ""), args.timeout) if args.run_browser else None
        result = build_result(config_path, config, artifact_root, browser)

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    if args.json or not args.output:
        print(json.dumps(result, indent=2))
    else:
        print(f"visual verification: {result['status']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
