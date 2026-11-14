# Agent Flywheel

**[Open the public tool](https://bigbirdreturns.github.io/axm-tools/agent-flywheel/)** · [Choose a model](MODEL_GUIDE.md) · [Download the tool kit](agent-flywheel-kit.zip) · [Source](https://github.com/BigBirdReturns/axm-tools/tree/main/agent-flywheel)

Give the tool an agent task, traces, failed runs or evaluation cases, and choose the model you want to do the research. The public page runs in the visitor's browser. It can call a visitor-configured model endpoint directly, prepare a handoff for an existing coding agent, or export the same work for the dependency-free local runner.

The tool diagnoses supplied evidence, proposes candidate prompt changes and evaluation cases, and can execute controlled comparisons when the visitor supplies labeled cases and a baseline prompt. Candidate selection uses development cases; the selected prompt freezes before held-out evaluation. Deterministic reference comparisons determine measured improvement. Unlabeled material still supports a research analysis and proposed experiment, with its evidence status retained.

## Use it in the browser

1. Enter the goal and task contract. Paste evidence or upload JSON, JSONL, CSV, or text. For measured improvement, include the current agent prompt and cases with expected answers.
2. Select **Diagnose** or **Improve**, then choose the model, endpoint, effort, output-token cap, and model-call ceiling. The [model guide](MODEL_GUIDE.md) explains the presets, custom endpoints, and local inference settings; [SOURCES.json](SOURCES.json) retains their dated source references.
3. Run the research. Findings cite development source IDs. Results show proposed prompts, actual case outcomes, the frozen decision, and request/response receipts. Cancellation retains a partial report.
4. Download **Report & evidence** to keep the complete result. **Import report** verifies an exported browser or CLI report before displaying it. **Work packet** exports the original task, evidence, splits, and budget for another run.

**Copy agent handoff** prepares a prompt for an existing coding agent without making a model call or requiring a key. The handoff contains development evidence only; attach the downloaded work packet for the runner to perform the separate qualification phase. **Load example** explicitly selects a synthetic support-routing example and a deterministic demonstration adapter. That adapter makes no external model calls and does not measure a language model's quality.

## Bring your own evidence

A replayable case contains an `input` and a supplied `expected` answer. `output` optionally records what an earlier agent produced. Explicit splits preserve your evaluation boundaries:

```json
[
  {"id":"dev-even","split":"development","input":"8","expected":"EVEN","output":"EVEN"},
  {"id":"dev-odd","split":"development","input":"7","expected":"ODD","output":"EVEN"},
  {"id":"hold-odd","split":"heldout","input":"19","expected":"ODD"},
  {"id":"reg-zero","split":"regression","input":"0","expected":"EVEN"}
]
```

The example task contract is “Return `EVEN` or `ODD` for the supplied integer.” Its intentionally weak baseline is “Return `EVEN` for every input.” These are synthetic labels, and actual results depend on the chosen model's responses. A complete six-case example packet is available in [examples/work.json](examples/work.json), with two development, two held-out, and two regression cases.

| Field | Accepted aliases or meaning |
| --- | --- |
| `input` | `question`, `prompt`; text or a JSON value to replay |
| `expected` | `reference`, `expected_output`; the supplied reference answer |
| `output` | `response`, `actual`; an earlier observed answer |
| `split` | `development`, `heldout`, or `regression` |
| `feedback`, `human_score`, `judge_score` | Retained evidence for the research model; scores do not become reference answers automatically |

JSON arrays, one-object-per-line JSONL, and CSV with these headers work directly. Prose and native trace objects, including MLflow-style `info`/`data` records, remain source material when they lack replayable inputs and references. Raw record fields stay in the work packet. Conflicting duplicate IDs and cross-split duplicate inputs are rejected. Unassigned labeled cases receive a stable, seeded development/held-out split; explicit assignments remain intact. The case limit caps the total labeled cases replayed across all splits, while the packet retains the full supplied evidence.

## What the experiment establishes

**Diagnose** makes one development-only research call and returns findings, hypotheses, candidate prompts, and proposed tests. **Improve** performs that diagnosis, evaluates the baseline and distinct proposed prompts on development cases, freezes the best prompt, and then evaluates the baseline and selected prompt on held-out and regression cases. The chosen model and settings stay fixed. A baseline tie preserves the baseline; duplicate baseline prompts are excluded from candidate experiments. Proposed tests remain separate from the supplied labels.

The `exact` metric trims outer whitespace, normalizes CRLF line endings, and compares exact text. The `json` metric parses replies and compares canonical JSON values, including objects, arrays, and scalars. Every displayed pass count derives from those comparisons. `QUALIFIED` requires positive held-out improvement and zero previously passing held-out/regression cases lost. `NO_CHANGE` records an unchanged measured result; `REJECTED` records regressions. Missing labels, a baseline, or a distinct held-out set produces `NEEDS_EVALUATION` with the diagnosis retained. Budget, cancellation, or execution failures produce `INCOMPLETE` with partial receipts.

Defaults are two candidates, twelve total labeled cases, and forty model calls. The engine calculates a conservative call plan and stops before starting an evaluation that exceeds its cap. It makes no automatic retries or adaptive searches against held-out results. The supported intervention is a prompt change; model-weight training, live production integrations, and deployment remain outside this tool. Qualification applies to the frozen supplied workload and its reference answers.

## Run locally or in CI

Use Node 20 or later from this directory. No package installation or build step is required. A downloaded browser work packet and the supplied example both work with `--request`:

```bash
# Supply FLYWHEEL_API_KEY through your existing secret mechanism.
node scripts/run.mjs --request examples/work.json --output parity-result.json
node scripts/run.mjs --verify parity-result.json
```

Choose another preset with `--preset flash` or `--preset local`. Endpoint, model, effort, token limit, sampling, and timeout overrides use the `FLYWHEEL_*` environment variables listed by `node scripts/run.mjs --help`. Connection credentials stay outside the request packet and command arguments. The [model guide](MODEL_GUIDE.md) contains complete connection examples.

These commands prepare a handoff or exercise the deterministic example without an external model request:

```bash
node scripts/run.mjs --request examples/work.json --handoff
node scripts/run.mjs --demo --output demonstration.json
node scripts/run.mjs --verify demonstration.json
```

The runner refuses to overwrite an existing result. Ctrl+C requests cancellation and retains the partial report. `--require-qualified` gives CI a nonzero exit unless a completed, valid report has `QUALIFIED` or `NO_CHANGE`; use the returned verdict when a pipeline specifically requires an improvement. Import the resulting JSON into the public page to inspect the same findings, cases, and receipts.

Work packets are frozen, content-identified exports. Reconstruct a new packet through the browser or `prepareWork` when changing the task; editing a packet's derived split or budget metadata fails validation. Report verification checks canonical SHA-256 digests, reconstructs the work packet, and independently recalculates reference correctness, candidate selection, regressions, and qualification from retained receipts. Those checks establish internal integrity and consistency; endpoint identity and output remain reported observations, not independently signed provider attestations.

## Privacy and public provenance

Model requests go directly to the visitor-selected endpoint. Diagnosis sends development source material; evaluation sends the selected task inputs. Downloaded reports contain the original work and model exchanges, including held-out evidence, so their contents retain the same sensitivity as the supplied material. The tool has no publication step. The API connection key remains outside work packets and reports; users should keep credentials out of the evidence they paste.

This independent AXM Tools implementation responds to the publicly described [Agent Flywheel research role](https://www.databricks.com/company/careers/engineering---pipeline/sr-research-scientist---agent-flywheel-8940421002): turn agent behavior into diagnosable failures, propose interventions, and measure whether they improve outcomes. The public source implements the bounded prompt-research workflow documented here. Databricks production access, endorsement, and internal deployment are not asserted.

## Architecture and ownership

This directory is self-contained static HTML, CSS and standard JavaScript, with a Node standard-library runner. It has no application server, database, telemetry, shared model account, package installation or build requirement. The visitor chooses any supported OpenRouter model or an OpenAI-compatible endpoint, including a local model. The owner explicitly requested model choice in the public tool on 14 November 2026. Optional model requests use only the visitor's endpoint and credentials. Keys remain in memory and are excluded from work packets and reports. The page performs model requests only after the visitor runs a job.

All shipped files are steward-owned. Examples are synthetic. No scheduled data writes exist. User evidence remains in the browser until the visitor invokes their selected model or downloads a packet. Public source and example data contain no private campaign records.

## What can rot

Model names, request fields, endpoint availability, CORS policies and local browser permissions may change. Presets are dated recommendations with primary-source links; endpoint and model fields remain editable. The page surfaces failures and retains interrupted work. The local runner uses the same engine without relying on hosted browser transport. Research outcomes depend on the supplied task, evidence, model and evaluation contract.
