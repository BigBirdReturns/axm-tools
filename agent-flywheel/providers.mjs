/** Browser/Node model transport. Credentials live only in the returned closure. */

const OPENROUTER_ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions';
const MAX_REQUEST_BYTES = 2 * 1024 * 1024;
const MAX_RESPONSE_BYTES = 4 * 1024 * 1024;
const MAX_MESSAGES = 64;
const encoder = new TextEncoder();
const EFFORTS = new Set(['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']);
const SONNET_IDS = new Set([
  'anthropic/claude-sonnet-5.5',
  'anthropic/claude-sonnet-5.5-20260928',
  'claude-sonnet-5-5',
]);
const FLASH_IDS = new Set(['google/gemini-3.8-flash', 'google/gemini-3.8-flash-20260902', 'gemini-3.8-flash']);
const QWEN_IDS = new Set(['qwen3.8', 'qwen3.8:27b', 'Qwen/Qwen3.8-27B']);

export const PROVIDER_PRESETS = Object.freeze([
  Object.freeze({
    id: 'sonnet', label: 'Claude Sonnet 5.5 · recommended', provider: 'openrouter',
    endpoint: OPENROUTER_ENDPOINT, model: 'anthropic/claude-sonnet-5.5',
    effort: 'high', maxTokens: 16384,
    description: 'Recommended starting point for diagnosis, experiment design and prompt candidates. High effort; provider-default sampling. Verify outcomes against your own references.',
    sourceUrl: 'https://openrouter.ai/anthropic/claude-sonnet-5.5',
  }),
  Object.freeze({
    id: 'flash', label: 'Gemini 3.8 Flash · economy', provider: 'openrouter',
    endpoint: OPENROUTER_ENDPOINT, model: 'google/gemini-3.8-flash',
    effort: 'medium', maxTokens: 8192,
    description: 'Lower-cost starting point for evidence triage and repeated experiments. Medium effort; provider-default sampling. Pricing depends on the chosen route.',
    sourceUrl: 'https://openrouter.ai/google/gemini-3.8-flash',
  }),
  Object.freeze({
    id: 'local', label: 'Qwen3.8 27B · local', provider: 'compatible',
    endpoint: 'http://localhost:11434/v1/chat/completions', model: 'qwen3.8:27b',
    effort: 'medium', maxTokens: 8192, temperature: 1, topP: 0.95,
    description: 'Ollama or a compatible local server. Configure sufficient server context, allow this page origin and grant the browser local-network access when requested. The endpoint and model remain editable.',
    sourceUrl: 'https://huggingface.co/Qwen/Qwen3.8-27B',
  }),
  Object.freeze({
    id: 'custom', label: 'Your model · compatible endpoint', provider: 'compatible',
    endpoint: '', model: '', effort: '', maxTokens: 8192,
    description: 'Supply the complete chat-completions URL and exact served model ID. HTTPS endpoints and HTTP loopback servers are supported. Use parameters your server accepts.',
    sourceUrl: 'https://docs.ollama.com/api/openai-compatibility',
  }),
]);

export class ProviderError extends Error {
  constructor(code, message, {status} = {}) {
    super(message);
    this.name = 'ProviderError';
    this.code = code;
    if (Number.isInteger(status)) this.status = status;
  }
}

function fail(code, message, details) { throw new ProviderError(code, message, details); }

function boundedString(value, label, min, max) {
  if (typeof value !== 'string' || value.length < min || value.length > max || /[\u0000-\u001f\u007f]/u.test(value)) {
    fail('INVALID_CONFIG', `${label} must contain ${min} to ${max} characters without control characters.`);
  }
  return value;
}

function integer(value, label, min, max) {
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    fail('INVALID_CONFIG', `${label} must be an integer from ${min} to ${max}.`);
  }
  return value;
}

function isLoopback(hostname) {
  const host = hostname.toLowerCase();
  if (host === 'localhost' || host.endsWith('.localhost') || host === '[::1]' || host === '::1') return true;
  const fields = host.split('.');
  return fields.length === 4 && fields[0] === '127' && fields.every(field => /^\d{1,3}$/u.test(field) && Number(field) <= 255);
}

function normalizeEndpoint(value, provider, apiKey) {
  boundedString(value, 'Endpoint URL', 1, 2048);
  let url;
  try { url = new URL(value); } catch { fail('INVALID_ENDPOINT', 'Enter a complete model endpoint URL.'); }
  if (url.username || url.password || url.hash) {
    fail('INVALID_ENDPOINT', 'The model endpoint must omit embedded credentials and fragments.');
  }
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && isLoopback(url.hostname))) {
    fail('INVALID_ENDPOINT', 'Use HTTPS for remote endpoints or HTTP on a loopback host for local inference.');
  }
  for (const key of url.searchParams.keys()) {
    if (/^(?:api[-_]?key|key|access[-_]?token|token|auth(?:orization)?|secret|password|credential|signature|sig)$/iu.test(key)) {
      fail('SECRET_IN_ENDPOINT', 'Put credentials in the API-key field, rather than the endpoint URL.');
    }
  }
  if (apiKey.length >= 8 && (value.includes(apiKey) || [...url.searchParams.values()].some(v => v.includes(apiKey)))) {
    fail('SECRET_IN_ENDPOINT', 'Put credentials in the API-key field, rather than the endpoint URL.');
  }
  if (provider === 'openrouter' && !['https://openrouter.ai', 'https://eu.openrouter.ai'].includes(url.origin)) {
    fail('INVALID_ENDPOINT', 'The OpenRouter preset requires an OpenRouter endpoint. Select a custom endpoint to use another provider.');
  }
  return url;
}

function normalizeConfig(config) {
  if (!config || typeof config !== 'object' || Array.isArray(config)) fail('INVALID_CONFIG', 'Model configuration must be an object.');
  const provider = config.provider ?? 'openrouter';
  if (!['openrouter', 'compatible'].includes(provider)) fail('INVALID_CONFIG', 'Provider must be openrouter or compatible.');
  const apiKey = config.apiKey ?? '';
  if (typeof apiKey !== 'string' || apiKey.length > 8192 || (apiKey && !/^[\x21-\x7e]+$/u.test(apiKey))) {
    fail('INVALID_CONFIG', 'The API key must contain printable ASCII characters without whitespace.');
  }
  const endpoint = normalizeEndpoint(config.endpoint ?? (provider === 'openrouter' ? OPENROUTER_ENDPOINT : ''), provider, apiKey);
  const model = boundedString(config.model ?? (provider === 'openrouter' ? 'anthropic/claude-sonnet-5.5' : ''), 'Model ID', 1, 256).trim();
  if (!model) fail('INVALID_CONFIG', 'Enter the exact served model ID.');
  if (apiKey.length >= 8 && model.includes(apiKey)) fail('SECRET_IN_CONFIG', 'The model ID must not contain the API key.');
  const effort = config.effort == null || config.effort === '' ? null : config.effort;
  if (effort !== null && !EFFORTS.has(effort)) fail('INVALID_CONFIG', 'Unsupported reasoning effort.');
  if (SONNET_IDS.has(model) && effort !== null && !['low', 'medium', 'high', 'xhigh', 'max'].includes(effort)) {
    fail('INVALID_CONFIG', 'Sonnet 5.5 accepts low, medium, high, xhigh or max effort.');
  }
  if (FLASH_IDS.has(model) && effort !== null && !['low', 'medium', 'high'].includes(effort)) {
    fail('INVALID_CONFIG', 'Gemini 3.8 Flash accepts low, medium or high effort.');
  }
  if (QWEN_IDS.has(model) && effort !== null && !['low', 'medium', 'xhigh'].includes(effort)) {
    fail('INVALID_CONFIG', 'Qwen3.8 accepts low, medium or xhigh effort.');
  }
  const maxTokens = integer(config.maxTokens ?? 8192, 'Output-token cap', 256, 32768);
  const timeoutMs = integer(config.timeoutMs ?? 120000, 'Request timeout in milliseconds', 1000, 300000);
  const settings = {provider, endpointOrigin: endpoint.origin, model, effort, maxTokens, timeoutMs};
  for (const [key, label, min, max] of [['temperature', 'Temperature', 0, 2], ['topP', 'Top-p', Number.MIN_VALUE, 1]]) {
    const value = config[key];
    if (value === undefined || value === null || value === '') continue;
    if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) {
      fail('INVALID_CONFIG', `${label} is outside its supported range.`);
    }
    if (SONNET_IDS.has(model)) fail('INVALID_CONFIG', 'Sonnet 5.5 uses effort control; remove temperature and top-p overrides.');
    settings[key] = value;
  }
  return {endpoint: endpoint.href, apiKey, settings: Object.freeze(settings)};
}

function normalizeMessages(messages, apiKey) {
  if (!Array.isArray(messages) || !messages.length || messages.length > MAX_MESSAGES) {
    fail('INVALID_REQUEST', `Supply between 1 and ${MAX_MESSAGES} text messages.`);
  }
  return messages.map(message => {
    if (!message || typeof message !== 'object' || Array.isArray(message) || !['system', 'developer', 'user', 'assistant'].includes(message.role) || typeof message.content !== 'string') {
      fail('INVALID_REQUEST', 'Each message needs a supported role and text content.');
    }
    if (message.content.length > MAX_REQUEST_BYTES) fail('REQUEST_TOO_LARGE', 'A model message exceeds the request-size limit.');
    if (apiKey.length >= 8 && message.content.includes(apiKey)) fail('SECRET_IN_CONTENT', 'The model input contains the configured API key. Remove it from the evidence or prompt.');
    return {role: message.role, content: message.content};
  });
}

async function readBoundedResponse(response, abortable, signal) {
  const lengthHeader = response.headers?.get?.('content-length');
  if (lengthHeader !== null && lengthHeader !== undefined && /^\d+$/u.test(lengthHeader) && Number(lengthHeader) > MAX_RESPONSE_BYTES) {
    await response.body?.cancel?.().catch(() => {});
    fail('RESPONSE_TOO_LARGE', 'The model response exceeds the 4 MiB response-size limit.');
  }
  if (!response.body?.getReader) fail('MALFORMED_RESPONSE', 'The model endpoint returned an empty or unreadable response.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8', {fatal: true});
  let bytes = 0;
  const text = [];
  let completed = false;
  try {
    while (true) {
      const {done, value} = await abortable(reader.read());
      if (done) { completed = true; break; }
      if (!(value instanceof Uint8Array)) fail('MALFORMED_RESPONSE', 'The model endpoint returned unreadable response data.');
      bytes += value.byteLength;
      if (bytes > MAX_RESPONSE_BYTES) fail('RESPONSE_TOO_LARGE', 'The model response exceeds the 4 MiB response-size limit.');
      text.push(decoder.decode(value, {stream: true}));
    }
    text.push(decoder.decode());
    return text.join('');
  } catch (error) {
    if (error instanceof ProviderError || signal.aborted) throw error;
    fail('MALFORMED_RESPONSE', 'The model response could not be read as UTF-8 text.');
  } finally {
    if (!completed) await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

function safeUsage(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const result = {};
  const copyNumbers = (source, keys, destination, integerOnly) => {
    for (const key of keys) {
      const number = source?.[key];
      if (typeof number === 'number' && Number.isFinite(number) && number >= 0 && number <= Number.MAX_SAFE_INTEGER && (!integerOnly || Number.isSafeInteger(number))) destination[key] = number;
    }
  };
  copyNumbers(value, ['prompt_tokens', 'completion_tokens', 'total_tokens', 'input_tokens', 'output_tokens'], result, true);
  copyNumbers(value, ['cost'], result, false);
  for (const [key, fields, integerOnly] of [
    ['prompt_tokens_details', ['cached_tokens', 'cache_write_tokens', 'audio_tokens'], true],
    ['completion_tokens_details', ['reasoning_tokens', 'audio_tokens', 'accepted_prediction_tokens', 'rejected_prediction_tokens'], true],
    ['cost_details', ['upstream_inference_cost', 'upstream_inference_prompt_cost', 'upstream_inference_completions_cost'], false],
  ]) {
    const nested = {};
    copyNumbers(value[key], fields, nested, integerOnly);
    if (Object.keys(nested).length) result[key] = nested;
  }
  return Object.keys(result).length ? result : null;
}

function parseCompletion(raw, settings, apiKey) {
  let data;
  try { data = JSON.parse(raw); } catch { fail('MALFORMED_RESPONSE', 'The model endpoint did not return valid JSON.'); }
  if (!data || typeof data !== 'object' || data.error) fail('MODEL_ERROR', 'The model endpoint returned an error response. Check the model, access and request settings.');
  const choice = data.choices?.[0];
  if (!choice || !choice.message || typeof choice.message !== 'object') fail('MALFORMED_RESPONSE', 'The model reply lacks a chat-completion message.');
  const finishReason = choice.finish_reason;
  if (['length', 'max_tokens', 'max_output_tokens'].includes(finishReason)) fail('TRUNCATED', 'The model exhausted its output-token cap before completing this step. Increase the cap or reduce the input.');
  if (['content_filter', 'safety', 'refusal'].includes(finishReason)) fail('FILTERED', 'The selected provider stopped this response under its content policy.');
  if (choice.message.tool_calls?.length || ['tool_calls', 'function_call'].includes(finishReason)) fail('UNSUPPORTED_REPLY', 'The model returned a tool call where this research step requires text.');
  if (typeof finishReason !== 'string' || !finishReason.length || finishReason.length > 64 || /[\u0000-\u001f]/u.test(finishReason)) {
    fail('MALFORMED_RESPONSE', 'The model reply lacks a terminal finish reason.');
  }
  let text = choice.message.content;
  if (Array.isArray(text) && text.every(part => part?.type === 'text' && typeof part.text === 'string')) text = text.map(part => part.text).join('');
  if (typeof text !== 'string' || !text.trim()) fail('EMPTY_RESPONSE', 'The model returned no final text for this step.');
  const model = data.model ?? settings.model;
  if (typeof model !== 'string' || !model.length || model.length > 256 || /[\u0000-\u001f\u007f]/u.test(model)) fail('MALFORMED_RESPONSE', 'The model endpoint returned an invalid model identity.');
  if (apiKey.length >= 8 && [text, model, finishReason].some(value => value.includes(apiKey))) fail('SECRET_IN_RESPONSE', 'The model response contains the configured API key and was not retained.');
  return {text, model, usage: safeUsage(data.usage), finishReason};
}

export function createClient(config = {}, {fetchImpl = globalThis.fetch} = {}) {
  if (typeof fetchImpl !== 'function') fail('INVALID_CONFIG', 'A Fetch-compatible transport is required.');
  const {endpoint, apiKey, settings} = normalizeConfig(config);

  async function complete({messages, stage, signal, jsonMode = false} = {}) {
    // Stage names are intentionally neither transmitted nor echoed in errors.
    void stage;
    if (signal?.aborted) fail('CANCELLED', 'The model request was cancelled.');
    if (settings.provider === 'openrouter' && !apiKey) fail('AUTH_REQUIRED', 'Enter your own OpenRouter API key before running a model request.');
    if (typeof jsonMode !== 'boolean') fail('INVALID_REQUEST', 'JSON mode must be a Boolean.');
    const body = {model: settings.model, messages: normalizeMessages(messages, apiKey), max_tokens: settings.maxTokens, stream: false};
    if (settings.effort !== null) {
      if (settings.provider === 'openrouter') body.reasoning = {effort: settings.effort, exclude: true};
      else body.reasoning_effort = settings.effort;
    }
    if (settings.temperature !== undefined) body.temperature = settings.temperature;
    if (settings.topP !== undefined) body.top_p = settings.topP;
    if (jsonMode) body.response_format = {type: 'json_object'};
    const serialized = JSON.stringify(body);
    if (encoder.encode(serialized).byteLength > MAX_REQUEST_BYTES) fail('REQUEST_TOO_LARGE', 'The model request exceeds the 2 MiB request-size limit.');

    const headers = {'Content-Type': 'application/json'};
    if (apiKey) headers.Authorization = `Bearer ${apiKey}`;
    if (settings.provider === 'openrouter') headers['X-OpenRouter-Title'] = 'AXM Agent Flywheel';
    const controller = new AbortController();
    let timedOut = false;
    const onAbort = () => controller.abort();
    let abortReject;
    const aborted = new Promise((_, reject) => { abortReject = reject; });
    const internalAbort = () => abortReject(new ProviderError(timedOut ? 'TIMEOUT' : 'CANCELLED', timedOut ? 'The model request exceeded its configured timeout.' : 'The model request was cancelled.'));
    controller.signal.addEventListener('abort', internalAbort, {once: true});
    signal?.addEventListener('abort', onAbort, {once: true});
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, settings.timeoutMs);
    const abortable = promise => Promise.race([promise, aborted]);
    const started = globalThis.performance?.now?.() ?? Date.now();
    try {
      if (signal?.aborted) controller.abort();
      const response = await abortable(fetchImpl(endpoint, {
        method: 'POST', headers, body: serialized, signal: controller.signal,
        redirect: 'error', credentials: 'omit', cache: 'no-store', mode: 'cors',
      }));
      if (response?.redirected || (response?.status >= 300 && response.status < 400)) fail('REDIRECT_BLOCKED', 'The model endpoint attempted a redirect. Enter its final inference URL directly.');
      if (!response || !Number.isInteger(response.status)) fail('MALFORMED_RESPONSE', 'The model transport returned an invalid HTTP response.');
      if (response.url) {
        let responseOrigin;
        try { responseOrigin = new URL(response.url).origin; } catch { fail('MALFORMED_RESPONSE', 'The model endpoint returned an invalid response URL.'); }
        if (responseOrigin !== settings.endpointOrigin) fail('REDIRECT_BLOCKED', 'The model response came from a different origin. Redirected credentials are not permitted.');
      }
      if (!response.ok) {
        await response.body?.cancel?.().catch(() => {});
        fail('HTTP_ERROR', `The model endpoint returned HTTP ${response.status}. Check its availability, your access and the selected model settings.`, {status: response.status});
      }
      const raw = await readBoundedResponse(response, abortable, controller.signal);
      const parsed = parseCompletion(raw, settings, apiKey);
      return {...parsed, elapsedMs: Math.max(0, Math.round((globalThis.performance?.now?.() ?? Date.now()) - started)), endpointOrigin: settings.endpointOrigin};
    } catch (error) {
      if (error instanceof ProviderError) throw error;
      if (controller.signal.aborted) fail(timedOut ? 'TIMEOUT' : 'CANCELLED', timedOut ? 'The model request exceeded its configured timeout.' : 'The model request was cancelled.');
      fail('NETWORK_ERROR', 'The selected model endpoint could not be reached. Check its URL, CORS permissions and network availability.');
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onAbort);
      controller.signal.removeEventListener('abort', internalAbort);
    }
  }

  return Object.freeze({metadata: settings, complete});
}
