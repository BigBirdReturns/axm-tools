'use strict';
/* Request-conditioned placement arithmetic. Built-in modules only. No execution. */
const crypto = require('node:crypto');
const VERSION = '0.1.0';
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fail = message => { throw Error(message); };
const obj = (x, name) => { if (!x || typeof x !== 'object' || Array.isArray(x)) fail(name + ': object required'); return x; };
const text = (x, name) => { if (typeof x !== 'string' || !x.trim() || x.length > 512) fail(name + ': bounded text required'); return x; };
const num = (x, name, min = 0, max = Number.MAX_SAFE_INTEGER) => { if (typeof x !== 'number' || !Number.isFinite(x) || x < min || x > max) fail(name + ': finite number out of range'); return x; };
const digest = (x, name) => { if (typeof x !== 'string' || !/^[a-f0-9]{64}$/.test(x)) fail(name + ': SHA-256 required'); return x; };
function instant(x, name) { text(x, name); if (!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(x) || !Number.isFinite(Date.parse(x))) fail(name + ': timezone-qualified timestamp required'); return Date.parse(x); }
function list(x, name, max = 100) { if (!Array.isArray(x) || x.length > max) fail(name + ': bounded array required'); return x; }
function canonical(x) { if (Array.isArray(x)) return '[' + x.map(canonical).join(',') + ']'; if (x && typeof x === 'object') return '{' + Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',') + '}'; if (typeof x === 'number' && !Number.isFinite(x)) fail('Nonfinite input'); return JSON.stringify(x); }
function fresh(record, now, name) { obj(record, name); const t=instant(record.observed_at,name+'.observed_at'), e=instant(record.expires_at,name+'.expires_at'); digest(record.source_sha256,name+'.source_sha256'); if (e<=t || t>now) fail(name+': invalid observation interval'); if (now>=e) fail(name+': expired'); }
function requestContract(r) {
 obj(r,'request'); if(r.schema!=='second-run/request-placement@1') fail('Unsupported request schema');
 text(r.tenant_id,'tenant_id'); digest(r.workload_sha256,'workload_sha256'); digest(r.validator_sha256,'validator_sha256');
 num(r.units,'units',1,1000000); if(!Number.isInteger(r.units)) fail('units must be integer');
 num(r.deadline_s,'deadline_s',0.001); num(r.budget_usd,'budget_usd'); num(r.minimum_acceptance,'minimum_acceptance',0,1);
 num(r.input_gb,'input_gb'); num(r.output_gb,'output_gb');
 if(!['local_only','allow_remote'].includes(r.data_policy)) fail('Unsupported data policy');
 list(r.allowed_providers,'allowed_providers').forEach(x=>text(x,'provider'));
 list(r.allowed_regions,'allowed_regions').forEach(x=>text(x,'region'));
 if(!r.allowed_providers.length || !r.allowed_regions.length) fail('Explicit provider and region allowlists required');
 if(r.cache_key!==null) digest(r.cache_key,'cache_key');
 return r;
}
function scoreCandidate(c,r,now) {
 obj(c,'candidate'); text(c.id,'candidate.id'); text(c.provider,'candidate.provider'); text(c.region,'candidate.region');
 if(typeof c.local!=='boolean' || typeof c.synthetic!=='boolean') fail('local and synthetic must be explicit booleans');
 if(!r.allowed_providers.includes(c.provider) || !r.allowed_regions.includes(c.region)) fail('Destination outside request policy');
 if(r.data_policy==='local_only'&&!c.local) fail('Private data requires local execution');
 if(c.tenant_id!==r.tenant_id) fail('Candidate tenant does not match');
 fresh(c.supply,now,'supply');
 if(!['available','allocated'].includes(c.supply.state)) fail('No observed available or allocated capacity');
 if(c.supply.state==='available'&&!(num(c.supply.quantity,'supply.quantity')>=1)) fail('No observed available capacity');
 const q=obj(c.quote,'quote'); fresh(q,now,'quote');
 for(const k of ['allocation_hour_usd','minimum_charge_s','billing_quantum_s','ingress_usd_per_gb','egress_usd_per_gb','fixed_usd','retention_s','storage_usd','validation_usd']) num(q[k],'quote.'+k,k==='billing_quantum_s'?0.001:0);
 if(!['acquire','reuse'].includes(q.lifecycle)) fail('quote.lifecycle must distinguish a new lease from reuse');
 if(q.lifecycle==='reuse'&&c.supply.state!=='allocated') fail('Reuse requires an allocated resource');
 const p=obj(c.performance,'performance'); fresh(p,now,'performance');
 if(!['retained_observation','operator_estimate','synthetic'].includes(p.basis)) fail('Unknown performance evidence basis');
 if(c.synthetic!==(p.basis==='synthetic')) fail('Synthetic label disagrees with performance basis');
 if(p.workload_sha256!==r.workload_sha256 || p.validator_sha256!==r.validator_sha256) fail('Workload or validator does not match qualification');
 digest(p.runtime_sha256,'runtime_sha256'); digest(p.model_sha256,'model_sha256');
 fresh(c.environment,now,'environment');
 if(c.environment.runtime_sha256!==p.runtime_sha256 || c.environment.model_sha256!==p.model_sha256) fail('Current/planned environment differs from performance qualification');
 if(!['observed','planned','synthetic'].includes(c.environment.basis)) fail('Environment basis not supported');
 if((c.environment.basis==='synthetic')!==c.synthetic) fail('Environment synthetic status mismatch');
 if(q.lifecycle==='reuse'&&c.environment.basis==='planned') fail('Warm reuse requires observed environment identity');
 if(p.reusable_result===true) fail('Result reuse requires a separate validated artifact contract, not a throughput estimate');
 num(p.acceptance_fraction,'acceptance_fraction',0,1); if(p.acceptance_fraction<r.minimum_acceptance || p.acceptance_fraction===0) fail('Acceptance estimate below request threshold');
 num(p.units_per_second,'units_per_second',0.000000001); num(p.maximum_units,'maximum_units',1); if(r.units>p.maximum_units) fail('Request exceeds calibrated workload envelope');
 for(const k of ['queue_s','setup_s','load_s','verify_s','release_s','latency_margin_s']) num(p[k],'performance.'+k);
 num(p.transfer_gb_per_s,'performance.transfer_gb_per_s',0.000000001);
 let cacheUsed=false, cacheReason='No compatible cache observation', load=p.load_s, run=r.units/p.units_per_second;
 if(r.cache_key && c.cache) {
  try {
   fresh(c.cache,now,'cache');
   for(const k of ['tenant_id','key','model_sha256','runtime_sha256']) {
    const expected=k==='tenant_id'?r.tenant_id:k==='key'?r.cache_key:p[k];
    if(c.cache[k]!==expected) fail('Cache identity mismatch: '+k);
   }
   if(c.cache.workload_sha256!==r.workload_sha256 || c.cache.units!==r.units) fail('Cache workload or unit-count mismatch');
   if(!['observed','synthetic'].includes(c.cache.basis)) fail('Cache basis not supported');
   if((c.cache.basis==='synthetic')!==c.synthetic) fail('Synthetic cache mismatch');
   num(c.cache.load_saved_s,'cache.load_saved_s',0,p.load_s);
   num(c.cache.run_saved_s,'cache.run_saved_s',0,run);
   load-=c.cache.load_saved_s; run-=c.cache.run_saved_s; cacheUsed=true; cacheReason='Exact tenant, workload, model, runtime and cache key; unexpired supplied estimate';
  }catch(e){cacheReason=e.message;}
 }
 const transfer=c.local?0:(r.input_gb+r.output_gb)/p.transfer_gb_per_s;
 const completion=transfer+p.queue_s+p.setup_s+load+run+p.verify_s+p.latency_margin_s;
 const untilRelease=completion+p.release_s+q.retention_s;
 const billedSeconds=Math.ceil(Math.max(untilRelease,q.minimum_charge_s)/q.billing_quantum_s)*q.billing_quantum_s;
 const cost=q.allocation_hour_usd*billedSeconds/3600+r.input_gb*q.ingress_usd_per_gb+r.output_gb*q.egress_usd_per_gb+q.fixed_usd+q.storage_usd+q.validation_usd;
 num(cost,'derived cost'); num(completion,'derived time');
 if(cost>r.budget_usd) fail('Modeled total cost exceeds request budget');
 if(completion>r.deadline_s) fail('Modeled completion exceeds deadline');
 const accepted=r.units*p.acceptance_fraction;
 return {id:c.id,provider:c.provider,region:c.region,synthetic:c.synthetic,input_basis:p.basis,
  estimated_total_usd:cost,estimated_accepted_units:accepted,usd_per_expected_accepted:cost/accepted,
  estimated_completion_s:completion,billable_s:billedSeconds,cache_used:cacheUsed,cache_reason:cacheReason,
  components:{transfer_s:transfer,queue_s:p.queue_s,setup_s:p.setup_s,load_s:load,run_s:run,verify_s:p.verify_s,latency_margin_s:p.latency_margin_s,release_s:p.release_s,retention_s:q.retention_s},
  lifecycle:q.lifecycle,minimum_charge_s:q.minimum_charge_s,
  commitments:{supply:c.supply.source_sha256,quote:q.source_sha256,performance:p.source_sha256,cache:cacheUsed?c.cache.source_sha256:null},
  executor_hint:typeof c.executor_hint==='string'?c.executor_hint:'existing execution owner'};
}
function place(request,snapshot,now=new Date().toISOString()) {
 const r=requestContract(request); obj(snapshot,'snapshot'); if(snapshot.schema!=='second-run/placement-inputs@1') fail('Unsupported input snapshot');
 const time=instant(now,'as_of'); list(snapshot.candidates,'candidates',100); const seen=new Set();
 const eligible=[],held=[];
 for(const c of snapshot.candidates) {
  const id=c&&c.id;
  if(typeof id!=='string'||!id||seen.has(id)) fail('Candidate identifiers must be nonempty and unique'); seen.add(id);
  try{eligible.push(scoreCandidate(c,r,time));}catch(e){held.push({id,reason:e.message});}
 }
 const mixed=new Set(eligible.map(c=>c.synthetic)).size>1;
 if(mixed) return {schema:'second-run/placement-result@1',version:VERSION,status:'HOLD',reason:'Synthetic and non-synthetic candidates cannot compete in one placement',execution_authorized:false,eligible:[],held};
 eligible.sort((a,b)=>a.usd_per_expected_accepted-b.usd_per_expected_accepted||a.estimated_completion_s-b.estimated_completion_s||a.id.localeCompare(b.id));
 return {schema:'second-run/placement-result@1',version:VERSION,as_of:now,status:eligible.length?'PLACEMENT_CALCULATED':'HOLD',
  execution_authorized:false,synthetic:eligible.length?eligible[0].synthetic:null,
  selected:eligible[0]||null,eligible,held,
  request_sha256:sha(canonical(r)),inputs_sha256:sha(canonical(snapshot)),
  scope:'Conditional cost model from supplied observations. Does not authenticate inputs, reserve capacity, enforce a billing cap, execute or retry work. Recheck state at execution admission. No medals, endorsements or provider preference affect arithmetic.'};
}
module.exports={VERSION,place,scoreCandidate,requestContract,canonical};
