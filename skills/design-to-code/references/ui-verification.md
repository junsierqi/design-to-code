# UI Verification

Use this reference to verify implemented UI. Record validation evidence in the active `idea-to-code` bundle with the correct validation type.

## Validation Priority

Prefer evidence in this order:

1. `real-product-path`: user-observable route or app path exercised locally
2. project-native component or integration tests
3. Playwright or browser automation against the running UI
4. DOM-only checks when runtime behavior is unavailable
5. source-only checks for skill/documentation repositories or unreachable runtimes
6. `unverified` with a concrete missing dependency

Do not claim real product-path validation when only source or DOM inspection ran.

## Required UI Checks

For each implemented UI slice, check:

- every `C-*` component renders in the expected view
- every `I-*` interaction performs a state change, navigation, mutation, input update, or visible feedback
- every `S-*` state is reachable or honestly deferred
- responsive layout holds for at least one desktop and one narrow viewport when applicable
- no unexpected console errors occur during the exercised path
- inputs accept text unless intentionally disabled
- icon-only buttons have accessible names

## Viewport Matrix

Define a viewport matrix for user-facing screens:

| Viewport | Purpose | Required When |
|---|---|---|
| mobile narrow | small phones and stacked layout | any responsive page |
| tablet or medium | intermediate layout | supplied design or complex grids |
| desktop | primary desktop design | most app UIs |
| wide desktop | large canvas / dashboard | wide design or dense data UI |

At minimum, verify the supplied design viewport and one narrow viewport when the UI is responsive. Record any skipped viewport with a reason.

## Visual Diff And Screenshot Baselines

When a baseline design screenshot is available, use screenshots to compare:

- layout structure and content hierarchy
- spacing and alignment
- typography scale
- color roles and contrast
- component state appearance
- responsive reflow

Automated pixel diff is useful but not required for every task. If used, define the comparison area and tolerance. If not used, provide manual-inspection screenshots and known difference notes.

Avoid full-page pixel diff as the only signal when data, time, fonts, or dynamic content make exact comparison unstable. Prefer cropped critical regions for high-value areas.

## Dead Button Scan

A visible button-like element is dead if it:

- has no click/submit/navigation behavior
- has an empty handler with no user feedback
- is styled as enabled but cannot be activated
- only logs to console without visible result

For each button, link, menu item, tab, row action, and icon control:

| Element | Expected Behavior | Evidence | Status |
|---|---|---|---|
| Export button | download or visible export feedback | Playwright click + toast screenshot | pass |

Deferred controls must explain the missing dependency and show disabled or placeholder feedback.

## State Verification

Exercise states with the least brittle method available:

- loading: delay or mock pending API response
- empty: no data or filter with no matches
- error: failed API or thrown loader
- validation: invalid form submission
- disabled: missing required input, permissions, or unavailable backend
- success: populated data and completed action

Record the route, fixture, mock, or source condition used to reach each state.

## Accessibility Smoke Checks

For interactive UI, verify at least:

- keyboard can reach primary controls
- focus indicator is visible
- form inputs have labels or accessible names
- icon-only controls have accessible names
- dialogs trap focus or follow the project's modal pattern
- color contrast is not obviously below acceptable thresholds
- error messages are associated with the relevant field when forms are present

Use automated accessibility tooling when the project already has it. Otherwise, record source-only or manual-inspection evidence honestly.

## Screenshot Evidence

Screenshots should support acceptance, not replace behavior checks.

Capture screenshots for:

- primary page or flow
- important interactions such as open dialogs, selected tabs, filtered results, or submitted forms
- loading, empty, and error states
- responsive narrow viewport when UI layout is part of acceptance

Use actual generated filenames in the report. Do not invent screenshot paths. Store task-only screenshots under the `idea-to-code` bundle artifacts or the project's established report folder.

## Evidence Quality For Interactions

An interaction test should prove behavior, not just presence:

- click and verify state change
- type and verify input value or downstream filter/submission state
- keyboard navigate and verify focus/selection
- open and close overlays
- submit invalid data and verify validation
- retry failed state and verify recovery

If a control cannot perform its real action because of a missing backend, verify visible placeholder feedback or a disabled state with an explicit reason.

## Console And Runtime Errors

Collect unexpected runtime errors when using a browser:

- page errors
- failed network calls relevant to the UI
- console errors from the implemented path

Classify known harmless framework/browser messages separately. Do not hide real errors by broad filtering.

## Source-Only Skill Repository Checks

When validating this skill repository, source-only checks are appropriate because the product is prompt/documentation/script content.

Run:

```bash
python skills/design-to-code/scripts/validate_design_to_code.py --root .
python skills/design-to-code/scripts/test_validate_design_to_code.py
```

These checks verify repository structure and prompt contracts; they do not prove behavior inside an arbitrary downstream frontend project.
