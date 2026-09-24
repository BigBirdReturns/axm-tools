'use strict';
// AUTHORED synthetic conditions for testing policy and arithmetic, not cloud observations.
const NOW='2026-09-24T19:00:00Z', hash=n=>String(n).repeat(64);
const observation=()=>({observed_at:'2026-09-24T18:59:50Z',expires_at:'2026-09-24T19:01:00Z',source_sha256:hash(9)});
function request(){return {schema:'second-run/request-placement@1',tenant_id:'demo',workload_sha256:hash(1),validator_sha256:hash(2),units:1000,deadline_s:10,budget_usd:1,minimum_acceptance:0.9,input_gb:0.01,output_gb:0.001,data_policy:'allow_remote',allowed_providers:['local','hotaisle','digitalocean'],allowed_regions:['device','demo-region'],cache_key:null};}
function candidate(id,provider,rate,throughput,local=false){return {id,provider,local,synthetic:true,tenant_id:'demo',region:local?'device':'demo-region',executor_hint:local?'existing local runtime':'existing approved endpoint; dstack for separately approved acquisition',
 supply:{...observation(),state:'allocated',quantity:1},
 environment:{...observation(),basis:'synthetic',model_sha256:hash(3),runtime_sha256:hash(4)},
 quote:{...observation(),lifecycle:'reuse',allocation_hour_usd:rate,minimum_charge_s:local?0:60,billing_quantum_s:local?1:60,ingress_usd_per_gb:0,egress_usd_per_gb:0,fixed_usd:0,retention_s:0,storage_usd:0,validation_usd:0},
 performance:{...observation(),basis:'synthetic',workload_sha256:hash(1),validator_sha256:hash(2),model_sha256:hash(3),runtime_sha256:hash(4),acceptance_fraction:0.95,units_per_second:throughput,maximum_units:10000,queue_s:0,setup_s:local?0:0.05,load_s:0,verify_s:0.02,release_s:0.02,latency_margin_s:0.01,transfer_gb_per_s:0.1}};}
function snapshot(){return {schema:'second-run/placement-inputs@1',candidates:[candidate('local','local',0.12,40,true),candidate('ha','hotaisle',2.99,250),candidate('do','digitalocean',4.41,180)]};}
const copy=x=>JSON.parse(JSON.stringify(x));
function cases(){const out=[];function add(id,mutate,expected){let r=request(),s=snapshot();mutate(r,s);out.push({id,request:r,snapshot:s,as_of:NOW,expected});}
 add('warm_ha_batch',()=>{},'ha');
 add('tiny_work_stays_local',r=>{r.units=10;r.deadline_s=2;},'local');
 add('private_work_stays_local',r=>{r.data_policy='local_only';r.deadline_s=40;},'local');
 add('minimum_lease_beats_hourly_ad',(_r,s)=>{s.candidates[1].quote.minimum_charge_s=3600;},'do');
 add('warm_but_queued_loses',(_r,s)=>{s.candidates[1].performance.queue_s=20;},'do');
 add('egress_can_reverse_price',(_r,s)=>{s.candidates[1].quote.egress_usd_per_gb=200;},'do');
 add('stale_stock_is_not_free_stock',(_r,s)=>{s.candidates[1].supply.expires_at=NOW;},'do');
 add('runtime_drift_needs_requalification',(_r,s)=>{s.candidates[1].environment.runtime_sha256=hash(8);},'do');
 add('matching_cache_avoids_reloading',(r,s)=>{r.cache_key=hash(7);const c=s.candidates[1];c.performance.load_s=100;c.cache={...observation(),basis:'synthetic',tenant_id:'demo',key:r.cache_key,model_sha256:hash(3),runtime_sha256:hash(4),workload_sha256:hash(1),units:r.units,load_saved_s:100,run_saved_s:0};},'ha');
 add('cross_tenant_cache_is_ignored',(r,s)=>{r.cache_key=hash(7);const c=s.candidates[1];c.performance.load_s=100;c.cache={...observation(),basis:'synthetic',tenant_id:'other',key:r.cache_key,model_sha256:hash(3),runtime_sha256:hash(4),workload_sha256:hash(1),units:r.units,load_saved_s:100,run_saved_s:0};},'do');
 add('no_eligible_route_holds',r=>{r.budget_usd=0;},null);
 add('unqualified_faster_model_is_held',(_r,s)=>{s.candidates[1].performance.validator_sha256=hash(6);s.candidates[1].performance.units_per_second=100000;},'do');
 return out;}
module.exports={NOW,hash,request,snapshot,candidate,cases,copy};
