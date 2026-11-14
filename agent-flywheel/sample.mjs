import {parseEvidence} from './engine.mjs';

const baselinePrompt = 'Route invoice, billing, charge, and payment questions to billing. Route sign-in, password reset, errors, crashes, and upload failures to technical. Route everything else to general. Use normal priority. Return only JSON with queue and priority.';
const strongPrompt = 'Check security-sensitive requests before general sign-in troubleshooting or billing keywords. Unauthorized access, an unknown device, exposed API tokens or secrets, leaked credentials, and account takeover require queue security and priority urgent. Otherwise route invoices, billing, charges, or payments to billing; sign-in failures, password resets, errors, crashes, or uploads to technical; other questions to general. Non-security requests have priority normal. Return only JSON with queue and priority.';
const partialPrompt = 'Check exposed secrets first: publicly exposed API tokens or secrets require queue security and priority urgent. Otherwise route invoices, billing, charges, or payments to billing; sign-in, password reset, errors, crashes, or uploads to technical; everything else to general. Use normal priority except exposed secrets. Return only JSON with queue and priority.';
const record = (id, split, input, queue, priority = 'normal') => ({id, split, input, expected: {queue, priority}});
const records = [
  record('dev-invoice', 'development', 'My monthly invoice shows a double charge.', 'billing'),
  record('dev-signin', 'development', 'I cannot sign in after a password reset.', 'technical'),
  record('dev-account', 'development', 'Someone accessed my account and changed my billing details.', 'security', 'urgent'),
  record('dev-token', 'development', 'An API token was pasted into a public support thread.', 'security', 'urgent'),
  record('dev-contact', 'development', 'Please change the invoice contact for our company.', 'billing'),
  record('dev-profile', 'development', 'How do I change my display name?', 'general'),
  record('hold-device', 'heldout', 'An unknown device signed in and sent a payment to a new account.', 'security', 'urgent'),
  record('hold-secret', 'heldout', 'Our API secret appeared in a public git repository.', 'security', 'urgent'),
  record('hold-invoice', 'heldout', 'I need a copy of the June invoice.', 'billing'),
  record('hold-upload', 'heldout', 'The upload freezes at 99 percent.', 'technical'),
  record('reg-invoice', 'regression', 'How can I download an invoice?', 'billing'),
  record('reg-crash', 'regression', 'The app crashes while uploading a file.', 'technical'),
];
const evidenceText = JSON.stringify(records, null, 2);
export const SAMPLE_CONFIG = Object.freeze({
  goal: 'Improve support-ticket routing while preserving ordinary billing and technical routes.',
  taskContract: 'Return a JSON object with queue (billing, technical, security, or general) and priority (normal or urgent). Security-sensitive access or credential exposure requires security/urgent, even when billing or technical words also appear.',
  baselinePrompt, mode: 'improve', metric: 'json', candidateLimit: 2, caseLimit: 12, maxCalls: 40, seed: 17,
  evidence: parseEvidence(evidenceText, 'synthetic-support-routing.json'), evidenceText,
  provenance: 'Synthetic support-routing example; no customer records.',
});

/** Explicit offline demonstration. No external model or endpoint is contacted. */
export function createDemoClient() {
  const metadata = Object.freeze({provider: 'demo', model: 'deterministic-demonstration-adapter', effort: 'none', maxTokens: 0,
    demonstration: true, description: 'Deterministic support-routing demonstration; not an external language model.'});
  return {metadata, async complete({messages, stage, signal}) {
    if (signal?.aborted) throw Object.assign(new Error('Demonstration cancelled'), {code: 'CANCELLED'});
    const start = performance.now(); let text;
    if (stage === 'diagnose') {
      const payload = JSON.parse(messages.find(m => m.role === 'user').content);
      const ids = payload.development_sources.filter(s => /accessed|token|secret/i.test(JSON.stringify(s.input ?? s.raw ?? s.text ?? ''))).map(s => s.id);
      const candidates = [{id: 'security-first', prompt: strongPrompt, rationale: 'Apply the declared security precedence before keyword-based billing and technical routing.'},
        {id: 'exposed-secrets-first', prompt: partialPrompt, rationale: 'Test a narrower fix for exposed credentials while retaining the original access routing.'}].slice(0, payload.candidate_limit);
      text = JSON.stringify({summary: 'The demonstration baseline routes by surface keywords and defaults to normal priority. The supplied development cases support testing security precedence and urgent handling before ordinary routing.',
        findings: [{title: 'Security precedence is missing', detail: 'Access compromise and public credential exposure can be routed as ordinary billing or general questions by the baseline instructions.', evidence_ids: ids}],
        hypotheses: [{id: 'H1', statement: 'Security-first routing will correct the development access/exposure failures.', test: 'Compare a complete precedence rule with a narrower exposed-secret rule using the fixed references.', expected_effect: 'Higher reference correctness, with ordinary billing and technical routes preserved.'}],
        candidates, proposed_tests: [{input: 'A leaked credential was used to change a payment method.', expected: {queue: 'security', priority: 'urgent'}, rationale: 'A combined access and billing case probes rule precedence; this proposed answer remains separate from supplied labels.'}]});
    } else {
      const instructions = messages.find(m => m.role === 'system').content.split('AGENT INSTRUCTIONS\n')[1] || '';
      const input = messages.filter(m => m.role === 'user').map(m => m.content).join('\n');
      const exposure = /(?:token|secret|credential).*(?:public|expos|leak)|(?:expos|leak).*(?:token|secret|credential)/i.test(input);
      const access = /someone accessed|unknown device|unauthori[sz]ed|account takeover|compromis/i.test(input);
      const full = instructions.includes('Check security-sensitive requests before');
      const narrow = instructions.includes('Check exposed secrets first');
      let queue = 'general', priority = 'normal';
      if ((full && (exposure || access)) || (narrow && exposure)) { queue = 'security'; priority = 'urgent'; }
      else if (/invoice|billing|charge|payment/i.test(input)) queue = 'billing';
      else if (/sign[ -]?in|password reset|error|crash|upload/i.test(input)) queue = 'technical';
      text = JSON.stringify({queue, priority});
    }
    return {text, model: metadata.model, usage: null, finishReason: 'stop', elapsedMs: performance.now() - start, endpointOrigin: null};
  }};
}
