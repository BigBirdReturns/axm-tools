#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
if(!globalThis.crypto)globalThis.crypto=crypto.webcrypto;
const E=require('./core.js');
const digest=crypto.createHash('sha256').update(fs.readFileSync(path.join(__dirname,'core.js'))).update('\n').update(fs.readFileSync(path.join(__dirname,'commons-core.js'))).digest('hex');
(async()=>{const target=process.argv[2];if(!target)throw Error('Usage: node verify-capsule.cjs path/to/handoff.json');const stat=fs.statSync(target);if(stat.size>30000000)throw Error('Capsule exceeds limit');const p=JSON.parse(fs.readFileSync(target,'utf8'));const w=await E.restore(p,digest);process.stdout.write(JSON.stringify({status:'PASS',engine_sha256:digest,workflow:w.workflow.id,source_revisions:w.sources.length,captures:w.captures.length,recomputed_decisions:w.decisions.length,declared_reviews:w.reviews.length,current:E.isCurrent(w),latest_status:w.decisions.at(-1)?.status,production_authority:false},null,2)+'\n');})().catch(e=>{process.stderr.write(e.message+'\n');process.exitCode=1;});
