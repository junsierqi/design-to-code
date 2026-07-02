#!/usr/bin/env python3
"""Validate design-to-code asset handling manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "design-to-code.asset-manifest.v1"
ASSET_TYPES = {"image", "logo", "icon", "font", "token", "video", "other"}
STATUSES = {"implemented", "reused", "generated", "deferred", "missing", "not-needed"}
REQUIRED_FIELDS = ("id", "type", "source_evidence", "handling_decision", "status")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def asset_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("assets"), list):
        return [asset for asset in payload["assets"] if isinstance(asset, dict)]
    if isinstance(payload, list):
        return [asset for asset in payload if isinstance(asset, dict)]
    return []


def validate_asset(asset: dict[str, Any], index: int, seen: set[str]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    prefix = f"assets[{index}]"
    asset_id = text(asset.get("id"))
    for field in REQUIRED_FIELDS:
        if not text(asset.get(field)):
            errors.append({"code": "missing-required-field", "field": f"{prefix}.{field}", "message": f"{field} is required"})
    if asset_id:
        if asset_id in seen:
            errors.append({"code": "duplicate-asset-id", "field": f"{prefix}.id", "message": f"duplicate asset id: {asset_id}"})
        seen.add(asset_id)
    asset_type = text(asset.get("type"))
    if asset_type and asset_type not in ASSET_TYPES:
        errors.append({"code": "invalid-asset-type", "field": f"{prefix}.type", "message": f"type must be one of: {', '.join(sorted(ASSET_TYPES))}"})
    status = text(asset.get("status"))
    if status and status not in STATUSES:
        errors.append({"code": "invalid-status", "field": f"{prefix}.status", "message": f"status must be one of: {', '.join(sorted(STATUSES))}"})
    required = bool(asset.get("required", True))
    if required and status in {"implemented", "reused", "generated"} and not text(asset.get("implementation_target")):
        errors.append({
            "code": "missing-implementation-target",
            "field": f"{prefix}.implementation_target",
            "message": "implemented, reused, or generated required assets need implementation_target",
        })
    if required and status in {"deferred", "missing"} and not text(asset.get("deferred_reason")):
        errors.append({
            "code": "missing-deferred-reason",
            "field": f"{prefix}.deferred_reason",
            "message": "deferred or missing required assets need deferred_reason",
        })
    if required and not text(asset.get("handling_decision")):
        errors.append({
            "code": "missing-handling-decision",
            "field": f"{prefix}.handling_decision",
            "message": "required assets need a handling decision",
        })
    return errors


def validate_manifest(payload: Any) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(payload, (dict, list)):
        return [{"code": "invalid-root", "field": "$", "message": "asset manifest must be an object or list"}]
    if isinstance(payload, dict):
        version = text(payload.get("schema_version"))
        if version and version != SCHEMA_VERSION:
            errors.append({"code": "unsupported-schema-version", "field": "schema_version", "message": f"schema_version must be {SCHEMA_VERSION}"})
        if "assets" not in payload:
            errors.append({"code": "missing-assets", "field": "assets", "message": "assets list is required"})
    rows = asset_rows(payload)
    if not rows:
        errors.append({"code": "empty-assets", "field": "assets", "message": "at least one asset row is required"})
    seen: set[str] = set()
    for index, asset in enumerate(rows):
        errors.extend(validate_asset(asset, index, seen))
    return errors


def result_payload(path: Path, payload: Any, errors: list[dict[str, str]]) -> dict[str, Any]:
    rows = asset_rows(payload)
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest": str(path),
        "ok": not errors,
        "asset_count": len(rows),
        "error_count": len(errors),
        "errors": errors,
        "problems": [error["message"] for error in errors],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a design-to-code asset manifest JSON file.")
    parser.add_argument("manifest", help="Asset manifest JSON path")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    args = parser.parse_args()

    path = Path(args.manifest)
    if not path.exists():
        payload: Any = {}
        errors = [{"code": "manifest-not-found", "field": "manifest", "message": f"asset manifest not found: {path}"}]
    else:
        try:
            payload = load_json(path)
            errors = validate_manifest(payload)
        except json.JSONDecodeError as exc:
            payload = {}
            errors = [{"code": "invalid-json", "field": "manifest", "message": f"invalid JSON: {exc.msg}"}]

    result = result_payload(path, payload, errors)
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["ok"]:
        print("asset manifest validation: PASS")
    else:
        print("asset manifest validation: FAIL")
        for error in result["errors"]:
            print(f"- {error['field']}: {error['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
