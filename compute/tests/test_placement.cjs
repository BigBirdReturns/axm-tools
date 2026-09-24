'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),P=require('../inputs/placement.cjs'),F=require('../inputs/fixtures.cjs'),C=require('../inputs/compose.cjs');
for(const c of F.cases())test('placement: '+c.id,()=>{const r=P.place(c.request,c.snapshot,c.as_of);assert.equal(r.selected?.id??null,c.expected);assert.equal(r.execution_authorized,false);if(r.selected)assert.equal(r.synthetic,true);});
function run(mut){let r=F.request(),s=F.snapshot();mut(r,s);return P.place(r,s,F.NOW);}
const mutations=[
 ['missing quote term',s=>{delete s.candidates[1].quote.minimum_charge_s;}],
 ['negative rate',s=>{s.candidates[1].quote.allocation_hour_usd=-1;}],
 ['future supply',s=>{s.candidates[1].supply.observed_at='2030-01-01T00:00:00Z';}],
 ['unknown availability',s=>{s.candidates[1].supply.state='unknown';}],
 ['wrong tenant',s=>{s.candidates[1].tenant_id='victim';}],
 ['planned environment cannot be warm',s=>{s.candidates[1].environment.basis='planned';}],
 ['too-small qualification envelope',s=>{s.candidates[1].performance.maximum_units=10;}],
 ['result-reuse claim requires separate proof',s=>{s.candidates[1].performance.reusable_result=true;}],
 ['acquisition not same as warm allocation',s=>{s.candidates[1].supply.state='available';}],
 ['bad digest',s=>{s.candidates[1].performance.source_sha256='partial';}],
];
for(const [name,m] of mutations)test('hold '+name,()=>{const r=run((_r,s)=>m(s));assert.equal(r.selected.id,'do');assert.ok(r.held.some(x=>x.id==='ha'));});
test('provider fame and medal fields have zero influence',()=>{const a=run(()=>{}),b=run((_r,s)=>{for(const c of s.candidates){c.medal='Platinum';c.followers=1e9;c.endorsement='buy this';}});assert.deepEqual(a.selected,b.selected);});
test('identity permutation with policy also renamed keeps numerical choice',()=>{const r=run((r,s)=>{r.allowed_providers=['alpha','beta','gamma'];s.candidates.forEach((c,i)=>c.provider=r.allowed_providers[i]);});assert.equal(r.selected.id,'ha');});
test('zero/invalid/fractional units refuse',()=>{for(const n of [0,-1,1.5,Infinity])assert.throws(()=>run(r=>r.units=n));});
test('empty destination policy refuses',()=>assert.throws(()=>run(r=>r.allowed_providers=[])));
test('duplicate candidates refuse',()=>assert.throws(()=>run((_r,s)=>s.candidates.push(F.copy(s.candidates[0])))));
test('prototype names do not change map behavior',()=>{const r=run((_r,s)=>s.candidates[1].id='__proto__');assert.equal(r.selected.id,'__proto__');});
test('cache savings do not cross unit counts',()=>{const c=F.cases().find(x=>x.id==='matching_cache_avoids_reloading');c.snapshot.candidates[1].cache.units=1;assert.equal(P.place(c.request,c.snapshot,F.NOW).selected.id,'do');});
test('synthetic and real cannot compete',()=>{const r=run((_r,s)=>{const c=s.candidates[1];c.synthetic=false;c.environment.basis='observed';c.performance.basis='retained_observation';});assert.equal(r.status,'HOLD');assert.match(r.reason,/Synthetic/);});
test('cost includes ingress, storage, validation, holding and release',()=>{const a=run(()=>{}),b=run((r,s)=>{r.budget_usd=10;const c=s.candidates[1];c.quote.storage_usd=.01;c.quote.validation_usd=.01;c.quote.ingress_usd_per_gb=1;c.quote.retention_s=120;c.performance.release_s=120;});assert.ok(b.eligible.find(c=>c.id==='ha').estimated_total_usd>a.selected.estimated_total_usd);});
test('source fingerprints retained and no execution key',()=>{const r=run(()=>{});assert.equal(r.request_sha256.length,64);assert.equal(r.selected.commitments.quote,F.hash(9));assert.equal(r.execution_authorized,false);});
test('supply join does not renew independent quote terms',()=>{const s=F.snapshot();const c=s.candidates[1];c.synthetic=false;c.performance.basis='retained_observation';c.environment.basis='planned';c.quote.lifecycle='acquire';c.supply_offer_id='type1';const o={schema:'second-run/supply-observation@1',synthetic:false,observed_at:'2026-09-24T19:00:00Z',expires_at:'2026-09-24T19:02:00Z',source_sha256:F.hash(8),offers:[{id:'type1',provider:'hotaisle',region:null,availability:'available',quantity:1,allocation_hour_usd:3,minimum_charge_s:3600}]};const j=C.compose(s,o).snapshot.candidates[1];assert.equal(j.quote.expires_at,c.quote.expires_at);assert.equal(j.quote.minimum_charge_s,3600);assert.equal(s.candidates[1].quote.minimum_charge_s,60);});
test('catalog cannot impersonate allocated runtime',()=>{const s=F.snapshot();s.candidates[1].supply_offer_id='type1';assert.throws(()=>C.compose(s,{schema:'second-run/supply-observation@1',synthetic:false,offers:[{id:'type1',provider:'hotaisle'}]}));});

test('nonfinite input cannot receive a stable commitment',()=>assert.throws(()=>run((_r,s)=>s.candidates[1].performance.acceptance_fraction=NaN)));
