// SPDX-License-Identifier: Apache-2.0
const fs=require("node:fs");
const path=require("node:path");
const assert=require("node:assert/strict");
const IR=require("../app.js");

const fixture=path.join(__dirname,"../examples/synthetic-identity-export.jsonl");
const raw=fs.readFileSync(fixture,"utf8");
const parsed=IR.parse(raw);
assert.equal(parsed.length,13,"synthetic case event count");
assert.equal(IR.SAMPLE.length,13,"embedded sample count");
assert.deepEqual(IR.normalize(IR.SAMPLE),parsed,"embedded sample must equal published evidence");

const results=IR.analyze(parsed);
const rules=new Set(results.map(f=>f.rule));
for(const rule of ["PASSWORD_SPRAY","LOGIN_AFTER_FAILURES",
                   "IDENTITY_PERSISTENCE","TOKEN_TO_EXPORT","UNTRUSTED_PAYLOAD"]){
  assert(rules.has(rule),"Missing "+rule);
}
assert.equal(results.length,5,"strict synthetic finding count");
const ids=new Set(parsed.map(e=>e.id));
for(const f of results){
  assert(f.evidence_ids.every(x=>ids.has(x)),"orphan evidence");
  assert.equal(f.authority,"REQUIRES_ORGANIZATION_APPROVAL");
  assert.equal(new Set(parsed.filter(e=>f.evidence_ids.includes(e.id)).map(e=>e.tenant)).size,1);
}
const preview=JSON.stringify(IR.sharePreview(parsed,results));
for(const secret of ["203.0.113.42","svc-payments","production-secret-store","ev-001","Ignore previous instructions"]){
  assert(!preview.includes(secret),"share preview leaked "+secret);
}
assert.throws(()=>IR.parse('{"id":"x", broken}'), /Invalid JSONL/);
assert.throws(()=>IR.parse('x'.repeat(IR.MAX_BYTES+1)),/2 MB/);
assert.throws(()=>IR.normalize([parsed[0],parsed[0]]),/Repeated/);
assert.throws(()=>IR.normalize([{...parsed[0],kind:"execute"}]),/Unknown event kind/);
assert.throws(()=>IR.normalize([{...parsed[0],ts:"2026-11-16T14:00:00"}]),/Timestamp/);

const benign=IR.analyze([{id:"ok-1",ts:"2026-11-16T14:00:00Z",
 tenant:"good",kind:"auth_success",actor:"owner",src:"192.0.2.8",
 target:"sso",outcome:"success"}]);
assert.deepEqual(benign,[],"legitimate lone auth not suspicious");
console.log("Browser engine PASS: 13 synthetic events, 5 findings, tenant isolation, source parity, safe preview, rejects, benign control");
