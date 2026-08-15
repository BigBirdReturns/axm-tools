import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = path.resolve(import.meta.dirname, "..", "..");
const output = path.join(root, "resolution-backfill", "out", "browser");
const port = 8877;
const origin = `http://127.0.0.1:${port}`;
const url = `${origin}/resolution-backfill/`;

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function waitForServer() {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Server is still starting.
    }
    await new Promise(resolve => setTimeout(resolve, 125));
  }
  throw new Error("loopback server did not start");
}

fs.mkdirSync(output, { recursive: true });
const server = spawn("python", ["-m", "http.server", String(port), "--bind", "127.0.0.1"], {
  cwd: root,
  stdio: ["ignore", "pipe", "pipe"],
});

let serverError = "";
server.stderr.on("data", chunk => { serverError += chunk.toString(); });

const browserErrors = [];
const externalRequests = [];
const results = [];
let browser = null;

try {
  await waitForServer();
  browser = await chromium.launch({ headless: true });
  const viewports = [
    { name: "desktop", width: 1600, height: 1000 },
    { name: "laptop", width: 1024, height: 900 },
    { name: "mobile", width: 390, height: 844 },
    { name: "compact", width: 320, height: 720 },
  ];

  for (const viewport of viewports) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      reducedMotion: "reduce",
    });
    try {
      const page = await context.newPage();
      page.setDefaultTimeout(15000);
      page.setDefaultNavigationTimeout(20000);
      page.on("pageerror", error => browserErrors.push(`${viewport.name}: ${error.message}`));
      page.on("console", message => {
        if (message.type() === "error") browserErrors.push(`${viewport.name}: console: ${message.text()}`);
      });
      page.on("request", request => {
        const requestUrl = new URL(request.url());
        if (requestUrl.origin !== origin) externalRequests.push(request.url());
      });

      await page.goto(url, { waitUntil: "networkidle" });
      await page.waitForSelector('body[data-ready="true"]');

      assert(await page.locator("details.surface-record").count() === 10, `${viewport.name}: expected ten surface records`);
      assert((await page.locator("#surfaceCount").textContent()) === "10", `${viewport.name}: surface metric is not 10`);
      assert((await page.locator("#qualifiedCount").textContent()) === "00", `${viewport.name}: no legacy surface may be qualified`);

      const failedMetric = Number(await page.locator("#failedCount").textContent());
      const criticalMetric = Number(await page.locator("#criticalCount").textContent());
      assert(failedMetric > 0, `${viewport.name}: failed-gate metric must remain visible`);
      assert(criticalMetric > 0, `${viewport.name}: critical-finding metric must remain visible`);

      const overflow = await page.evaluate(() => ({
        document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        body: document.body.scrollWidth - document.body.clientWidth,
        hero: [...document.querySelectorAll(".hero-title span")].map(element => {
          const rect = element.getBoundingClientRect();
          return { left: rect.left, right: rect.right, viewport: innerWidth };
        }),
        controls: [...document.querySelectorAll("button, input, summary")].map(element => {
          const rect = element.getBoundingClientRect();
          return { width: rect.width, left: rect.left, right: rect.right };
        }),
      }));
      assert(overflow.document <= 1 && overflow.body <= 1, `${viewport.name}: page has horizontal overflow ${JSON.stringify(overflow)}`);
      assert(overflow.hero.every(rect => rect.left >= -1 && rect.right <= rect.viewport + 1), `${viewport.name}: display line clips outside viewport`);
      assert(overflow.controls.every(rect => rect.width > 0 && rect.left >= -1 && rect.right <= viewport.width + 1), `${viewport.name}: control clips outside viewport`);

      await page.locator('button[data-filter="critical"]').click();
      assert(await page.locator("details.surface-record").count() === 5, `${viewport.name}: critical filter should show five surfaces`);
      await page.locator('button[data-filter="all"]').click();

      await page.locator("#searchInput").fill("registered place identity");
      assert(await page.locator("details.surface-record").count() === 1, `${viewport.name}: unique evidence phrase should isolate one surface`);
      await page.locator("#searchInput").fill("");

      const firstRecord = page.locator("details.surface-record").first();
      await firstRecord.locator("summary").click();
      assert(await firstRecord.locator(".gate").count() === 12, `${viewport.name}: opened record must expose twelve gates`);
      assert(await firstRecord.locator(".finding").count() >= 1, `${viewport.name}: opened record must expose findings`);
      assert(await firstRecord.locator(".asset-queue li").count() >= 1, `${viewport.name}: opened record must expose required assets`);

      if (viewport.name === "desktop") {
        const initialTheme = await page.locator("html").getAttribute("data-theme");
        await page.locator("#themeToggle").click();
        const changedTheme = await page.locator("html").getAttribute("data-theme");
        assert(changedTheme !== initialTheme, "desktop: theme control did not change theme");
        await page.reload({ waitUntil: "networkidle" });
        await page.waitForSelector('body[data-ready="true"]');
        assert((await page.locator("html").getAttribute("data-theme")) === changedTheme, "desktop: theme did not persist across reload");
      }

      await page.keyboard.press("Tab");
      const focused = await page.evaluate(() => document.activeElement?.tagName || "");
      assert(Boolean(focused), `${viewport.name}: keyboard focus did not enter the page`);

      await page.screenshot({
        path: path.join(output, `${viewport.name}-full.png`),
        fullPage: true,
        animations: "disabled",
      });

      results.push({
        viewport,
        surfaceRecords: 10,
        failedMetric,
        criticalMetric,
        horizontalOverflow: Math.max(overflow.document, overflow.body),
        result: "PASS",
      });
    } finally {
      await context.close().catch(() => {});
    }
  }

  assert(browserErrors.length === 0, `browser errors: ${browserErrors.join(" | ")}`);
  assert(externalRequests.length === 0, `unexpected external requests: ${externalRequests.join(" | ")}`);

  const receipt = {
    schema: "axm-tools/resolution-backfill-browser-playtest@1",
    generated_at: new Date().toISOString(),
    url,
    viewports: results,
    exercised: [
      "inventory load",
      "ten governed surface records",
      "critical filter",
      "full-text search",
      "record expansion",
      "twelve-gate detail",
      "asset queue",
      "light-dark persistence",
      "keyboard entry",
      "document and element overflow",
      "reduced motion",
      "external-request refusal",
    ],
    browser_errors: browserErrors,
    external_requests: externalRequests,
    result: "PASS",
  };
  fs.writeFileSync(path.join(output, "playtest.json"), `${JSON.stringify(receipt, null, 2)}\n`);
  console.log(JSON.stringify(receipt, null, 2));
} catch (error) {
  console.error(error.stack || error.message);
  if (serverError) console.error(serverError);
  process.exitCode = 1;
} finally {
  if (browser) await browser.close().catch(() => {});
  server.kill("SIGTERM");
  await Promise.race([
    new Promise(resolve => server.once("exit", resolve)),
    new Promise(resolve => setTimeout(resolve, 2000)),
  ]);
}
