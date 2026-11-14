# Choose the model; keep the experiment

The public page calls the endpoint and model you select. The same engine runs in your existing environment through `scripts/run.mjs`; an exported handoff also works with a coding agent. The research packet, reference cases and results remain portable across providers.

## Recommended starting settings

Recommendations checked 14 November 2026. These are initial operating settings for this tool, not a comparative model-quality benchmark.

| Use | Model | Settings |
| --- | --- | --- |
| Default research model | `anthropic/claude-sonnet-5.5` through OpenRouter | High reasoning effort; 16,384 maximum output tokens per call; provider-default sampling. |
| Lower-cost first pass | `google/gemini-3.8-flash` through OpenRouter | Medium reasoning effort; 8,192 maximum output tokens per call; provider-default sampling. |
| User-owned local inference | Ollama `qwen3.8:27b`, or an editable compatible model | Medium reasoning effort; 8,192 maximum output tokens; temperature 1.0; top-p 0.95; begin with a configured 32,768-token server context. |

Use the default for failure analysis, experiment design and technical synthesis. Use the economy preset for initial triage and larger batches. Choose a local endpoint when the work should run on your own infrastructure. The model field remains editable: the presets are conveniences, and an OpenAI-compatible endpoint can serve another model.

Sonnet 5.5 uses adaptive thinking and rejects explicit temperature, top-p and top-k overrides. Its output allocation covers reasoning and visible text. The cloud presets therefore use the provider's unified reasoning-effort field and omit sampling overrides. See the [Anthropic migration guide](https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide), [OpenRouter reasoning contract](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens), and [Google's model reference](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).

For local Qwen, the [model card](https://huggingface.co/Qwen/Qwen3.8-27B) gives model-specific sampling guidance, and [Ollama's library](https://ollama.com/library/qwen3.8) identifies the available tags. Architecture context length and model-download size do not determine total runtime memory. Configure the actual server context and use the model identifier that your server exposes.

## Budget and evidence

Begin with two candidate prompt changes, twelve labeled cases and a forty-call ceiling. The page shows the planned call count before execution. Diagnosis usually needs one call. Improvement replays the baseline and candidate prompts on development cases, freezes a choice, then evaluates the baseline and selected prompt on the held-out and regression cases. Keeping the same model and generation settings across those calls makes the prompt intervention the declared variable.

Provider prices and routes change. Consult the selected provider's current rates; retained usage describes actual responses. A token-limit response is incomplete and stays visible. The runner does not silently retry requests, increase budgets or switch models.

The research model proposes interventions. Supplied expected outputs and the chosen exact-text or canonical-JSON comparator determine measured correctness. Proposed tests remain proposals until someone supplies or validates their reference answers. For unlabeled traces or prose, the result contains analysis, evidence citations, hypotheses and an experiment plan.

## Connection and custody

On the public page, API credentials remain in memory and go only to the endpoint selected for a run. Exported work and reports exclude that connection key. The site has no AXM inference backend or shared model account. OpenRouter supports browser-origin requests; other endpoints must permit the page's origin through their normal CORS configuration.

For Ollama, permit the exact public origin `https://bigbirdreturns.github.io` with its documented `OLLAMA_ORIGINS` configuration, then accept the browser's normal local-network permission when prompted. Alternatively, serve the downloaded page on localhost or run the CLI. The [Ollama compatibility reference](https://docs.ollama.com/api/openai-compatibility), [origin configuration](https://docs.ollama.com/faq) and [browser local-network guidance](https://developer.chrome.com/blog/local-network-access) describe these controls.

For a local or CI run:

```bash
export FLYWHEEL_ENDPOINT='https://openrouter.ai/api/v1/chat/completions'
export FLYWHEEL_MODEL='anthropic/claude-sonnet-5.5'
# Supply FLYWHEEL_API_KEY through your existing secret mechanism.
node scripts/run.mjs --request work.json --output result.json
node scripts/run.mjs --verify result.json
```

Use `--preset flash` or `--preset local` to select the other presets. Advanced environment variables appear in `node scripts/run.mjs --help`. Set `--require-qualified` when a CI step should accept only a qualified improvement or an unchanged baseline. Source-level and provider-protocol tests use controlled responses; they do not establish a model's quality on your task.
