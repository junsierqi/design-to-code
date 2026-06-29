# Playwright Patterns

Use this reference when a downstream frontend project has Playwright or an equivalent browser automation tool. The design-to-code repository itself does not require Playwright; these are implementation patterns for real UI projects.

## Browser Evidence Contract

Record:

- route or URL under test
- viewport size
- fixture or account state
- design source or baseline screenshot
- action steps
- assertions
- screenshot paths
- console/page errors
- validation type, usually `real-product-path` when the app route is exercised

If Playwright is unavailable, fall back to project-native tests, DOM-only checks, source-only checks, or manual-inspection evidence and state the limitation.

## Installation Pattern

Prefer project-local Playwright when the target app already has it. For design-to-code skill dogfood or one-off task evidence, keep Playwright dependencies in an artifact directory instead of the repository root:

```bash
mkdir -p .idea-to-code/design-to-code-playwright-dogfood
cd .idea-to-code/design-to-code-playwright-dogfood
npm init -y
npm install --save-dev @playwright/test
npx playwright install chromium
```

The design-to-code repository provides a repeatable fixture generator:

```bash
python skills/design-to-code/scripts/dogfood_playwright_fixture.py --output .idea-to-code/design-to-code-playwright-dogfood --install
```

Use `--skip-browser` when validating script output in CI or when browser execution is intentionally deferred.

## System Browser Fallback

When Playwright's bundled Chromium download is blocked, too slow, or unavailable, use an installed Chromium-family browser and record the fallback as a limitation in the validation evidence.

Set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` or pass the equivalent script option:

```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="/usr/bin/google-chrome" npm test
python skills/design-to-code/scripts/dogfood_playwright_fixture.py --browser-executable "/usr/bin/google-chrome"
```

Windows PowerShell example:

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"
npm test
```

Use this config pattern in generated or task-local Playwright projects:

```js
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  use: {
    browserName: 'chromium',
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined
    }
  }
});
```

This still exercises a real browser path. It is not identical to bundled Playwright Chromium, so the report must name the executable path or say that automatic system-browser discovery was used.

## Screenshot Pattern

```ts
import { test, expect } from '@playwright/test';

test('dashboard visual evidence', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: 'Project health' })).toBeVisible();
  await page.screenshot({ path: 'artifacts/dashboard-desktop.png', fullPage: true });
});
```

Use stable data where possible. Avoid exact full-page screenshot comparison when time, generated ids, animations, or external media make the page unstable.

## Interaction Pattern

Every interactive trace row should prove behavior:

```ts
test('search filters projects', async ({ page }) => {
  await page.goto('/dashboard');
  await page.getByRole('textbox', { name: /search/i }).fill('Apollo');
  await expect(page.getByText('Apollo launch')).toBeVisible();
  await expect(page.getByText('Billing sync')).toBeHidden();
});
```

Presence-only checks are not enough for `I-*` rows.

## State Pattern

Exercise states through mocks, route interception, fixtures, or local state controls:

- loading: delay a response and assert skeletons
- empty: return an empty list or apply a no-match filter
- error: return a failed response and assert recovery UI
- validation: submit invalid form data
- disabled: assert unavailable actions are disabled or explain why

## Console Error Pattern

Collect unexpected errors:

```ts
const errors: string[] = [];
page.on('pageerror', err => errors.push(err.message));
page.on('console', msg => {
  if (msg.type() === 'error') errors.push(msg.text());
});
```

Filter only known harmless messages with a named reason.

## Accessibility Pattern

At minimum:

- use role-based locators for primary controls
- verify keyboard focus for primary flow
- check accessible names for icon-only actions
- verify dialogs and overlays follow project modal behavior

Use axe or the project's accessibility tooling when already available; do not add a new dependency for a small task unless the project normally uses it.

## Viewport Matrix Pattern

Run the supplied design viewport and at least one narrow viewport:

```ts
for (const viewport of [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
]) {
  test(`dashboard viewport ${viewport.width}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto('/dashboard');
    await expect(page.getByRole('main')).toBeVisible();
  });
}
```

Record skipped viewports with a reason.
