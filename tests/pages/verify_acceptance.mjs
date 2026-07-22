// AXM Readiness regression harness — drives the real Pages surface in a
// headless browser and asserts the operational intake behavior a buyer sees.
//
// Fixture: tests/fixtures/acceptance_two_sheets.xlsx is synthetic. The
// maintenance sheet deliberately omits required_part_id so the missing-link
// finding remains covered.

import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

async function loadPlaywright() {
  try { return await import("playwright"); }
  catch { return await import("/opt/node22/lib/node_modules/playwright/index.mjs"); }
}

const here = dirname(fileURLToPath(import.meta.url));
const PAGE = resolve(here, "../../acceptance.html");
const XLSX = resolve(here, "../fixtures/acceptance_two_sheets.xlsx");

let failures = 0;
function check(name, ok, detail = "") {
  console.log(`${ok ? "  ok " : "FAIL "} ${name}${!ok && detail ? " — " + detail : ""}`);
  if (!ok) failures++;
}

const { chromium } = await loadPlaywright();
const exe = process.env.AXM_CHROMIUM_PATH;
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const page = await browser.newPage();

const pageErrors = [];
const netRequests = [];
page.on("pageerror", (e) => pageErrors.push(String(e.message)));
page.on("request", (r) => { if (!r.url().startsWith("file://")) netRequests.push(r.url()); });

await page.goto("file://" + PAGE);
await page.waitForSelector("#findingView .finding", { timeout: 20000 });

// --- worked example: the canonical cross-surface result ---
const kinds = await page.$$eval("#findingView .finding .fkind", (es) => es.map((e) => e.innerText.trim()));
check("worked example: 2 masked shortages lead, 1 supportable closes",
  JSON.stringify(kinds) === JSON.stringify([
    "ADMINISTRATIVE STOCK MASKS A PHYSICAL SHORTAGE",
    "ADMINISTRATIVE STOCK MASKS A PHYSICAL SHORTAGE",
    "SUPPORTABLE FROM STOCK ON RECORD",
  ]), JSON.stringify(kinds));

const heroVerdict = await page.$eval("#heroVerdict", (e) => e.innerText);
const heroSubject = await page.$eval("#heroSubject", (e) => e.innerText);
check("hero identifies the masked shortage and down asset",
  heroVerdict.includes("Masked shortage") && heroSubject.includes("ASSET-A17"), `${heroVerdict} / ${heroSubject}`);

check("every finding cites file/row/hash evidence",
  await page.$eval("#findingView", (e) => e.innerText.includes("sha-256")));

const boxes = await page.$$eval("#summaryView .box b", (bs) => bs.map((b) => b.innerText.trim()));
check("surface tallies: 3 pass / 1 pass-with-gaps / 1 fail",
  JSON.stringify(boxes) === JSON.stringify(["3", "1", "1"]), JSON.stringify(boxes));

const statuses = await page.$$eval("#surfaceTable tbody tr", (trs) =>
  trs.map((tr) => {
    const td = tr.querySelectorAll("td");
    return td[0].innerText.trim() + "=" + td[1].innerText.trim();
  }));
check("the deliberately-bad export FAILs",
  statuses.some((s) => s.startsWith("bad_availability_export.csv=FAIL")), JSON.stringify(statuses));

const asks = await page.$$eval("#asksView li", (es) => es.map((e) => e.innerText));
check("asks are generated and end with the declared-gap standing rule",
  asks.length >= 2 && asks[asks.length - 1].includes("If a field is not tracked"), JSON.stringify(asks.length));

// --- boundary, deployment posture, and operator surface ---
await page.click('[data-tab="about"]');
const bodyText = await page.$eval("body", (e) => e.innerText);
check("honesty boundary present",
  bodyText.includes("does not mint Genesis shards") && bodyText.includes("candidates for custody, not truth"));
check("public-page CUI boundary present",
  /dummy or de-identified data/i.test(bodyText) && /CUI/i.test(bodyText));
check("operator workflow exposes finding, surfaces, evidence, asks, data, and about",
  JSON.stringify(await page.$$eval(".navbtn .navlabel", es => es.map(e => e.innerText.trim()))) === JSON.stringify(["Finding","Surfaces","Evidence","Asks","Data","About"]));
check("standalone launcher is linked",
  (await page.getAttribute("#offlineLink", "href")) === "AXM_Readiness_Offline.html");

// --- theme toggle ---
const before = await page.$eval("html", (e) => e.dataset.theme);
await page.click("#themeBtn");
const after = await page.$eval("html", (e) => e.dataset.theme);
check("theme toggle flips light/dark", before !== after, `${before} -> ${after}`);

// --- a real XLSX through the dependency-free reader ---
await page.click('[data-tab="data"]');
await page.setInputFiles("#fileInput", XLSX);
await page.click("#analyzeBtn");
await page.waitForFunction(
  () => document.getElementById("statusMsg").textContent.includes("Analyzed"),
  null, { timeout: 20000 });

const xlsxTypes = await page.$$eval("#surfaceTable tbody tr td:nth-child(3)", (tds) => tds.map((t) => t.innerText.trim()));
check("XLSX: both sheets classified (inventory + maintenance)",
  JSON.stringify(xlsxTypes) === JSON.stringify(["inventory", "maintenance"]), JSON.stringify(xlsxTypes));

const xlsxKinds = await page.$$eval("#findingView .finding .fkind", (es) => es.map((e) => e.innerText.trim()));
check("XLSX: missing part linkage surfaces as the finding, not a crash",
  JSON.stringify(xlsxKinds) === JSON.stringify(["BLOCKED WORK WITHOUT PART LINKAGE"]), JSON.stringify(xlsxKinds));

check("export buttons enabled after analysis",
  await page.$eval("#exportJsonBtn", (b) => !b.disabled) && await page.$eval("#exportHtmlBtn", (b) => !b.disabled));

// --- core promises ---
check("zero non-file network requests", netRequests.length === 0, JSON.stringify(netRequests));
check("no JavaScript errors", pageErrors.length === 0, JSON.stringify(pageErrors));

await browser.close();

if (failures) {
  console.error(`\n${failures} assertion(s) failed`);
  process.exit(1);
}
console.log("\nAXM Readiness acceptance page: all assertions passed");
