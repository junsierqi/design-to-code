#!/usr/bin/env python3
"""Generate a Playwright spec scaffold from design-to-code UI trace JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


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


def js_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def safe_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", " ", value).strip().lower()
    return text or "trace row"


def row_kind(row: dict[str, Any]) -> str:
    row_id = str(row.get("id", ""))
    kind = str(row.get("type") or row.get("tag") or "").lower()
    if row_id.startswith("I-") or "interaction" in kind:
        return "interaction"
    if row_id.startswith("S-") or "state" in kind:
        return "state"
    if row_id.startswith("R-") or "responsive" in kind:
        return "responsive"
    if row_id.startswith("A-") or "accessibility" in kind:
        return "accessibility"
    return "component"


def selector_for(row: dict[str, Any]) -> str:
    return str(row.get("selector") or row.get("source_evidence") or "").strip()


def expected_for(row: dict[str, Any]) -> str:
    return str(row.get("expected_ui_behavior") or row.get("expected_behavior") or "").strip()


def test_block(row: dict[str, Any], default_url: str) -> str:
    row_id = str(row.get("id", "TRACE"))
    kind = row_kind(row)
    selector = selector_for(row)
    expected = expected_for(row)
    title = f"{row_id} {safe_name(expected or selector or kind)}"
    lines = [
        f"test({js_string(title)}, async ({{ page }}) => {{",
        f"  // Covers: {row_id}",
        f"  // Source evidence: {selector or 'not supplied'}",
        f"  // Expected behavior: {expected or 'not supplied'}",
        f"  await page.goto(process.env.PLAYWRIGHT_BASE_URL || {js_string(default_url)});",
    ]
    if selector:
        lines.append(f"  const target = page.locator({js_string(selector)}).first();")
        lines.append("  await expect(target).toBeVisible();")
    else:
        lines.append("  // TODO: Add a stable selector for this trace row.")
        lines.append("  const target = page.getByRole('main');")
        lines.append("  await expect(target).toBeVisible();")
    if kind == "interaction":
        trigger = str(row.get("trigger") or "click").lower()
        if trigger == "input":
            lines.append("  await target.fill('design-to-code check');")
            lines.append("  await expect(target).toHaveValue(/design-to-code check/);")
        else:
            lines.append("  await target.click();")
            lines.append("  // TODO: Assert the visible state change, navigation, mutation, or feedback for this interaction.")
    elif kind == "state":
        lines.append("  // TODO: Arrange fixture/mock data that reaches this state, then assert the visible state.")
    elif kind == "responsive":
        lines.insert(1, "  await page.setViewportSize({ width: 390, height: 844 });")
        lines.append("  await expect(page.locator('body')).toBeVisible();")
    elif kind == "accessibility":
        lines.append("  await expect(target).toBeEnabled();")
        lines.append("  // TODO: Verify keyboard path, focus visibility, and accessible name where applicable.")
    else:
        lines.append("  await expect(target).toBeVisible();")
    lines.append(f"  await page.screenshot({{ path: path.join(artifacts, {js_string(row_id.lower() + '.png')}), fullPage: true }});")
    lines.append("});")
    return "\n".join(lines)


def generate(trace: Any, default_url: str = "/") -> str:
    rows = trace_rows(trace)
    header = """const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const artifacts = path.join(__dirname, '..', 'artifacts');

test.beforeAll(() => {
  fs.mkdirSync(artifacts, { recursive: true });
});

test.beforeEach(async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('close', () => {
    expect(errors).toEqual([]);
  });
});
"""
    if not rows:
        return header + "\n\ntest('trace scaffold placeholder', async ({ page }) => {\n  await page.goto(process.env.PLAYWRIGHT_BASE_URL || '/');\n  await expect(page.locator('body')).toBeVisible();\n  // TODO: Add UI trace rows before relying on this generated spec.\n});\n"
    return header + "\n\n" + "\n\n".join(test_block(row, default_url) for row in rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True, help="Trace JSON path")
    parser.add_argument("--output", help="Output Playwright spec path")
    parser.add_argument("--default-url", default="/", help="Fallback URL when PLAYWRIGHT_BASE_URL is not set")
    args = parser.parse_args()

    trace_path = Path(args.trace)
    if not trace_path.exists():
        raise SystemExit(f"trace file not found: {trace_path}")
    spec = generate(load_json(trace_path), default_url=args.default_url)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(spec, encoding="utf-8")
    else:
        print(spec, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
