#!/usr/bin/env python3
"""Capture local or public design source evidence into a reproducible snapshot."""

from __future__ import annotations

import argparse
import json
import shutil
import socket
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import ProxyHandler, Request, build_opener


TEXT_TYPES = ("text/", "application/json", "application/xml", "application/xhtml+xml")


class SnapshotError(Exception):
    def __init__(self, diagnostic: dict[str, Any]) -> None:
        super().__init__(diagnostic["diagnostic"]["message"])
        self.diagnostic = diagnostic


def diagnostic(code: str, message: str, source: str, retryable: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "source": source,
        "diagnostic": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "details": details or {},
        },
    }


def classify_url_error(source: str, error: BaseException) -> dict[str, Any]:
    if isinstance(error, HTTPError):
        return diagnostic(
            "http-error",
            f"HTTP {error.code} while fetching design source: {source}",
            source,
            retryable=500 <= error.code < 600,
            details={"status": error.code, "reason": error.reason},
        )
    reason = error.reason if isinstance(error, URLError) else error
    reason_text = str(reason)
    if isinstance(reason, TimeoutError) or "timed out" in reason_text.lower():
        return diagnostic("timeout", f"Timed out while fetching design source: {source}", source, retryable=True)
    if isinstance(reason, ConnectionRefusedError) or "connection refused" in reason_text.lower():
        return diagnostic("connection-refused", f"Connection refused while fetching design source: {source}", source, retryable=True)
    if isinstance(reason, socket.gaierror):
        return diagnostic("dns-error", f"DNS lookup failed while fetching design source: {source}", source, retryable=True, details={"reason": reason_text})
    if isinstance(error, ValueError):
        return diagnostic("invalid-url", f"Invalid design source URL: {source}", source, retryable=False, details={"reason": reason_text})
    return diagnostic("url-error", f"Could not fetch design source: {source}", source, retryable=True, details={"reason": reason_text})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def is_probably_text(content_type: str, path: Path) -> bool:
    lowered = content_type.lower()
    return lowered.startswith(TEXT_TYPES) or path.suffix.lower() in {".html", ".htm", ".json", ".txt", ".md", ".svg", ".css", ".js"}


def sample_text(data: bytes, limit: int = 1200) -> str:
    return data[:limit].decode("utf-8", errors="replace")


def local_path_from_source(source: str) -> Path:
    parsed = urlparse(source)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path)).resolve()
    return Path(source).resolve()


def capture_local(source: str, output: Path) -> dict[str, Any]:
    path = local_path_from_source(source)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"design source not found: {source}")
    data = path.read_bytes()
    content_type = "text/html" if path.suffix.lower() in {".html", ".htm"} else "application/octet-stream"
    artifact = output / f"source-content{path.suffix or '.bin'}"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, artifact)
    return {
        "source": source,
        "source_type": "local-file",
        "path": str(path),
        "content_type": content_type,
        "size_bytes": len(data),
        "artifact": artifact.name,
        "text_sample": sample_text(data) if is_probably_text(content_type, path) else "",
    }


def capture_url(source: str, output: Path, timeout: float) -> dict[str, Any]:
    request = Request(source, headers={"User-Agent": "design-to-code-snapshot/1.0"})
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            data = response.read()
            final_url = response.geturl()
            content_type = response.headers.get("content-type", "application/octet-stream").split(";")[0]
            status = getattr(response, "status", 200)
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        raise SnapshotError(classify_url_error(source, error)) from error
    suffix = ".html" if is_probably_text(content_type, Path(urlparse(final_url).path)) else ".bin"
    artifact = output / f"source-content{suffix}"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(data)
    return {
        "source": source,
        "source_type": "url",
        "url": source,
        "final_url": final_url,
        "status": status,
        "content_type": content_type,
        "size_bytes": len(data),
        "artifact": artifact.name,
        "text_sample": sample_text(data) if is_probably_text(content_type, artifact) else "",
    }


def capture(source: str, output: Path, timeout: float = 10.0) -> dict[str, Any]:
    parsed = urlparse(source)
    output.mkdir(parents=True, exist_ok=True)
    if parsed.scheme in {"http", "https"}:
        snapshot = capture_url(source, output, timeout)
    elif parsed.scheme in {"", "file"} or (len(parsed.scheme) == 1 and parsed.scheme.isalpha()):
        snapshot = capture_local(source, output)
    else:
        raise ValueError(f"unsupported design source scheme: {parsed.scheme}")
    result = {"schema_version": "design-to-code.snapshot.v1", **snapshot}
    write_json(output / "snapshot.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Local path, file:// URL, or public http(s) URL")
    parser.add_argument("--output", required=True, help="Snapshot output directory")
    parser.add_argument("--timeout", type=float, default=10.0, help="URL fetch timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Print machine-readable result")
    args = parser.parse_args()
    try:
        result = capture(args.source, Path(args.output), timeout=args.timeout)
    except SnapshotError as error:
        if args.json:
            print(json.dumps(error.diagnostic, indent=2))
            return 1
        raise SystemExit(error.diagnostic["diagnostic"]["message"])
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("design snapshot: PASS")
        print(f"- source type: {result['source_type']}")
        print(f"- output: {Path(args.output).resolve()}")
        print(f"- artifact: {result['artifact']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
