#!/usr/bin/env python3
"""Regression tests for the design-to-code skill repository validator."""

from __future__ import annotations

import importlib.util
import json
import argparse
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[3]


def selected_repo_root() -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root", help="Repository root to validate")
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0], *remaining]
    if args.root:
        return Path(args.root).resolve()
    cwd = Path.cwd().resolve()
    return cwd if (cwd / "skills" / "design-to-code" / "SKILL.md").exists() else SCRIPT_REPO_ROOT


REPO_ROOT = selected_repo_root()
VALIDATOR_PATH = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "validate_design_to_code.py"
DOGFOOD_PATH = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "dogfood_playwright_fixture.py"

spec = importlib.util.spec_from_file_location("validate_design_to_code", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)


def write_test_png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    compressed = zlib.compress(raw)

    def chunk(name: bytes, data: bytes) -> bytes:
        import binascii

        return len(data).to_bytes(4, "big") + name + data + binascii.crc32(name + data).to_bytes(4, "big")

    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes([8, 2, 0, 0, 0])
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b""))


class ValidateDesignToCodeTests(unittest.TestCase):
    def test_current_repository_contract_passes(self) -> None:
        problems = validator.validate(REPO_ROOT)
        self.assertEqual([], problems)

    def test_current_repository_strict_contract_passes(self) -> None:
        problems = validator.validate(REPO_ROOT, strict=True)
        self.assertEqual([], problems)

    def test_strict_validation_reports_missing_referenced_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp) / "repo"
            shutil.copytree(REPO_ROOT, tmp_root, ignore=shutil.ignore_patterns(".git", ".idea-to-code"))
            skill = tmp_root / "skills" / "design-to-code" / "SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8") + "\nRead `references/missing-reference.md` when broken.\n",
                encoding="utf-8",
            )

            problems = validator.validate(tmp_root, strict=True)

        self.assertIn(
            "strict: SKILL.md references missing file: skills/design-to-code/references/missing-reference.md",
            problems,
        )

    def test_missing_reference_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp) / "repo"
            shutil.copytree(REPO_ROOT, tmp_root, ignore=shutil.ignore_patterns(".git", ".idea-to-code"))
            target = tmp_root / "skills" / "design-to-code" / "references" / "ui-verification.md"
            target.unlink()

            problems = validator.validate(tmp_root)

        self.assertIn("missing required file: skills/design-to-code/references/ui-verification.md", problems)

    def test_legacy_standalone_gate_text_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp) / "repo"
            shutil.copytree(REPO_ROOT, tmp_root, ignore=shutil.ignore_patterns(".git", ".idea-to-code"))
            skill = tmp_root / "skills" / "design-to-code" / "SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8") + "\nFully autonomous. Zero user interaction\n",
                encoding="utf-8",
            )

            problems = validator.validate(tmp_root)

        self.assertIn(
            "SKILL.md still contains standalone legacy phrase: Fully autonomous. Zero user interaction",
            problems,
        )

    def test_design_rule_contract_terms_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp) / "repo"
            shutil.copytree(REPO_ROOT, tmp_root, ignore=shutil.ignore_patterns(".git", ".idea-to-code"))
            reference = tmp_root / "skills" / "design-to-code" / "references" / "ui-implementation.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace("Design Token Mapping", "Token Mapping Removed"),
                encoding="utf-8",
            )

            problems = validator.validate(tmp_root)

        self.assertIn(
            "skills/design-to-code/references/ui-implementation.md missing required phrase: Design Token Mapping",
            problems,
        )

    def test_html_interaction_extractor_outputs_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "prototype.html"
            html.write_text(
                """
                <form onsubmit="saveProject()">
                  <input id="search" placeholder="Search projects" oninput="filterRows()" />
                  <button id="new-project" onclick="openCreate()">New project</button>
                  <button id="archive-project">Archive</button>
                  <div data-action="exportCsv">Export</div>
                  <a href="/reports">Reports</a>
                  <div role="button" aria-label="Retry">Retry</div>
                  <script>
                    document.getElementById('archive-project').addEventListener('click', archiveProject);
                    document.querySelector('[data-action="exportCsv"]').addEventListener('keydown', exportCsv);
                  </script>
                </form>
                """,
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "extract_html_interactions.py"
            json_result = subprocess.run(
                [sys.executable, str(script), str(html)],
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(json_result.stdout)
            markdown_result = subprocess.run(
                [sys.executable, str(script), str(html), "--format", "markdown"],
                text=True,
                capture_output=True,
                check=True,
            )

        selectors = {row["selector"] for row in payload["interactions"]}
        self.assertIn("#search", selectors)
        self.assertIn("#new-project", selectors)
        self.assertIn("#archive-project", selectors)
        self.assertIn('[data-action="exportCsv"]', selectors)
        self.assertIn('a[href="/reports"]', selectors)
        archive = next(row for row in payload["interactions"] if row["selector"] == "#archive-project")
        export = next(row for row in payload["interactions"] if row["selector"] == '[data-action="exportCsv"]')
        self.assertEqual("detected", archive["behavior_status"])
        self.assertIn("addEventListener(click)", archive["handler"])
        self.assertEqual("detected", export["behavior_status"])
        self.assertIn("addEventListener(keydown)", export["handler"])
        self.assertIn("I-1", markdown_result.stdout)
        self.assertIn("Expected Behavior", markdown_result.stdout)

    def test_html_interaction_extractor_preserves_distinct_fallback_elements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "prototype.html"
            html.write_text(
                """
                <main>
                  <button>Save</button>
                  <button>Cancel</button>
                </main>
                """,
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "extract_html_interactions.py"
            result = subprocess.run(
                [sys.executable, str(script), str(html)],
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(result.stdout)

        labels = [row["label"] for row in payload["interactions"]]
        selectors = [row["selector"] for row in payload["interactions"]]
        self.assertEqual(["Save", "Cancel"], labels)
        self.assertEqual(["I-1", "I-2"], [row["id"] for row in payload["interactions"]])
        self.assertEqual(2, len(set(selectors)))
        self.assertTrue(all("button" in selector for selector in selectors))
        self.assertTrue(all(":nth-of-type(" in selector for selector in selectors))

    def test_html_interaction_extractor_preserves_distinct_class_fallback_elements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "prototype.html"
            html.write_text(
                """
                <main>
                  <button class="secondary">Save draft</button>
                  <button class="secondary">Discard draft</button>
                </main>
                """,
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "extract_html_interactions.py"
            result = subprocess.run(
                [sys.executable, str(script), str(html)],
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(result.stdout)

        labels = [row["label"] for row in payload["interactions"]]
        selectors = [row["selector"] for row in payload["interactions"]]
        self.assertEqual(["Save draft", "Discard draft"], labels)
        self.assertEqual(2, len(set(selectors)))
        self.assertTrue(all("button.secondary" in selector for selector in selectors))

    def test_html_interaction_extractor_detects_framework_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "prototype.html"
            source.write_text(
                """
                <Button data-testid="jsx-save" onClick={saveProject}>Save</Button>
                <button data-testid="vue-save" @click="saveProject">Save</button>
                <form data-testid="vue-form" v-on:submit.prevent="submitProject"></form>
                <button data-testid="svelte-save" on:click={saveProject}>Save</button>
                """,
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "extract_html_interactions.py"
            result = subprocess.run(
                [sys.executable, str(script), str(source)],
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(result.stdout)

        by_selector = {row["selector"]: row for row in payload["interactions"]}
        self.assertIn("jsx", by_selector['[data-testid="jsx-save"]']["source_kind"])
        self.assertIn("vue", by_selector['[data-testid="vue-save"]']["source_kind"])
        self.assertIn("vue", by_selector['[data-testid="vue-form"]']["source_kind"])
        self.assertIn("svelte", by_selector['[data-testid="svelte-save"]']["source_kind"])
        self.assertEqual(4, len(payload["interactions"]))
        self.assertEqual("detected", by_selector['[data-testid="vue-save"]']["behavior_status"])

    def test_acceptance_report_generator_outputs_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace = tmp_path / "trace.json"
            validation = tmp_path / "validation.json"
            report = tmp_path / "report.md"
            trace.write_text(
                json.dumps({
                    "rows": [
                        {
                            "id": "C-1",
                            "type": "component",
                            "source_evidence": "reference.png",
                            "expected_ui_behavior": "Header visible",
                            "implementation": "src/Header.tsx:10",
                            "verification": "screenshot header.png",
                            "status": "pass",
                        }
                    ]
                }),
                encoding="utf-8",
            )
            validation.write_text(
                json.dumps({
                    "validation_type": "manual-inspection",
                    "result": "pass-with-limitations",
                    "checks": [{"id": "C-1", "name": "Header", "status": "pass", "evidence": "visible"}],
                    "attempts": [{"name": "system browser fallback", "status": "pass", "validation_type": "real-product-path", "limitation": "used Chrome"}],
                    "visual_differences": [{"area": "gap", "design": "16", "implementation": "18", "reason": "token", "accepted": True}],
                }),
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "generate_acceptance_report.py"
            subprocess.run(
                [sys.executable, str(script), "--trace", str(trace), "--validation", str(validation), "--output", str(report)],
                text=True,
                capture_output=True,
                check=True,
            )
            text = report.read_text(encoding="utf-8")

        self.assertIn("## UI Trace", text)
        self.assertIn("| ID | Type | Source Evidence | Expected UI / Behavior | Implementation | Verification | Status |", text)
        self.assertIn("src/Header.tsx:10", text)
        self.assertIn("screenshot header.png", text)
        self.assertIn("## Validation Checks", text)
        self.assertIn("## Browser Attempts", text)
        self.assertIn("system browser fallback", text)
        self.assertIn("## Visual Differences", text)
        self.assertIn("pass-with-limitations", text)

    def test_acceptance_report_generator_accepts_utf8_bom_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace = tmp_path / "trace.json"
            validation = tmp_path / "validation.json"
            report = tmp_path / "report.md"
            trace.write_text('{"rows":[]}', encoding="utf-8-sig")
            validation.write_text('{"validation_type":"manual-inspection","result":"pass"}', encoding="utf-8-sig")
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "generate_acceptance_report.py"
            subprocess.run(
                [sys.executable, str(script), "--trace", str(trace), "--validation", str(validation), "--output", str(report)],
                text=True,
                capture_output=True,
                check=True,
            )
            text = report.read_text(encoding="utf-8")

        self.assertIn("Result: pass", text)

    def test_acceptance_report_strict_passes_complete_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace = tmp_path / "trace.json"
            validation = tmp_path / "validation.json"
            report = tmp_path / "report.md"
            trace.write_text(
                json.dumps({
                    "rows": [
                        {
                            "id": "I-1",
                            "type": "interaction",
                            "source_evidence": "#save",
                            "expected_ui_behavior": "Save feedback appears",
                            "implementation": "src/App.tsx:10",
                            "verification": "test save feedback",
                            "status": "pass",
                        }
                    ]
                }),
                encoding="utf-8",
            )
            validation.write_text(
                json.dumps({
                    "validation_type": "source-only",
                    "result": "pass",
                    "checks": [{"id": "I-1", "name": "Save", "status": "pass", "evidence": "asserted"}],
                }),
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "generate_acceptance_report.py"
            result = subprocess.run(
                [sys.executable, str(script), "--trace", str(trace), "--validation", str(validation), "--output", str(report), "--strict"],
                text=True,
                capture_output=True,
                check=True,
            )
            report_exists = report.exists()

        self.assertEqual("", result.stderr)
        self.assertTrue(report_exists)

    def test_acceptance_report_strict_fails_incomplete_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace = tmp_path / "trace.json"
            validation = tmp_path / "validation.json"
            report = tmp_path / "report.md"
            trace.write_text('{"rows":[]}', encoding="utf-8")
            validation.write_text(
                json.dumps({
                    "validation_type": "source-only",
                    "result": "progress",
                    "checks": [{"id": "I-1", "name": "Save", "status": "fail", "evidence": "missing"}],
                }),
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "generate_acceptance_report.py"
            result = subprocess.run(
                [sys.executable, str(script), "--trace", str(trace), "--validation", str(validation), "--output", str(report), "--strict"],
                text=True,
                capture_output=True,
            )
            report_exists = report.exists()

        self.assertEqual(1, result.returncode)
        self.assertIn("strict: no UI trace rows supplied", result.stderr)
        self.assertIn("strict: validation result is not passing: progress", result.stderr)
        self.assertIn("strict: validation check is not passing: I-1 status=fail", result.stderr)
        self.assertTrue(report_exists)

    def test_acceptance_report_strict_fails_invalid_trace_schema_and_missing_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace = tmp_path / "trace.json"
            validation = tmp_path / "validation.json"
            report = tmp_path / "report.md"
            trace.write_text(
                json.dumps({
                    "rows": [
                        {
                            "id": "I-1",
                            "type": "interaction",
                            "source_evidence": "#save",
                            "expected_ui_behavior": "Save feedback appears",
                            "implementation": "src/App.tsx:10",
                            "verification": "test save feedback",
                            "status": "pass",
                        },
                        {
                            "id": "bad-id",
                            "type": "component",
                            "source_evidence": "header frame",
                            "expected_ui_behavior": "Header visible",
                            "status": "pass",
                        },
                    ]
                }),
                encoding="utf-8",
            )
            validation.write_text(
                json.dumps({
                    "validation_type": "source-only",
                    "result": "pass",
                    "checks": [{"id": "C-99", "name": "Unrelated", "status": "pass", "evidence": "asserted"}],
                }),
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "generate_acceptance_report.py"
            result = subprocess.run(
                [sys.executable, str(script), "--trace", str(trace), "--validation", str(validation), "--output", str(report), "--strict"],
                text=True,
                capture_output=True,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("strict: trace row 2 has invalid id: bad-id", result.stderr)
        self.assertIn("strict: trace row bad-id missing implementation", result.stderr)
        self.assertIn("strict: trace row bad-id missing verification", result.stderr)
        self.assertIn("strict: trace row has no validation check coverage: I-1", result.stderr)

    def test_acceptance_report_strict_validates_artifacts_when_root_supplied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifacts = tmp_path / "artifacts"
            artifacts.mkdir()
            screenshot = artifacts / "save.png"
            screenshot.write_bytes(b"not empty")
            trace = tmp_path / "trace.json"
            validation = tmp_path / "validation.json"
            report = tmp_path / "report.md"
            trace.write_text(
                json.dumps({
                    "rows": [
                        {
                            "id": "I-1",
                            "type": "interaction",
                            "source_evidence": "#save",
                            "expected_ui_behavior": "Save feedback appears",
                            "implementation": "src/App.tsx:10",
                            "verification": "save.png",
                            "status": "pass",
                        }
                    ]
                }),
                encoding="utf-8",
            )
            validation.write_text(
                json.dumps({
                    "validation_type": "source-only",
                    "result": "pass",
                    "checks": [{"id": "I-1", "name": "Save", "status": "pass", "evidence": "save.png"}],
                }),
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "generate_acceptance_report.py"
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--trace",
                    str(trace),
                    "--validation",
                    str(validation),
                    "--output",
                    str(report),
                    "--strict",
                    "--artifact-root",
                    str(artifacts),
                ],
                text=True,
                capture_output=True,
            )

        self.assertEqual(0, result.returncode, result.stderr)

    def test_acceptance_report_strict_fails_missing_or_empty_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifacts = tmp_path / "artifacts"
            artifacts.mkdir()
            (artifacts / "empty.png").write_bytes(b"")
            trace = tmp_path / "trace.json"
            validation = tmp_path / "validation.json"
            report = tmp_path / "report.md"
            trace.write_text(
                json.dumps({
                    "rows": [
                        {
                            "id": "I-1",
                            "type": "interaction",
                            "source_evidence": "#save",
                            "expected_ui_behavior": "Save feedback appears",
                            "implementation": "src/App.tsx:10",
                            "verification": "missing.png",
                            "status": "pass",
                        }
                    ]
                }),
                encoding="utf-8",
            )
            validation.write_text(
                json.dumps({
                    "validation_type": "source-only",
                    "result": "pass",
                    "checks": [{"id": "I-1", "name": "Save", "status": "pass", "evidence": "empty.png"}],
                }),
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "generate_acceptance_report.py"
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--trace",
                    str(trace),
                    "--validation",
                    str(validation),
                    "--output",
                    str(report),
                    "--strict",
                    "--artifact-root",
                    str(artifacts),
                ],
                text=True,
                capture_output=True,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("strict: artifact does not exist for I-1: missing.png", result.stderr)
        self.assertIn("strict: artifact is empty for I-1: empty.png", result.stderr)

    def test_validate_trace_cli_passes_complete_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifacts = tmp_path / "artifacts"
            artifacts.mkdir()
            (artifacts / "save.png").write_bytes(b"image")
            trace = tmp_path / "trace.json"
            validation = tmp_path / "validation.json"
            trace.write_text(
                json.dumps({
                    "rows": [
                        {
                            "id": "I-1",
                            "type": "interaction",
                            "source_evidence": "#save",
                            "expected_ui_behavior": "Save feedback appears",
                            "implementation": "src/App.tsx:10",
                            "verification": "save.png",
                            "status": "pass",
                            "behavior_status": "detected",
                            "handler": "onclick=save",
                        }
                    ]
                }),
                encoding="utf-8",
            )
            validation.write_text(
                json.dumps({"checks": [{"id": "TC-I-1", "covers": "I-1", "status": "pass", "evidence": "save.png"}]}),
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "validate_trace.py"
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    str(trace),
                    "--validation",
                    str(validation),
                    "--artifact-root",
                    str(artifacts),
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(result.stdout)

        self.assertTrue(payload["ok"])
        self.assertEqual([], payload["problems"])
        self.assertEqual("design-to-code.trace-validation.v1", payload["schema_version"])
        self.assertEqual([], payload["errors"])

    def test_validate_trace_cli_fails_invalid_rows_and_missing_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace = tmp_path / "trace.json"
            validation = tmp_path / "validation.json"
            trace.write_text(
                json.dumps({
                    "rows": [
                        {
                            "id": "bad-id",
                            "type": "interaction",
                            "source_evidence": "#export",
                            "expected_ui_behavior": "Export runs",
                            "implementation": "",
                            "verification": "",
                            "status": "pass",
                            "behavior_status": "candidate-missing-handler",
                        },
                        {
                            "id": "S-1",
                            "type": "state",
                            "source_evidence": "error view",
                            "expected_ui_behavior": "Error renders",
                            "implementation": "src/App.tsx",
                            "verification": "manual",
                            "status": "deferred",
                        },
                    ]
                }),
                encoding="utf-8",
            )
            validation.write_text(json.dumps({"checks": [{"id": "TC-X", "covers": "C-9", "status": "pass"}]}), encoding="utf-8")
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "validate_trace.py"
            result = subprocess.run(
                [sys.executable, str(script), str(trace), "--validation", str(validation)],
                text=True,
                capture_output=True,
            )
            json_result = subprocess.run(
                [sys.executable, str(script), str(trace), "--validation", str(validation), "--json"],
                text=True,
                capture_output=True,
            )
            payload = json.loads(json_result.stdout)

        self.assertEqual(1, result.returncode)
        self.assertIn("trace row 1 has invalid id: bad-id", result.stdout)
        self.assertIn("trace row bad-id missing implementation", result.stdout)
        self.assertIn("interaction row bad-id has no detected behavior or deferred reason", result.stdout)
        self.assertIn("trace row S-1 is deferred/blocked without a reason or owner", result.stdout)
        self.assertIn("trace row has no validation check coverage: S-1", result.stdout)
        codes = {error["code"] for error in payload["errors"]}
        self.assertIn("TRACE_INVALID_ID", codes)
        self.assertIn("TRACE_MISSING_FIELD", codes)
        self.assertIn("TRACE_INTERACTION_BEHAVIOR_MISSING", codes)
        self.assertIn("TRACE_DEFERRED_REASON_MISSING", codes)
        self.assertIn("VALIDATION_COVERAGE_MISSING", codes)

    def test_validate_trace_cli_checks_artifact_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            artifacts = tmp_path / "artifacts"
            artifacts.mkdir()
            (artifacts / "empty.png").write_bytes(b"")
            trace = tmp_path / "trace.json"
            trace.write_text(
                json.dumps({
                    "rows": [
                        {
                            "id": "C-1",
                            "type": "component",
                            "source_evidence": "frame",
                            "expected_ui_behavior": "Header visible",
                            "implementation": "src/Header.tsx",
                            "verification": "missing.png empty.png",
                            "status": "pass",
                        }
                    ]
                }),
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "validate_trace.py"
            result = subprocess.run(
                [sys.executable, str(script), str(trace), "--artifact-root", str(artifacts)],
                text=True,
                capture_output=True,
            )
            json_result = subprocess.run(
                [sys.executable, str(script), str(trace), "--artifact-root", str(artifacts), "--json"],
                text=True,
                capture_output=True,
            )
            payload = json.loads(json_result.stdout)

        self.assertEqual(1, result.returncode)
        self.assertIn("artifact does not exist for C-1: missing.png", result.stdout)
        self.assertIn("artifact is empty for C-1: empty.png", result.stdout)
        codes = {error["code"] for error in payload["errors"]}
        self.assertIn("ARTIFACT_MISSING", codes)
        self.assertIn("ARTIFACT_EMPTY", codes)

    def test_trace_to_acceptance_matrix_outputs_markdown_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace = tmp_path / "trace.json"
            matrix = tmp_path / "matrix.md"
            trace.write_text(
                json.dumps({
                    "rows": [
                        {"id": "C-1", "type": "component", "source_evidence": "header", "expected_ui_behavior": "Header renders", "verification": "screenshot"},
                        {"id": "I-1", "type": "interaction", "selector": "#save", "expected_behavior": "Save toast appears", "verification": "playwright"},
                        {"id": "S-1", "type": "state", "source_evidence": "error fixture", "expected_ui_behavior": "Error state renders"},
                        {"id": "R-1", "type": "responsive", "source_evidence": "mobile frame", "expected_ui_behavior": "Stacks on mobile"},
                        {"id": "A-1", "type": "accessibility", "source_evidence": "icon button", "expected_ui_behavior": "Accessible name exists"},
                    ]
                }),
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "trace_to_acceptance_matrix.py"
            subprocess.run(
                [sys.executable, str(script), str(trace), "--output", str(matrix)],
                text=True,
                capture_output=True,
                check=True,
            )
            json_result = subprocess.run(
                [sys.executable, str(script), str(trace), "--format", "json"],
                text=True,
                capture_output=True,
                check=True,
            )
            markdown_text = matrix.read_text(encoding="utf-8")
            payload = json.loads(json_result.stdout)

        self.assertIn("| ID | User Goal Fit | Acceptance Examples |", markdown_text)
        self.assertIn("C-1", markdown_text)
        self.assertIn("I-1", markdown_text)
        self.assertEqual(5, len(payload["rows"]))
        by_id = {row["ID"]: row for row in payload["rows"]}
        self.assertEqual("real-product-path", by_id["I-1"]["Validation Type"])
        self.assertEqual("source-only", by_id["C-1"]["Validation Type"])

    def test_canonical_examples_pass_current_tools(self) -> None:
        examples = REPO_ROOT / "skills" / "design-to-code" / "examples"
        trace = examples / "trace.json"
        validation = examples / "validation.json"
        html = examples / "pipeline-source.html"
        validator_script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "validate_trace.py"
        analyzer_script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "analyze_design_source.py"
        matrix_script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "trace_to_acceptance_matrix.py"
        trace_result = subprocess.run(
            [sys.executable, str(validator_script), str(trace), "--validation", str(validation), "--json"],
            text=True,
            capture_output=True,
            check=True,
        )
        manifest_result = subprocess.run(
            [sys.executable, str(analyzer_script), str(html)],
            text=True,
            capture_output=True,
            check=True,
        )
        matrix_result = subprocess.run(
            [sys.executable, str(matrix_script), str(trace), "--format", "json"],
            text=True,
            capture_output=True,
            check=True,
        )
        trace_payload = json.loads(trace_result.stdout)
        manifest_payload = json.loads(manifest_result.stdout)
        matrix_payload = json.loads(matrix_result.stdout)

        self.assertTrue(trace_payload["ok"])
        self.assertEqual("html", manifest_payload["source_type"])
        self.assertGreaterEqual(len(manifest_payload["trace_seeds"]), 2)
        self.assertEqual(2, len(matrix_payload["rows"]))

    def test_generate_playwright_checks_maps_trace_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace = tmp_path / "trace.json"
            spec = tmp_path / "ui-trace.spec.js"
            trace.write_text(
                json.dumps({
                    "rows": [
                        {
                            "id": "C-1",
                            "type": "component",
                            "source_evidence": "main",
                            "expected_ui_behavior": "Dashboard renders",
                            "implementation": "src/App.tsx",
                            "verification": "screenshot",
                            "status": "pass",
                        },
                        {
                            "id": "I-1",
                            "type": "interaction",
                            "selector": "#search",
                            "trigger": "input",
                            "expected_behavior": "Search filters rows",
                            "implementation": "src/App.tsx",
                            "verification": "playwright",
                            "status": "pass",
                        },
                        {
                            "id": "R-1",
                            "type": "responsive",
                            "source_evidence": "mobile frame",
                            "expected_ui_behavior": "Mobile stacks content",
                            "implementation": "src/App.css",
                            "verification": "viewport",
                            "status": "pass",
                        },
                        {
                            "id": "A-1",
                            "type": "accessibility",
                            "source_evidence": "button[aria-label='Save']",
                            "expected_ui_behavior": "Save has accessible name",
                            "implementation": "src/App.tsx",
                            "verification": "role locator",
                            "status": "pass",
                        },
                    ]
                }),
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "generate_playwright_checks.py"
            subprocess.run(
                [sys.executable, str(script), "--trace", str(trace), "--output", str(spec), "--default-url", "/dashboard"],
                text=True,
                capture_output=True,
                check=True,
            )
            text = spec.read_text(encoding="utf-8")

        self.assertIn("Covers: C-1", text)
        self.assertIn("Covers: I-1", text)
        self.assertIn("await target.fill('design-to-code check');", text)
        self.assertIn("await page.setViewportSize({ width: 390, height: 844 });", text)
        self.assertIn("Verify keyboard path", text)
        self.assertIn("PLAYWRIGHT_BASE_URL", text)
        self.assertIn("/dashboard", text)

    def test_generate_playwright_checks_outputs_placeholder_for_empty_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.json"
            trace.write_text('{"rows":[]}', encoding="utf-8")
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "generate_playwright_checks.py"
            result = subprocess.run(
                [sys.executable, str(script), "--trace", str(trace)],
                text=True,
                capture_output=True,
                check=True,
            )

        self.assertIn("trace scaffold placeholder", result.stdout)
        self.assertIn("Add UI trace rows", result.stdout)

    def test_analyze_design_source_extracts_html_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "prototype.html"
            html.write_text(
                """
                <main>
                  <h1>Projects</h1>
                  <button id="save" onclick="saveProject()">Save</button>
                  <img src="hero.png" />
                </main>
                """,
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "analyze_design_source.py"
            result = subprocess.run(
                [sys.executable, str(script), str(html)],
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(result.stdout)

        self.assertEqual("html", payload["source_type"])
        self.assertIn("hero.png", payload["assets"])
        self.assertEqual("I-1", payload["trace_seeds"][0]["id"])
        self.assertEqual("#save", payload["trace_seeds"][0]["selector"])

    def test_analyze_design_source_reports_image_and_pdf_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            png = tmp_path / "frame.png"
            pdf = tmp_path / "mockup.pdf"
            png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (320).to_bytes(4, "big") + (200).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
            pdf.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /Type /Page >> endobj\n")
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "analyze_design_source.py"
            png_result = subprocess.run([sys.executable, str(script), str(png)], text=True, capture_output=True, check=True)
            pdf_result = subprocess.run([sys.executable, str(script), str(pdf)], text=True, capture_output=True, check=True)
            png_payload = json.loads(png_result.stdout)
            pdf_payload = json.loads(pdf_result.stdout)

        self.assertEqual("image", png_payload["source_type"])
        self.assertEqual({"width": 320, "height": 200}, png_payload["dimensions"])
        self.assertEqual("pdf", pdf_payload["source_type"])
        self.assertEqual(2, pdf_payload["page_count"])

    def test_analyze_design_source_directory_manifest_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.md").write_text("# Flow\n\nClick save.", encoding="utf-8")
            (root / "figma.json").write_text('{"document":{},"components":{}}', encoding="utf-8")
            (root / "ignore.bin").write_bytes(b"ignored")
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "analyze_design_source.py"
            json_result = subprocess.run([sys.executable, str(script), str(root)], text=True, capture_output=True, check=True)
            md_result = subprocess.run([sys.executable, str(script), str(root), "--format", "markdown"], text=True, capture_output=True, check=True)
            payload = json.loads(json_result.stdout)

        self.assertEqual("directory", payload["source_type"])
        self.assertEqual(2, payload["file_count"])
        self.assertEqual(["figma-json", "text-spec"], sorted(item["source_type"] for item in payload["files"]))
        self.assertIn("| File | Type | Trace Seeds |", md_result.stdout)

    def test_analyze_design_source_reports_missing_input(self) -> None:
        script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "analyze_design_source.py"
        result = subprocess.run(
            [sys.executable, str(script), str(Path("missing-design-source.png"))],
            text=True,
            capture_output=True,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("design source not found", result.stderr or result.stdout)

    def test_compare_screenshots_passes_identical_pngs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            expected = tmp_path / "expected.png"
            actual = tmp_path / "actual.png"
            write_test_png(expected, 2, 2, (255, 0, 0))
            write_test_png(actual, 2, 2, (255, 0, 0))
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "compare_screenshots.py"
            result = subprocess.run(
                [sys.executable, str(script), "--expected", str(expected), "--actual", str(actual), "--threshold", "0", "--json"],
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(result.stdout)

        self.assertTrue(payload["ok"])
        self.assertEqual(0, payload["different_bytes"])

    def test_compare_screenshots_fails_threshold_and_dimension_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            expected = tmp_path / "expected.png"
            actual = tmp_path / "actual.png"
            mismatch = tmp_path / "mismatch.png"
            write_test_png(expected, 2, 2, (255, 0, 0))
            write_test_png(actual, 2, 2, (0, 0, 255))
            write_test_png(mismatch, 3, 2, (255, 0, 0))
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "compare_screenshots.py"
            diff_result = subprocess.run(
                [sys.executable, str(script), "--expected", str(expected), "--actual", str(actual), "--threshold", "0.01", "--json"],
                text=True,
                capture_output=True,
            )
            dimension_result = subprocess.run(
                [sys.executable, str(script), "--expected", str(expected), "--actual", str(mismatch), "--json"],
                text=True,
                capture_output=True,
            )
            diff_payload = json.loads(diff_result.stdout)
            dimension_payload = json.loads(dimension_result.stdout)

        self.assertEqual(1, diff_result.returncode)
        self.assertGreater(diff_payload["diff_ratio"], 0.01)
        self.assertEqual(1, dimension_result.returncode)
        self.assertFalse(dimension_payload["same_dimensions"])

    def test_ui_smoke_check_reports_accessibility_and_i18n_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "prototype.html"
            html.write_text(
                """
                <main>
                  <button><svg></svg></button>
                  <img src="hero.png">
                  <p>This is a very long visible sentence that should be wrapped carefully on narrow mobile layouts.</p>
                  <button aria-label="Save">OK</button>
                </main>
                """,
                encoding="utf-8",
            )
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "ui_smoke_check.py"
            result = subprocess.run(
                [sys.executable, str(script), str(html), "--i18n", "--strict", "--json"],
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)
            checks = {finding["check"] for finding in payload["findings"]}

        self.assertEqual(1, result.returncode)
        self.assertIn("accessible-name", checks)
        self.assertIn("image-alt", checks)
        self.assertIn("long-text", checks)
        self.assertIn("i18n-literal", checks)

    def test_ui_smoke_check_passes_named_controls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "prototype.html"
            html.write_text('<main><button aria-label="Save"></button><img src="hero.png" alt="Hero"></main>', encoding="utf-8")
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "ui_smoke_check.py"
            result = subprocess.run(
                [sys.executable, str(script), str(html), "--strict", "--json"],
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(result.stdout)

        self.assertTrue(payload["ok"])
        self.assertEqual([], payload["findings"])

    def test_design_to_code_pipeline_generates_end_to_end_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "pipeline"
            source = REPO_ROOT / "skills" / "design-to-code" / "examples" / "pipeline-source.html"
            script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "design_to_code_pipeline.py"
            result = subprocess.run(
                [sys.executable, str(script), "--source", str(source), "--output", str(output), "--json"],
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(result.stdout)
            generated = {path.name for path in output.iterdir()}
            trace = json.loads((output / "trace.json").read_text(encoding="utf-8"))
            validation = json.loads((output / "validation.json").read_text(encoding="utf-8"))
            report = (output / "acceptance-report.md").read_text(encoding="utf-8")
            spec = (output / "ui-trace.spec.js").read_text(encoding="utf-8")

        self.assertTrue(payload["ok"])
        self.assertIn("manifest.json", generated)
        self.assertIn("trace.json", generated)
        self.assertIn("smoke.json", generated)
        self.assertIn("validation.json", generated)
        self.assertIn("ui-trace.spec.js", generated)
        self.assertIn("acceptance-matrix.md", generated)
        self.assertIn("acceptance-report.md", generated)
        self.assertGreaterEqual(len(trace["rows"]), 2)
        self.assertEqual("fixture-only", validation["validation_type"])
        self.assertIn("## UI Trace", report)
        self.assertIn("Covers: I-1", spec)

    def test_dogfood_tooling_surfaces_failed_and_deferred_ui_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            html = tmp_path / "prototype.html"
            trace = tmp_path / "trace.json"
            validation = tmp_path / "validation.json"
            report = tmp_path / "report.md"
            html.write_text(
                """
                <main>
                  <button id="create-project" onclick="openCreate()">Create project</button>
                  <button id="dead-export">Export</button>
                  <input name="projectSearch" placeholder="Search projects" oninput="filterProjects()" />
                  <a href="/settings">Settings</a>
                </main>
                """,
                encoding="utf-8",
            )
            extractor = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "extract_html_interactions.py"
            reporter = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "generate_acceptance_report.py"
            subprocess.run(
                [sys.executable, str(extractor), str(html), "--output", str(trace)],
                text=True,
                capture_output=True,
                check=True,
            )
            trace_payload = json.loads(trace.read_text(encoding="utf-8"))
            validation.write_text(
                json.dumps({
                    "validation_type": "manual-inspection",
                    "result": "progress",
                    "limitations": "Mock dogfood fixture: no browser runtime, but failed/deferred checks must be visible.",
                    "checks": [
                        {
                            "id": "I-1",
                            "name": "Create project button",
                            "status": "pass",
                            "evidence": "Inline onclick handler extracted.",
                        },
                        {
                            "id": "I-2",
                            "name": "Export button dead-button scan",
                            "status": "fail",
                            "evidence": "Button extracted without handler or href; requires implementation or disabled placeholder.",
                        },
                        {
                            "id": "R-1",
                            "name": "Narrow viewport responsive behavior",
                            "status": "deferred",
                            "evidence": "No browser runtime in this fixture.",
                        },
                    ],
                    "visual_differences": [
                        {
                            "area": "Export action",
                            "design": "Visible enabled button",
                            "implementation": "No behavior detected",
                            "reason": "Mocked missing implementation",
                            "accepted": False,
                        }
                    ],
                }),
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, str(reporter), "--trace", str(trace), "--validation", str(validation), "--output", str(report)],
                text=True,
                capture_output=True,
                check=True,
            )
            report_text = report.read_text(encoding="utf-8")

        selectors = {row["selector"] for row in trace_payload["interactions"]}
        self.assertIn("#create-project", selectors)
        self.assertIn("#dead-export", selectors)
        self.assertIn('input[name="projectSearch"]', selectors)
        self.assertIn('a[href="/settings"]', selectors)
        self.assertIn("Export button dead-button scan", report_text)
        self.assertIn("fail", report_text)
        self.assertIn("deferred", report_text)
        self.assertIn("No behavior detected", report_text)

    def test_playwright_dogfood_fixture_generates_controlled_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dogfood"
            result = subprocess.run(
                [sys.executable, str(DOGFOOD_PATH), "--output", str(output), "--skip-browser"],
                text=True,
                capture_output=True,
                check=True,
            )
            config = (output / "playwright.config.js").read_text(encoding="utf-8")
            spec_text = (output / "tests" / "ui.spec.js").read_text(encoding="utf-8")
            trace = json.loads((output / "trace.json").read_text(encoding="utf-8"))
            validation = json.loads((output / "validation.json").read_text(encoding="utf-8"))
            report = (output / "acceptance-report.md").read_text(encoding="utf-8")

        self.assertIn("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", config)
        self.assertIn("page.locator('#empty')", spec_text)
        self.assertIn("getByRole('button', { name: 'Create new project' })", spec_text)
        self.assertEqual("fixture-only", validation["validation_type"])
        self.assertEqual("skipped", validation["result"])
        self.assertIn("Browser run skipped by --skip-browser", validation["limitations"])
        self.assertTrue((trace["trace"]))
        self.assertIn("## UI Trace", report)
        self.assertIn("dogfood output:", result.stdout)

    def test_playwright_dogfood_fixture_blocks_browser_run_without_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dogfood"
            result = subprocess.run(
                [sys.executable, str(DOGFOOD_PATH), "--output", str(output)],
                text=True,
                capture_output=True,
            )
            validation = json.loads((output / "validation.json").read_text(encoding="utf-8"))

        self.assertEqual(2, result.returncode)
        self.assertEqual("blocked", validation["result"])
        self.assertEqual("fixture-only", validation["validation_type"])
        self.assertIn("Playwright dependencies are not installed", validation["limitations"])
        self.assertEqual("dependency check", validation["attempts"][0]["name"])
        self.assertEqual("blocked", validation["attempts"][0]["status"])
        self.assertIn("--install", result.stdout)

    def test_playwright_dogfood_fixture_reports_invalid_browser_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dogfood"
            missing_browser = Path(tmp) / "missing-browser.exe"
            result = subprocess.run(
                [
                    sys.executable,
                    str(DOGFOOD_PATH),
                    "--output",
                    str(output),
                    "--browser-executable",
                    str(missing_browser),
                ],
                text=True,
                capture_output=True,
            )
            validation = json.loads((output / "validation.json").read_text(encoding="utf-8"))
            generated_names = {path.name for path in output.iterdir()}

        self.assertEqual(2, result.returncode)
        self.assertEqual("blocked", validation["result"])
        self.assertEqual("fixture-only", validation["validation_type"])
        self.assertIn("Browser executable not found", validation["limitations"])
        self.assertEqual("dependency check", validation["attempts"][0]["name"])
        self.assertEqual("explicit browser", validation["attempts"][1]["name"])
        self.assertEqual("blocked", validation["attempts"][1]["status"])
        self.assertIn("acceptance-report.md", generated_names)

    def test_install_skill_dry_run_reports_copy_action(self) -> None:
        script = REPO_ROOT / "scripts" / "install_skill.py"
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(script), "--target", str(Path(tmp) / "design-to-code"), "--dry-run"],
                text=True,
                capture_output=True,
                check=True,
            )

        self.assertIn("DRY RUN copy", result.stdout)
        self.assertIn("idea-to-code", result.stdout)
        self.assertIn("skills", result.stdout)

    def test_regression_script_accepts_explicit_root(self) -> None:
        script = REPO_ROOT / "skills" / "design-to-code" / "scripts" / "test_validate_design_to_code.py"
        result = subprocess.run(
            [sys.executable, str(script), "--root", str(REPO_ROOT), "-k", "test_current_repository_contract_passes"],
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("OK", result.stderr)

    def test_install_skill_refuses_existing_target_without_force(self) -> None:
        script = REPO_ROOT / "scripts" / "install_skill.py"
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "design-to-code"
            target.mkdir()
            (target / "local.txt").write_text("keep", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), "--target", str(target)],
                text=True,
                capture_output=True,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("use --force to overwrite", result.stderr or result.stdout)

    def test_install_skill_force_overwrites_existing_target(self) -> None:
        script = REPO_ROOT / "scripts" / "install_skill.py"
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "design-to-code"
            target.mkdir()
            (target / "local.txt").write_text("remove", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), "--target", str(target), "--force"],
                text=True,
                capture_output=True,
                check=True,
            )
            installed_skill = target / "SKILL.md"
            local_file = target / "local.txt"
            self.assertTrue(installed_skill.exists())
            self.assertFalse(local_file.exists())

        self.assertIn("copy", result.stdout)

    def test_install_skill_verify_reports_hash_parity(self) -> None:
        script = REPO_ROOT / "scripts" / "install_skill.py"
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "design-to-code"
            subprocess.run(
                [sys.executable, str(script), "--target", str(target), "--force"],
                text=True,
                capture_output=True,
                check=True,
            )
            result = subprocess.run(
                [sys.executable, str(script), "--target", str(target), "--verify"],
                text=True,
                capture_output=True,
                check=True,
            )

        self.assertIn("parity ok:", result.stdout)

    def test_install_skill_verify_reports_hash_mismatch(self) -> None:
        script = REPO_ROOT / "scripts" / "install_skill.py"
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "design-to-code"
            subprocess.run(
                [sys.executable, str(script), "--target", str(target), "--force"],
                text=True,
                capture_output=True,
                check=True,
            )
            skill = target / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\nmodified\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), "--target", str(target), "--verify"],
                text=True,
                capture_output=True,
            )

        self.assertEqual(2, result.returncode)
        self.assertIn("parity FAIL", result.stdout)
        self.assertIn("hash mismatch: SKILL.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
