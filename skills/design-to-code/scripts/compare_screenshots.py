#!/usr/bin/env python3
"""Compare PNG screenshots with dependency-light pixel metrics."""

from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path
from typing import Any


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    distances = (abs(estimate - left), abs(estimate - up), abs(estimate - upper_left))
    if distances[0] <= distances[1] and distances[0] <= distances[2]:
        return left
    if distances[1] <= distances[2]:
        return up
    return upper_left


def read_png(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"not a PNG file: {path}")
    index = len(PNG_SIGNATURE)
    width = height = color_type = bit_depth = None
    compressed = bytearray()
    while index + 8 <= len(data):
        length = int.from_bytes(data[index:index + 4], "big")
        chunk_type = data[index + 4:index + 8]
        chunk_data = data[index + 8:index + 8 + length]
        index += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk_data[:10])
            if bit_depth != 8 or color_type not in {0, 2, 6}:
                raise ValueError(f"unsupported PNG format in {path}: bit_depth={bit_depth} color_type={color_type}")
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            break
    if width is None or height is None or color_type is None:
        raise ValueError(f"missing PNG IHDR: {path}")
    channels = {0: 1, 2: 3, 6: 4}[color_type]
    raw = zlib.decompress(bytes(compressed))
    stride = width * channels
    rows: list[bytes] = []
    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        scanline = bytearray(raw[offset:offset + stride])
        offset += stride
        for i, value in enumerate(scanline):
            left = scanline[i - channels] if i >= channels else 0
            up = previous[i]
            upper_left = previous[i - channels] if i >= channels else 0
            if filter_type == 1:
                scanline[i] = (value + left) & 0xFF
            elif filter_type == 2:
                scanline[i] = (value + up) & 0xFF
            elif filter_type == 3:
                scanline[i] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                scanline[i] = (value + paeth(left, up, upper_left)) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG filter {filter_type} in {path}")
        rows.append(bytes(scanline))
        previous = scanline
    return {"path": str(path), "width": width, "height": height, "channels": channels, "rows": rows}


def compare(expected: Path, actual: Path, threshold: float | None = None) -> dict[str, Any]:
    left = read_png(expected)
    right = read_png(actual)
    same_dimensions = left["width"] == right["width"] and left["height"] == right["height"]
    comparable_rows = min(left["height"], right["height"])
    comparable_bytes = 0
    different_bytes = 0
    for row_index in range(comparable_rows):
        left_row = left["rows"][row_index]
        right_row = right["rows"][row_index]
        width = min(len(left_row), len(right_row))
        comparable_bytes += width
        different_bytes += sum(1 for i in range(width) if left_row[i] != right_row[i])
    dimension_penalty = 0 if same_dimensions else 1
    diff_ratio = 1.0 if comparable_bytes == 0 else different_bytes / comparable_bytes
    passed = same_dimensions and (threshold is None or diff_ratio <= threshold)
    if dimension_penalty:
        passed = False
    return {
        "expected": {"path": left["path"], "width": left["width"], "height": left["height"]},
        "actual": {"path": right["path"], "width": right["width"], "height": right["height"]},
        "same_dimensions": same_dimensions,
        "different_bytes": different_bytes,
        "compared_bytes": comparable_bytes,
        "diff_ratio": diff_ratio,
        "threshold": threshold,
        "ok": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", required=True, help="Expected/baseline PNG")
    parser.add_argument("--actual", required=True, help="Actual PNG")
    parser.add_argument("--threshold", type=float, default=None, help="Maximum allowed byte diff ratio")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    args = parser.parse_args()

    try:
        result = compare(Path(args.expected), Path(args.actual), threshold=args.threshold)
    except (OSError, ValueError, zlib.error) as error:
        raise SystemExit(str(error))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "PASS" if result["ok"] else "FAIL"
        print(f"screenshot comparison: {status}")
        print(f"- same dimensions: {result['same_dimensions']}")
        print(f"- diff ratio: {result['diff_ratio']:.6f}")
        if result["threshold"] is not None:
            print(f"- threshold: {result['threshold']:.6f}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
