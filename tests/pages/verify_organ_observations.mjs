// Drives the Organ Evolution observation overlay through a loopback-only origin.

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
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const pageErrors = [];
const externalRequests = [];
page.on("pageerror", error => pageErrors.push(String(error.message)));
page.on("request", request => {
  if (!request.url().startsWith(ORIGIN + "/")) externalRequests.push(request.url());
});

try {
  await page.goto(ORIGIN + "/organ-evolution/");
  await page.waitForSelector(".observation-panel");
  const body = await page.locator("#workspace").innerText();
  check("default Bloodstream anatomy carries the live observation panel",
    body.includes("Observed implementation state") && body.includes("BigBirdReturns/axm-bloodstream"));
  check("required current workflow failure remains visible",
    body.includes("Workflow Required Not Green") && body.includes("concluded failure"));
  check("workflow result is displayed with declared role and lifecycle",
    body.includes("Permanent Gate · Current · required · declared"));
  check("local observation retains source and limitation",
    body.includes("operator restart receipt") && body.includes("One workstation and one ledger only"));
  check("machine facts do not present themselves as readiness or authority",
    body.includes("Neither record changes the organ health envelope") && body.includes("This is not a health or readiness verdict"));
  const digest = await page.locator(".observation-digest code").innerText();
  check("complete source digest is rendered in a wrap-safe custody field",
    digest.startsWith("organobs1_") && digest.length === 74, digest);

  const top = await page.locator("#topStats").innerText();
  check("top rail distinguishes current red gates from role gaps",
    top.includes("2 observed organs") && top.includes("1 current red gates") && top.includes("0 workflow role gaps"));

  await page.getByRole("button", { name: /Genesis/ }).click();
  await page.waitForTimeout(50);
  const genesis = await page.locator("#workspace").innerText();
  check("switching organs switches the observed repository",
    genesis.includes("BigBirdReturns/axm-genesis") && !genesis.includes("BigBirdReturns/axm-bloodstream"));
  check("green required gate and release tag remain visible",
    genesis.includes("Permanent Gate · Current · required · declared") && genesis.includes("completed · success") && genesis.includes("v1.0.0"));

  check("observation overlay emits no JavaScript errors", pageErrors.length === 0, JSON.stringify(pageErrors));
  check("observation overlay makes zero outbound requests", externalRequests.length === 0, JSON.stringify(externalRequests));
} finally {
  await browser.close();
  await new Promise(resolveClose => server.close(resolveClose));
}

if (failures) {
  console.error(`\n${failures} assertion(s) failed`);
  process.exit(1);
}
console.log("\nOrgan Evolution observation overlay: all assertions passed");
