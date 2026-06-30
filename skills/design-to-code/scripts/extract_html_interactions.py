#!/usr/bin/env python3
"""Extract UI trace seed rows from an HTML prototype."""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


INTERACTIVE_TAGS = {"button", "a", "input", "textarea", "select", "option", "form"}
EVENT_ATTRS = {
    "onclick",
    "onchange",
    "onsubmit",
    "oninput",
    "onkeydown",
    "onkeyup",
    "onfocus",
    "onblur",
}

FRAMEWORK_EVENT_PATTERNS = [
    ("jsx", re.compile(r"\bon(?P<event>Click|Change|Input|Submit|KeyDown|KeyUp|Focus|Blur)\s*=\s*[{'\"](?P<handler>[^}'\"]+)", re.IGNORECASE)),
    ("vue", re.compile(r"(?:@|v-on:)(?P<event>click|change|input|submit|keydown|keyup|focus|blur)(?:\.[A-Za-z0-9_.-]+)?\s*=\s*['\"](?P<handler>[^'\"]+)", re.IGNORECASE)),
    ("svelte", re.compile(r"\bon:(?P<event>click|change|input|submit|keydown|keyup|focus|blur)\s*=\s*[{'\"](?P<handler>[^}'\"]+)", re.IGNORECASE)),
]


class InteractionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, Any]] = []
        self._stack: list[dict[str, Any]] = []
        self._scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {name.lower(): value or "" for name, value in attrs}
        item = {"tag": tag.lower(), "attrs": attr, "text": []}
        self._stack.append(item)

        is_interactive = tag.lower() in INTERACTIVE_TAGS or attr.get("role") in {"button", "link", "tab", "menuitem"}
        has_event = any(name in attr for name in EVENT_ATTRS)
        is_editable = "contenteditable" in attr and attr.get("contenteditable", "true").lower() != "false"
        has_action_hint = any(name in attr for name in ("data-action", "data-click", "aria-expanded"))
        has_keyboard_hint = attr.get("tabindex", "") not in {"", "-1"}
        if is_interactive or has_event or is_editable or has_action_hint or has_keyboard_hint:
            self.rows.append(self._row(tag.lower(), attr, has_event, is_editable))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        while self._stack:
            item = self._stack.pop()
            if item["tag"] == tag:
                text = " ".join("".join(item["text"]).split())
                self._attach_text(item["tag"], item["attrs"], text)
                if self._stack and text:
                    self._stack[-1]["text"].append(text)
                break

    def handle_data(self, data: str) -> None:
        if self._stack:
            self._stack[-1]["text"].append(data)
            if self._stack[-1]["tag"] == "script":
                self._scripts.append(data)

    def _attach_text(self, tag: str, attrs: dict[str, str], text: str) -> None:
        if not text:
            return
        for row in reversed(self.rows):
            if row["_tag"] == tag and row["_attrs"] is attrs:
                row["label"] = text
                row["expected_behavior"] = expected_behavior(row)
                return

    def _row(self, tag: str, attrs: dict[str, str], has_event: bool, is_editable: bool) -> dict[str, Any]:
        row_id = f"I-{len(self.rows) + 1}"
        selector = selector_for(tag, attrs)
        trigger = trigger_for(tag, attrs, has_event, is_editable)
        row = {
            "id": row_id,
            "type": "interaction",
            "tag": tag,
            "selector": selector,
            "label": attrs.get("aria-label") or attrs.get("placeholder") or attrs.get("value") or attrs.get("name") or "",
            "trigger": trigger,
            "handler": first_handler(attrs),
            "behavior_status": behavior_status(tag, attrs, has_event, is_editable),
            "source_kind": "html",
            "expected_behavior": "",
            "_tag": tag,
            "_attrs": attrs,
        }
        row["expected_behavior"] = expected_behavior(row)
        return row

    def attach_script_handlers(self) -> None:
        handlers = script_event_handlers("\n".join(self._scripts))
        by_selector = {row["selector"]: row for row in self.rows}
        for selector, events in handlers.items():
            handler = ", ".join(f"addEventListener({event})" for event in sorted(events))
            row = by_selector.get(selector)
            if row:
                row["handler"] = row["handler"] or handler
                row["trigger"] = row["trigger"] if row["trigger"] != "click" else sorted(events)[0]
                row["behavior_status"] = "detected"
                row["expected_behavior"] = expected_behavior(row)
            else:
                self.rows.append({
                    "id": f"I-{len(self.rows) + 1}",
                    "type": "interaction",
                    "tag": "script-bound",
                    "selector": selector,
                    "label": selector,
                    "trigger": sorted(events)[0],
                    "handler": handler,
                    "behavior_status": "detected",
                    "source_kind": "script",
                    "expected_behavior": "Execute visible UI behavior from script event listener",
                })


def selector_for(tag: str, attrs: dict[str, str]) -> str:
    if attrs.get("id"):
        return f"#{attrs['id']}"
    if attrs.get("data-testid"):
        return f"[data-testid=\"{attrs['data-testid']}\"]"
    if attrs.get("data-action"):
        return f"[data-action=\"{attrs['data-action']}\"]"
    if attrs.get("name"):
        return f"{tag}[name=\"{attrs['name']}\"]"
    if attrs.get("aria-label"):
        return f"{tag}[aria-label=\"{attrs['aria-label']}\"]"
    if attrs.get("href"):
        return f"a[href=\"{attrs['href']}\"]"
    classes = attrs.get("class", "").split()
    if classes:
        return f"{tag}.{classes[0]}"
    return tag


def first_handler(attrs: dict[str, str]) -> str:
    for name in sorted(EVENT_ATTRS):
        if name in attrs:
            return f"{name}={attrs[name]}"
    return ""


def script_event_handlers(script: str) -> dict[str, set[str]]:
    handlers: dict[str, set[str]] = {}
    patterns = [
        r"document\s*\.\s*querySelector\s*\(\s*['\"](?P<selector>.+?)['\"]\s*\)\s*\.\s*addEventListener\s*\(\s*['\"](?P<event>[^'\"]+)['\"]",
        r"document\s*\.\s*getElementById\s*\(\s*['\"](?P<id>[^'\"]+)['\"]\s*\)\s*\.\s*addEventListener\s*\(\s*['\"](?P<event>[^'\"]+)['\"]",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, script):
            selector = match.groupdict().get("selector") or f"#{match.group('id')}"
            handlers.setdefault(selector, set()).add(match.group("event"))
    return handlers


def attrs_from_tag(tag_text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in re.finditer(r"([:@A-Za-z_][:@A-Za-z0-9_.-]*)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|{([^}]*)})", tag_text):
        attrs[match.group(1).lower()] = next(group for group in match.groups()[1:] if group is not None)
    return attrs


def selector_from_framework_tag(tag_name: str, attrs: dict[str, str]) -> str:
    return selector_for(tag_name.lower(), {
        "id": attrs.get("id", ""),
        "data-testid": attrs.get("data-testid", ""),
        "data-action": attrs.get("data-action", ""),
        "name": attrs.get("name", ""),
        "aria-label": attrs.get("aria-label", ""),
        "href": attrs.get("href", ""),
        "class": attrs.get("class", ""),
    })


def framework_event_rows(source: str, start_index: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tag_match in re.finditer(r"<(?P<tag>[A-Za-z][A-Za-z0-9_.:-]*)(?P<attrs>[^<>]*?)>", source, re.DOTALL):
        tag_text = tag_match.group(0)
        attrs = attrs_from_tag(tag_text)
        selector = selector_from_framework_tag(tag_match.group("tag"), attrs)
        for source_kind, pattern in FRAMEWORK_EVENT_PATTERNS:
            for event_match in pattern.finditer(tag_text):
                rows.append({
                    "id": f"I-{start_index + len(rows) + 1}",
                    "type": "interaction",
                    "tag": tag_match.group("tag"),
                    "selector": selector,
                    "label": attrs.get("aria-label") or attrs.get("placeholder") or attrs.get("value") or attrs.get("name") or selector,
                    "trigger": event_match.group("event").lower(),
                    "handler": f"{source_kind}:{event_match.group('event').lower()}={event_match.group('handler').strip()}",
                    "behavior_status": "detected",
                    "source_kind": source_kind,
                    "expected_behavior": f"Execute visible UI behavior from {source_kind} event binding",
                })
    return rows


def trigger_for(tag: str, attrs: dict[str, str], has_event: bool, is_editable: bool) -> str:
    if tag in {"input", "textarea", "select"} or is_editable:
        return "input"
    if tag == "form":
        return "submit"
    if has_event:
        for name in sorted(EVENT_ATTRS):
            if name in attrs:
                return name.removeprefix("on")
    return "click"


def behavior_status(tag: str, attrs: dict[str, str], has_event: bool, is_editable: bool) -> str:
    if has_event or is_editable or tag in {"a", "input", "textarea", "select", "form"}:
        return "detected"
    if attrs.get("href"):
        return "detected"
    return "candidate-missing-handler"


def expected_behavior(row: dict[str, Any]) -> str:
    if row["tag"] == "a":
        return "Navigate or update view"
    if row["tag"] == "form":
        return "Submit form and show success, validation, or error state"
    if row["trigger"] == "input":
        return "Accept input and update value, filtering, validation, or submission state"
    if row["handler"]:
        return "Execute visible UI behavior from handler"
    return "Provide visible click feedback or documented deferred behavior"


def public_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean = []
    for row in rows:
        clean.append({k: v for k, v in row.items() if not k.startswith("_")})
    return clean


def merge_duplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("selector", "")), str(row.get("trigger", "")))
        target = by_key.get(key)
        if not target:
            target = dict(row)
            by_key[key] = target
            merged.append(target)
            continue
        for field in ("source_kind", "handler"):
            values = [part.strip() for part in str(target.get(field, "")).split(",") if part.strip()]
            incoming = str(row.get(field, "")).strip()
            if incoming and incoming not in values:
                values.append(incoming)
            target[field] = ", ".join(values)
        if row.get("behavior_status") == "detected":
            target["behavior_status"] = "detected"
            target["expected_behavior"] = row.get("expected_behavior", target.get("expected_behavior", ""))
        if not target.get("label") and row.get("label"):
            target["label"] = row["label"]
    for index, row in enumerate(merged, start=1):
        row["id"] = f"I-{index}"
    return merged


def markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| ID | Element | Selector | Trigger | Handler | Expected Behavior |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {id} | {tag} {label} | `{selector}` | {trigger} | `{handler}` | {expected_behavior} |".format(
                **{k: str(v).replace("|", "\\|") for k, v in row.items()}
            )
        )
    return "\n".join(lines) + "\n"


def extract(path: Path) -> list[dict[str, Any]]:
    source = path.read_text(encoding="utf-8")
    parser = InteractionParser()
    parser.feed(source)
    parser.attach_script_handlers()
    rows = public_rows(parser.rows)
    rows.extend(framework_event_rows(source, len(rows)))
    return merge_duplicate_rows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", help="HTML prototype path")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", help="Optional output path")
    args = parser.parse_args()

    html_path = Path(args.html)
    if not html_path.exists():
        raise SystemExit(f"HTML file not found: {html_path}")
    rows = extract(html_path)
    output = json.dumps({"interactions": rows}, indent=2) + "\n" if args.format == "json" else markdown(rows)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
