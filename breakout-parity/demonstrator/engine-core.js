"use strict";

let state;

function clone(x){return JSON.parse(JSON.stringify(x));}
function clamp(x,a,b){return Math.max(a,Math.min(b,x));}
function pct(x){return `${(x*100).toFixed(1)}%`;}
function fmtMonth(x){return Number.isFinite(x)?`${x.toFixed(1)} mo`:"—";}
function nowIso(){return new Date().toISOString();}
function stable(obj){if(Array.isArray(obj))return `[${obj.map(stable).join(",")}]`;if(obj&&typeof obj==="object")return `{${Object.keys(obj).sort().map(k=>JSON.stringify(k)+":"+stable(obj[k])).join(",")}}`;return JSON.stringify(obj);}
async function sha256(text){
  if(globalThis.crypto&&globalThis.crypto.subtle){const buf=await globalThis.crypto.subtle.digest("SHA-256",new TextEncoder().encode(text));return [...new Uint8Array(buf)].map(b=>b.toString(16).padStart(2,"0")).join("");}
  const K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49bc174,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
  const H=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
  const bytes=[...new TextEncoder().encode(text)],bitLen=bytes.length*8;bytes.push(0x80);while(bytes.length%64!==56)bytes.push(0);for(let i=7;i>=0;i--)bytes.push((bitLen/2**(i*8))&255);
  const rotr=(x,n)=>(x>>>n)|(x<<(32-n));
  for(let off=0;off<bytes.length;off+=64){const w=new Uint32Array(64);for(let i=0;i<16;i++)w[i]=((bytes[off+i*4]<<24)|(bytes[off+i*4+1]<<16)|(bytes[off+i*4+2]<<8)|bytes[off+i*4+3])>>>0;for(let i=16;i<64;i++){const s0=rotr(w[i-15],7)^rotr(w[i-15],18)^(w[i-15]>>>3),s1=rotr(w[i-2],17)^rotr(w[i-2],19)^(w[i-2]>>>10);w[i]=(w[i-16]+s0+w[i-7]+s1)>>>0;}let[a,b,c,d,e,f,g,h]=H;for(let i=0;i<64;i++){const S1=rotr(e,6)^rotr(e,11)^rotr(e,25),ch=(e&f)^((~e)&g),t1=(h+S1+ch+K[i]+w[i])>>>0,S0=rotr(a,2)^rotr(a,13)^rotr(a,22),maj=(a&b)^(a&c)^(b&c),t2=(S0+maj)>>>0;h=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=b;b=a;a=(t1+t2)>>>0;}H[0]=(H[0]+a)>>>0;H[1]=(H[1]+b)>>>0;H[2]=(H[2]+c)>>>0;H[3]=(H[3]+d)>>>0;H[4]=(H[4]+e)>>>0;H[5]=(H[5]+f)>>>0;H[6]=(H[6]+g)>>>0;H[7]=(H[7]+h)>>>0;}
  return H.map(x=>x.toString(16).padStart(8,"0")).join("");
}

function initScenario(key){
  const sc=clone(SCENARIOS[key]);
  state={scenarioKey:key,scenario:sc,month:0,role:"facilitator",selected:null,holdDeclared:false,flex:false,capacityBoost:1,physicalLatency:sc.physicalLatency,signalRedundancy:sc.signalRedundancy,failedResource:null,failureEnds:null,n1Occurred:false,n1Passed:false,knownHoldouts:0,falseActions:0,dissent:[],log:[],actions:[],lastInjectIndex:-1,gate:{state:"baseline_incomplete",reason:"Baseline has not been challenged.",pass:false},resources:{},threats:sc.threats.map(t=>({...t,state:t.hidden?"hidden":"signaled",confidence:t.initialConfidence,finding:"none",observedStrategy:t.actual==="decoy"?"unknown":(t.visibility>.7?t.strategy:"unknown"),inspected:false,sampled:false,cureVerified:false,controlled:false,restored:false,breached:false,restorationDue:null,restorationAt:null,history:[]}))};
  Object.keys(sc.capacity).forEach(r=>state.resources[r]={base:sc.capacity[r],used:0});
  log("Scenario loaded",`${sc.id}: ${sc.title}`,"good");
  applyInjects();computeGate(false);render();
}

function visibleThreats(){return state.threats.filter(t=>!t.hidden||t.revealed);}
function getThreat(id){return state.threats.find(t=>t.id===id);}
function activeReal(){return state.threats.filter(t=>(t.actual==="real"||t.actual==="holdout")&&!t.controlled&&!t.breached&&state.month>=t.arrival);}
function usableCapacity(resource){const r=state.resources[resource];if(!r)return 99;let cap=r.base*state.capacityBoost;if(state.failedResource===resource&&state.month<state.failureEnds)cap*=state.flex?.55:0.05;else if(state.flex)cap*=1.15;return cap;}
function capacityLoad(){
  const active=visibleThreats().filter(t=>!t.controlled&&!t.restored&&!t.breached&&state.month>=t.arrival).length;
  const decoys=visibleThreats().filter(t=>t.actual==="decoy"&&!t.restored&&state.month>=t.arrival).length;
  const cap=Object.keys(state.resources).reduce((s,r)=>s+usableCapacity(r),0);
  return (active+decoys*.55)/Math.max(1,cap*.42);
}
function remainingStages(t){
  if(t.controlled)return 0;
  let n=0;
  if(t.state==="hidden")n+=6;
  if(t.state==="signaled")n+=5;
  if(t.state==="triaged")n+=4;
  if(!t.inspected)n+=2;
  if(!t.sampled&&t.actual!=="decoy")n+=2;
  if(t.finding==="none"||t.finding==="unresolved")n+=1.5;
  if(t.finding==="significant")n+=1;
  return n;
}
function threatMargin(t){
  if(t.controlled)return 99;
  const deadline=t.arrival+t.clock+state.physicalLatency;
  const loadPenalty=Math.max(0,capacityLoad()-1)*6;
  const ambiguityPenalty=(t.ambiguity||.5)*2.5;
  const signalPenalty=(1-(t.visibility||.5)*state.signalRedundancy)*3;
  const response=remainingStages(t)+loadPenalty+ambiguityPenalty+Math.max(0,signalPenalty)+(state.failedResource?1:0);
  return deadline-state.month-response;
}
function truthMinMargin(){const arr=activeReal().map(threatMargin);return arr.length?Math.min(...arr):24;}
function estimatedRisk(margin){let r=.25*Math.exp(-.35*margin);if(state.knownHoldouts>0)r=Math.max(r,.45);if(capacityLoad()>1.8)r=Math.max(r,.06+(capacityLoad()-1.8)*.12);return clamp(r,0,.95);}
function restorationRate(){const controlled=state.threats.filter(t=>t.controlled);if(!controlled.length)return 1;return controlled.filter(t=>t.restored&&t.restorationAt<=t.restorationDue).length/controlled.length;}
function detectHiddenHoldout(){return state.threats.some(t=>t.actual==="holdout"&&!t.revealed);}

function computeGate(commit=true){
  const margin=truthMinMargin(),risk=estimatedRisk(margin),restore=restorationRate(),load=capacityLoad();
  let gateState="operate",reason="Portfolio remains inside the qualified envelope.",pass=true;
  if(state.knownHoldouts>0||detectHiddenHoldout()) {gateState="baseline_incomplete";reason=state.knownHoldouts?"A strategically relevant holdout is outside the baseline.":"Baseline confidence remains unresolved; a hidden holdout may exist.";pass=false;}
  if(margin<6){gateState="hold";reason=`Adverse portfolio margin is ${margin.toFixed(1)} months, below the six-month floor.`;pass=false;}
  if(risk>.05){gateState="hold";reason=`Estimated breach risk is ${pct(risk)}, above the five-percent ceiling.`;pass=false;}
  if(restore<.95){gateState="hold";reason=`Restoration performance is ${pct(restore)}, below the 95-percent floor.`;pass=false;}
  if(state.n1Occurred&&!state.n1Passed){gateState="hold";reason="N-1 capacity has not been demonstrated after the critical-node loss.";pass=false;}
  if(load>1.45){gateState="hold";reason=`Portfolio load is ${load.toFixed(2)}x, beyond the certified saturation boundary.`;pass=false;}
  if(state.holdDeclared){gateState="hold";reason="The gate authority declared a HOLD pending reinforcement and recertification.";pass=false;}
  if(activeReal().some(t=>t.breached)){gateState="fail";reason="At least one threat reached coercive advantage before control.";pass=false;}
  state.gate={state:gateState,reason,pass,metrics:{margin,risk,restore,load,n1:state.n1Occurred?state.n1Passed:null,holdouts:state.knownHoldouts}};
  if(commit)log("Gate evaluated",`${gateState.toUpperCase()}: ${reason}`,pass?"good":"warn");
  return state.gate;
}

function log(title,text,kind=""){state.log.push({month:state.month,time:nowIso(),title,text,kind});}
function recordAction(role,target,action,result){state.actions.push({sequence:state.actions.length+1,month:state.month,role,target:target||null,action,result,time:nowIso()});}
function advance(months){
  const start=state.month;state.month+=months;
  applyInjects(start);
  for(const t of activeReal()){
    if(state.month>=t.arrival+t.clock+state.physicalLatency&&!t.controlled){t.breached=true;t.state="breached";log("Coercive breach",`${t.id} crossed its adverse clock before control.`,"bad");}
  }
  for(const t of state.threats.filter(t=>t.controlled&&!t.restored&&t.restorationDue!==null)){
    if(state.month>t.restorationDue)log("Restoration overdue",`${t.id} passed its promised restoration date.`,"bad");
  }
}
function applyInjects(prev=-1){
  const sc=state.scenario;
  if(sc.n1&&state.month>=sc.n1.month&&!state.n1Occurred){state.n1Occurred=true;state.failedResource=sc.n1.resource;state.failureEnds=sc.n1.month+sc.n1.duration;log("N-1 failure",`${sc.n1.resource} capacity degraded until M+${state.failureEnds}.`,"warn");}
  if(state.failedResource&&state.month>=state.failureEnds){log("Critical node restored",`${state.failedResource} returned after the N-1 interval.`,"good");state.failedResource=null;state.failureEnds=null;}
  sc.injects.forEach((inj,i)=>{if(inj.month<=state.month&&i>state.lastInjectIndex){state.lastInjectIndex=i;log(inj.title,inj.text,"warn");}});
}

function targetRequired(action){return !["baselineSearch","activateFlex","addCapacity","declareHold","recertify"].includes(action);}
function canAct(role,action,target){
  const a=ACTIONS[action];if(!a)return "Unknown action.";if(a.role!==role)return `${ROLES[role].label} lacks authority for ${a.label}.`;
  if(targetRequired(action)&&!target)return "Select a registry object.";
  if(target&&target.hidden&&!target.revealed)return "The object is outside the visible registry.";
  if(a.resource&&usableCapacity(a.resource)<.35)return `${a.resource} capacity is unavailable under the current N-1 failure.`;
  if(target&&target.breached)return "The object has already breached.";
  if(target&&target.restored&&!["audit"].includes(action))return "The object is already restored.";
  return null;
}
