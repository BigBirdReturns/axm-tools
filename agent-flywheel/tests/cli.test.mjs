import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, readFile, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';

const script=fileURLToPath(new URL('../scripts/run.mjs',import.meta.url));
function command(args) {
  return new Promise((resolve,reject)=>{
    const child=spawn(process.execPath,[script,...args],{stdio:['ignore','pipe','pipe']});
    let out='',err='';
    child.stdout.on('data',data=>{out+=data});child.stderr.on('data',data=>{err+=data});
    child.on('error',reject);child.on('close',code=>resolve({code,out,err}));
  });
}

test('portable CLI executes the explicit demonstration and verifies its retained report',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'flywheel-cli-'));
  try {
    const path=join(dir,'result.json');
    const run=await command(['--demo','--output',path]);
    assert.equal(run.code,0,run.err+'\n'+run.out);
    const report=JSON.parse(await readFile(path,'utf8'));
    assert.equal(report.schema,'axm.agent-flywheel.report.v1');
    assert.equal(report.status,'completed');
    const checked=await command(['--verify',path]);
    assert.equal(checked.code,0,checked.err+'\n'+checked.out);
    assert.equal(JSON.parse(checked.out).valid,true);
  } finally {await rm(dir,{recursive:true,force:true});}
});

test('portable CLI preserves an existing result before starting a model run',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'flywheel-existing-'));
  try {
    const path=join(dir,'result.json');
    await writeFile(path,'existing result\n');
    const result=await command(['--demo','--output',path]);
    assert.equal(result.code,1);
    assert.match(result.err,/already exists/);
    assert.equal(await readFile(path,'utf8'),'existing result\n');
  } finally {await rm(dir,{recursive:true,force:true});}
});
