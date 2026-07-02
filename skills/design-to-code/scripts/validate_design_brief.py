#!/usr/bin/env python3
"""Validate a design-to-code design brief before implementation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "design-to-code.design-brief.v1"
INTERACTIVITY_LEVELS = {"full", "static", "prototype"}
SOURCE_TYPES = {"image", "figma", "html", "pdf", "live-url", "wireframe", "other"}
REQUIRED_TOP_LEVEL = (
    "product_goal",
    "visual_sources",
    "interactivity_level",
    "target_surfaces",
    "acceptance_notes",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def validate_source(source: Any, index: int) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    prefix = f"visual_sources[{index}]"
    if not isinstance(source, dict):
        return [{"code": "invalid-source", "field": prefix, "message": "visual source must be an object"}]

    source_type = text(source.get("type"))
    if not source_type:
        errors.append({"code": "missing-source-type", "field": f"{prefix}.type", "message": "visual source type is required"})
    elif source_type not in SOURCE_TYPES:
        errors.append({"code": "invalid-source-type", "field": f"{prefix}.type", "message": f"visual source type must be one of: {', '.join(sorted(SOURCE_TYPES))}"})

    if not text(source.get("path")) and not text(source.get("url")) and not text(source.get("description")):
        errors.append({
            "code": "missing-source-location",
            "field": prefix,
            "message": "visual source needs path, url, or description",
        })

    return errors


def validate_brief(payload: Any) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        return [{"code": "invalid-root", "field": "$", "message": "design brief must be a JSON object"}]

    for field in REQUIRED_TOP_LEVEL:
        value = payload.get(field)
        if value in (None, "", [], {}):
            errors.append({"code": "missing-required-field", "field": field, "message": f"{field} is required"})

    if text(payload.get("schema_version")) and text(payload.get("schema_version")) != SCHEMA_VERSION:
        errors.append({"code": "unsupported-schema-version", "field": "schema_version", "message": f"schema_version must be {SCHEMA_VERSION}"})

    if not text(payload.get("product_goal")):
        errors.append({"code": "empty-product-goal", "field": "product_goal", "message": "product_goal must describe the product outcome"})

    level = text(payload.get("interactivity_level"))
    if level and level not in INTERACTIVITY_LEVELS:
        errors.append({"code": "invalid-interactivity-level", "field": "interactivity_level", "message": f"interactivity_level must be one of: {', '.join(sorted(INTERACTIVITY_LEVELS))}"})

    sources = payload.get("visual_sources")
    if isinstance(sources, list):
        if not sources:
            errors.append({"code": "empty-visual-sources", "field": "visual_sources", "message": "at least one visual source is required"})
        for index, source in enumerate(sources):
            errors.extend(validate_source(source, index))
    elif sources is not None:
        errors.append({"code": "invalid-visual-sources", "field": "visual_sources", "message": "visual_sources must be a list"})

    surfaces = payload.get("target_surfaces")
    if isinstance(surfaces, list):
        if not any(text(item) for item in surfaces):
            errors.append({"code": "empty-target-surfaces", "field": "target_surfaces", "message": "target_surfaces needs at least one surface such as desktop or mobile"})
    elif surfaces is not None:
        errors.append({"code": "invalid-target-surfaces", "field": "target_surfaces", "message": "target_surfaces must be a list"})

    notes = payload.get("acceptance_notes")
    if isinstance(notes, list):
        if not any(text(item) for item in notes):
            errors.append({"code": "empty-acceptance-notes", "field": "acceptance_notes", "message": "acceptance_notes needs at least one observable acceptance note"})
    elif notes is not None:
        errors.append({"code": "invalid-acceptance-notes", "field": "acceptance_notes", "message": "acceptance_notes must be a list"})

    return errors


def result_payload(path: Path, errors: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "brief": str(path),
        "ok": not errors,
        "error_count": len(errors),
        "errors": errors,
        "problems": [error["message"] for error in errors],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a design-to-code design brief JSON file.")
    parser.add_argument("brief", help="Path to design brief JSON")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    args = parser.parse_args()

    path = Path(args.brief)
    if not path.exists():
        errors = [{"code": "brief-not-found", "field": "brief", "message": f"design brief not found: {path}"}]
        payload = result_payload(path, errors)
    else:
        try:
            payload = result_payload(path, validate_brief(load_json(path)))
        except json.JSONDecodeError as exc:
            payload = result_payload(path, [{"code": "invalid-json", "field": "brief", "message": f"invalid JSON: {exc.msg}"}])

    if args.json:
        print(json.dumps(payload, indent=2))
    elif payload["ok"]:
        print("design brief validation: PASS")
    else:
        print("design brief validation: FAIL")
        for error in payload["errors"]:
            print(f"- {error['field']}: {error['message']}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
