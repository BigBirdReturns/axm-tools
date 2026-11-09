'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
if(!globalThis.crypto)globalThis.crypto=crypto.webcrypto;
const root=path.resolve(__dirname,'..'),E=require('../engine.js');
(async()=>{
 const read=n=>JSON.parse(fs.readFileSync(path.join(root,n),'utf8')),bytes=n=>fs.readFileSync(path.join(root,n)),sha=b=>crypto.createHash('sha256').update(b).digest('hex');
 const meta=read('build-meta.json'),engine=bytes('engine.js'),core=bytes('commons-core.js');
 const identity=(a,b)=>sha(Buffer.concat([Buffer.from('axm-i3x-engine/1\0'),a,Buffer.from('\0'),b]));
 const actual=identity(engine,core);if(meta.engine_sha256!==actual)throw Error('Complete computation source digest mismatch');
 if(meta.engine_file_sha256!==sha(engine)||meta.team_commons_source_sha256!==sha(core))throw Error('Component digest mismatch');
 const r=await E.selftest(read('data/capture.json'),actual,read('scenarios.json'));
 const check=(name,pass)=>{if(!pass)throw Error(name);r.checks.push({name,pass});};
 check('Engine identity binds the copied Team Commons implementation',identity(engine,Buffer.concat([core,Buffer.from(' ')]))!==actual);
 check('Engine identity binds the i3X decision implementation',identity(Buffer.concat([engine,Buffer.from(' ')]),core)!==actual);
 r.passed=r.checks.length;r.total=r.checks.length;
 fs.writeFileSync(path.join(root,'data/qualification.json'),JSON.stringify(r,null,2)+'\n');console.log(JSON.stringify(r));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
