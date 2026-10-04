/** S-06.02.25: real Chromium against the built CRM and its real local API.
 * Start the real server with a disposable OFFSETX_DATA_DIR and local API token.
 * Install Playwright separately (npm install --no-save playwright), then run:
 * OFFSETX_TEST_API_TOKEN=... node scripts/live/screen_opens_at_top.mjs
 * Optional: OFFSETX_TEST_BASE_URL, PLAYWRIGHT_MODULE, CHROMIUM_EXECUTABLE_PATH,
 * CHROMIUM_ARGS_JSON. Only campaign-list failures are injected.
 */
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const base = process.env.OFFSETX_TEST_BASE_URL || "http://127.0.0.1:8766";
const token = process.env.OFFSETX_TEST_API_TOKEN;
assert.ok(token, "Set OFFSETX_TEST_API_TOKEN for the disposable local server");
assert.ok(["localhost", "127.0.0.1"].includes(new URL(base).hostname), "Use a disposable loopback server");
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROMIUM_EXECUTABLE_PATH || undefined,
  args: JSON.parse(process.env.CHROMIUM_ARGS_JSON || "[]")
});
let checks = 0;
const campaignWarning = (page) => page.locator("#main-content > .state-panel").filter({ hasText: "Could not refresh campaigns" });

async function visibleAtTop(page, warning) {
  await page.waitForFunction(() => document.activeElement?.id === "main-content");
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const bar = await page.locator(".topbar").boundingBox();
  const bottom = bar.y + bar.height;
  for (const locator of [page.locator("#main-content h1"), ...(warning ? [campaignWarning(page)] : [])]) {
    const box = await locator.boundingBox();
    assert.ok(box && box.y >= bottom && box.y + box.height <= page.viewportSize().height,
      `${await locator.textContent()} must be fully visible below topbar: ${JSON.stringify({ box, bottom })}`);
  }
  // Long forms and the AI chat intentionally extend below the viewport.
  // Their first panel must start in view, with its header/first action visible.
  const panel = page.locator("#main-content .panel, #main-content .state-panel, #main-content .ai-shell")
    .filter({ hasNot: page.getByText("Could not refresh campaigns", { exact: true }) }).first();
  const panelBox = await panel.boundingBox();
  assert.ok(panelBox && panelBox.y >= bottom && panelBox.y < page.viewportSize().height, "First panel starts in view");
  const firstContent = panel.locator("h1, h2, strong, button, input, select").first();
  const firstBox = await firstContent.boundingBox();
  assert.ok(firstBox && firstBox.y >= bottom && firstBox.y + firstBox.height <= page.viewportSize().height, "First panel header/action is fully visible");
  assert.equal(await page.evaluate(() => window.scrollY), 0, "Screen opens at its top");
  checks++;
}

async function navigate(page, screen) {
  // Exercise the navigation link, starting below the screen's top.
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.locator(page.viewportSize().width < 860 ? ".mobile-nav" : ".sidebar").locator(`a[href="#${screen}"]`).click();
  await page.waitForFunction((screen) =>
    location.hash === `#${screen}` && document.querySelector(`a[href="#${screen}"][aria-current="page"]`), screen);
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function refresh(page) {
  await page.getByRole("button", { name: "Set local API token" }).click();
  await page.getByRole("button", { name: "Save for session" }).click();
}

try {
  console.log(`Chromium ${browser.version()}`);
  for (const width of [1280, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    await context.addInitScript((token) => { if (location.protocol === "http:" || location.protocol === "https:") sessionStorage.setItem("offsetx-api-token", token); }, token);
    const page = await context.newPage();
    await page.goto(`${base}/#dashboard`);
    await page.waitForFunction(() => {
      const select = document.querySelector('[aria-label="Active campaign"]');
      return select instanceof HTMLSelectElement && !select.disabled;
    });
    for (const screen of ["settings", "contacts", "ai", "product"]) {
      await navigate(page, screen);
      await visibleAtTop(page, false);
      console.log(`PASS ${width} ${screen}: title visible, focus main, scroll 0`);
    }

    let release;
    let pending;
    await page.route(/\/api\/v1\/campaigns\?/, async (route) => {
      await new Promise((resolve) => { release = resolve; pending?.(); });
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "Campaign list temporarily unavailable" }) });
    });
    for (const screen of ["settings", "contacts", "ai", "product"]) {
      const requested = new Promise((resolve) => { pending = resolve; });
      await refresh(page);
      await requested;
      await navigate(page, screen);
      release();
      await campaignWarning(page).waitFor();
      await visibleAtTop(page, true);
      console.log(`PASS ${width} ${screen}: delayed warning and title visible, focus main`);
    }
    // Warning already rendered when a new route opens.
    for (const screen of ["settings", "contacts", "ai", "product"]) {
      await navigate(page, screen);
      await visibleAtTop(page, true);
      console.log(`PASS ${width} ${screen}: existing warning and title visible`);
    }
    await context.close();

    // Initial failure keeps Settings and AI reachable; campaign-dependent
    // Contacts/Product must remain blocked until the list has loaded (D-130).
    const failed = await browser.newContext({ viewport: { width, height: 900 } });
    await failed.addInitScript((token) => { if (location.protocol === "http:" || location.protocol === "https:") sessionStorage.setItem("offsetx-api-token", token); }, token);
    const blocked = await failed.newPage();
    await blocked.route(/\/api\/v1\/campaigns\?/, (route) => route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"Unavailable"}' }));
    await blocked.goto(`${base}/#settings`);
    await campaignWarning(blocked).waitFor();
    await visibleAtTop(blocked, true);
    await navigate(blocked, "ai");
    await visibleAtTop(blocked, true);
    for (const screen of ["contacts", "product"]) {
      await navigate(blocked, screen);
      assert.equal(await blocked.locator("#main-content h1").count(), 0, `${screen} stays gated on initial failure`);
      const box = await campaignWarning(blocked).boundingBox();
      assert.ok(box && box.y >= (width < 860 ? 60 : 68) && box.y + box.height <= 900);
      await blocked.waitForFunction(() => document.activeElement?.id === "main-content");
      assert.equal(await blocked.evaluate(() => window.scrollY), 0, "Blocked screen opens at its top");
      checks++;
    }
    await failed.close();
    console.log(`PASS ${width}: initial failure recovery screens visible; campaign-dependent screens gated`);
  }
  console.log(`${checks} browser checks passed`);
} finally {
  await browser.close();
}
