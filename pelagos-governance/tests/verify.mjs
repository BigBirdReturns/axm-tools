import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import net from 'node:net';
import { chromium } from 'playwright';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TOOL = path.resolve(HERE, '..');
const REPO = path.resolve(TOOL, '..');

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}

async function waitServer(url, tries = 80) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url);
      if (r.ok) return;
    } catch {}
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error(`server did not start: ${url}`);
}

function monitor(page, origin) {
  const external = [];
  const consoleErrors = [];
  const pageErrors = [];
  page.on('request', req => {
    const u = req.url();
    if (u.startsWith('data:') || u.startsWith('blob:')) return;
    try {
      if (new URL(u).origin !== origin) external.push(u);
    } catch {
      external.push(u);
    }
  });
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', err => pageErrors.push(String(err.stack || err)));
  return { external, consoleErrors, pageErrors };
}

async function main() {
  const port = await freePort();
  const origin = `http://127.0.0.1:${port}`;
  const server = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], {
    cwd: REPO,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let serverErr = '';
  server.stderr.on('data', d => { serverErr += d.toString(); });

  const launchOptions = { headless: true };
  if (fs.existsSync('/usr/bin/chromium')) launchOptions.executablePath = '/usr/bin/chromium';
  const browser = await chromium.launch(launchOptions);
  try {
    await waitServer(`${origin}/pelagos-governance/`);
    const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage();
    const monitorState = monitor(page, origin);

    await page.goto(`${origin}/pelagos-governance/`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => document.body.dataset.ready === 'pass');
    assert.match(await page.title(), /DDV-PEL-003/);

    const baseline = await page.evaluate(() => {
      const t = window.__PELAGOS_TEST__;
      return {
        keys: Object.keys(t.PUBLIC),
        counts: {
          counterparties: t.PUBLIC.counterparties.length,
          instruments: t.PUBLIC.instruments.length,
          claims: t.PUBLIC.claims.length,
          evidence: t.PUBLIC.evidence.length,
          rights: t.PUBLIC.rights.length,
          exceptions: t.PUBLIC.exceptions.length,
          invariants: t.PUBLIC.invariants.length,
          stress: t.PUBLIC.stress_scenarios.length,
          roles: t.PUBLIC.role_profiles.length,
          apertures: t.PUBLIC.apertures.length,
          plans: t.PUBLIC.qualification_plans.length,
        },
        admission: t.workspaceAdmission(),
        runtime: t.runtimeHealth(),
      };
    });
    assert.equal(baseline.keys.length, 19);
    assert.deepEqual(baseline.counts, {
      counterparties: 18, instruments: 14, claims: 54, evidence: 13,
      rights: 10, exceptions: 28, invariants: 40, stress: 10,
      roles: 7, apertures: 4, plans: 26,
    });
    assert.equal(baseline.admission, null);
    assert.equal(baseline.runtime.unexpected_resources.length, 0);

    // Pelagos admission is the first private-use gate.
    await page.click('#admitWorkspace');
    await page.fill('#admissionForm [name="company_name"]', 'Pelagos Frontier Technologies');
    await page.fill('#admissionForm [name="decision_owner"]', 'Samuel Scrivens');
    await page.fill('#admissionForm [name="technical_owner"]', 'Shrey Naphade');
    await page.fill('#admissionForm [name="communications_owner"]', 'Daniel Scrivens');
    await page.fill('#admissionForm [name="custodian"]', 'Samuel Scrivens');
    await page.fill('#admissionForm [name="authority_source"]', 'CEO internal operating authority for this private working copy');
    await page.fill('#admissionForm [name="note"]', 'Admit as a private working copy. Public claims remain candidate until corrected by exact Pelagos evidence.');
    await page.click('#saveAdmission');
    await page.waitForFunction(() => !!window.__PELAGOS_TEST__.workspaceAdmission());
    const admitted = await page.evaluate(() => window.__PELAGOS_TEST__.workspaceAdmission());
    assert.equal(admitted.custodian, 'Samuel Scrivens');
    assert.equal(admitted.decision_owner, 'Samuel Scrivens');

    // Evidence stays local, hashes correctly, and refuses duplicate bytes.
    await page.click('button[data-view="evidence"]');
    const evidence = Buffer.from('Pelagos private test evidence\nconfiguration: Vantage V0\n', 'utf8');
    await page.setInputFiles('#sourceFiles', { name: 'test-evidence.txt', mimeType: 'text/plain', buffer: evidence });
    await page.waitForFunction(() => window.__PELAGOS_TEST__.workspace.source_receipts.length === 1);
    const firstSource = await page.evaluate(() => window.__PELAGOS_TEST__.workspace.source_receipts[0]);
    assert.equal(firstSource.network_transmitted, false);
    assert.equal(firstSource.source_bytes_retained, false);
    assert.equal(firstSource.sha256.length, 64);
    await page.setInputFiles('#sourceFiles', { name: 'duplicate-name.txt', mimeType: 'text/plain', buffer: evidence });
    await page.waitForFunction(() => window.__PELAGOS_TEST__.workspace.receipts.some(r => r.kind === 'source_duplicate_refused'));
    assert.equal(await page.evaluate(() => window.__PELAGOS_TEST__.workspace.source_receipts.length), 1);

    // Create an authority-attributed object, then append a successor state.
    await page.click('button[data-view="docket"]');
    await page.click('#addIntake');
    await page.selectOption('#intakeForm [name="object_type"]', { label: 'In-kind Contribution' });
    await page.fill('#intakeForm [name="counterparty"]', 'Test Strategic Foundry');
    await page.fill('#intakeForm [name="summary"]', 'Factory offers prototype capacity in exchange for rights still to be resolved.');
    await page.selectOption('#intakeForm [name="state"]', { label: 'Offered' });
    await page.fill('#intakeForm [name="offered"]', 'Prototype tooling and line time');
    await page.fill('#intakeForm [name="requested"]', 'Public attribution and preferred manufacturing status');
    await page.fill('#intakeForm [name="consideration"]', 'Unknown valuation and ongoing engineering burden');
    await page.fill('#intakeForm [name="rights"]', 'Exclusivity, tooling ownership and exit remain open');
    await page.fill('#intakeForm [name="authority"]', 'CEO internal operating authority');
    await page.check('#intakeForm input[name="source_receipt_ids"]');
    await page.click('#saveIntake');
    await page.waitForFunction(() => window.__PELAGOS_TEST__.effectiveIntake().length === 1);
    let localObject = await page.evaluate(() => window.__PELAGOS_TEST__.effectiveIntake()[0]);
    assert.equal(localObject.record_state, 'authority-attributed');
    assert.equal(localObject.state, 'Offered');

    await page.click('button[data-sub="intake"]');
    await page.click('[data-edit-intake="INT-LOCAL-0001"]');
    await page.selectOption('#intakeForm [name="state"]', { label: 'Negotiating' });
    await page.fill('#intakeForm [name="summary"]', 'Successor state: negotiating bounded pilot capacity; no exclusivity accepted.');
    await page.click('#saveIntake');
    await page.waitForFunction(() => window.__PELAGOS_TEST__.workspace.intake.length === 2);
    const successor = await page.evaluate(() => ({
      effective: window.__PELAGOS_TEST__.effectiveIntake(),
      all: window.__PELAGOS_TEST__.workspace.intake,
    }));
    assert.equal(successor.effective.length, 1);
    assert.equal(successor.effective[0].id, 'INT-LOCAL-0002');
    assert.equal(successor.effective[0].supersedes, 'INT-LOCAL-0001');
    assert.equal(successor.all[0].state, 'Offered');
    assert.equal(successor.all[1].state, 'Negotiating');

    // A requested authority-attributed decision without authority must stay draft.
    await page.click('button[data-view="decisions"]');
    await page.click('[data-open-decision="EX-001"]');
    await page.selectOption('#decisionForm [name="record_state"]', 'recorded');
    await page.fill('#decisionForm [name="rationale"]', 'Hold until exact legal entities and signing thresholds are attached.');
    await page.click('#saveDecision');
    await page.waitForFunction(() => window.__PELAGOS_TEST__.workspace.decisions.length === 1);
    assert.equal(await page.evaluate(() => window.__PELAGOS_TEST__.workspace.decisions[0].record_state), 'draft');

    // With a named authority source the successor decision may be recorded.
    await page.click('[data-open-decision="EX-001"]');
    await page.selectOption('#decisionForm [name="record_state"]', 'recorded');
    await page.fill('#decisionForm [name="rationale"]', 'Samuel confirms the current operating entity and retains a separate legal-entity schedule for each binding instrument.');
    await page.fill('#decisionForm [name="authority_source"]', 'CEO internal entity and signing authority schedule');
    await page.fill('#decisionForm [name="evidence_ids"]', firstSource.id);
    await page.click('#saveDecision');
    await page.waitForFunction(() => window.__PELAGOS_TEST__.workspace.decisions.length === 2);
    assert.equal(await page.evaluate(() => window.__PELAGOS_TEST__.workspace.decisions.at(-1).record_state), 'recorded');

    // A public claim correction appends and retains the prior value.
    await page.click('button[data-view="claims"]');
    await page.click('[data-correct-claim="CL-002"]');
    await page.fill('#correctionForm [name="proposed_value"]', 'Vantage V0 has completed a bounded untethered salt-water platform test; deploy-anywhere remains a product objective.');
    await page.fill('#correctionForm [name="rationale"]', 'Align claim language to current evidence state and retain superseded version.');
    await page.fill('#correctionForm [name="evidence_ids"]', 'EV-005');
    await page.fill('#correctionForm [name="authority_source"]', 'Communications owner review');
    await page.click('#saveCorrection');
    await page.waitForFunction(() => window.__PELAGOS_TEST__.workspace.corrections.length === 1);
    const correction = await page.evaluate(() => window.__PELAGOS_TEST__.workspace.corrections[0]);
    assert.ok(correction.prior_value);
    assert.equal(correction.supersedes, null);

    // Stress, encryption, ledger and cold replay operate against live workspace state.
    await page.click('button[data-view="stress"]');
    await page.click('#runStress');
    await page.waitForFunction(() => window.__PELAGOS_TEST__.workspace.stress_runs.length === 1);
    assert.equal(await page.evaluate(() => window.__PELAGOS_TEST__.workspace.stress_runs[0].results.length), 10);

    const cryptoResult = await page.evaluate(async () => {
      const t = window.__PELAGOS_TEST__;
      const envelope = await t.encryptWorkspace('test-only-passphrase');
      const restored = await t.decryptWorkspace(envelope, 'test-only-passphrase');
      const ledger = await t.verifyReceipts();
      const replay = await t.coldReplay();
      return {
        schema: envelope.schema,
        iterations: envelope.iterations,
        restoredSchema: restored.schema,
        restoredIntake: restored.intake.length,
        ledger,
        replay,
      };
    });
    assert.equal(cryptoResult.schema, 'ddv/pelagos-governance-encrypted-backup@1');
    assert.equal(cryptoResult.iterations, 250000);
    assert.equal(cryptoResult.restoredSchema, 'ddv/pelagos-governance-workspace@3');
    assert.equal(cryptoResult.restoredIntake, 2);
    assert.equal(cryptoResult.ledger.ok, true);
    assert.equal(cryptoResult.replay.checks.find(x => x[0] === 'Pelagos working copy admitted')[1], true);
    assert.equal(cryptoResult.replay.checks.find(x => x[0] === 'Legal entity and signer authority resolved')[1], true);

    // Full workspace export uses current release identity.
    await page.click('button[data-view="handoff"]');
    const downloadPromise = page.waitForEvent('download');
    await page.click('[data-export="full"]');
    const exportDownload = await downloadPromise;
    assert.equal(exportDownload.suggestedFilename(), 'DDV-PEL-003-full-workspace.json');

    // Mobile and reduced-motion contract.
    await page.setViewportSize({ width: 320, height: 900 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert.ok(overflow <= 1, `mobile horizontal overflow: ${overflow}`);
    assert.equal(await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches), false);

    assert.deepEqual(monitorState.external, []);
    assert.deepEqual(monitorState.pageErrors, []);
    const materialErrors = monitorState.consoleErrors.filter(x => !/favicon/i.test(x));
    assert.deepEqual(materialErrors, []);
    await context.close();

    const reduced = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 800, height: 800 } });
    const reducedPage = await reduced.newPage();
    const reducedMonitor = monitor(reducedPage, origin);
    await reducedPage.goto(`${origin}/pelagos-governance/`, { waitUntil: 'networkidle' });
    await reducedPage.waitForFunction(() => document.body.dataset.ready === 'pass');
    assert.equal(await reducedPage.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches), true);
    assert.deepEqual(reducedMonitor.external, []);
    assert.deepEqual(reducedMonitor.pageErrors, []);
    await reduced.close();

    // The private-use standalone is self-contained and boots without subresource requests.
    const offline = await browser.newContext({ viewport: { width: 1000, height: 900 } });
    const offlinePage = await offline.newPage();
    const offlineMonitor = monitor(offlinePage, origin);
    await offlinePage.goto(`${origin}/pelagos-governance/standalone.html`, { waitUntil: 'networkidle' });
    await offlinePage.waitForFunction(() => document.body.dataset.ready === 'pass');
    assert.match(await offlinePage.title(), /Standalone/);
    assert.equal(await offlinePage.evaluate(() => window.__PELAGOS_TEST__.PUBLIC.meta.artifact_id), 'DDV-PEL-003');
    assert.equal(await offlinePage.evaluate(() => window.__PELAGOS_TEST__.runtimeHealth().unexpected_resources.length), 0);
    assert.deepEqual(offlineMonitor.external, []);
    assert.deepEqual(offlineMonitor.pageErrors, []);
    await offline.close();

    console.log('PASS 18/18 browser qualification campaigns');
  } finally {
    await browser.close();
    server.kill('SIGTERM');
    await new Promise(resolve => server.once('exit', resolve));
    if (serverErr && !/Serving HTTP/.test(serverErr)) process.stderr.write(serverErr);
  }
}

main().catch(err => {
  console.error(err.stack || err);
  process.exit(1);
});
