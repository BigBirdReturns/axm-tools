// Drives the real Organ Evolution surface through a loopback-only origin.
// The page has no runtime dependencies, backend, analytics, or external requests.

import { fileURLToPath } from "node:url";
import { dirname, extname, join, normalize, resolve } from "node:path";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";

async function loadPlaywright() {
  try { return await import("playwright"); }
  catch { return await import("/opt/node22/lib/node_modules/playwright/index.mjs"); }
}

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "../..");
const EXAMPLE = resolve(ROOT, "organ-evolution/data/axm-estate.example.json");
const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
};

const server = createServer(async (req, res) => {
  try {
    const requestPath = decodeURIComponent(new URL(req.url, "http://127.0.0.1").pathname);
    let relative = requestPath.replace(/^\/+/, "");
    if (!relative || relative === "organ-evolution") relative = "organ-evolution/index.html";
    if (relative.endsWith("/")) relative += "index.html";
    const candidate = normalize(join(ROOT, relative));
    if (!candidate.startsWith(ROOT)) return res.writeHead(403).end("forbidden");
    const bytes = await readFile(candidate);
    res.writeHead(200, {
      "content-type": MIME[extname(candidate).toLowerCase()] || "application/octet-stream",
      "cache-control": "no-store",
    });
    res.end(bytes);
  } catch {
    res.writeHead(404).end("not found");
  }
});

await new Promise((ok, bad) => {
  server.once("error", bad);
  server.listen(0, "127.0.0.1", ok);
});
const ORIGIN = `http://127.0.0.1:${server.address().port}`;

let failures = 0;
function check(name, ok, detail = "") {
  console.log(`${ok ? "  ok " : "FAIL "} ${name}${!ok && detail ? " — " + detail : ""}`);
  if (!ok) failures++;
}

const { chromium } = await loadPlaywright();
const exe = process.env.AXM_CHROMIUM_PATH;
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const pageErrors = [];
const externalRequests = [];
page.on("pageerror", e => pageErrors.push(String(e.message)));
page.on("request", r => { if (!r.url().startsWith(ORIGIN + "/")) externalRequests.push(r.url()); });

try {
  await page.goto(ORIGIN + "/organ-evolution/");
  await page.waitForSelector("#organList .organ-button");

  check("worked estate loads nine organs",
    await page.locator("#organList .organ-button").count() === 9);
  check("Bloodstream is the default organ",
    (await page.locator("#organList .organ-button.active").innerText()).includes("Bloodstream"));
  check("anatomy renders the estate dependency map",
    await page.locator(".organ-map svg .map-node").count() === 9);
  check("authority membrane remains explicit",
    (await page.locator("#workspace").innerText()).includes("Authority membrane") &&
    (await page.locator("#workspace").innerText()).includes("Forbidden"));

  await page.click('[data-view="evolution"]');
  await page.waitForSelector(".candidate-strip .candidate");
  check("Bloodstream exposes three evolution candidates",
    await page.locator(".candidate-strip .candidate").count() === 3);

  await page.getByRole("button", { name: /Expand Bloodstream into the universal estate orchestrator/ }).click();
  check("scope expansion is blocked by hard gates",
    (await page.locator(".section-title .tag.red").innerText()).includes("Blocked"));
  const findings = await page.locator(".flag-list").last().innerText();
  check("capture geometry is surfaced without motive inference",
    findings.includes("Authority and benefit concentration") && findings.includes("Evidence dependence"));
  check("candidate editor exposes all twelve fitness dimensions",
    await page.locator('[data-dimension]').count() === 12);
  check("candidate editor exposes all five hard gates",
    await page.locator('[data-gate]').count() === 5);

  await page.locator('#dim-authority').fill('5');
  await page.reload();
  await page.click('[data-view="evolution"]');
  await page.getByRole("button", { name: /Expand Bloodstream into the universal estate orchestrator/ }).click();
  check("local workspace survives reload",
    await page.locator('#dim-authority').inputValue() === '5');

  await page.click('[data-view="actors"]');
  const actorText = await page.locator("#workspace").innerText();
  check("actor view preserves self-declared, ascribed, and inferred interests",
    actorText.includes("Self Declared") && actorText.includes("Ascribed") && actorText.includes("Inferred"));
  const roleHeaders = await page.locator(".role-grid .head").allTextContents();
  check("actor matrix separates sponsor, validator, decider, and beneficiary",
    ["Sponsor", "Validator", "Decider", "Beneficiary"].every(label => roleHeaders.includes(label)));

  await page.click('[data-view="evidence"]');
  check("evidence ledger distinguishes class and independence",
    (await page.locator("#workspace").innerText()).includes("confirmed") &&
    (await page.locator("#workspace").innerText()).includes("independent"));

  await page.click('[data-view="stress"]');
  await page.click('#runStressBtn');
  await page.waitForSelector('#stressResult table');
  check("seven stress scenarios execute",
    await page.locator('#stressResult tbody tr').count() === 7);
  check("stress matrix keeps all three candidate columns",
    await page.locator('#stressResult thead th').count() === 4);

  await page.click('[data-view="decision"]');
  const memo = await page.locator('#memo').innerText();
  check("decision memorandum carries the complete analytical shape",
    ["Classification.", "Actors and mechanism.", "Receipts and limits.", "Wider map.", "Control question."].every(x => memo.includes(x)));
  check("decision surface does not auto-accept blocked work",
    (await page.locator("#workspace").innerText()).includes("Blocked"));

  await page.setInputFiles('#fileInput', EXAMPLE);
  await page.waitForTimeout(150);
  check("example JSON round-trips through the import seam",
    await page.locator("#organList .organ-button").count() === 9 &&
    (await page.locator("#organList .organ-button.active").innerText()).includes("Bloodstream"));

  await page.click('#newOrganBtn');
  await page.fill('#editorDialog input[name="name"]', 'Test Organ');
  await page.fill('#editorDialog input[name="class"]', 'repair');
  await page.fill('#editorDialog textarea[name="mission"]', 'Prove reversible local creation.');
  await page.click('#dialogSave');
  await page.waitForTimeout(80);
  check("a new local organ can be created without backend write-back",
    await page.locator("#organList .organ-button").count() === 10 &&
    (await page.locator("#organList").innerText()).includes("Test Organ"));

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const mobileErrors = [];
  mobile.on("pageerror", e => mobileErrors.push(String(e.message)));
  await mobile.goto(ORIGIN + "/organ-evolution/");
  await mobile.waitForSelector("#organList .organ-button");
  const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check("mobile surface contains overflow inside components rather than the page",
    overflow <= 2, String(overflow));
  check("mobile run has no JavaScript errors", mobileErrors.length === 0, JSON.stringify(mobileErrors));
  await mobile.close();

  check("zero outbound network requests", externalRequests.length === 0, JSON.stringify(externalRequests));
  check("desktop run has no JavaScript errors", pageErrors.length === 0, JSON.stringify(pageErrors));
} finally {
  await browser.close();
  await new Promise(resolveClose => server.close(resolveClose));
}

if (failures) {
  console.error(`\n${failures} assertion(s) failed`);
  process.exit(1);
}
console.log("\nOrgan Evolution surface: all assertions passed");
