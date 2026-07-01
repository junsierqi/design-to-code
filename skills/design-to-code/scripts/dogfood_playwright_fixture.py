#!/usr/bin/env python3
"""Generate and optionally run the design-to-code Playwright dogfood fixture."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


PACKAGE_JSON = """{
  "name": "design-to-code-playwright-dogfood",
  "private": true,
  "scripts": {
    "test": "playwright test --reporter=line"
  },
  "devDependencies": {
    "@playwright/test": "^1.57.0"
  }
}
"""

PLAYWRIGHT_CONFIG = """const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 30000,
  use: {
    browserName: 'chromium',
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined
    },
    viewport: { width: 960, height: 640 },
    screenshot: 'only-on-failure'
  }
});
"""

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Design-to-code Playwright Dogfood</title>
  <style>
    :root {
      --bg: #f6f8fb;
      --panel: #ffffff;
      --line: #d7dde8;
      --ink: #111827;
      --muted: #667085;
      --primary: #2563eb;
      --success: #15803d;
      --warning: #b45309;
      --danger: #dc2626;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Segoe UI", Arial, sans-serif;
    }
    header {
      height: 64px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 32px;
    }
    .brand { font-weight: 800; font-size: 18px; }
    nav { display: flex; gap: 20px; color: var(--muted); font-size: 14px; }
    main { padding: 28px 32px 44px; max-width: 1180px; margin: 0 auto; }
    .toolbar { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-bottom: 22px; }
    h1 { margin: 0; font-size: 32px; line-height: 1.2; }
    p { margin: 0; color: var(--muted); }
    button, input {
      min-height: 40px;
      border-radius: 8px;
      border: 1px solid var(--line);
      font: inherit;
    }
    button {
      padding: 0 16px;
      background: var(--primary);
      color: #fff;
      border-color: var(--primary);
      cursor: pointer;
      font-weight: 700;
    }
    button.secondary { background: #fff; color: var(--ink); border-color: var(--line); }
    input { width: 260px; padding: 0 12px; background: #fff; color: var(--ink); }
    .cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 18px; }
    .card, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }
    .metric { font-size: 28px; font-weight: 800; margin-top: 8px; }
    .grid { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; align-items: start; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 12px 6px; font-size: 14px; }
    th { color: var(--muted); font-weight: 700; }
    .pill { display: inline-block; border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 700; }
    .green { color: var(--success); background: #dcfce7; }
    .amber { color: var(--warning); background: #fef3c7; }
    .red { color: var(--danger); background: #fee2e2; }
    #empty { display: none; padding: 16px 6px; color: var(--muted); }
    #toast { margin-top: 14px; min-height: 22px; color: var(--success); font-weight: 700; }
    @media (max-width: 700px) {
      header { padding: 0 18px; }
      nav { display: none; }
      main { padding: 22px 18px 34px; }
      .toolbar { align-items: stretch; flex-direction: column; }
      .toolbar > div:last-child { display: grid; grid-template-columns: 1fr; gap: 10px; }
      input { width: 100%; }
      .cards, .grid { grid-template-columns: 1fr; }
      h1 { font-size: 26px; }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">Atlas Console</div>
    <nav aria-label="Primary">
      <span>Projects</span>
      <span>Insights</span>
      <span>Settings</span>
    </nav>
  </header>
  <main>
    <section class="toolbar" aria-label="Project actions">
      <div>
        <h1>Project health</h1>
        <p>Mock dashboard for design-to-code browser verification.</p>
      </div>
      <div>
        <input aria-label="Search projects" id="search" placeholder="Search projects" />
        <button aria-label="Create new project" id="create-project">New project</button>
      </div>
    </section>
    <section class="cards" aria-label="Metrics">
      <article class="card"><p>Active projects</p><div class="metric">18</div></article>
      <article class="card"><p>Blocked tasks</p><div class="metric">3</div></article>
      <article class="card"><p>Release confidence</p><div class="metric">92%</div></article>
    </section>
    <section class="grid">
      <article class="panel">
        <h2>Recent projects</h2>
        <table aria-label="Recent projects">
          <thead><tr><th>Name</th><th>Owner</th><th>Status</th></tr></thead>
          <tbody id="rows">
            <tr><td>Apollo launch</td><td>Mira</td><td><span class="pill green">Healthy</span></td></tr>
            <tr><td>Billing sync</td><td>Jon</td><td><span class="pill amber">Watching</span></td></tr>
            <tr><td>Mobile polish</td><td>Leah</td><td><span class="pill red">Blocked</span></td></tr>
          </tbody>
        </table>
        <p id="empty">No matching projects</p>
      </article>
      <aside class="panel">
        <h2>System states</h2>
        <p>Empty: no matching projects</p>
        <p>Error: retryable sync failure</p>
        <button class="secondary" id="retry">Retry</button>
        <div role="status" id="toast" aria-live="polite"></div>
      </aside>
    </section>
  </main>
  <script>
    const toast = document.querySelector('#toast');
    const search = document.querySelector('#search');
    const empty = document.querySelector('#empty');
    const rows = Array.from(document.querySelectorAll('#rows tr'));
    document.querySelector('#create-project').addEventListener('click', () => {
      toast.textContent = 'Create project opened';
    });
    document.querySelector('#retry').addEventListener('click', () => {
      toast.textContent = 'Retry queued';
    });
    search.addEventListener('input', () => {
      const term = search.value.trim().toLowerCase();
      let visible = 0;
      rows.forEach(row => {
        const match = row.textContent.toLowerCase().includes(term);
        row.style.display = match ? '' : 'none';
        if (match) visible += 1;
      });
      empty.style.display = visible ? 'none' : 'block';
    });
  </script>
</body>
</html>
"""

UI_SPEC = """const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const root = path.resolve(__dirname, '..');
const appUrl = 'file://' + path.join(root, 'index.html').replace(/\\\\/g, '/');
const artifacts = path.join(root, 'artifacts');

test.beforeAll(() => {
  fs.mkdirSync(artifacts, { recursive: true });
});

test('dashboard renders and captures desktop screenshot', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  await page.goto(appUrl);
  await expect(page.getByRole('heading', { name: 'Project health' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create new project' })).toBeVisible();
  await expect(page.getByText('Apollo launch')).toBeVisible();
  await page.screenshot({ path: path.join(artifacts, 'dashboard-desktop.png'), fullPage: true });
  expect(errors).toEqual([]);
});

test('search input filters rows and exposes empty state', async ({ page }) => {
  await page.goto(appUrl);
  await page.getByRole('textbox', { name: 'Search projects' }).fill('Apollo');
  await expect(page.getByText('Apollo launch')).toBeVisible();
  await expect(page.getByText('Billing sync')).toBeHidden();
  await page.getByRole('textbox', { name: 'Search projects' }).fill('zzz');
  await expect(page.locator('#empty')).toHaveText('No matching projects');
  await page.screenshot({ path: path.join(artifacts, 'dashboard-empty.png'), fullPage: true });
});

test('primary actions provide visible feedback', async ({ page }) => {
  await page.goto(appUrl);
  await page.getByRole('button', { name: 'Create new project' }).click();
  await expect(page.getByRole('status')).toHaveText('Create project opened');
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByRole('status')).toHaveText('Retry queued');
});

test('mobile viewport stacks content and captures screenshot', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(appUrl);
  await expect(page.getByRole('heading', { name: 'Project health' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create new project' })).toBeVisible();
  await page.screenshot({ path: path.join(artifacts, 'dashboard-mobile.png'), fullPage: true });
});
"""


TRACE = {
    "trace": [
        {"id": "C-1", "type": "component", "source_evidence": "Mock dashboard fixture", "expected_behavior": "Dashboard shell renders heading, metrics, table, and status panel", "implementation": "index.html dashboard shell", "verification": "tests/ui.spec.js dashboard renders and captures desktop screenshot", "status": "pass"},
        {"id": "I-1", "type": "interaction", "source_evidence": "button[aria-label=\"Create new project\"]", "expected_behavior": "Clicking the primary action shows visible status feedback", "implementation": "index.html #create-project click listener", "verification": "tests/ui.spec.js primary actions provide visible feedback", "status": "pass"},
        {"id": "I-2", "type": "interaction", "source_evidence": "input[aria-label=\"Search projects\"]", "expected_behavior": "Typing filters rows and reaches an empty state", "implementation": "index.html #search input listener", "verification": "tests/ui.spec.js search input filters rows and exposes empty state", "status": "pass"},
        {"id": "I-3", "type": "interaction", "source_evidence": "button text Retry", "expected_behavior": "Clicking Retry shows visible retry queued feedback", "implementation": "index.html #retry click listener", "verification": "tests/ui.spec.js primary actions provide visible feedback", "status": "pass"},
        {"id": "S-1", "type": "state", "source_evidence": "#empty empty-state node", "expected_behavior": "No matching projects appears after a no-result search", "implementation": "index.html #empty state", "verification": "tests/ui.spec.js search input filters rows and exposes empty state", "status": "pass"},
        {"id": "R-1", "type": "responsive", "source_evidence": "Viewport 390x844", "expected_behavior": "Mobile viewport remains usable and screenshot is captured", "implementation": "index.html max-width 700px media query", "verification": "tests/ui.spec.js mobile viewport stacks content and captures screenshot", "status": "pass"},
        {"id": "A-1", "type": "accessibility", "source_evidence": "Role-based Playwright locators", "expected_behavior": "Primary button and search input expose accessible names", "implementation": "index.html aria-labels and semantic controls", "verification": "tests/ui.spec.js role-based locators", "status": "pass"},
    ]
}


def system_browser_candidates() -> list[Path]:
    home = Path.home()
    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LocalAppData", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
        home / ".local/bin/chrome",
    ]
    return [path for path in candidates if str(path) and path.exists()]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(command[0])
    if executable:
        command = [executable, *command[1:]]
    try:
        return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    except FileNotFoundError:
        return subprocess.CompletedProcess(command, 127, "", f"command not found: {command[0]}\n")


def write_fixture(output: Path) -> None:
    write(output / "package.json", PACKAGE_JSON)
    write(output / "playwright.config.js", PLAYWRIGHT_CONFIG)
    write(output / "index.html", INDEX_HTML)
    write(output / "tests" / "ui.spec.js", UI_SPEC)
    write(output / "trace.json", json.dumps(TRACE, indent=2) + "\n")


def playwright_dependency_installed(output: Path) -> bool:
    return (output / "node_modules" / "@playwright" / "test").exists()


def validation_payload(result: str, validation_type: str, limitation: str, command_output: str, attempts: list[dict[str, str]]) -> dict[str, object]:
    checks = [
        {"id": "TC-C-1", "name": "Dashboard shell renders", "status": result, "evidence": "Playwright dashboard render test; screenshot artifacts/dashboard-desktop.png when browser ran"},
        {"id": "TC-I-1", "name": "Create action feedback", "status": result, "evidence": "Clicked Create new project and asserted role=status text"},
        {"id": "TC-I-2", "name": "Search filters and empty state", "status": result, "evidence": "Filled Search projects, asserted filtered rows and #empty text"},
        {"id": "TC-I-3", "name": "Retry action feedback", "status": result, "evidence": "Clicked Retry and asserted role=status text"},
        {"id": "TC-R-1", "name": "Mobile responsive viewport", "status": result, "evidence": "Viewport 390x844; screenshot artifacts/dashboard-mobile.png when browser ran"},
        {"id": "TC-ERR-1", "name": "Console and page errors", "status": result, "evidence": "Desktop test collects pageerror and console error events"},
    ]
    return {
        "validation_type": validation_type,
        "result": result,
        "limitations": limitation,
        "attempts": attempts,
        "checks": checks,
        "command_output": command_output[-4000:],
        "visual_differences": [
            {
                "area": "Design source",
                "design": "No external screenshot baseline; this is a controlled dogfood fixture",
                "implementation": "Screenshots and trace validate the skill verification workflow",
                "reason": "The fixture tests skill capability rather than matching a supplied design",
                "accepted": True,
            }
        ],
    }


def generate_report(output: Path) -> None:
    reporter = Path(__file__).with_name("generate_acceptance_report.py")
    result = run(
        [
            sys.executable,
            str(reporter),
            "--trace",
            str(output / "trace.json"),
            "--validation",
            str(output / "validation.json"),
            "--title",
            "Design-to-code Playwright Dogfood Acceptance Report",
            "--output",
            str(output / "acceptance-report.md"),
        ],
        cwd=output,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "acceptance report generation failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".idea-to-code/design-to-code-playwright-dogfood", help="Output directory for generated fixture and artifacts")
    parser.add_argument("--install", action="store_true", help="Run npm install in the generated fixture directory")
    parser.add_argument("--skip-browser", action="store_true", help="Generate files and report without running Playwright")
    parser.add_argument("--browser-executable", help="Chrome/Chromium/Edge executable path for system browser fallback")
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    write_fixture(output)

    command_output = ""
    attempts: list[dict[str, str]] = []
    limitation = "No limitations recorded."
    result_status = "pass"
    validation_type = "real-product-path"

    if args.install:
        install = run(["npm", "install", "--no-audit", "--no-fund"], cwd=output)
        command_output += "$ npm install --no-audit --no-fund\n" + install.stdout + install.stderr
        attempts.append({
            "name": "npm install",
            "status": "pass" if install.returncode == 0 else "blocked",
            "validation_type": "source-only",
            "limitation": "" if install.returncode == 0 else "npm install failed",
        })
        if install.returncode != 0:
            result_status = "blocked"
            validation_type = "fixture-only"
            limitation = "npm install failed; generated fixture files are available but browser validation did not run."
    elif not args.skip_browser and not playwright_dependency_installed(output):
        result_status = "blocked"
        validation_type = "fixture-only"
        limitation = "Playwright dependencies are not installed in the generated fixture directory; rerun with --install before browser validation."
        attempts.append({
            "name": "dependency check",
            "status": "blocked",
            "validation_type": "fixture-only",
            "limitation": limitation,
        })

    explicit_browser = Path(args.browser_executable).resolve() if args.browser_executable else None
    if explicit_browser and not explicit_browser.exists():
        result_status = "blocked"
        validation_type = "fixture-only"
        limitation = f"Browser executable not found: {explicit_browser}"
        attempts.append({
            "name": "explicit browser",
            "status": "blocked",
            "validation_type": "fixture-only",
            "limitation": limitation,
        })

    if args.skip_browser:
        result_status = "skipped"
        validation_type = "fixture-only"
        limitation = "Browser run skipped by --skip-browser; generated fixture, trace, validation, and report are available."
        attempts.append({
            "name": "browser run",
            "status": "skipped",
            "validation_type": "fixture-only",
            "limitation": limitation,
        })
    elif result_status != "blocked":
        env = os.environ.copy()
        browser = explicit_browser
        if browser:
            env["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"] = str(browser)
        test = run(["npm", "test"], cwd=output, env=env)
        command_output += "$ npm test\n" + test.stdout + test.stderr
        attempts.append({
            "name": "bundled playwright browser" if not browser else "explicit browser",
            "status": "pass" if test.returncode == 0 else "blocked",
            "validation_type": "real-product-path" if test.returncode == 0 else "fixture-only",
            "limitation": "" if test.returncode == 0 else "Initial Playwright browser command failed",
        })
        if test.returncode != 0 and "Executable doesn't exist" in (test.stdout + test.stderr):
            fallback = browser or (system_browser_candidates()[0] if system_browser_candidates() else None)
            if fallback:
                env["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"] = str(fallback)
                retry = run(["npm", "test"], cwd=output, env=env)
                command_output += f"$ npm test with PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH={fallback}\n" + retry.stdout + retry.stderr
                test = retry
                limitation = f"Bundled Playwright browser was unavailable; used system browser fallback at {fallback}."
                attempts.append({
                    "name": "system browser fallback",
                    "status": "pass" if retry.returncode == 0 else "blocked",
                    "validation_type": "real-product-path" if retry.returncode == 0 else "fixture-only",
                    "limitation": limitation,
                })
        if test.returncode != 0:
            result_status = "blocked"
            validation_type = "fixture-only"
            if limitation == "No limitations recorded.":
                limitation = "Playwright test command failed; inspect command_output in validation.json."

    write(output / "validation.json", json.dumps(validation_payload(result_status, validation_type, limitation, command_output, attempts), indent=2) + "\n")
    generate_report(output)

    print(f"dogfood output: {output}")
    print(f"result: {result_status}")
    print(f"validation_type: {validation_type}")
    if limitation != "No limitations recorded.":
        print(f"limitation: {limitation}")
    if args.skip_browser:
        print("next: run with --install to install Playwright dependencies, then omit --skip-browser for real browser validation")
    elif result_status == "blocked":
        print("next: rerun with --install, or install dependencies in the output directory and set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH / --browser-executable when needed")
    return 0 if result_status in {"pass", "skipped"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
