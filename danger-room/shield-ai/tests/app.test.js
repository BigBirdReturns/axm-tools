/* Browser-free acceptance checks: local-file crypto fallback, portability and admission safety. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createHash} = require('node:crypto');
const root = path.resolve(__dirname, '..');
function browser(saved = null) {
  const elements = new Map();
  const element = selector => {
    if (!elements.has(selector)) elements.set(selector, {
      textContent: '', innerHTML: '', dataset: {}, listeners: {},
      addEventListener(type, handler) { this.listeners[type] = handler; },
      showModal() { this.open = true; }, close() { this.open = false; }
    });
    return elements.get(selector);
  };
  const storage = new Map(saved ? [['ddv-sim-v1', saved]] : []);
  const context = vm.createContext({
    console, TextEncoder, Uint8Array, DataView, URL, Blob,
    crypto: undefined, // HTTP previews and file:// must retain the same integrity gate.
    document: {querySelector: element, addEventListener() {}, documentElement: {dataset: {}}},
    localStorage: {getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value)},
    setTimeout() {}, clearTimeout() {}, setInterval() {}, clearInterval() {}
  });
  for (const file of ['data.js', 'recorded.js', 'engine.js', 'business.js', 'capture.js', 'app.js']) {
    vm.runInContext(fs.readFileSync(path.join(root, file), 'utf8'), context, {filename: file});
  }
  return {context, element, storage};
}
const copy = value => JSON.parse(JSON.stringify(value));
async function settleRestore(app) {
  for (let i = 0; i < 100; i++) {
    await new Promise(resolve => setImmediate(resolve));
    if (app.context.SDApp.getState().quality.accepted) return;
  }
  throw new Error('Saved valid acceptance did not restore.');
}
(async () => {
  const app = browser(), {SimEngine: engine, SDApp: api} = app.context;
  for (const value of ['', 'abc', 'The quick brown fox jumps over the lazy dog', '中文 🦅 café', 'a'.repeat(56), 'a'.repeat(1000)]) {
    const record = {value};
    await engine.seal(record);
    const expected = createHash('sha256').update(engine.canonical({value}), 'utf8').digest('hex');
    assert.equal(record.integrity.digest, expected, 'Fallback must match Node SHA-256 on canonical UTF-8 bytes.');
    assert.equal(await engine.verify(record), true);
  }
  for (const view of ['today', 'accounts', 'integration', 'people', 'product', 'room', 'school', 'review', 'evidence']) {
    await api.dispatch('navigate', view);
    assert.ok(app.element('#view').innerHTML.length > 500, view + ' must render.');
  }
  await api.workingDay();
  const state = api.getState();
  assert.equal(state.quality.accepted.scope, 'timing');
  assert.equal(state.quality.runs.length, 11);
  assert.equal(state.opportunities.find(o => o.id === 'OP-103').customerAcceptance, false);
  assert.equal(app.context.SDModel.metrics(state).commit, 0, 'Technical readiness cannot imply buyer acceptance.');
  const portable = copy(state);
  assert.ok(await api.validateAcceptedState(portable));
  const altered = copy(portable);
  altered.quality.runs[1].metrics.maxError = 0;
  await engine.seal(altered.quality.runs[1]);
  await assert.rejects(api.validateAcceptedState(altered), /differs from deterministic replay/);
  assert.equal(api.getState().quality.accepted.suiteId, portable.quality.accepted.suiteId, 'Failed verification must not mutate active state.');
  const incomplete = copy(portable);
  incomplete.quality.suites[0].runIds.pop();
  await assert.rejects(api.validateAcceptedState(incomplete), /complete fixed fresh-seed/);
  const missingRegression = copy(portable);
  missingRegression.quality.suites[0].regressionRunIds = [];
  await assert.rejects(api.validateAcceptedState(missingRegression), /curriculum regressions are incomplete/);
  const restored = browser(JSON.stringify(portable));
  assert.equal(restored.context.SDApp.getState().quality.accepted, null, 'Boot must block admission while verification is pending.');
  await settleRestore(restored);
  assert.equal(restored.context.SDApp.getState().quality.accepted.suiteId, portable.quality.accepted.suiteId);
  // Import through the real file-handler path, including rejection without active-state replacement.
  const importHandler = restored.element('#import-file').listeners.change;
  await importHandler({target: {files: [{name: 'valid.json', size: 100, text: async () => JSON.stringify(portable)}], value: 'valid.json'}});
  assert.equal(restored.context.SDApp.getState().quality.accepted.suiteId, portable.quality.accepted.suiteId);
  const original = restored.context.SDApp.getState();
  await importHandler({target: {files: [{name: 'tampered.json', size: 100, text: async () => JSON.stringify(altered)}], value: 'tampered.json'}});
  assert.equal(restored.context.SDApp.getState(), original, 'Bad import must preserve the original workspace object.');
  assert.match(restored.element('#dialog-body').innerHTML, /differs from deterministic replay/);
  state.quality.requiredScope = 'expanded';
  await api.suite();
  await assert.rejects(api.accept(), /failed cases/);
  assert.equal(state.quality.accepted, null);
  await api.dispatch('camera-example');
  assert.ok(app.element('#view').innerHTML.length > 500);
  console.log('PASS: SHA-256 fallback vectors, nine views, no-crypto working day, commercial gate, exact suite/regressions, portable reload/import, rehashed tamper rejection, and expanded-scope rejection.');
})().catch(error => { console.error(error); process.exitCode = 1; });
