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
        self.assertEqual("explicit browser", validation["attempts"][0]["name"])
        self.assertEqual("blocked", validation["attempts"][0]["status"])
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


if __name__ == "__main__":
    unittest.main()
