# design-to-code

A Codex skill for implementing frontend UI from visual design sources such as screenshots, mockups, wireframes, HTML prototypes, live URLs, PDFs, and Figma references.

`design-to-code` is a UI-specialized profile on top of `idea-to-code`. `idea-to-code` owns delivery lifecycle state, requirements, role gates, verification evidence, checkpoints, and closeout. `design-to-code` owns the UI-specific guidance for design-source analysis, component/interaction/state traceability, missing-backend mocks, browser verification, screenshots, and visual acceptance reporting.

## Use When

- A user asks to implement UI from a screenshot, mockup, wireframe, HTML prototype, PDF, live URL, or Figma link.
- The visual reference is the source of truth.
- The design references backend APIs or data that may not exist yet.
- The work needs responsive behavior, interaction testing, screenshots, and visual acceptance evidence.

## What's Included

- `skills/design-to-code/SKILL.md` - concise runtime entrypoint and idea-to-code foundation contract
- `skills/design-to-code/references/` - focused UI implementation references
- `skills/design-to-code/scripts/validate_design_to_code.py` - source-only repository contract validator
- `skills/design-to-code/scripts/extract_html_interactions.py` - HTML prototype interaction extractor
- `skills/design-to-code/scripts/generate_acceptance_report.py` - Markdown acceptance report generator
- `skills/design-to-code/scripts/dogfood_playwright_fixture.py` - isolated Playwright dogfood fixture generator and runner
- `skills/design-to-code/scripts/test_validate_design_to_code.py` - regression tests for the validator and skill contract
- `skills/design-to-code/agents/openai.yaml` - Codex/OpenAI UI metadata
- `scripts/install_skill.py` - dry-run capable installer for the skill directory

## Requirements

- A frontend project to modify
- Node/package tooling appropriate to the target project
- Playwright when runtime UI verification is required
- The `idea-to-code` skill for full lifecycle tracking

`design-to-code` is designed to run on top of `idea-to-code`. It is not a hard import dependency that prevents the skill text from loading, but full lifecycle behavior requires `idea-to-code` to be installed. If `idea-to-code` is unavailable, the skill instructs agents to continue with equivalent visible planning and traceability, then report the missing lifecycle evidence as a residual risk.

## Validate

Run these commands from the repository root before publishing changes:

```bash
python skills/design-to-code/scripts/validate_design_to_code.py --root .
python skills/design-to-code/scripts/validate_design_to_code.py --root . --strict
python skills/design-to-code/scripts/test_validate_design_to_code.py --root .
```

These are source-only checks for this skill repository. They do not replace runtime verification inside a downstream frontend project.

## Tooling

Canonical example inputs live under `skills/design-to-code/examples/`.

Extract interaction seed rows from an HTML prototype:

```bash
python skills/design-to-code/scripts/extract_html_interactions.py prototype.html --format markdown
```

Validate UI trace rows before implementation or closeout:

```bash
python skills/design-to-code/scripts/validate_trace.py trace.json --validation validation.json --artifact-root artifacts
```

Use `--json` when another tool needs `schema_version`, legacy `problems`, and structured `errors` with stable codes.

Generate an acceptance matrix seed from UI trace rows:

```bash
python skills/design-to-code/scripts/trace_to_acceptance_matrix.py trace.json --format markdown
```

Generate a Playwright spec scaffold from UI trace rows:

```bash
python skills/design-to-code/scripts/generate_playwright_checks.py --trace trace.json --output e2e/idea-to-code/ui-trace.spec.js --default-url /dashboard
```

Create a design-source manifest from a local file or directory:

```bash
python skills/design-to-code/scripts/analyze_design_source.py ./designs --format markdown
```

Figma export JSON files are detected as `figma-json` and include a compact
`figma_summary` for frames, components, and styles. The summary includes up to
50 representative items by default; use `--max-figma-items 0` when a full
uncapped export summary is needed.

Capture a reproducible snapshot from a local file, `file://` URL, or public
`http(s)` design source:

```bash
python skills/design-to-code/scripts/capture_design_snapshot.py ./designs/source.html --output .idea-to-code/design-snapshot --json
```

Compare screenshot artifacts with a byte-diff threshold. PNG files work with the
standard-library fallback; install Pillow only when comparing JPEG, WebP, or
other raster formats. Use `--check-deps` to preflight optional image support and
`--require-pillow` when non-PNG comparison must fail early without Pillow:

```bash
python skills/design-to-code/scripts/compare_screenshots.py --expected baseline.png --actual actual.png --threshold 0.01 --json
```

Run lightweight source-level UI smoke checks:

```bash
python skills/design-to-code/scripts/ui_smoke_check.py prototype.html --i18n --strict
```

Run the local end-to-end tooling pipeline for an HTML source:

```bash
python skills/design-to-code/scripts/design_to_code_pipeline.py --source skills/design-to-code/examples/pipeline-source.html --output .idea-to-code/design-to-code-pipeline-example --json
```

Add `--check-browser-deps` to preflight local Playwright availability. Add
`--run-browser` to run the generated Playwright spec when a local Playwright
binary is already installed, or pass `--browser-command` to point at one
explicitly. When browser dependencies are missing, the pipeline records a
`browser_run` step as `blocked` instead of claiming browser validation passed.

Generate an acceptance report from trace and validation JSON:

```bash
python skills/design-to-code/scripts/generate_acceptance_report.py --trace trace.json --validation validation.json --output report.md
```

Use strict mode when the report is acting as a gate:

```bash
python skills/design-to-code/scripts/generate_acceptance_report.py --trace trace.json --validation validation.json --output report.md --strict
```

Validate referenced artifacts as well:

```bash
python skills/design-to-code/scripts/generate_acceptance_report.py --trace trace.json --validation validation.json --output report.md --strict --artifact-root artifacts
```

Generate and optionally run the official Playwright dogfood fixture:

```bash
python skills/design-to-code/scripts/dogfood_playwright_fixture.py --output .idea-to-code/design-to-code-playwright-dogfood --skip-browser
```

Install Playwright dependencies inside the generated artifact directory, not the repository root. Browser validation is blocked until these fixture-local dependencies exist:

```bash
python skills/design-to-code/scripts/dogfood_playwright_fixture.py --output .idea-to-code/design-to-code-playwright-dogfood --install
```

If Playwright's bundled Chromium download is unavailable or slow, use an installed Chrome, Chromium, or Edge executable as the real-browser fallback:

```bash
set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
python skills/design-to-code/scripts/dogfood_playwright_fixture.py --output .idea-to-code/design-to-code-playwright-dogfood
```

PowerShell equivalent:

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"
python skills/design-to-code/scripts/dogfood_playwright_fixture.py --output .idea-to-code/design-to-code-playwright-dogfood
```

The script writes `package.json`, Playwright tests, screenshots, `trace.json`, `validation.json`, and `acceptance-report.md` under the output directory. It does not add root npm dependencies.

Preview installation:

```bash
python scripts/install_skill.py --dry-run
```

Install or overwrite an existing local copy:

```bash
python scripts/install_skill.py --force
```

Verify source/installed file hash parity:

```bash
python scripts/install_skill.py --verify
```

The installer reports whether `idea-to-code` is installed next to the target `design-to-code` skill.

## Install

Copy or symlink `skills/design-to-code/` into your Codex skills directory, commonly:

```bash
$HOME/.codex/skills/design-to-code
```

Only `skills/design-to-code/` is the installable runtime skill. Repository-root files such as this README are maintenance scaffolding.
