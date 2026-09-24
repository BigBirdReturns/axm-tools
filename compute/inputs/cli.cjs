#!/usr/bin/env node
'use strict';
const fs=require('node:fs'),path=require('node:path'),P=require('./placement.cjs');
function read(p){const st=fs.lstatSync(p);if(!st.isFile()||st.isSymbolicLink()||st.size>2*1024*1024)throw Error('Only regular JSON files up to 2 MiB');return JSON.parse(fs.readFileSync(p,'utf8'));}
try{
 const [cmd,...args]=process.argv.slice(2);let result;
 if(cmd==='demo'&&!args.length){result={evidence:'SYNTHETIC_POLICY_CASES',executed:false,results:require('./fixtures.cjs').cases().map(c=>({id:c.id,expected:c.expected,result:P.place(c.request,c.snapshot,c.as_of)}))};}
 else if(cmd==='place'&&[2,3].includes(args.length)){result=P.place(read(args[0]),read(args[1]),args[2]||new Date().toISOString());}
 else if(cmd==='compose'&&args.length===2){result=require('./compose.cjs').compose(read(args[0]),read(args[1]));}
 else throw Error('Use: node inputs/cli.cjs demo | place REQUEST.json INPUTS.json [AS_OF] | compose INPUTS.json SUPPLY.json');
 console.log(JSON.stringify(result,null,2));if(result.status==='HOLD')process.exitCode=2;
}catch(e){console.error('REQUEST INPUTS: '+e.message);process.exitCode=2;}
