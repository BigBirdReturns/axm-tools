#!/usr/bin/env node
'use strict';
// Never executes a command, model output, or proof artifact from the packet.
const fs=require('node:fs'),path=require('node:path');
const C=require('../source/research-core.js');
const L=require('../source/continuity.js');
require('../source/measurements.js');
require('../source/judgment.js');
(async()=>{
 const file=process.argv[2];if(!file)throw Error('Usage: node scripts/check_packet.cjs packet.json --recompute');
 const stat=fs.statSync(file);if(stat.size>12000000)throw Error('Packet exceeds 12 MB.');
 const packet=C.parse(fs.readFileSync(file,'utf8')),ws=await L.verify(packet),v=await L.view(ws);
 const out={packet_sha256:packet.sha256,journal_replay:'PASS',original_source_bytes:'PASS',local_plan_and_output_digests:'PASS',events:ws.events.length,attempts:v.counts,latest_applicability:v.current,review_ready:!!v.review?.ready,frozen_editions:v.reports.length,external_anchor:'NOT_INDEPENDENTLY_VERIFIED',source_truth:'NOT_ESTABLISHED',proof_checker:'NOT_RUN',external_authority:'NONE'};
 if(process.argv.includes('--recompute')){
  const p=C.latest(C.state(ws),'policy');out.current_raw_evaluation=C.compare(['run-a','run-b'].map(id=>C.latest(C.state(ws),id).data),p.data);
  out.recompute_boundary='Arithmetic over current parsed records. Does not readmit stale source bindings, produce a new review, or rerun a model.';
 }
 process.stdout.write(JSON.stringify(out,null,2)+'\n');
})().catch(e=>{console.error('REFUSED: '+e.message);process.exitCode=1;});
