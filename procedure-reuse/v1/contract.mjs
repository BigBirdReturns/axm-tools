/* AXM Procedure Reuse 1.0.0. Pure caller-side rules; no browser or provider access. */
export const VERSION = 'axm-procedure-reuse/1.0.0';
export const EXPECTED = Object.freeze({account:'DEMO-A', record:'R-1042', item:'KIT-01', effect:'draft.local.save', quantity:3, status:'DRAFT'});
export const CASES = Object.freeze(['baseline','cosmetic-drift','semantic-drift','postcondition-failure']);
export const VERDICTS = Object.freeze(['PASS','PASS','UNKNOWN','FAIL']);
export function admit(observed, binding) {
  if (!observed || !binding || typeof binding.run!=='string' || !binding.run || typeof binding.origin!=='string' || !binding.origin || !Number.isInteger(binding.case) || binding.case<1 || binding.case>4) return {decision:'UNKNOWN', reason:'Missing caller binding'};
  if (observed.origin !== binding.origin || observed.run !== binding.run || observed.case !== binding.case) return {decision:'UNKNOWN', reason:'Origin, run or case changed'};
  for (const key of ['account','record','item','effect']) {
    if (observed[key] !== EXPECTED[key]) return {decision:'UNKNOWN', reason:`Changed ${key}`};
  }
  if (observed.saveTargets !== 1 || observed.quantityTargets !== 1 || observed.dialogs !== 0) return {decision:'UNKNOWN', reason:'Ambiguous or obstructed controls'};
  return {decision:'ADMIT', reason:'Observed preconditions match the pinned contract'};
}
export function verify(readback, binding) {
  if (!readback || !readback.record || !binding) return {verdict:'UNKNOWN', reason:'No fresh saved-record evidence'};
  if (readback.run !== binding.run || readback.case !== binding.case) return {verdict:'UNKNOWN', reason:'Read-back belongs to a different run or case'};
  const r = readback.record;
  if (!['account','id','item','quantity','status','revision'].every(k=>Object.hasOwn(r,k)) || !['saveAttempts','externalAttempts','readSequence','lastSaveSequence'].every(k=>Number.isSafeInteger(readback[k]))) return {verdict:'UNKNOWN', reason:'Incomplete or malformed read-back evidence'};
  if (r.account !== EXPECTED.account || r.id !== EXPECTED.record || r.item !== EXPECTED.item) return {verdict:'FAIL', reason:'Saved identity is wrong'};
  if (r.quantity !== EXPECTED.quantity || r.status !== EXPECTED.status || r.revision !== 1) return {verdict:'FAIL', reason:'Saved record does not satisfy the requested postcondition'};
  if (readback.saveAttempts !== 1 || readback.externalAttempts !== 0 || readback.readSequence <= readback.lastSaveSequence) return {verdict:'FAIL', reason:'Write count, effect boundary or read order is wrong'};
  return {verdict:'PASS', reason:'Fresh record matches the requested local draft'};
}
export function checkReceipt(receipt) {
  const errors=[];
  if (!receipt || receipt.schema !== 'axm/procedure-reuse-fixture-receipt@1' || receipt.version !== VERSION || !receipt.run) return {conforms:false, errors:['Unknown or incomplete receipt']};
  if (!Array.isArray(receipt.cases) || receipt.cases.length !== 4) return {conforms:false, errors:['Four sealed cases are required']};
  receipt.cases.forEach((c,i)=>{
    if (!c || c.case !== i+1 || c.run !== receipt.run || c.reportedVerdict !== VERDICTS[i]) errors.push(`Case ${i+1}: wrong identity or verdict`);
    if (!c || !Array.isArray(c.events) || !c.readback || !c.readback.record) {errors.push(`Case ${i+1}: evidence missing`);return;}
    const events=c.events;
    if (!events.every((e,j)=>e && e.sequence===j && ['edit','save-attempt','external-attempt','read-back','caller-verdict','page-reload'].includes(e.type))) errors.push(`Case ${i+1}: malformed event sequence`);
    const counts={saves:events.filter(e=>e.type==='save-attempt').length, external:events.filter(e=>e.type==='external-attempt').length, edits:events.filter(e=>e.type==='edit').length};
    if (counts.external || (i===2 ? counts.saves!==0 || counts.edits!==0 : counts.saves!==1)) errors.push(`Case ${i+1}: forbidden action or repeated save`);
    const actual=verify(c.readback,{run:receipt.run,case:i+1});
    if (i!==2 && actual.verdict!==VERDICTS[i]) errors.push(`Case ${i+1}: read-back contradicts expected outcome`);
    if (i===2 && (c.effect===EXPECTED.effect || c.readback.record.quantity!==1 || c.readback.record.revision!==0)) errors.push('Case 3: unsafe effect or untouched record was not demonstrated');
    if (c.readback.saveAttempts!==counts.saves || c.readback.externalAttempts!==counts.external) errors.push(`Case ${i+1}: counters disagree`);
    const lastRead=events.filter(e=>e.type==='read-back').at(-1);
    const lastSave=events.filter(e=>e.type==='save-attempt').at(-1);
    if (!lastRead || lastRead.sequence!==c.readback.readSequence || c.readback.lastSaveSequence!==(lastSave?.sequence ?? -1)) errors.push(`Case ${i+1}: evidence order disagrees`);
  });
  if (!Number.isInteger(receipt.reloads) || receipt.reloads<1) errors.push('Reload continuity was not exercised');
  return {conforms:errors.length===0, errors};
}
