
"use strict";
const defaults = {n:100000,floor:90,fa:0,va:0.10,pa:95,fb:12000,vb:0.03,pb:85};
const numberFormat = new Intl.NumberFormat('en-US',{maximumFractionDigits:2});
const dollars = x => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(x);
const unit = x => '$' + x.toLocaleString('en-US',{minimumFractionDigits:4,maximumFractionDigits:4});
function validateInputs(x){
  const keys=Object.keys(defaults);
  if(keys.some(k=>typeof x[k]!== 'number'||!Number.isFinite(x[k]))) throw new Error('Enter a finite number in every field. Blank fields are not zero.');
  if(!Number.isInteger(x.n)||x.n<1||x.n>1e12) throw new Error('Submitted jobs must be a whole number from 1 to 1,000,000,000,000.');
  if(x.floor<0||x.floor>100) throw new Error('The minimum success rate must be between 0% and 100%.');
  for(const k of ['pa','pb']) if(x[k]<0.001||x[k]>100) throw new Error('Both scenario success rates must be at least 0.001% and no more than 100%.');
  for(const k of ['fa','fb']) if(x[k]<0||x[k]>1e12) throw new Error('Fixed costs must be nonnegative and no greater than one trillion USD.');
  for(const k of ['va','vb']) if(x[k]<0||x[k]>1e9) throw new Error('Variable costs must be nonnegative and no greater than one billion USD per job.');
}
function computeScenario(x){
  validateInputs(x);
  const result=(f,v,pct)=>{const p=pct/100;return {total:f+x.n*v,accepted:x.n*p,cost:(f+x.n*v)/(x.n*p),passes:pct+1e-12>=x.floor};};
  const a=result(x.fa,x.va,x.pa), b=result(x.fb,x.vb,x.pb);
  // cA-cB = intercept/N + slope, with rates in fractions.
  const intercept=x.fa/(x.pa/100)-x.fb/(x.pb/100);
  const slope=x.va/(x.pa/100)-x.vb/(x.pb/100);
  let crossover=null;
  if(slope!==0){const n=-intercept/slope;if(Number.isFinite(n)&&n>0)crossover=n;}
  return {a,b,crossover,identical:intercept===0&&slope===0};
}
function readInputs(){const x={};for(const k of Object.keys(defaults)){const t=document.getElementById(k).value.trim();x[k]=t===''?NaN:Number(t);}return x;}
function resultMarkup(r){return `<div class="value">${unit(r.cost)}</div><div class="unit">per verified successful task</div><p>${dollars(r.total)} total / ${numberFormat.format(r.accepted)} expected successful tasks</p><span class="status ${r.passes?'pass':'fail'}">${r.passes?'Meets stated success-rate floor':'Fails stated success-rate floor'}</span>`;}
let current=null;
function update(){
 try{
  const x=readInputs(),r=computeScenario(x);current={x,r};
  document.getElementById('input-error').hidden=true;document.getElementById('export').disabled=false;
  document.getElementById('a-result').innerHTML=resultMarkup(r.a);document.getElementById('b-result').innerHTML=resultMarkup(r.b);
  let gate;
  if(!r.a.passes&&!r.b.passes)gate='Neither scenario meets the stated success-rate floor. A cost comparison cannot make either eligible.';
  else if(r.a.passes&&!r.b.passes)gate='Only A meets the stated success-rate floor. B remains ineligible even where its cost per successful task is lower.';
  else if(!r.a.passes&&r.b.passes)gate='Only B meets the stated success-rate floor. A remains ineligible even where its cost per successful task is lower.';
  else {const tie=Math.abs(r.a.cost-r.b.cost)<1e-10;gate=tie?'Both meet the success-rate floor and have the same calculated unit cost.':`Both meet the success-rate floor. ${r.a.cost<r.b.cost?'A':'B'} has the lower calculated unit cost at this volume; other constraints still require separate verification.`;}
  let cross=r.identical?'The two cost-per-success functions are identical under these inputs.':r.crossover!==null?`The mathematical crossover is ${numberFormat.format(r.crossover)} submitted jobs (about ${Math.ceil(r.crossover).toLocaleString('en-US')} whole jobs). This does not override a failed acceptance gate.`:'There is no positive-volume cost crossover under these constant-input assumptions.';
  document.getElementById('comparison').textContent=gate+' '+cross;
 }catch(e){
  current=null;document.getElementById('export').disabled=true;
  const el=document.getElementById('input-error');el.textContent=e.message;el.hidden=false;
  document.getElementById('a-result').textContent='Awaiting valid inputs.';document.getElementById('b-result').textContent='Awaiting valid inputs.';
  document.getElementById('comparison').textContent='Correct the inputs to calculate. Previous outputs have been cleared.';
 }
}
document.getElementById('cost-form').addEventListener('input',update);
document.getElementById('cost-form').addEventListener('submit',e=>e.preventDefault());
document.getElementById('cost-form').addEventListener('reset',()=>setTimeout(update,0));
document.getElementById('high-volume').addEventListener('click',()=>{document.getElementById('n').value='1000000';update();});
document.getElementById('export').addEventListener('click',()=>{
 if(!current)return;
 const data={schema:'open-ai-economics/scenario-v1',exported_at:new Date().toISOString(),assumption_status:'user-entered illustrative assumptions; not vendor prices or measured benchmarks',horizon:'same user-defined accounting horizon for both alternatives',inputs:current.x,results:current.r,formula:'(F + N*v)/(N*p)',notes:['p is a fraction, while pa/pb inputs are percentages.','Fixed costs, variable costs and success rates are assumed constant.','Acceptance gate checks only the user-specified success-rate floor.','Error losses, capacity steps and additional security/legal constraints are not modeled.']};
 const u=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=u;a.download='ai-economics-scenario.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),2000);
});
window.economicsModel={computeScenario,validateInputs,defaults};
update();
