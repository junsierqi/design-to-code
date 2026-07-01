#!/usr/bin/env python3
"""Create a deterministic manifest for local design source artifacts."""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import extract_html_interactions  # noqa: E402


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
HTML_EXTENSIONS = {".html", ".htm"}
TEXT_EXTENSIONS = {".md", ".txt"}
JSON_EXTENSIONS = {".json"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | HTML_EXTENSIONS | TEXT_EXTENSIONS | JSON_EXTENSIONS | PDF_EXTENSIONS


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def image_size(path: Path) -> dict[str, int] | None:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return {"width": width, "height": height}
    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            length = int.from_bytes(data[index:index + 2], "big")
            if marker in range(0xC0, 0xC4) and index + 7 < len(data):
                height = int.from_bytes(data[index + 3:index + 5], "big")
                width = int.from_bytes(data[index + 5:index + 7], "big")
                return {"width": width, "height": height}
            index += max(length, 2)
    return None


def pdf_page_count(path: Path) -> int:
    data = path.read_bytes()
    return len(re.findall(rb"/Type\s*/Page\b", data))


def text_summary(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    headings = [line.lstrip("# ").strip() for line in lines if line.startswith("#")]
    return {
        "line_count": len(text.splitlines()),
        "non_empty_line_count": len(lines),
        "headings": headings[:20],
        "text_sample": " ".join(lines)[:500],
    }


def html_manifest(path: Path) -> dict[str, Any]:
    text = read_text(path)
    interactions = extract_html_interactions.extract(path)
    assets = sorted(set(re.findall(r"(?:src|href)\s*=\s*['\"]([^'\"]+\.(?:png|jpg|jpeg|webp|gif|svg|css|js))", text, re.I)))
    return {
        "path": str(path),
        "source_type": "html",
        "summary": text_summary(text),
        "assets": assets,
        "trace_seeds": interactions,
    }


def walk_figma_nodes(node: Any) -> list[dict[str, Any]]:
    if not isinstance(node, dict):
        return []
    items = []
    node_type = str(node.get("type", ""))
    if node_type:
        items.append({
            "id": str(node.get("id", "")),
            "name": str(node.get("name", "")),
            "type": node_type,
            "child_count": len(node.get("children", [])) if isinstance(node.get("children"), list) else 0,
        })
    for child in node.get("children", []) if isinstance(node.get("children"), list) else []:
        items.extend(walk_figma_nodes(child))
    return items


def figma_summary(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = walk_figma_nodes(payload.get("document"))
    frame_like_types = {"FRAME", "COMPONENT", "COMPONENT_SET", "INSTANCE"}
    frames = [node for node in nodes if node["type"] in frame_like_types]
    components = payload.get("components", {})
    styles = payload.get("styles", {})
    return {
        "document_name": payload.get("name", ""),
        "node_count": len(nodes),
        "frame_count": len(frames),
        "frames": frames[:50],
        "component_count": len(components) if isinstance(components, dict) else 0,
        "component_names": [str(value.get("name", key)) for key, value in list(components.items())[:50] if isinstance(value, dict)] if isinstance(components, dict) else [],
        "style_count": len(styles) if isinstance(styles, dict) else 0,
        "style_names": [str(value.get("name", key)) for key, value in list(styles.items())[:50] if isinstance(value, dict)] if isinstance(styles, dict) else [],
    }


def json_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(read_text(path))
    keys = sorted(payload.keys()) if isinstance(payload, dict) else []
    source_type = "json"
    if any(key.lower() in {"frames", "document", "components", "styles"} for key in keys):
        source_type = "figma-json"
    result = {
        "path": str(path),
        "source_type": source_type,
        "json_type": type(payload).__name__,
        "top_level_keys": keys[:50],
        "trace_seeds": [],
    }
    if source_type == "figma-json" and isinstance(payload, dict):
        result["figma_summary"] = figma_summary(payload)
    return result


def file_manifest(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    base = {
        "path": str(path),
        "name": path.name,
        "extension": suffix,
        "size_bytes": path.stat().st_size,
    }
    if suffix in HTML_EXTENSIONS:
        base.update(html_manifest(path))
    elif suffix in IMAGE_EXTENSIONS:
        base.update({"source_type": "image", "dimensions": image_size(path), "trace_seeds": []})
    elif suffix in PDF_EXTENSIONS:
        base.update({"source_type": "pdf", "page_count": pdf_page_count(path), "trace_seeds": []})
    elif suffix in TEXT_EXTENSIONS:
        base.update({"source_type": "text-spec", "summary": text_summary(read_text(path)), "trace_seeds": []})
    elif suffix in JSON_EXTENSIONS:
        base.update(json_manifest(path))
    else:
        raise ValueError(f"unsupported design source extension: {suffix or '<none>'}")
    return base


def analyze(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"design source not found: {path}")
    if path.is_dir():
        files = [child for child in sorted(path.rglob("*")) if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS]
        return {
            "path": str(path),
            "source_type": "directory",
            "file_count": len(files),
            "files": [file_manifest(child) for child in files],
        }
    return file_manifest(path)


def markdown(manifest: dict[str, Any]) -> str:
    lines = [
        f"# Design Source Manifest",
        "",
        f"- Path: `{manifest.get('path', '')}`",
        f"- Source type: {manifest.get('source_type', '')}",
    ]
    files = manifest.get("files")
    if isinstance(files, list):
        lines.append(f"- File count: {len(files)}")
        lines.extend(["", "| File | Type | Trace Seeds |", "|---|---|---|"])
        for item in files:
            lines.append(f"| `{Path(str(item.get('path', ''))).name}` | {item.get('source_type', '')} | {len(item.get('trace_seeds', []))} |")
    else:
        lines.append(f"- Trace seeds: {len(manifest.get('trace_seeds', []))}")
        if manifest.get("dimensions"):
            dimensions = manifest["dimensions"]
            lines.append(f"- Dimensions: {dimensions.get('width')}x{dimensions.get('height')}")
        if "page_count" in manifest:
            lines.append(f"- Page count: {manifest.get('page_count')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Local design source file or directory")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", help="Optional output path")
    args = parser.parse_args()

    try:
        manifest = analyze(Path(args.source))
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error))
    output = json.dumps(manifest, indent=2) + "\n" if args.format == "json" else markdown(manifest)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
