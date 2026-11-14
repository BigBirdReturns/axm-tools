import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {parseEvidence, mergeEvidence, summarizeEvidence, prepareWork, buildHandoff, runResearch, verifyReport, canonical, estimateCalls} from '../engine.mjs';
import {SAMPLE_CONFIG, createDemoClient} from '../sample.mjs';

const copy = value => JSON.parse(JSON.stringify(value));
function resign(report) {
  const body = copy(report); delete body.manifest.sha256;
  report.manifest.sha256 = createHash('sha256').update(canonical(body)).digest('hex');
  return report;
}
const genericRecords = [
  {id: 'd-urgent', split: 'development', input: 'urgent request', expected: 'YES'},
  {id: 'd-normal', split: 'development', input: 'routine request', expected: 'NO'},
  {id: 'h-urgent', split: 'heldout', input: 'HELDOUT-ONLY-SECRET urgent request', expected: 'YES'},
  {id: 'h-normal', split: 'heldout', input: 'HELDOUT-SECOND-SENTINEL ordinary request', expected: 'NO'},
  {id: 'r-normal', split: 'regression', input: 'REGRESSION-ONLY-SENTINEL routine request', expected: 'NO'},
];
function genericConfig(overrides = {}) {
  return {goal: 'Improve the visitor-provided urgent-request classifier.', taskContract: 'Return YES if the input contains the word urgent, otherwise NO.',
    baselinePrompt: 'Always return NO.', evidence: parseEvidence(JSON.stringify(genericRecords), 'own-cases.json'), mode: 'improve', metric: 'exact',
    candidateLimit: 2, caseLimit: 12, maxCalls: 40, seed: 17, ...overrides};
}
function genericClient({calls = [], proposal, onCall} = {}) {
  return {metadata: {provider: 'test', model: 'test-prompt-executor', effort: 'fixed', maxTokens: 1000}, async complete(request) {
    calls.push(copy({...request, signal: undefined})); onCall?.(request, calls.length);
    if (request.signal?.aborted) throw Object.assign(new Error('Cancelled'), {code: 'CANCELLED'});
    const payload = request.stage === 'diagnose' ? JSON.parse(request.messages[1].content) : null;
    const text = request.stage === 'diagnose' ? JSON.stringify(proposal || {
      summary: 'The development urgent request contradicts the constant-NO baseline.',
      findings: [{title: 'Constant response misses an urgent case', detail: 'Test an input-dependent decision rule.', evidence_ids: [payload.development_sources[0].id]}],
      hypotheses: [{id: 'H1', statement: 'An urgent-sensitive instruction improves the declared classification task.', test: 'Compare against supplied reference answers.', expected_effect: 'One additional development pass.'}],
      candidates: [{id: 'urgent-sensitive', prompt: 'Return YES exactly when the input contains the word urgent; otherwise return NO.', rationale: 'Implement the visitor task contract.'}],
      proposed_tests: [{input: 'urgent new suggested case', expected: 'YES', rationale: 'A proposed test remains unadmitted.'}],
    }) : (/Return YES exactly/.test(request.messages[0].content.split('AGENT INSTRUCTIONS\n')[1]) && /\burgent\b/.test(request.messages[1].content) ? 'YES' : 'NO');
    return {text, model: 'test-prompt-executor', usage: {input_tokens: 10, output_tokens: 5}, finishReason: 'stop', elapsedMs: 0.1, endpointOrigin: null};
  }};
}

test('JSON, JSONL, CSV, prose and native traces preserve evidence without inventing labels', () => {
  const json = parseEvidence('[{"id":"a","question":"Question","reference":"Answer","response":"Old","feedback":"wrong"}]', 'a.json');
  assert.equal(json.records[0].input, 'Question'); assert.equal(json.records[0].expected, 'Answer'); assert.equal(json.records[0].raw.response, 'Old');
  const lines = parseEvidence('{"id":"b","prompt":"One"}\n{"id":"c","input":"Two","expected_output":null}', 'b.jsonl');
  assert.equal(lines.records[0].has_expected, false); assert.equal(lines.records[1].has_expected, true);
  const csv = parseEvidence('id,input,expected,split\nx,"Hello, visitor","A ""quoted"" reply",development\n', 'cases.csv');
  assert.equal(csv.records[0].input, 'Hello, visitor'); assert.equal(csv.records[0].expected, 'A "quoted" reply');
  const prose = parseEvidence('Our agent loses customer context after a tool timeout.');
  assert.equal(prose.documents.length, 1); assert.equal(summarizeEvidence(prose).labeled, 0);
  const native = parseEvidence('{"info":{"trace_id":"mlflow-1"},"data":{"spans":[{"name":"tool"}]}}', 'trace.json');
  assert.equal(native.records[0].has_input, false); assert.deepEqual(native.records[0].raw.data.spans, [{name: 'tool'}]);
});

test('conflicting duplicate IDs and malformed CSV fail explicitly', () => {
  const one = parseEvidence('[{"id":"same","input":"one"}]'), two = parseEvidence('[{"id":"same","input":"two"}]');
  assert.throws(() => mergeEvidence([one, two]), /Conflicting duplicate/);
  assert.equal(mergeEvidence([one, one]).records.length, 1);
  assert.throws(() => parseEvidence('id,input\nx,"unfinished', 'broken.csv'), /unterminated/);
});

test('visitor task runs actual prompt candidates through the supplied client', async () => {
  const calls = [], work = await prepareWork(genericConfig()), report = await runResearch(work, {client: genericClient({calls})});
  assert.equal(report.verdict, 'QUALIFIED'); assert.equal(report.metrics.baseline_passed, 1); assert.equal(report.metrics.candidate_passed, 2);
  assert.equal(report.metrics.total, 2); assert.equal(report.metrics.calls, calls.length); assert.equal(report.metrics.regressions, 0);
  assert.equal(report.metrics.calls, 11); assert.equal(report.candidates[0].selected, true);
  assert.deepEqual(await verifyReport(report), {valid: true, errors: []});
  assert.equal(work.plannedCalls, estimateCalls(work));
});

test('diagnosis and handoff exclude held-out and regression inputs and references', async () => {
  const calls = [], work = await prepareWork(genericConfig());
  const handoff = buildHandoff(work);
  assert.ok(!handoff.includes('HELDOUT-ONLY-SECRET')); assert.ok(!handoff.includes('REGRESSION-ONLY-SENTINEL'));
  const report = await runResearch(work, {client: genericClient({calls})});
  assert.ok(!JSON.stringify(calls[0]).includes('HELDOUT-ONLY-SECRET')); assert.ok(!JSON.stringify(calls[0]).includes('REGRESSION-ONLY-SENTINEL'));
  const selection = report.provenance.selection;
  assert.ok(report.receipts.filter(r => r.stage === 'heldout' || r.stage === 'regression').every(r => r.sequence >= selection.after_call));
  const latest = new Map(report.events.map(e => [e.id, e.status]));
  for (const id of ['development', 'heldout', 'regression']) assert.equal(latest.get(id), 'completed');
});

test('example client is explicitly deterministic and changed visitor input changes observed results', async () => {
  const first = await runResearch(await prepareWork(SAMPLE_CONFIG), {client: createDemoClient()});
  const records = JSON.parse(SAMPLE_CONFIG.evidenceText);
  const changed = records.find(r => r.id === 'hold-device'); changed.input = 'I need the invoice for our account.'; changed.expected = {queue: 'billing', priority: 'normal'};
  const work = await prepareWork({...SAMPLE_CONFIG, evidence: parseEvidence(JSON.stringify(records), 'changed.json')});
  const second = await runResearch(work, {client: createDemoClient()});
  assert.equal(first.metrics.baseline_passed, 2); assert.equal(second.metrics.baseline_passed, 3);
  assert.notEqual(first.work.integrity.sha256, second.work.integrity.sha256); assert.notEqual(first.metrics.delta, second.metrics.delta);
  assert.equal(second.provenance.model.demonstration, true); assert.equal(second.provenance.model.model, 'deterministic-demonstration-adapter');
  assert.equal((await verifyReport(second)).valid, true);
});

test('work packets reconstruct deterministically and reject modified splits or cross-split duplicates', async () => {
  const work = await prepareWork(genericConfig());
  assert.deepEqual(await prepareWork(copy(work)), work); assert.ok(Object.isFrozen(work.evidence.records));
  const altered = copy(work); altered.splits.heldout[0] = altered.splits.development[0];
  await assert.rejects(prepareWork(altered), /reconstructed/);
  const duplicate = copy(genericRecords); duplicate[2].input = duplicate[0].input;
  await assert.rejects(prepareWork(genericConfig({evidence: parseEvidence(JSON.stringify(duplicate))})), /Cross-split duplicate/);
});

test('held-out evidence citations are rejected before candidate execution', async () => {
  const proposal = {summary: 'Invalid citation', findings: [{title: 'Bad', detail: 'This should fail', evidence_ids: ['h-urgent']}], hypotheses: [], candidates: [], proposed_tests: []};
  const report = await runResearch(await prepareWork(genericConfig()), {client: genericClient({proposal})});
  assert.equal(report.status, 'failed'); assert.equal(report.verdict, 'INCOMPLETE'); assert.equal(report.receipts.length, 1);
  assert.match(report.summary, /held-out evidence ID/); assert.equal((await verifyReport(report)).valid, true);
});

test('budget preflight retains diagnosis and stops before starting an unfunded experiment', async () => {
  const calls = [], report = await runResearch(await prepareWork(genericConfig({maxCalls: 5})), {client: genericClient({calls})});
  assert.equal(report.status, 'stopped'); assert.equal(report.verdict, 'INCOMPLETE'); assert.equal(calls.length, 1);
  assert.ok(report.analysis); assert.equal(report.cases.length, 0); assert.equal(report.provenance.terminal_error.code, 'BUDGET');
  assert.equal((await verifyReport(report)).valid, true);
});

test('cancellation retains attempted calls and prevents subsequent model requests', async () => {
  const controller = new AbortController(), calls = [];
  const report = await runResearch(await prepareWork(genericConfig()), {signal: controller.signal,
    client: genericClient({calls, onCall: (_, count) => { if (count === 3) controller.abort(); }})});
  assert.equal(report.status, 'stopped'); assert.equal(report.verdict, 'INCOMPLETE'); assert.equal(calls.length, 3); assert.equal(report.receipts.length, 3);
  assert.equal(report.receipts.at(-1).status, 'cancelled'); assert.equal((await verifyReport(report)).valid, true);
});

test('unlabeled visitor prose yields useful diagnosis and explicitly needs evaluation for improvement', async () => {
  const evidence = parseEvidence('We lose context after a tool timeout and need an experiment design.');
  const proposal = {summary: 'Inspect timeout recovery and retained task context.', findings: [{title: 'Reported timeout failure', detail: 'This is a reported observation, not a measured benchmark.', evidence_ids: [evidence.documents[0].id]}],
    hypotheses: [{id: 'H1', statement: 'Checkpoint task context before tools.', test: 'Inject a timeout with a known expected outcome.', expected_effect: 'Resume the pending task.'}], candidates: [], proposed_tests: [{input: 'Simulated timeout', expected: 'resume', rationale: 'Needs supplied labels before scoring.'}]};
  for (const mode of ['diagnose', 'improve']) {
    const report = await runResearch(await prepareWork(genericConfig({evidence, mode})), {client: genericClient({proposal})});
    assert.equal(report.verdict, mode === 'diagnose' ? 'DIAGNOSED' : 'NEEDS_EVALUATION'); assert.equal(report.metrics.total, null);
    assert.equal(report.receipts.length, 1); assert.equal(report.analysis.proposed_tests[0].evidence_status, 'model-proposed; not admitted as a supplied label');
    assert.equal((await verifyReport(report)).valid, true);
  }
});

test('tampered report bytes fail their canonical digest', async () => {
  const report = await runResearch(await prepareWork(genericConfig()), {client: genericClient()});
  report.summary += ' altered';
  const result = await verifyReport(report); assert.equal(result.valid, false); assert.ok(result.errors.includes('Report digest mismatch'));
});

test('rehashed false metrics still fail independent receipt/reference recomputation', async () => {
  const report = await runResearch(await prepareWork(genericConfig()), {client: genericClient()});
  report.metrics.baseline_passed = 0; report.metrics.delta = 1; resign(report);
  const result = await verifyReport(report); assert.equal(result.valid, false); assert.ok(result.errors.includes('False metric: baseline_passed'));
});

test('rehashed altered reference or false pass flag still fails', async () => {
  const original = await runResearch(await prepareWork(genericConfig()), {client: genericClient()});
  const changed = copy(original); changed.cases.find(c => c.split === 'heldout').expected = 'DIFFERENT'; resign(changed);
  assert.ok((await verifyReport(changed)).errors.includes('Case input or reference changed'));
  const flag = copy(original); flag.cases.find(c => c.split === 'heldout').candidate_passed = false; resign(flag);
  assert.ok((await verifyReport(flag)).errors.includes('Case pass flag disagrees with the reference comparator'));
});

test('an already competent baseline remains selected on development ties', async () => {
  const initial = await runResearch(await prepareWork(SAMPLE_CONFIG), {client: createDemoClient()});
  const prompt = initial.candidates.find(c => c.selected).prompt;
  const report = await runResearch(await prepareWork({...SAMPLE_CONFIG, baselinePrompt: prompt}), {client: createDemoClient()});
  assert.equal(report.verdict, 'NO_CHANGE'); assert.equal(report.provenance.selection.candidate_id, 'baseline');
  assert.equal(report.metrics.delta, 0); assert.equal(report.candidates.length, 1); // Identical baseline proposal excluded from experiments.
  assert.equal((await verifyReport(report)).valid, true);
});

test('a response model change fails instead of mixing models in an improvement claim', async () => {
  const underlying = genericClient(); let count = 0;
  const client = {metadata: underlying.metadata, async complete(request) { const response = await underlying.complete(request); if (++count > 1) response.model = 'different-model'; return response; }};
  const report = await runResearch(await prepareWork(genericConfig()), {client});
  assert.equal(report.status, 'failed'); assert.equal(report.verdict, 'INCOMPLETE'); assert.equal(report.provenance.terminal_error.code, 'MODEL_CHANGED');
  assert.equal(report.metrics.calls, 2); assert.equal((await verifyReport(report)).valid, true);
});
