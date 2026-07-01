#!/usr/bin/env python3
"""Run lightweight source-level UI smoke checks for HTML artifacts."""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


CONTROL_TAGS = {"button", "a", "input", "textarea", "select"}
ROLE_CONTROLS = {"button", "link", "tab", "menuitem", "switch", "checkbox"}


class SmokeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.controls: list[dict[str, Any]] = []
        self.images: list[dict[str, str]] = []
        self._stack: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = {name.lower(): value or "" for name, value in attrs}
        item = {"tag": tag, "attrs": attr, "text": []}
        self._stack.append(item)
        if tag in CONTROL_TAGS or attr.get("role") in ROLE_CONTROLS:
            self.controls.append(item)
        if tag == "img":
            self.images.append(attr)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        while self._stack:
            item = self._stack.pop()
            text = " ".join("".join(item["text"]).split())
            item["label_text"] = text
            if self._stack and text:
                self._stack[-1]["text"].append(text)
            if item["tag"] == tag:
                break

    def handle_data(self, data: str) -> None:
        if self._stack:
            self._stack[-1]["text"].append(data)


def accessible_name(control: dict[str, Any]) -> str:
    attrs = control["attrs"]
    return attrs.get("aria-label") or attrs.get("title") or attrs.get("alt") or attrs.get("placeholder") or attrs.get("value") or control.get("label_text", "")


def selector(control: dict[str, Any]) -> str:
    attrs = control["attrs"]
    if attrs.get("id"):
        return f"#{attrs['id']}"
    if attrs.get("data-testid"):
        return f"[data-testid=\"{attrs['data-testid']}\"]"
    if attrs.get("aria-label"):
        return f"{control['tag']}[aria-label=\"{attrs['aria-label']}\"]"
    return control["tag"]


def smoke_check(path: Path, long_text_limit: int = 80, i18n: bool = False) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    parser = SmokeParser()
    parser.feed(text)
    findings: list[dict[str, str]] = []
    for control in parser.controls:
        name = accessible_name(control).strip()
        if not name:
            findings.append({"severity": "error", "check": "accessible-name", "target": selector(control), "message": "interactive control has no accessible name"})
        if len(name) > long_text_limit:
            findings.append({"severity": "warning", "check": "long-control-text", "target": selector(control), "message": "control text may overflow narrow layouts"})
    for attrs in parser.images:
        if "alt" not in attrs:
            findings.append({"severity": "warning", "check": "image-alt", "target": attrs.get("src", "img"), "message": "image is missing alt text"})
    long_texts = [match.strip() for match in re.findall(r">([^<>]{%d,})<" % long_text_limit, text)]
    for value in long_texts[:20]:
        findings.append({"severity": "warning", "check": "long-text", "target": value[:40], "message": "visible text may need responsive wrapping or i18n expansion checks"})
    if i18n:
        literal_texts = [match.strip() for match in re.findall(r">([A-Za-z][A-Za-z0-9 ,.'!?/-]{3,})<", text)]
        for value in literal_texts[:20]:
            findings.append({"severity": "info", "check": "i18n-literal", "target": value[:40], "message": "visible hardcoded text should use the project i18n system when available"})
    return {"path": str(path), "ok": not any(f["severity"] == "error" for f in findings), "finding_count": len(findings), "findings": findings}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", help="HTML file to inspect")
    parser.add_argument("--long-text-limit", type=int, default=80)
    parser.add_argument("--i18n", action="store_true", help="Report visible hardcoded text hints")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when any finding is present")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    args = parser.parse_args()

    html = Path(args.html)
    if not html.exists():
        raise SystemExit(f"HTML file not found: {html}")
    result = smoke_check(html, long_text_limit=args.long_text_limit, i18n=args.i18n)
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["findings"]:
        print("ui smoke check: FINDINGS")
        for finding in result["findings"]:
            print(f"- {finding['severity']} {finding['check']} {finding['target']}: {finding['message']}")
    else:
        print("ui smoke check: PASS")
    return 1 if (args.strict and result["findings"]) or not result["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
