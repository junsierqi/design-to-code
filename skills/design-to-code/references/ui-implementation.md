# UI Implementation

Use this reference while editing frontend code. The lifecycle and evidence gates still belong to `idea-to-code`; this file covers design-to-code UI implementation decisions.

## Project Discovery

Before editing, inspect the target project for:

- framework and router
- package manager and build commands
- UI library, icon library, styling system, and design tokens
- existing component boundaries and naming patterns
- test runner and browser/runtime tooling
- API clients, mock conventions, fixtures, and environment variables

Use `scripts/inspect_frontend_project.py` when a local project root is available
to seed this discovery with framework, package-manager, script, route, styling,
and test-tooling signals. Treat the output as implementation guidance, not as a
substitute for reading the files you will edit.

Prefer existing project patterns over new abstractions. Add a new abstraction only when it removes real duplication or matches a local convention.

## Framework Adaptation

Common framework cues:

- React / Next.js: `package.json`, `src/app`, `pages`, `react-router`, hooks, JSX/TSX
- Vue / Nuxt: `.vue` files, composables, Pinia/Vuex, `pages`
- Angular: modules, standalone components, services, RxJS
- Svelte / SvelteKit: `.svelte`, stores, routes
- Tauri / Electron: desktop shell plus web frontend

Use the project-native routing, state, and styling approach. Do not introduce a parallel routing or state system for one screen.

## Missing Backend And Data

When the design references unavailable APIs:

- create mocks that match the expected real interface
- use realistic data with mixed statuses, long names, empty values, and edge cases
- isolate mock code so migration to the real backend is obvious
- document expected endpoint, request, response, and environment switch in the report

Do not block UI implementation solely because the backend is missing unless the UI cannot be meaningfully exercised without external credentials or proprietary data.

## Component Boundaries

Map `C-*` rows to components or local subcomponents:

- layout shell
- navigation
- repeated cards/rows
- forms
- dialogs/drawers
- tables/lists
- toolbar controls
- empty/error/loading views

Keep components focused. Avoid one large file that mixes data fetching, routing, rendering, formatting, and interaction state unless the project already uses that pattern for small screens.

## Interaction Behavior

Every `I-*` row needs an observable result:

- navigation changes route or visible view
- toggle opens/closes a panel or changes selected state
- input accepts text and updates data, filter, validation, or submission state
- mutation changes local/mock data or gives explicit feedback
- disabled action exposes a clear disabled state or reason
- export/download either triggers the action or shows honest placeholder feedback

Visible controls with no behavior are defects unless explicitly marked deferred in the trace.

## Visual Fidelity

Match the design in this order:

1. layout and information hierarchy
2. spacing, alignment, and responsive behavior
3. typography scale and weight
4. color and contrast
5. component states and interaction feedback
6. shadows, borders, motion, and polish

Use real or project-approved icons and assets where available. Do not invent unverified imports from UI libraries; confirm component and icon names exist before use.

## Design Token Mapping

Map design values to the project's design system before adding raw CSS values:

| Design Value | Project Token / Utility | Fallback | Notes |
|---|---|---|---|
| primary blue | `--color-primary` | exact hex only if no token exists | verify contrast |

Check:

- color roles, not just hex values
- typography family, size, line height, and weight
- spacing scale and grid gaps
- radius, border, divider, and shadow tokens
- z-index, overlay, and backdrop conventions
- semantic status colors for success, warning, error, and info

Use raw values only when the project has no matching token or when exact fidelity is required. Record raw-value decisions in the acceptance report.

## Theme And Mode Support

If the project supports themes or dark mode:

- use semantic tokens instead of hardcoded light-mode colors
- verify focus, hover, selected, disabled, and error states in each supported mode when practical
- avoid images or shadows that only work on one background

If the design only shows one mode, preserve the current project behavior for other modes and record any unverified mode risk.

## Assets, Icons, And Fonts

Create an asset inventory when the design includes images, logos, illustrations, custom icons, or fonts:

| Asset | Source | Replacement Strategy | Verification |
|---|---|---|---|
| logo | design export | existing brand asset | renders at header size |

Rules:

- prefer existing project assets and icon libraries
- verify icon names and imports exist before using them
- preserve aspect ratio and meaningful alt text
- avoid embedding large base64 assets in source files
- document missing licensed fonts or proprietary assets
- use fallback fonts that preserve layout when exact fonts are unavailable

Do not silently replace a brand-critical asset with a generic placeholder. If the asset is unavailable, show an honest placeholder state and record it as deferred.

## Motion And Microinteractions

Implement motion only when it is visible in the design/prototype or already standard in the project:

- menu, modal, drawer, toast, and tab transitions
- loading skeletons or progress indicators
- hover/press feedback
- reduced-motion behavior when the project supports it

Keep motion short and functional. Do not add decorative animation that changes the product tone.

## Internationalization And Text Resilience

If the project has an i18n system, use it. Do not hardcode user-facing strings unless the local codebase already does.

Check text resilience:

- long labels
- narrow mobile widths
- translated strings that expand by 30-50 percent
- numbers, currency, dates, and units
- empty or unknown values
- right-to-left layout only if the product supports it

Controls must not rely on a fixed English label width unless the project explicitly does.

## Responsive Behavior

If the design only shows one viewport, infer a conservative responsive path:

- preserve primary actions above the fold
- stack dense columns on narrow screens
- keep controls reachable without horizontal page scroll
- avoid text overlap and clipped buttons
- keep fixed-format elements stable with explicit dimensions, aspect ratio, or grid constraints

Record inferred responsive behavior as `R-*` trace rows when it materially affects acceptance.

## Accessibility Basics

For every interactive UI:

- use semantic buttons, links, labels, and headings
- preserve keyboard focus and visible focus indicators
- ensure inputs are editable unless intentionally disabled
- provide accessible names for icon-only controls
- avoid color-only state communication

Add `A-*` trace rows when accessibility behavior is central to the design or workflow.

## Implementation Anti-Patterns

Avoid:

- pixel-copying the screenshot while ignoring project tokens
- duplicating a component that already exists in the product
- shipping unverified icon or UI-library imports
- treating all text as fixed-size and single-line
- hiding overflow instead of designing a resilient layout
- making disabled controls look enabled
- adding local mock shapes that cannot map to a real API later
