'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
if(!globalThis.crypto)globalThis.crypto=crypto.webcrypto;
const root=path.resolve(__dirname,'..'),E=require('../engine.js');
(async()=>{const read=n=>JSON.parse(fs.readFileSync(path.join(root,n),'utf8'));const meta=read('build-meta.json');const actual=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'engine.js'))).digest('hex');if(meta.engine_sha256!==actual)throw Error('Source digest mismatch');const r=await E.selftest(read('data/capture.json'),actual,read('scenarios.json'));fs.writeFileSync(path.join(root,'data/qualification.json'),JSON.stringify(r,null,2)+'\n');console.log(JSON.stringify(r));})().catch(e=>{console.error(e.stack);process.exitCode=1;});
