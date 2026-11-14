import assert from 'node:assert/strict';
import test from 'node:test';
import {createClient, PROVIDER_PRESETS, ProviderError} from '../providers.mjs';

const secret = 'private-test-key-never-retain';
const messages = [{role: 'user', content: 'Analyze the supplied development evidence.'}];
const preset = id => PROVIDER_PRESETS.find(item => item.id === id);
const result = (overrides = {}) => new Response(JSON.stringify({
  model: 'provider/reported-model',
  choices: [{message: {content: '{"summary":"Measured response"}'}, finish_reason: 'stop'}],
  usage: {prompt_tokens: 10, completion_tokens: 20, total_tokens: 30, cost: 0.001, completion_tokens_details: {reasoning_tokens: 12}},
  ...overrides,
}), {headers: {'Content-Type': 'application/json'}});
const rejects = (promise, code) => assert.rejects(promise, error => error instanceof ProviderError && error.code === code && !JSON.stringify(error).includes(secret) && !error.message.includes(secret));

test('presets are explicit, immutable and current; client construction performs no calls', () => {
  assert.deepEqual(PROVIDER_PRESETS.map(item => item.id), ['sonnet', 'flash', 'local', 'custom']);
  assert.equal(preset('sonnet').model, 'anthropic/claude-sonnet-5.5');
  assert.equal(preset('flash').model, 'google/gemini-3.8-flash');
  assert.equal(preset('local').model, 'qwen3.8:27b');
  assert.equal(preset('sonnet').temperature, undefined);
  assert.ok(Object.isFrozen(PROVIDER_PRESETS) && PROVIDER_PRESETS.every(Object.isFrozen));
  let calls = 0;
  const client = createClient({...preset('sonnet'), apiKey: secret}, {fetchImpl: () => { calls++; }});
  assert.equal(calls, 0);
  assert.equal(client.metadata.endpointOrigin, 'https://openrouter.ai');
  assert.ok(Object.isFrozen(client.metadata));
  assert.ok(!JSON.stringify(client).includes(secret));
});

test('Sonnet request uses effort and bounded output without incompatible sampling', async () => {
  const seen = [];
  const client = createClient({...preset('sonnet'), apiKey: secret}, {fetchImpl: async (...args) => { seen.push(args); return result(); }});
  const reply = await client.complete({messages, stage: 'diagnose', jsonMode: true});
  assert.equal(seen.length, 1);
  const [url, options] = seen[0];
  assert.equal(url, 'https://openrouter.ai/api/v1/chat/completions');
  assert.equal(options.headers.Authorization, `Bearer ${secret}`);
  assert.equal(options.redirect, 'error');
  assert.equal(options.credentials, 'omit');
  assert.equal(options.mode, 'cors');
  const body = JSON.parse(options.body);
  assert.deepEqual(body.reasoning, {effort: 'high', exclude: true});
  assert.deepEqual(body.response_format, {type: 'json_object'});
  assert.equal(body.max_tokens, 16384);
  assert.equal(body.temperature, undefined);
  assert.equal(body.top_p, undefined);
  assert.ok(!options.body.includes(secret));
  assert.equal(reply.model, 'provider/reported-model');
  assert.equal(reply.finishReason, 'stop');
  assert.deepEqual(reply.usage, {prompt_tokens: 10, completion_tokens: 20, total_tokens: 30, cost: 0.001, completion_tokens_details: {reasoning_tokens: 12}});
  assert.ok(reply.elapsedMs >= 0);
  assert.ok(!JSON.stringify(reply).includes(secret));
});

test('Flash and local presets preserve their own request contracts', async () => {
  const calls = [];
  for (const id of ['flash', 'local']) {
    const client = createClient({...preset(id), ...(id === 'flash' ? {apiKey: secret} : {})}, {fetchImpl: async (url, options) => { calls.push({url, options, body: JSON.parse(options.body)}); return result(); }});
    await client.complete({messages});
  }
  assert.deepEqual(calls[0].body.reasoning, {effort: 'medium', exclude: true});
  assert.equal(calls[0].body.max_tokens, 8192);
  assert.equal(calls[0].body.temperature, undefined);
  assert.equal(calls[1].options.headers.Authorization, undefined);
  assert.equal(calls[1].body.reasoning_effort, 'medium');
  assert.equal(calls[1].body.reasoning, undefined);
  assert.equal(calls[1].body.temperature, 1);
  assert.equal(calls[1].body.top_p, 0.95);
});

test('custom endpoint preserves explicit API version but excludes URL query from metadata', async () => {
  let called;
  const client = createClient({provider: 'compatible', endpoint: 'https://inference.example/v1/chat/completions?api-version=2026-01-01', model: 'my-model', apiKey: secret}, {fetchImpl: async (url, options) => { called = {url, body: JSON.parse(options.body)}; return result(); }});
  await client.complete({messages});
  assert.match(called.url, /api-version=2026-01-01/u);
  assert.equal(called.body.reasoning_effort, undefined);
  assert.equal(client.metadata.endpointOrigin, 'https://inference.example');
  assert.ok(!JSON.stringify(client.metadata).includes('api-version'));
  assert.ok(!JSON.stringify(client.metadata).includes(secret));
});

test('unsafe destinations, credential placement, incompatible knobs and bounds fail before fetch', () => {
  const configs = [
    {...preset('local'), endpoint: 'http://192.168.1.20:11434/v1/chat/completions'},
    {...preset('local'), endpoint: 'file:///tmp/model'},
    {...preset('local'), endpoint: 'https://user:password@model.example/v1/chat/completions'},
    {...preset('local'), endpoint: 'https://model.example/v1/chat/completions?api_key=private'},
    {...preset('local'), endpoint: `https://model.example/v1/chat/completions?custom=${secret}`, apiKey: secret},
    {...preset('sonnet'), endpoint: 'https://unrelated.example/v1/chat/completions', apiKey: secret},
    {...preset('sonnet'), temperature: 0.2},
    {...preset('sonnet'), effort: 'none'},
    {...preset('flash'), effort: 'minimal'},
    {...preset('local'), effort: 'high'},
    {...preset('local'), maxTokens: 32769},
    {...preset('local'), maxTokens: 255},
    {...preset('local'), maxTokens: true},
    {...preset('local'), timeoutMs: 300001},
    {...preset('local'), temperature: NaN},
    {...preset('local'), topP: 0},
    {...preset('local'), apiKey: 'unsafe\r\nkey'},
    {...preset('local'), model: secret, apiKey: secret},
  ];
  for (const config of configs) assert.throws(() => createClient(config), error => error instanceof ProviderError && !error.message.includes(secret));
  assert.equal(createClient({...preset('local'), endpoint: 'http://[::1]:11434/v1/chat/completions'}).metadata.endpointOrigin, 'http://[::1]:11434');
});

test('missing key, secret in prompt and oversized UTF-8 request cause no network call', async () => {
  let calls = 0;
  const fetchImpl = async () => { calls++; return result(); };
  await rejects(createClient(preset('sonnet'), {fetchImpl}).complete({messages}), 'AUTH_REQUIRED');
  const client = createClient({...preset('sonnet'), apiKey: secret}, {fetchImpl});
  await rejects(client.complete({messages: [{role: 'user', content: `Do not expose ${secret}`}]}), 'SECRET_IN_CONTENT');
  await rejects(client.complete({messages: [{role: 'user', content: '界'.repeat(750000)}]}), 'REQUEST_TOO_LARGE');
  await rejects(client.complete({messages: []}), 'INVALID_REQUEST');
  assert.equal(calls, 0);
});

test('HTTP, network and malformed failures reveal neither provider body nor request secrets', async () => {
  const cases = [
    [async () => new Response(`upstream echoed ${secret}`, {status: 401}), 'HTTP_ERROR'],
    [async () => { throw new Error(`URL contained ${secret}`); }, 'NETWORK_ERROR'],
    [async () => new Response(`invalid JSON ${secret}`), 'MALFORMED_RESPONSE'],
    [async () => result({error: {message: secret}}), 'MODEL_ERROR'],
    [async () => result({choices: []}), 'MALFORMED_RESPONSE'],
    [async () => result({choices: [{message: {content: secret}, finish_reason: 'stop'}]}), 'SECRET_IN_RESPONSE'],
  ];
  for (const [fetchImpl, code] of cases) await rejects(createClient({...preset('sonnet'), apiKey: secret}, {fetchImpl}).complete({messages}), code);
});

test('truncated, empty, filtered and tool-call replies are explicit terminal errors', async () => {
  for (const [content, finish_reason, code] of [
    ['partial JSON', 'length', 'TRUNCATED'],
    ['', 'stop', 'EMPTY_RESPONSE'],
    ['', 'content_filter', 'FILTERED'],
    [null, 'tool_calls', 'UNSUPPORTED_REPLY'],
    ['text', null, 'MALFORMED_RESPONSE'],
  ]) {
    const fetchImpl = async () => result({choices: [{message: {content}, finish_reason}]});
    await rejects(createClient(preset('local'), {fetchImpl}).complete({messages}), code);
  }
});

test('redirects are blocked before response content is read', async () => {
  const client = createClient({...preset('sonnet'), apiKey: secret}, {fetchImpl: async (_, options) => {
    assert.equal(options.redirect, 'error');
    return new Response(secret, {status: 307, headers: {Location: 'https://unrelated.example'}});
  }});
  await rejects(client.complete({messages}), 'REDIRECT_BLOCKED');
});

test('response byte cap is enforced from declared length and from streamed bytes', async () => {
  const huge = 'x'.repeat(4 * 1024 * 1024 + 1);
  for (const response of [new Response('small', {headers: {'Content-Length': String(huge.length)}}), new Response(huge)]) {
    await rejects(createClient(preset('local'), {fetchImpl: async () => response}).complete({messages}), 'RESPONSE_TOO_LARGE');
  }
});

test('cancellation stops before submission or interrupts a pending call without retry', async () => {
  let calls = 0;
  const first = new AbortController();
  first.abort(secret);
  const never = createClient(preset('local'), {fetchImpl: async () => { calls++; return result(); }});
  await rejects(never.complete({messages, signal: first.signal}), 'CANCELLED');
  assert.equal(calls, 0);
  const second = new AbortController();
  let requestSignal;
  const client = createClient(preset('local'), {fetchImpl: (_, options) => { calls++; requestSignal = options.signal; return new Promise(() => {}); }});
  const pending = client.complete({messages, signal: second.signal});
  second.abort(secret);
  await rejects(pending, 'CANCELLED');
  assert.equal(calls, 1);
  assert.equal(requestSignal.aborted, true);
});

test('timeout bounds the whole pending request and does not retry', async () => {
  let calls = 0;
  const client = createClient({...preset('local'), timeoutMs: 1000}, {fetchImpl: () => { calls++; return new Promise(() => {}); }});
  await rejects(client.complete({messages}), 'TIMEOUT');
  assert.equal(calls, 1);
});

test('usage whitelisting removes strings and arbitrary upstream metadata', async () => {
  const reply = await createClient(preset('local'), {fetchImpl: async () => result({usage: {prompt_tokens: 12, completion_tokens: -1, total_tokens: 'secret', provider_debug: secret, completion_tokens_details: {reasoning_tokens: 5, debug: secret}}})}).complete({messages});
  assert.deepEqual(reply.usage, {prompt_tokens: 12, completion_tokens_details: {reasoning_tokens: 5}});
  assert.ok(!JSON.stringify(reply).includes(secret));
});
