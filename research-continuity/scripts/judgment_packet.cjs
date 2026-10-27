#!/usr/bin/env node
'use strict';
/* Consume the retained object, not the original conversation or running process.
   Uses only installed, known owner code. Never evaluates code from the packet. */
const fs=require('node:fs');
const C=require('../source/research-core.js');
const L=require('../source/continuity.js');
require('../source/measurements.js');
const R=require('../source/judgment.js');
(async()=>{
 const p=process.argv[2];if(!p)throw Error('Usage: node scripts/judgment_packet.cjs packet.json [as-of UTC]');
 if(fs.statSync(p).size>12000000)throw Error('Packet exceeds 12 MB.');
 const packet=C.parse(fs.readFileSync(p,'utf8'));const ws=await L.verify(packet);await R.verify(ws);
 const state=R.get(ws);if(!state)throw Error('No retained judgment in this packet.');
 const asOf=process.argv[3]||state.last_at;
 const current=R.assess(state,asOf);
 const sourceVersions=Object.values(state.sources).flat().length;
 const refusals=ws.events.filter(e=>e.type==='record'&&e.payload.data?.schema==='research-continuity/judgment-refusal@1').length;
 const out={schema:'research-continuity/cold-judgment@1',packet_sha256:packet.sha256,journal_replay:'PASS',judgment_replay:'PASS',as_of:asOf,recorded_rationale:R.head(state).rationale,alternatives:R.head(state).alternatives,original_decision:state.judgments[0],current,judgment_count:state.judgments.length,source_versions:sourceVersions,refused_transitions:refusals,historical_editions:C.state(ws).reports.length,origin_process_required:false,external_authority:false};
 process.stdout.write(JSON.stringify(out,null,2)+'\n');
})().catch(e=>{console.error('REFUSED: '+e.message);process.exitCode=1;});
