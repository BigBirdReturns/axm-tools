'use strict';
const {canonical}=require('./placement.cjs'), crypto=require('node:crypto');
function compose(template,observation) {
 if(template?.schema!=='second-run/placement-inputs@1'||observation?.schema!=='second-run/supply-observation@1') throw Error('Unsupported compose schemas');
 if(observation.synthetic!==false) throw Error('Only explicitly non-synthetic captured supply may enter this join');
 if(!Array.isArray(observation.offers)||!Array.isArray(template.candidates)) throw Error('Arrays required');
 const byId=new Map(); for(const o of observation.offers){if(byId.has(o.id))throw Error('Duplicate supply offer id');byId.set(o.id,o);}
 const out=JSON.parse(JSON.stringify(template)); const held=[];
 for(const c of out.candidates) {
  if(!c.supply_offer_id) continue;
  const row=byId.get(c.supply_offer_id);
  if(!row){held.push({id:c.id,reason:'No matching source offer'});c.supply={...c.supply,state:'unknown'};continue;}
  if(c.provider!==row.provider||c.quote.lifecycle!=='acquire'||c.synthetic) throw Error('Join requires matching provider, new-lease lifecycle and non-synthetic qualification');
  const existingQuote=c.quote; const expires=[existingQuote.expires_at,observation.expires_at];
  if(expires.some(t=>!Number.isFinite(Date.parse(t))))throw Error('Missing independent quote/supply expiry');
  c.supply={state:row.availability,quantity:row.quantity,observed_at:observation.observed_at,expires_at:observation.expires_at,source_sha256:observation.source_sha256};
  const evidence={terms:existingQuote.source_sha256,offer:observation.source_sha256};
  c.quote={...existingQuote,allocation_hour_usd:row.allocation_hour_usd,minimum_charge_s:row.minimum_charge_s,
   observed_at:[existingQuote.observed_at,observation.observed_at].sort((a,b)=>Date.parse(a)-Date.parse(b)).pop(),
   expires_at:expires.sort((a,b)=>Date.parse(a)-Date.parse(b))[0],source_sha256:crypto.createHash('sha256').update(canonical(evidence)).digest('hex'),source_components:evidence};
  if(row.region!==null&&row.region!==c.region)throw Error('Region mismatch');
  c.source_region_scope=row.region===null?'Source offer has no region; candidate region remains separately supplied':'matched';
 }
 return {snapshot:out,join_holds:held,scope:'Observed rate/minimum/availability only. Existing terms expire independently. No automatic catalog overwrite or runtime qualification.'};
}
module.exports={compose};
