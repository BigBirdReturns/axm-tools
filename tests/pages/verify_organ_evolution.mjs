// Drives the real Organ Evolution surface through a loopback-only origin.
// The page has no runtime dependencies, backend, analytics, or external requests.

import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, extname, join, normalize, resolve } from "node:path";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isDeepStrictEqual } from "node:util";
import { createServer } from "node:http";

async function loadPlaywright() {
  try { return await import("playwright"); }
  catch { return await import("/opt/node22/lib/node_modules/playwright/index.mjs"); }
}

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "../..");
const EXAMPLE = resolve(ROOT, "organ-evolution/data/axm-estate.example.json");
const ACCEPTED = resolve(ROOT, "organ-evolution/data/fixtures/accepted-decision.fixture.json");
const DECISION_COMPILER = resolve(ROOT, "organ-evolution/scripts/decision_job.py");
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

  check("worked estate loads ten organs",
    await page.locator("#organList .organ-button").count() === 10);
  check("Bloodstream is the default organ",
    (await page.locator("#organList .organ-button.active").innerText()).includes("Bloodstream"));
  check("anatomy renders the estate dependency map",
    await page.locator(".organ-map svg .map-node").count() === 10);
  check("authority membrane remains explicit",
    (await page.locator("#workspace").innerText()).includes("Authority membrane") &&
    (await page.locator("#workspace").innerText()).includes("Forbidden"));
  check("Supplier Foundry is a first-class estate organ",
    (await page.locator("#organList").innerText()).includes("Supplier Foundry"));

  await page.getByRole("button", { name: /Supplier Foundry/ }).click();
  const foundryAnatomy = await page.locator("#workspace").innerText();
  check("Supplier Foundry refuses capability, policy, and scheduling authority",
    foundryAnatomy.includes("define domain capability") &&
    foundryAnatomy.includes("choose estate policy") &&
    foundryAnatomy.includes("schedule the estate"));
  await page.click('[data-view="evolution"]');
  const foundryPostures = (await page.locator(".candidate-strip").innerText()).toUpperCase();
  check("Supplier Foundry exposes a bounded admissible lane and a held expansion",
    await page.locator(".candidate-strip .candidate").count() === 2 &&
    foundryPostures.includes("ADMISSIBLE") &&
    foundryPostures.includes("HOLD"), foundryPostures);
  await page.getByRole("button", { name: /Bloodstream/ }).click();

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
  check("circulation export remains disabled before an accepted admissible decision",
    await page.locator('#exportJobBtn').isDisabled());

  await page.setInputFiles('#fileInput', EXAMPLE);
  await page.waitForTimeout(150);
  check("example JSON round-trips through the import seam",
    await page.locator("#organList .organ-button").count() === 10 &&
    (await page.locator("#organList .organ-button.active").innerText()).includes("Bloodstream"));

  await page.click('#newOrganBtn');
  await page.fill('#editorDialog input[name="name"]', 'Test Organ');
  await page.fill('#editorDialog input[name="class"]', 'repair');
  await page.fill('#editorDialog textarea[name="mission"]', 'Prove reversible local creation.');
  await page.click('#dialogSave');
  await page.waitForTimeout(80);
  check("a new local organ can be created without backend write-back",
    await page.locator("#organList .organ-button").count() === 11 &&
    (await page.locator("#organList").innerText()).includes("Test Organ"));

  const fixture = JSON.parse(await readFile(ACCEPTED, "utf-8"));
  const decisionPage = await browser.newPage({ viewport: { width: 1180, height: 900 } });
  const decisionErrors = [];
  const decisionExternal = [];
  decisionPage.on("pageerror", error => decisionErrors.push(String(error.message)));
  decisionPage.on("request", request => {
    const url = request.url();
    if (url.startsWith("http") && !url.startsWith(ORIGIN + "/")) decisionExternal.push(url);
  });
  await decisionPage.goto(ORIGIN + "/organ-evolution/");
  await decisionPage.setInputFiles('#fileInput', ACCEPTED);
  await decisionPage.waitForTimeout(100);
  await decisionPage.click('[data-view="decision"]');
  check("accepted decision renders mandate, circulation, and execution custody",
    (await decisionPage.locator("#workspace").innerText()).includes("Mandate and circulation") &&
    (await decisionPage.locator("#workspace").innerText()).includes("Execution evidence") &&
    (await decisionPage.locator("#workspace").innerText()).includes("Compiler boundary"));
  check("accepted admissible fixture enables circulation export",
    !(await decisionPage.locator('#exportJobBtn').isDisabled()));

  const browserJob = await decisionPage.evaluate(async accepted => {
    return await window.AXM_DECISION_JOB.build(accepted);
  }, fixture);
  const temp = await mkdtemp(join(tmpdir(), "organ-decision-"));
  const pythonOutput = join(temp, "job.json");
  try {
    execFileSync(process.env.PYTHON || "python", [
      DECISION_COMPILER,
      "build",
      ACCEPTED,
      "--output",
      pythonOutput,
    ], {stdio: "pipe"});
    const pythonJob = JSON.parse(await readFile(pythonOutput, "utf-8"));
    check("browser and Python compile byte-equivalent decision jobs",
      isDeepStrictEqual(browserJob, pythonJob));

    const downloadPromise = decisionPage.waitForEvent('download');
    await decisionPage.click('#exportJobBtn');
    const jobDownload = await downloadPromise;
    const downloadedPath = await jobDownload.path();
    const downloadedJob = JSON.parse(await readFile(downloadedPath, "utf-8"));
    check("the visible export seam emits the exact qualified job",
      isDeepStrictEqual(downloadedJob, pythonJob));
    check("decision, job, and execution identities remain independently bound",
      pythonJob.decision.decisionId.startsWith("orgdec1_") &&
      pythonJob.jobId.startsWith("organjob1_") &&
      pythonJob.execution.executionId.startsWith("organexec1_") &&
      pythonJob.execution.jobId === pythonJob.jobId);
  } finally {
    await rm(temp, {recursive: true, force: true});
  }
  check("decision compiler page has no JavaScript errors",
    decisionErrors.length === 0, JSON.stringify(decisionErrors));
  check("decision compiler page makes zero outbound requests",
    decisionExternal.length === 0, JSON.stringify(decisionExternal));
  await decisionPage.close();

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
