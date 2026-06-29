# Design Source Analysis

Use this reference to turn a visual source into implementation-ready UI trace items. The output feeds the active `idea-to-code` requirements, acceptance matrix, implementation plan, and final report.

## Source Types

| Source | Detection | Analysis Method |
|---|---|---|
| Image | PNG, JPG, JPEG, WebP | Inspect layout, typography, color, components, responsive assumptions, and visible interactions. |
| PDF | PDF file or exported mockup | Render pages when possible, then analyze each page as a visual source. |
| HTML prototype | HTML with markup, styles, or scripts | Inspect DOM, event handlers, inputs, anchors, state changes, and visual layout. |
| Figma link | `figma.com` URL | Use available exports/API access when possible; otherwise ask for exported frames only if the visual source is unavailable. |
| Live URL | `http` or `https` URL | Capture screenshots and inspect DOM/runtime behavior when permitted. |
| Architecture doc | Markdown or spec with components/data flow | Treat naming and architecture as authoritative; use visuals for layout and styling. |

When architecture docs and visuals disagree, preserve the architecture for code structure and use the design for visual/interaction requirements. Record the decision in the `idea-to-code` bundle.

## Figma And Design System Signals

When Figma access or exported Figma metadata is available, inspect more than the frame bitmap:

- frame names, page names, and flow order
- component instances and variants
- auto-layout direction, gap, padding, constraints, and resizing behavior
- layer names that imply semantic roles or data fields
- local styles, variables, tokens, and typography styles
- interactive prototype links, overlays, and starting points
- hidden layers or alternate variants that explain states

Do not treat Figma layer names as implementation names automatically. Use them as evidence, then map them to the target project's component and domain language.

If only exported images are available, ask for Figma metadata only when the missing information changes layout, variants, responsive behavior, or interaction semantics.

## Multi-Screen Flow Map

For designs with more than one screen or frame, create a flow map before implementation:

| Flow ID | From | Trigger | To | Data / State Carried | Notes |
|---|---|---|---|---|---|
| F-1 | List | click row | Detail | selected item id | modal or route depends on project convention |

Map:

- entry points and default screen
- navigation links, tabs, steppers, drawers, and modals
- back/cancel/close behavior
- persisted state across screens
- empty/error states per screen
- destructive or irreversible actions

Every flow edge that changes visible UI should connect to one or more `I-*` trace rows.

## Design State Inventory

Look for explicit and implied states:

- default
- hover
- focused
- pressed
- selected
- disabled
- loading
- empty
- error
- success
- validation
- permission denied
- offline or unavailable dependency

If the design shows variants, map each variant to a state row or explain why it is visual-only. If the design omits a required operational state, infer a conservative state that follows the project design system and record it as an assumption.

## Responsive Frame Interpretation

When multiple frames are supplied, treat them as breakpoint evidence:

- identify which dimensions correspond to mobile, tablet, desktop, or wide desktop
- record which elements reflow, collapse, hide, or become menus
- preserve primary actions and critical content priority
- check whether repeated grids, tables, and sidebars need alternate layouts

When only one frame is supplied, infer a responsive strategy and mark it as inferred in the trace. Do not invent a complex responsive design when a simple project-standard stack is sufficient.

## Source Precedence

Use this precedence when sources conflict:

1. explicit user instruction
2. project governance and existing product patterns
3. architecture or component spec
4. Figma prototype behavior and design-system metadata
5. visual layout and screenshots
6. inferred conventions

Record meaningful conflicts and the chosen source of truth in the active bundle.

## Component / Interaction / State Lists

Create trace IDs before implementation:

- `C-*` for visible components and meaningful subcomponents
- `I-*` for click, input, select, hover, drag, keyboard, file, navigation, and mutation interactions
- `S-*` for loading, empty, error, success, disabled, validation, permission, and offline states
- `R-*` for responsive layout requirements when the design implies multiple viewports
- `A-*` for accessibility requirements such as labels, focus, contrast, keyboard path, and semantic roles

Minimum expected state coverage:

- loading
- empty
- error
- success / populated
- disabled or unavailable action when applicable
- validation state for forms
- responsive breakpoint behavior for user-facing screens

## Interaction Extraction

For HTML prototypes, use the source as executable specification:

- collect `onclick`, `onchange`, `onsubmit`, keyboard handlers, and script-bound listeners
- collect editable `input`, `textarea`, `select`, and `contenteditable` elements
- collect anchors, route links, menus, tabs, toggles, dialogs, and controls with button semantics
- inspect script functions for view switching, mutation, filtering, upload, export, and toast behavior

The repository extractor also performs lightweight static scans for common prototype bindings:

- HTML inline handlers such as `onclick`, `oninput`, and `onsubmit`
- script handlers using `document.querySelector(...).addEventListener(...)`
- script handlers using `document.getElementById(...).addEventListener(...)`
- JSX-style `onClick={...}`, `onChange={...}`, and related event props
- Vue `@click="..."` and `v-on:submit.prevent="..."` style bindings
- Svelte `on:click={...}` style bindings

Treat these as source extraction hints, not a full JavaScript, JSX, Vue, or Svelte AST parser. When a visible control is detected without a concrete handler, keep it in the trace with `candidate-missing-handler` or an explicit deferred behavior instead of silently dropping it.

For images, Figma, or PDFs, scan every visible element and ask what the user can click, type, drag, select, hover, or navigate. If it appears interactive, add an `I-*` row even when behavior must be inferred.

Do not summarize repeated visible interactions away. Pattern groups are allowed, but the trace must still account for each visible instance or the instance set.

## Trace Matrix Shape

Use this structure in the bundle, report, or generated task evidence:

| ID | Type | View | Source Evidence | Expected UI / Behavior | Related REQ | Implementation | Verification | Status |
|---|---|---|---|---|---|---|---|---|
| C-1 | component | Dashboard | screenshot header | Header with logo, nav, and account area | REQ-1 | pending | pending | pending |
| I-1 | interaction | Dashboard | Export button | Click provides download or visible feedback | REQ-2 | pending | pending | pending |
| S-1 | state | Table | no-data scenario | Empty state explains no results and offers recovery | REQ-2 | pending | pending | pending |

Rules:

- source evidence must point to a frame, screenshot, DOM selector, file, line, or visible region
- expected behavior must be observable
- implementation should cite file paths and lines when known
- verification must name the command, test, screenshot, or manual inspection path
- deferred rows need a concrete reason and owner, such as missing backend API

## Design Quality Checklist

Before implementation, confirm the analysis covers:

- screen inventory and flow map
- component inventory
- interaction inventory
- state inventory
- responsive assumptions
- design token or style signals
- asset and icon inventory
- text length and localization risks
- accessibility-relevant labels, focus, and contrast cues

## Ambiguity Handling

Decide ordinary UI details without stopping:

- exact mock data values
- reasonable empty/error copy
- common responsive stacking
- standard hover/focus styles matching the project

Ask the user only when the ambiguity changes architecture, product behavior, brand-critical visuals, security, data persistence, payment/destructive flows, or a contract with another team.

Record assumptions in the active `idea-to-code` bundle as acceptance context.
