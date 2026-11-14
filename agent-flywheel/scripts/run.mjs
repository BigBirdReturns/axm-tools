#!/usr/bin/env node
import {readFile, open, mkdir, access} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {parseArgs} from 'node:util';
import {pathToFileURL} from 'node:url';
import {prepareWork, runResearch, verifyReport, buildHandoff} from '../engine.mjs';
import {PROVIDER_PRESETS, createClient} from '../providers.mjs';
import {SAMPLE_CONFIG, createDemoClient} from '../sample.mjs';

const HELP = `Agent Flywheel: run the same public research engine in your environment.

  node scripts/run.mjs --request work.json --output result.json
  node scripts/run.mjs --request work.json --handoff
  node scripts/run.mjs --verify result.json
  node scripts/run.mjs --demo --output demonstration.json

Options:
  --preset sonnet|flash|local|custom   Model settings preset; default sonnet
  --require-qualified                Exit nonzero unless QUALIFIED or NO_CHANGE
  --demo                             Explicit deterministic synthetic adapter
  --help                             Show this help without calling a model

Connection comes from the caller's environment:
  FLYWHEEL_API_KEY, FLYWHEEL_ENDPOINT, FLYWHEEL_MODEL, FLYWHEEL_PROVIDER,
  FLYWHEEL_EFFORT, FLYWHEEL_MAX_TOKENS, FLYWHEEL_TEMPERATURE,
  FLYWHEEL_TOP_P, FLYWHEEL_TIMEOUT_MS.

The API key is never a command argument or report field. Work inputs and
responses remain in the caller's environment and chosen model provider.
An existing output file is never overwritten. Node 20 or later; no packages.
`;

function optionalNumber(value, label) {
  if (value === undefined || value === '') return undefined;
  const number = Number(value);
  if (!Number.isFinite(number)) throw new Error(`${label} must be a finite number.`);
  return number;
}

export async function main(argv = process.argv.slice(2), environment = process.env) {
  const {values} = parseArgs({args:argv,options:{
    request:{type:'string'},output:{type:'string'},preset:{type:'string',default:'sonnet'},
    verify:{type:'string'},handoff:{type:'boolean'},demo:{type:'boolean'},
    'require-qualified':{type:'boolean'},help:{type:'boolean'},
  }});
  if (values.help) { process.stdout.write(HELP); return 0; }
  if (values.verify) {
    const report = JSON.parse(await readFile(resolve(values.verify),'utf8'));
    const result = await verifyReport(report);
    process.stdout.write(JSON.stringify({run_id:report.run_id,...result},null,2)+'\n');
    return result.valid ? 0 : 2;
  }
  if (values.demo && values.request) throw new Error('Choose the supplied request or the explicit demonstration.');
  if (!values.demo && !values.request) throw new Error('Supply --request work.json or --demo.');
  const source = values.demo ? structuredClone(SAMPLE_CONFIG) : JSON.parse(await readFile(resolve(values.request),'utf8'));
  const work = await prepareWork(source);
  if (values.handoff) { process.stdout.write(buildHandoff(work)+'\n'); return 0; }
  if (!values.output) throw new Error('Supply --output to retain the complete result.');
  const output = resolve(values.output);
  try { await access(output); throw new Error('The output already exists; choose a new result path.'); }
  catch(error) { if (error.code !== 'ENOENT') throw error; }

  const preset = PROVIDER_PRESETS.find(item => item.id === values.preset);
  if (!preset) throw new Error('Unknown preset; choose sonnet, flash, local or custom.');
  const config = {
    ...preset,
    provider:environment.FLYWHEEL_PROVIDER || preset.provider,
    endpoint:environment.FLYWHEEL_ENDPOINT || preset.endpoint,
    model:environment.FLYWHEEL_MODEL || preset.model,
    apiKey:environment.FLYWHEEL_API_KEY || '',
    effort:environment.FLYWHEEL_EFFORT ?? preset.effort,
    maxTokens:optionalNumber(environment.FLYWHEEL_MAX_TOKENS,'FLYWHEEL_MAX_TOKENS') ?? preset.maxTokens,
    temperature:optionalNumber(environment.FLYWHEEL_TEMPERATURE,'FLYWHEEL_TEMPERATURE') ?? preset.temperature,
    topP:optionalNumber(environment.FLYWHEEL_TOP_P,'FLYWHEEL_TOP_P') ?? preset.topP,
    timeoutMs:optionalNumber(environment.FLYWHEEL_TIMEOUT_MS,'FLYWHEEL_TIMEOUT_MS') ?? 180000,
  };
  const client = values.demo ? createDemoClient() : createClient(config);
  const controller = new AbortController();
  const stop = () => controller.abort(new Error('Interrupted by the caller.'));
  process.once('SIGINT',stop);
  let report;
  try {
    report = await runResearch(work,{client,signal:controller.signal,onEvent:event=>{
      process.stderr.write(JSON.stringify({event:event.id,status:event.status,label:event.label})+'\n');
    }});
  } finally { process.removeListener('SIGINT',stop); }
  const verification = await verifyReport(report);
  await mkdir(dirname(output),{recursive:true});
  const handle = await open(output,'wx',0o600);
  try { await handle.writeFile(JSON.stringify(report,null,2)+'\n'); } finally { await handle.close(); }
  process.stdout.write(JSON.stringify({run_id:report.run_id,status:report.status,verdict:report.verdict,
    metrics:report.metrics,verified:verification.valid,errors:verification.errors,output},null,2)+'\n');
  if (!verification.valid) return 2;
  if (report.status !== 'completed') return 1;
  if (values['require-qualified'] && !['QUALIFIED','NO_CHANGE'].includes(report.verdict)) return 3;
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { process.exitCode = await main(); }
  catch(error) { process.stderr.write(`Agent Flywheel stopped: ${error.message}\n`); process.exitCode=1; }
}
