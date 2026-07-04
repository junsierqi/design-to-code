---
name: design-to-code
description: Use when the user provides a visual UI source such as an image, mockup, wireframe, HTML prototype, Figma link, PDF, or live URL and wants it implemented as working, verified frontend UI. Use idea-to-code as the lifecycle foundation, then apply design-to-code references for visual analysis, UI implementation, runtime verification, screenshots, and acceptance reporting.
---

# Design To Code

Implement working frontend UI from visual design sources. This skill is a UI-specialized profile on top of the `idea-to-code` delivery lifecycle.

## Foundation Contract

Use `idea-to-code` for delivery state and gates whenever that skill is available:

- intake, assumptions, requirements, acceptance matrix, and implementation plan
- implementation-ready gate before product-file edits
- Planner, Implementer, Validator, Reviewer, and Closer evidence
- validation type, checkpoints, pre-close verify, finalize, and final verify
- durable `.idea-to-code/<slug>/` task state

When `idea-to-code` is available, design-to-code must obey all idea-to-code rules, lifecycle gates, evidence requirements, visibility requirements, and final handoff rules. The UI-specific instructions in this skill add domain guidance; they do not narrow, replace, or bypass any idea-to-code requirement.

When invoking idea-to-code commands for a design-to-code task, use the profile name `design-to-code` where supported. Every user-visible design-to-code message must use the profile-aware role/source prefix when `idea-to-code` is available:

```text
[idea-to-code/design-to-code][Role/source]
```

For example, use `implementation ready --profile design-to-code` or `implementation show-ready --profile design-to-code` when the installed idea-to-code version supports profile-aware READY output. If the installed idea-to-code version does not support `--profile`, fall back to `[idea-to-code][Role/source]` and record that profile-aware visibility was unavailable. Do not use a standalone `[design-to-code]` prefix.

## Execution Visibility

Design-to-code inherits the `idea-to-code` user-visible output contract. This includes commentary updates, plans, validation summaries, review findings, blocker reports, final responses, and follow-up explanations. The role must match the active work: `Planner`, `Implementer`, `Validator`, `Reviewer`, or `Closer`; the source is `agent` unless a real subagent returned usable evidence.

Read-only UI analysis is allowed without implementation edits, but it must not look like a lifecycle bypass. For read-only UI reviews, use `[idea-to-code/design-to-code][Reviewer/agent]` or the current role-specific profile prefix, state `Mode: read-only analysis`, and explicitly say whether the review is tracked in an `idea-to-code` bundle or is untracked ordinary analysis. If it is untracked ordinary analysis, do not claim READY, role-gated delivery, finalize, or accepted implementation evidence. If the analysis leads to code changes, create or resume the bundle and proceed through READY before editing.

Use `design-to-code` for the UI-specific work that generic idea delivery does not define:

- design brief validation for product goal, visual sources, interactivity level, target surfaces, and acceptance notes
- design-source analysis across images, HTML prototypes, Figma, PDFs, live URLs, and architecture docs
- component / interaction / state extraction
- frontend framework adaptation and missing-backend mocks
- UI behavior verification, screenshots, accessibility basics, and dead-button checks
- visual acceptance reporting and designer/backend handoff notes

If `idea-to-code` cannot be loaded, continue with the same visible planning discipline in this skill: write a concrete task list, preserve traceability from design elements to implementation and tests, run the strongest local validation, and report any missing lifecycle evidence as a residual risk.

## When To Use

Use this skill when the design artifact is the source of truth and the expected output is working UI, not only critique or visual exploration.

Typical triggers:

- "implement this design"
- "build from this mockup"
- "turn this screenshot into UI"
- "recreate this Figma / HTML prototype"
- any visual reference plus a request for frontend implementation

Prefer plain `idea-to-code` when the work is not driven by a visual UI source. Prefer product-design or design-to-code image-specific workflows only when the user is asking for ideation or design critique rather than implementation.

## Runtime Workflow

1. Load `idea-to-code` first and create or resume the delivery bundle.
2. Confirm or validate a compact design brief covering product goal, visual source, interactivity level, target surfaces, and acceptance notes.
3. In the bundle requirements, record that `design-to-code` owns UI-specific analysis and verification.
4. Read only the design-to-code references needed for the current source and task:
   - `references/design-source-analysis.md`
   - `references/ui-implementation.md`
   - `references/ui-verification.md`
   - `references/acceptance-report.md`
   - `references/playwright-patterns.md` when browser automation patterns are needed
5. Build a trace matrix from design source to implementation:
   - `C-*` component items
   - `I-*` interaction items
   - `S-*` state items
   - optional `A-*` accessibility or `R-*` responsive items
6. Map trace items to `idea-to-code` `REQ-*` / `TASK-*` entries before editing.
7. Implement the smallest coherent UI slice while matching the target project conventions.
8. Validate behavior and visual evidence with project-native tests, Playwright/runtime checks, screenshots, or source-only checks when runtime is unavailable.
9. Finalize through `idea-to-code`; include design-to-code trace coverage, screenshots, known visual differences, and deferred backend/API work in the closeout.

## Reference Routing

Read `references/design-source-analysis.md` when:

- the design source must be interpreted
- the input is an image, PDF, Figma link, live URL, architecture doc, or HTML prototype
- the task needs a component / interaction / state trace matrix

Read `references/ui-implementation.md` when:

- editing frontend code
- mocking missing APIs or data
- adapting to React, Vue, Angular, Svelte, Next.js, Nuxt, Tauri, or Electron
- choosing component boundaries, styling, icons, or responsive behavior

Read `references/ui-verification.md` when:

- writing tests or runtime checks
- using Playwright or browser inspection
- checking loading, empty, error, disabled, responsive, and accessibility states
- scanning for dead buttons or readonly inputs

Read `references/playwright-patterns.md` when:

- the target project has Playwright or equivalent browser automation
- you need reusable screenshot, interaction, state, console error, accessibility, or viewport patterns
- you need to distinguish real-product-path browser evidence from fallback validation

Read `references/acceptance-report.md` when:

- preparing the final report
- organizing screenshots
- documenting design differences, backend handoff, or remaining visual polish

## Required UI Trace

Every run must maintain a UI trace table in the active `idea-to-code` bundle or final report.

Minimum columns:

| ID | Type | Source Evidence | Expected UI / Behavior | Implementation | Verification | Status |
|----|------|-----------------|------------------------|----------------|--------------|--------|
| C-1 | component | Header in screenshot | Header renders with logo and nav | file:line | test/screenshot | pass |
| I-1 | interaction | HTML onclick or visible button | Click opens modal | file:line | Playwright step | pass |
| S-1 | state | Missing backend assumption | Empty state renders | file:line | test/screenshot | pass |

Rules:

- one row per distinct component, interaction, or state
- repeated interactions may use pattern groups, but each visible instance must be accounted for
- every interactive element must be implemented or explicitly deferred with a reason
- every `REQ-*` that affects UI should cite the related `C-*`, `I-*`, or `S-*` rows

## Validation

For this skill repository itself, run:

```bash
python skills/design-to-code/scripts/validate_design_to_code.py --root .
python skills/design-to-code/scripts/validate_design_to_code.py --root . --strict
python skills/design-to-code/scripts/test_validate_design_to_code.py
```

For user projects, prefer real product-path validation. When that is unavailable, record the lower validation type honestly in the `idea-to-code` bundle.

## Common Failure Modes

- treating an HTML prototype as a static screenshot and missing executable interactions
- shipping visible buttons with no behavior
- verifying only presence instead of click/input state changes
- omitting loading, empty, error, disabled, and responsive states
- inventing screenshot names instead of using generated evidence
- replacing UI-specific traceability with generic implementation notes
- duplicating `idea-to-code` lifecycle gates inside design-to-code instead of using the shared foundation
